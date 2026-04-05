from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q, Avg
import base64
import hashlib

from .models import Device, ModelVersion, Round, ClientUpdate, RoundMetrics, DeviceToken
from .serializers import (
    DeviceSerializer, DeviceRegisterSerializer, ModelVersionSerializer,
    RoundSerializer, ClientUpdateSerializer, ClientUpdateSubmitSerializer,
    RoundStatusSerializer
)
from .auth import DeviceAuthentication, IsDeviceAuthenticated


@api_view(['POST'])
@permission_classes([permissions.AllowAny])
def register_device(request):
    """Register a new mobile device and get auth token."""
    serializer = DeviceRegisterSerializer(data=request.data)
    if serializer.is_valid():
        device, token = serializer.save()
        return Response({
            'device_id': str(device.device_id),
            'token': token.token,
            'message': 'Device registered successfully'
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([IsDeviceAuthenticated])
def get_latest_model(request):
    """Get latest active global model (ONNX preferred for mobile)."""
    model = ModelVersion.objects.filter(is_active=True).first()
    if not model:
        return Response(
            {'error': 'No active model available'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    return Response({
        'version': model.version,
        'description': model.description,
        'onnx_url': request.build_absolute_uri(model.onnx_file.url) if model.onnx_file else None,
        'model_url': request.build_absolute_uri(model.model_file.url),
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
    
    if round_obj.status != 'active':
        return Response(
            {'error': f'Round is {round_obj.status}, updates not accepted'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check device hasn't already submitted for this round
    if ClientUpdate.objects.filter(device=request.device, round=round_obj).exists():
        return Response(
            {'error': 'Device already submitted update for this round'},
            status=status.HTTP_409_CONFLICT
        )
    
    # Decode and validate weight delta
    try:
        weight_delta = base64.b64decode(validated_data.pop('weight_delta'))
    except Exception as e:
        return Response(
            {'error': f'Invalid weight_delta encoding: {str(e)}'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify hash matches
    computed_hash = hashlib.sha256(weight_delta).hexdigest()
    if computed_hash != validated_data['parameters_hash']:
        return Response(
            {'error': 'parameters_hash mismatch, data corrupted'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create update record
    update = ClientUpdate.objects.create(
        device=request.device,
        round=round_obj,
        weight_delta=weight_delta,
        status='received',
        **validated_data
    )
    
    return Response({
        'update_id': str(update.update_id),
        'status': 'Update received and queued for aggregation',
        'round_number': round_obj.round_number
    }, status=status.HTTP_201_CREATED)


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
    """Admin endpoint: Trigger Flower aggregation for closed round."""
    from .flower_integration import run_aggregation
    
    round_obj = get_object_or_404(Round, id=round_id)
    
    if round_obj.status != 'closed':
        return Response(
            {'error': 'Round must be closed before aggregation'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        round_obj.aggregation_status = 'in_progress'
        round_obj.save()
        
        # Run aggregation (placeholder - implemented in flower_integration)
        result = run_aggregation(round_obj)
        
        round_obj.aggregation_status = 'completed'
        round_obj.status = 'completed'
        round_obj.ended_at = timezone.now()
        round_obj.save()
        
        return Response({
            'message': 'Aggregation completed',
            'round_number': round_obj.round_number,
            'result': result
        }, status=status.HTTP_200_OK)
    except Exception as e:
        round_obj.aggregation_status = 'failed'
        round_obj.save()
        return Response(
            {'error': f'Aggregation failed: {str(e)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
