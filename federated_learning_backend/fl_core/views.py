from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Avg
from django.db import IntegrityError, transaction
import base64
import hashlib
from io import BytesIO
import numpy as np
import os
from datetime import timedelta

from .models import Device, ModelVersion, Round, ClientUpdate, RoundMetrics, DeviceToken
from .tasks import trigger_aggregation_task
from .serializers import (
    DeviceSerializer, DeviceRegisterSerializer, ModelVersionSerializer,
    RoundSerializer, ClientUpdateSerializer, ClientUpdateSubmitSerializer,
    RoundStatusSerializer
)
from .auth import DeviceAuthentication, IsDeviceAuthenticated
from .aggregation import validate_weights_structure


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_device(request):
    """Register a new mobile device and get auth token with expiry (FIX 1)."""
    serializer = DeviceRegisterSerializer(data=request.data)
    if serializer.is_valid():
        device, token = serializer.save()
        return Response({
            'device_id': str(device.device_id),
            'token': token.token,
            'expires_in': 86400,  # 24 hours in seconds
            'expires_at': token.expires_at,
            'message': 'Device registered successfully'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([permissions.AllowAny])
def test_task(request):
    """Test Celery task pipeline. Endpoint to verify Redis + Celery worker are connected.
    
    GET /api/fl/test-task/ should trigger a Celery task.
    Check celery-worker logs to confirm task was received.
    """
    import logging
    logger = logging.getLogger(__name__)
    logger.info("🧪 TEST ENDPOINT CALLED — Triggering Celery task...")
    
    try:
        # Trigger task asynchronously
        task = trigger_aggregation_task.delay(round_id=1)
        logger.info(f"✅ Task queued with ID: {task.id}")
        
        return Response({
            "status": "task triggered",
            "task_id": str(task.id),
            "message": "Check celery-worker logs for 'Received task' message"
        }, status=status.HTTP_200_OK)
    except Exception as e:
        logger.error(f"❌ Failed to trigger task: {e}")
        return Response({
            "status": "error",
            "error": str(e)
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_latest_model(request):
    """Get latest active global model (ONNX preferred for mobile).
    
    FIX 2: Enforces single source of truth - only ONE active model exists.
    FIX 3: Returns SHA256 hash for model integrity verification.
    """
    model = ModelVersion.objects.filter(is_active=True).order_by('-version').first()
    
    if not model:
        return Response(
            {'error': 'No active model available'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # FIX 3: Calculate model file hash for integrity verification
    model_hash = None
    if model.model_file:
        try:
            file_path = model.model_file.path
            with open(file_path, "rb") as f:
                file_bytes = f.read()
                model_hash = hashlib.sha256(file_bytes).hexdigest()
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to compute model hash: {e}")
    
    return Response({
        'version': model.version,
        'description': model.description,
        'onnx_url': request.build_absolute_uri(model.onnx_file.url) if model.onnx_file else None,
        'model_url': request.build_absolute_uri(model.model_file.url) if model.model_file else None,
        'hash_sha256': model_hash,
        'created_at': model.created_at
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_current_round(request):
    """Get current active round details and check if device should participate."""
    round_obj = Round.objects.filter(status='active').first()
    if not round_obj:
        return Response(
            {'error': 'No active round', 'status': 'waiting'},
            status=status.HTTP_200_OK
        )
    
    # Check if device already submitted update for this round
    existing_update = ClientUpdate.objects.filter(
        device=request.device,
        round=round_obj
    ).first()
    
    return Response({
        'round_number': round_obj.round_number,
        'round_id': round_obj.id,
        'model_version': round_obj.model_version.version,
        'status': round_obj.status,
        'min_clients': round_obj.min_clients,
        'deadline': round_obj.closed_at,
        'already_submitted': existing_update is not None,
        'submitted_at': existing_update.submitted_at if existing_update else None
    }, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_round_status(request, round_id):
    """Get detailed status of a specific round."""
    round_obj = get_object_or_404(Round, id=round_id)
    serializer = RoundStatusSerializer(round_obj)
    return Response(serializer.data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsDeviceAuthenticated])
def submit_update(request):
    """Submit local training update for federated round."""
    serializer = ClientUpdateSubmitSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    validated_data = serializer.validated_data
    round_obj = get_object_or_404(Round, id=validated_data['round_id'])
    
    # FIX 2: Enforce Round Status Check
    if round_obj.status != 'active':
        return Response(
            {'error': 'Round is not active'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # FIX 6: Model Version Check
    client_model_version = validated_data.get('model_version')
    if client_model_version != round_obj.model_version.version:
        return Response(
            {'error': 'Model version mismatch'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Remove model_version from validated_data before create
    validated_data.pop('model_version')
    
    # Decode and validate weight delta
    try:
        weight_delta = base64.b64decode(validated_data.pop('weight_delta'))
    except Exception as e:
        return Response(
            {'error': f'Invalid weight_delta encoding: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # FIX 4: Weight Size Validation
    MAX_WEIGHT_SIZE = 10 * 1024 * 1024  # 10MB
    if len(weight_delta) > MAX_WEIGHT_SIZE:
        return Response(
            {'error': 'Weight data too large'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # FIX 5: Safe Weight Structure Validation (NPZ format)
    try:
        # Deserialize NPZ format (safe, no pickle)
        bio = BytesIO(weight_delta)
        with np.load(bio, allow_pickle=False) as npz_file:
            weights = {key: npz_file[key] for key in npz_file.files}
        
        # Validate structure
        is_valid, error_msg = validate_weights_structure(weights)
        if not is_valid:
            return Response(
                {'error': f'Invalid weight structure: {error_msg}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        print("=== DEBUG WEIGHT TYPE ===")
        print("TYPE:", type(weights))
        if weights:
            first_key = list(weights.keys())[0]
            print("FIRST VALUE TYPE:", type(weights[first_key]))
        print("=========================")
        
    except Exception as e:
        return Response(
            {'error': f'Invalid weight structure: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify hash matches
    computed_hash = hashlib.sha256(weight_delta).hexdigest()
    if computed_hash != validated_data['parameters_hash']:
        return Response(
            {'error': 'parameters_hash mismatch, data corrupted'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # FIX 3: Strong Duplicate Protection (Atomic)
    try:
        with transaction.atomic():
            update = ClientUpdate.objects.create(
                device=request.device,
                round=round_obj,
                weight_delta=weight_delta,
                status='received',
                **validated_data
            )
    except IntegrityError:
        return Response(
            {'error': 'Update already submitted for this round'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    return Response({
        'update_id': str(update.update_id),
        'status': 'received',
        'received_hash': computed_hash,
        'timestamp': timezone.now(),
        'round_number': round_obj.round_number
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def refresh_token(request):
    """FIX 1: Refresh expired device token.
    
    Takes old token and device_id, returns new token if old one is expired.
    """
    device_id = request.data.get('device_id')
    old_token = request.data.get('expired_token')

    if not device_id or not old_token:
        return Response(
            {'error': 'Missing device_id or expired_token'},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        token_obj = DeviceToken.objects.filter(device_id=device_id, token=old_token).first()

        if not token_obj:
            return Response(
                {'error': 'Token not found'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not token_obj.is_expired():
            return Response(
                {'error': 'Token has not expired yet'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate new token
        import secrets
        new_token = secrets.token_urlsafe(32)

        token_obj.token = new_token
        token_obj.expires_at = timezone.now() + timedelta(hours=24)
        token_obj.save()

        return Response({
            'token': new_token,
            'expires_in': 86400,  # 24 hours
            'expires_at': token_obj.expires_at
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Token refresh failed: {e}")
        return Response(
            {'error': 'Token refresh failed'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_update_receipt(request, update_id):
    """FIX 6: Get submission receipt for a previously submitted update.
    
    Allows client to verify their update was stored correctly.
    """
    try:
        update = ClientUpdate.objects.filter(update_id=update_id).first()

        if not update:
            return Response(
                {'error': 'Update not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only allow device to view its own updates
        if update.device != request.device:
            return Response(
                {'error': 'Unauthorized'},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response({
            'update_id': str(update.update_id),
            'status': update.status,
            'hash': update.parameters_hash,
            'timestamp': update.submitted_at,
            'round_number': update.round.round_number,
            'is_valid': update.is_valid,
            'validation_error': update.validation_error if not update.is_valid else None
        }, status=status.HTTP_200_OK)
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Get receipt failed: {e}")
        return Response(
            {'error': 'Failed to retrieve receipt'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_device_profile(request):
    """Get device profile and round history."""
    device = request.device
    device_serializer = DeviceSerializer(device)
    
    # Get recent updates
    recent_updates = ClientUpdate.objects.filter(device=device).order_by('-submitted_at')[:10]
    
    return Response({
        'device': device_serializer.data,
        'total_updates': device.updates.count(),
        'recent_updates': [{
            'round_number': u.round.round_number,
            'status': u.status,
            'num_examples': u.num_examples,
            'local_accuracy': u.local_accuracy,
            'submitted_at': u.submitted_at
        } for u in recent_updates]
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def create_round(request):
    """Admin endpoint: Create new federated round."""
    round_number = request.data.get('round_number')
    model_version_id = request.data.get('model_version_id')
    min_clients = request.data.get('min_clients', 3)
    max_clients = request.data.get('max_clients', 100)
    
    if not round_number or not model_version_id:
        return Response(
            {'error': 'Missing round_number or model_version_id'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    model_version = get_object_or_404(ModelVersion, id=model_version_id)
    
    round_obj = Round.objects.create(
        round_number=round_number,
        model_version=model_version,
        min_clients=min_clients,
        max_clients=max_clients,
        status='active',
        started_at=timezone.now()
    )
    
    # Create metrics record
    RoundMetrics.objects.create(round=round_obj)
    
    serializer = RoundSerializer(round_obj)
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def close_round(request, round_id):
    """Admin endpoint: Close a round (stop accepting updates)."""
    round_obj = get_object_or_404(Round, id=round_id)
    
    if round_obj.status != 'active':
        return Response(
            {'error': f'Cannot close round in {round_obj.status} state'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    round_obj.status = 'closed'
    round_obj.closed_at = timezone.now()
    round_obj.save()
    
    # Update metrics
    updates = round_obj.client_updates.filter(status__in=['received', 'validated'])
    metrics = round_obj.metrics
    metrics.participating_clients = updates.count()
    metrics.avg_local_loss = updates.values_list('local_loss', flat=True).aggregate(
        avg=Avg('local_loss')
    )['avg']
    metrics.avg_local_accuracy = updates.values_list('local_accuracy', flat=True).aggregate(
        avg=Avg('local_accuracy')
    )['avg']
    metrics.save()
    
    return Response({
        'message': f'Round {round_obj.round_number} closed',
        'participating_devices': metrics.participating_clients
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def trigger_aggregation(request, round_id):
    """Admin endpoint: Trigger Flower aggregation for closed round (async via Celery)."""
    from .tasks import trigger_aggregation_task
    
    round_obj = get_object_or_404(Round, id=round_id)
    
    # FIX 3 + 4: Check if already aggregated or aggregating
    if round_obj.status == 'aggregated':
        return Response(
            {'status': 'already_aggregated', 'round_id': round_id},
            status=status.HTTP_200_OK
        )
    
    if round_obj.aggregation_status == 'in_progress':
        return Response(
            {'status': 'already_running', 'round_id': round_id},
            status=status.HTTP_200_OK
        )
    
    if round_obj.status != 'closed':
        return Response(
            {'error': 'Round must be closed before aggregation'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # FIX 1: Trigger async aggregation task
    trigger_aggregation_task.delay(round_id)
    
    return Response({
        'status': 'aggregation_started',
        'round_id': round_id
    }, status=status.HTTP_200_OK)
