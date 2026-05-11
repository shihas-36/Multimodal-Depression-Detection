"""
Model Communication Module - Handle all model service interactions

This module manages:
- Sending aggregated weights to model service for inference/training
- Receiving and storing ONNX models built by model service
- Tracking model build status and versioning
- Error handling and retry logic
"""

import base64
import hashlib
import requests
import logging
from io import BytesIO
from django.utils import timezone
from django.core.files.base import ContentFile
from .models import ModelVersion

logger = logging.getLogger(__name__)

# Model service configuration
MODEL_SERVICE_URL = "http://localhost:8080"
MODEL_SERVICE_TIMEOUT = 30


# ============================================================================
# HEALTH CHECK
# ============================================================================

def check_model_service_health():
    """
    Check if model service is available.
    
    Returns:
        dict: {'status': 'ok'|'error', 'message': str}
    """
    health_url = f"{MODEL_SERVICE_URL}/health"
    
    try:
        response = requests.get(
            health_url,
            timeout=5
        )
        
        if response.status_code == 200:
            logger.info(f"[MODEL_COMM] ✓ Model service is healthy")
            try:
                return {
                    'status': 'ok',
                    'message': response.json().get('message', 'Service OK')
                }
            except:
                return {
                    'status': 'ok',
                    'message': 'Service OK'
                }
        else:
            logger.warning(f"[MODEL_COMM] Model service returned {response.status_code}")
            return {
                'status': 'error',
                'message': f'Service returned status {response.status_code}'
            }
    except Exception as e:
        logger.error(f"[MODEL_COMM] Cannot reach model service: {e}")
        return {
            'status': 'error',
            'message': f'Cannot connect to model service: {str(e)}'
        }


# ============================================================================
# SENDING WEIGHTS TO MODEL SERVICE
# ============================================================================

def send_weights_to_model_service(aggregated_data, round_number, aggregated_hash):
    """
    Send aggregated weights to the model service for model rebuild.
    
    Uses file upload endpoint to send weights for rebuild.
    
    Args:
        aggregated_data: serialized NPZ weights
        round_number: round number for tracking
        aggregated_hash: SHA256 hash of weights
        
    Returns:
        dict: response with status and details
    """
    rebuild_url = f"{MODEL_SERVICE_URL}/rebuild"
    
    try:
        # Create a file-like object with aggregated weights
        files = {
            'file': ('aggregated_weights.npz', aggregated_data, 'application/octet-stream')
        }
        
        data = {
            'round_number': str(round_number),
            'weights_hash': aggregated_hash,
            'timestamp': timezone.now().isoformat()
        }
        
        logger.info(f"[MODEL_COMM] Sending aggregated weights to {rebuild_url} (round {round_number}, size={len(aggregated_data):,} bytes)")
        
        response = requests.post(
            rebuild_url,
            files=files,
            data=data,
            timeout=MODEL_SERVICE_TIMEOUT
        )
        
        if response.status_code in [200, 201]:
            logger.info(f"[MODEL_COMM] ✓ Model service accepted weights for round {round_number}")
            try:
                service_response = response.json()
            except:
                service_response = response.text
            
            return {
                'status': 'success',
                'http_status': response.status_code,
                'service_response': service_response
            }
        else:
            logger.warning(f"[MODEL_COMM] Model service returned status {response.status_code}: {response.text}")
            return {
                'status': 'warning',
                'http_status': response.status_code,
                'response': response.text
            }
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[MODEL_COMM] Cannot connect to model service at {rebuild_url}: {e}")
        return {
            'status': 'error',
            'reason': 'model_service_unreachable',
            'details': str(e)
        }
    except Exception as e:
        logger.error(f"[MODEL_COMM] Error sending weights to model service: {e}")
        return {
            'status': 'error',
            'reason': 'request_failed',
            'details': str(e)
        }


# ============================================================================
# RECEIVING ONNX MODELS FROM MODEL SERVICE
# ============================================================================

def fetch_onnx_model_from_service(round_number):
    """
    Fetch ONNX model built by model service.
    
    Model service builds the model after receiving aggregated weights.
    This fetches the built ONNX model via download endpoint.
    
    Args:
        round_number: round number (for reference/logging)
        
    Returns:
        dict: {
            'status': 'success'|'error',
            'onnx_data': bytes or None,
            'model_hash': str or None,
            'service_message': str
        }
    """
    download_url = f"{MODEL_SERVICE_URL}/download"
    
    try:
        logger.info(f"[MODEL_COMM] Fetching ONNX model from {download_url}")
        
        response = requests.get(
            download_url,
            timeout=MODEL_SERVICE_TIMEOUT
        )
        
        if response.status_code == 200:
            onnx_data = response.content
            
            if onnx_data and len(onnx_data) > 0:
                onnx_hash = hashlib.sha256(onnx_data).hexdigest()
                logger.info(f"[MODEL_COMM] ✓ Received ONNX model: {len(onnx_data):,} bytes (hash={onnx_hash})")
                return {
                    'status': 'success',
                    'onnx_data': onnx_data,
                    'model_hash': onnx_hash,
                    'service_message': f'Model received successfully'
                }
            else:
                logger.warning(f"[MODEL_COMM] Downloaded empty model")
                return {
                    'status': 'error',
                    'reason': 'empty_model_data',
                    'service_message': 'Model service returned empty data'
                }
                
        elif response.status_code == 404:
            logger.warning(f"[MODEL_COMM] No model available yet (round {round_number})")
            return {
                'status': 'error',
                'reason': 'model_not_ready',
                'service_message': 'Model not ready yet - may still be building'
            }
        else:
            logger.error(f"[MODEL_COMM] Model service error {response.status_code}: {response.text}")
            return {
                'status': 'error',
                'http_status': response.status_code,
                'details': response.text
            }
            
    except requests.exceptions.ConnectionError as e:
        logger.error(f"[MODEL_COMM] Cannot connect to model service at {download_url}: {e}")
        return {
            'status': 'error',
            'reason': 'model_service_unreachable',
            'details': str(e)
        }
    except Exception as e:
        logger.error(f"[MODEL_COMM] Error fetching ONNX model: {e}")
        return {
            'status': 'error',
            'reason': 'request_failed',
            'details': str(e)
        }


# ============================================================================
# STORING ONNX MODELS
# ============================================================================

def store_onnx_model(onnx_data, round_number, aggregated_weights_hash=None, model_version_id=None):
    """
    Store ONNX model received from model service.
    
    Args:
        onnx_data: raw ONNX model bytes
        round_number: round number (for versioning)
        aggregated_weights_hash: hash of weights this model was built from
        model_version_id: optional ID of existing ModelVersion to update
        
    Returns:
        dict: {
            'status': 'success'|'error',
            'model_version': ModelVersion object or None,
            'message': str,
            'onnx_hash': str
        }
    """
    try:
        if not onnx_data or len(onnx_data) == 0:
            logger.error("[MODEL_COMM] Cannot store empty ONNX data")
            return {
                'status': 'error',
                'reason': 'empty_onnx_data',
                'message': 'ONNX data is empty'
            }
        
        # Compute hash for integrity tracking
        onnx_hash = hashlib.sha256(onnx_data).hexdigest()
        
        # Check if model_version_id provided
        if model_version_id:
            try:
                model_version = ModelVersion.objects.get(id=model_version_id)
                logger.info(f"[MODEL_COMM] Updating existing model version {model_version.version} (ID: {model_version_id})")
            except ModelVersion.DoesNotExist:
                logger.warning(f"[MODEL_COMM] Provided model_version_id {model_version_id} not found, creating new.")
                model_version = None
        else:
            # Create version string
            version_str = f"aggregated.round_{round_number}"
            
            # Check if version already exists
            try:
                model_version = ModelVersion.objects.get(version=version_str)
                logger.warning(f"[MODEL_COMM] Model version {version_str} already exists, updating...")
            except ModelVersion.DoesNotExist:
                model_version = None
        
        if model_version is None:
            version_str = f"aggregated.round_{round_number}"
            model_version = ModelVersion.objects.create(
                version=version_str,
                description=f"ONNX model built from aggregated weights - Round {round_number}",
                is_active=False  # Must be explicitly activated
            )
        
        # Save ONNX file
        onnx_filename = f"model_round_{round_number}.onnx"
        model_version.onnx_file.save(
            onnx_filename,
            ContentFile(onnx_data),
            save=True
        )
        
        logger.info(f"[MODEL_COMM] ✓ Stored ONNX model: {onnx_filename}")
        logger.info(f"[MODEL_COMM]   - Version: {model_version.version}")
        logger.info(f"[MODEL_COMM]   - Size: {len(onnx_data):,} bytes")
        logger.info(f"[MODEL_COMM]   - Hash: {onnx_hash}")
        
        return {
            'status': 'success',
            'model_version': model_version,
            'message': f'ONNX model stored successfully',
            'onnx_hash': onnx_hash,
            'onnx_size': len(onnx_data)
        }
        
    except Exception as e:
        logger.error(f"[MODEL_COMM] Failed to store ONNX model: {e}", exc_info=True)
        return {
            'status': 'error',
            'reason': 'storage_failed',
            'message': str(e)
        }


# ============================================================================
# ACTIVATE MODEL
# ============================================================================

def activate_model_version(version_str):
    """
    Activate a model version for production use.
    
    Args:
        version_str: version string of model to activate
        
    Returns:
        dict: {
            'status': 'success'|'error',
            'message': str,
            'model_version': ModelVersion or None
        }
    """
    try:
        model_version = ModelVersion.objects.get(version=version_str)
        
        # Deactivate all other versions
        ModelVersion.objects.exclude(id=model_version.id).update(is_active=False)
        
        # Activate this version
        model_version.is_active = True
        model_version.save()
        
        logger.info(f"[MODEL_COMM] ✓ Activated model version: {version_str}")
        
        return {
            'status': 'success',
            'message': f'Model version {version_str} activated',
            'model_version': model_version
        }
        
    except ModelVersion.DoesNotExist:
        logger.error(f"[MODEL_COMM] Model version {version_str} not found")
        return {
            'status': 'error',
            'reason': 'model_not_found',
            'message': f'Model version {version_str} not found'
        }
    except Exception as e:
        logger.error(f"[MODEL_COMM] Failed to activate model version: {e}")
        return {
            'status': 'error',
            'reason': 'activation_failed',
            'message': str(e)
        }


# ============================================================================
# FULL WORKFLOW: Send weights → Wait for model → Store ONNX
# ============================================================================

def trigger_model_build_and_store(aggregated_data, round_number, aggregated_hash, model_version_id=None):
    """
    Complete workflow:
    1. Check model service health
    2. Send aggregated weights to model service for rebuild
    3. Fetch built ONNX model from model service
    4. Store ONNX model in database (linked to existing version if provided)
    5. Return status
    
    Args:
        aggregated_data: serialized NPZ weights
        round_number: round number
        aggregated_hash: hash of aggregated weights
        model_version_id: optional ID of existing ModelVersion to update
        
    Returns:
        dict: workflow result with all statuses
    """
    logger.info(f"[MODEL_COMM] === Starting model build workflow for round {round_number} ===")
    
    # Step 0: Check service health
    health_result = check_model_service_health()
    if health_result['status'] != 'ok':
        logger.error(f"[MODEL_COMM] Model service is not healthy: {health_result['message']}")
        return {
            'workflow_status': 'failed_at_health_check',
            'health_result': health_result
        }
    
    # Step 1: Send weights for rebuild
    send_result = send_weights_to_model_service(
        aggregated_data,
        round_number,
        aggregated_hash
    )
    
    if send_result['status'] != 'success':
        logger.error(f"[MODEL_COMM] Failed to send weights: {send_result}")
        return {
            'workflow_status': 'failed_at_send',
            'send_result': send_result
        }
    
    # Step 2: Fetch ONNX model
    fetch_result = fetch_onnx_model_from_service(round_number)
    
    if fetch_result['status'] != 'success':
        logger.error(f"[MODEL_COMM] Failed to fetch ONNX model: {fetch_result}")
        return {
            'workflow_status': 'failed_at_fetch',
            'send_result': send_result,
            'fetch_result': fetch_result
        }
    
    # Step 3: Store ONNX model
    onnx_data = fetch_result.get('onnx_data')
    store_result = store_onnx_model(
        onnx_data,
        round_number,
        aggregated_weights_hash=aggregated_hash,
        model_version_id=model_version_id
    )
    
    if store_result['status'] != 'success':
        logger.error(f"[MODEL_COMM] Failed to store ONNX model: {store_result}")
        return {
            'workflow_status': 'failed_at_store',
            'send_result': send_result,
            'fetch_result': fetch_result,
            'store_result': store_result
        }
    
    logger.info(f"[MODEL_COMM] === Model build workflow completed successfully ===")
    
    return {
        'workflow_status': 'success',
        'send_result': send_result,
        'fetch_result': fetch_result,
        'store_result': store_result,
        'model_version': store_result.get('model_version')
    }
