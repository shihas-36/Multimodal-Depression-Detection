"""
Flower Integration Module

Handles:
- Aggregation of client updates
- Model update from aggregated weights
- Global model versioning
"""

import io
import hashlib
import pickle
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg
from django.db import transaction
import logging

# Optional imports - only needed for ML operations (Celery worker)
try:
    import numpy as np
    import torch
    HAS_ML_LIBS = True
except ImportError:
    HAS_ML_LIBS = False
    logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


def deserialize_weights(weight_delta_bytes):
    """Deserialize client weight delta from bytes."""
    try:
        return pickle.loads(weight_delta_bytes)
    except Exception as e:
        logger.error(f"Failed to deserialize weights: {e}")
        raise ValueError(f"Invalid weight delta format: {e}")


def serialize_weights(weights):
    """Serialize weights for storage."""
    return pickle.dumps(weights)


def aggregate_updates(round_obj):
    """
    Federated Averaging (FedAvg) aggregation with validation.
    
    Args:
        round_obj: Round model instance
        
    Returns:
        dict with aggregated weights, status, metrics
    """
    from .models import ClientUpdate
    
    # Get all updates from round
    updates = round_obj.client_updates.filter(status__in=['received', 'validated'])
    
    if not updates.exists():
        logger.warning(f"No updates for round {round_obj.round_number}")
        return {
            'status': 'failed',
            'reason': 'No client updates found',
            'participating_count': 0
        }
    
    # FIX 1: Validate all updates - separate into valid and invalid
    valid_updates = []
    invalid_updates = []
    
    for update in updates:
        is_valid, error = validate_client_update(update)
        
        if is_valid:
            valid_updates.append(update)
        else:
            invalid_updates.append((update.id, error))
            # FIX 5: Mark invalid in DB
            update.is_valid = False
            update.validation_error = error
            update.save()
    
    # FIX 4: Log invalid updates
    for update_id, error in invalid_updates:
        logger.warning(f"Invalid update {update_id}: {error}")
    
    # FIX 3: Handle NO VALID UPDATES case
    if not valid_updates:
        logger.error(f"No valid updates for aggregation in round {round_obj.round_number}")
        return {
            'status': 'failed',
            'reason': 'No valid updates for aggregation',
            'participating_count': 0,
            'invalid_count': len(invalid_updates)
        }
    
    try:
        # FIX 2: Collect num_examples alongside weights for weighted averaging
        all_weights = []
        num_examples_list = []
        
        for update in valid_updates:
            weights = deserialize_weights(update.weight_delta)
            all_weights.append(weights)
            num_examples_list.append(update.num_examples)  # Store num_examples for weighting
        
        # FIX 3: Call FedAvg with both weights and num_examples for proper weighting
        aggregated_weights = fedavg_aggregate(all_weights, num_examples_list)
        
        # Track total examples for metrics
        total_examples = sum(num_examples_list)
        
        # Update metrics (use valid_updates only)
        valid_update_ids = [u.id for u in valid_updates]
        metrics = round_obj.metrics
        metrics.participating_clients = len(valid_updates)
        
        # Aggregate metrics only from valid updates
        metrics_query = round_obj.client_updates.filter(
            id__in=valid_update_ids
        ).aggregate(
            avg_loss=Avg('local_loss'),
            avg_accuracy=Avg('local_accuracy')
        )
        metrics.avg_local_loss = metrics_query['avg_loss']
        metrics.avg_local_accuracy = metrics_query['avg_accuracy']
        metrics.aggregation_time_ms = 1000  # Placeholder
        metrics.save()
        
        return {
            'status': 'success',
            'participating_count': len(valid_updates),
            'invalid_count': len(invalid_updates),
            'total_examples': total_examples,
            'aggregated_weights': aggregated_weights,
            'metrics': {
                'avg_local_loss': metrics.avg_local_loss,
                'avg_local_accuracy': metrics.avg_local_accuracy,
            }
        }
        
    except Exception as e:
        logger.error(f"Aggregation failed for round {round_obj.round_number}: {e}")
        return {
            'status': 'failed',
            'reason': str(e),
            'participating_count': len(valid_updates),
            'invalid_count': len(invalid_updates)
        }


def fedavg_aggregate(weight_list, num_examples_list):
    """
    Federated Averaging (FedAvg) with importance weighting.
    
    Implements proper FedAvg: weighted averaging based on num_examples from each client.
    This prevents clients with less data from having equal influence as those with more data.
    
    Args:
        weight_list: List of weight dicts/arrays from clients
        num_examples_list: List of num_examples corresponding to each client
        
    Returns:
        Aggregated weights in same format
    
    FIX 1: Weighted averaging
    FIX 4: Division by zero prevention
    FIX 5: Key consistency check
    FIX 6: Single client handling
    """
    if not weight_list:
        raise ValueError("No weights to aggregate")
    
    if len(weight_list) != len(num_examples_list):
        raise ValueError("Weight list and num_examples list length mismatch")
    
    # FIX 6: Handle single client case (no averaging needed)
    if len(weight_list) == 1:
        logger.info("Single client update, returning weights as-is")
        return weight_list[0]
    
    # FIX 4: Prevent division by zero
    total_examples = sum(num_examples_list)
    if total_examples == 0:
        raise Exception("Total num_examples is zero - cannot perform aggregation")
    
    # For dict-based weights (PyTorch state_dict style)
    if isinstance(weight_list[0], dict):
        # FIX 5: Ensure consistent keys across all clients
        base_keys = set(weight_list[0].keys())
        for i, weights in enumerate(weight_list):
            if set(weights.keys()) != base_keys:
                raise Exception(
                    f"Weight keys mismatch: client {i} has keys {set(weights.keys())}, "
                    f"expected {base_keys}"
                )
        
        aggregated = {}
        
        for key in base_keys:
            weighted_sum = None
            
            # FIX 1: Weighted averaging - accumulate weighted values
            for i, weights in enumerate(weight_list):
                weight = weights[key]
                num_examples = num_examples_list[i]
                
                if weighted_sum is None:
                    weighted_sum = weight * num_examples
                else:
                    weighted_sum += weight * num_examples
            
            # Divide by total examples to get weighted average
            aggregated[key] = weighted_sum / total_examples
        
        logger.info(
            f"FedAvg completed: {len(weight_list)} clients, "
            f"total_examples={total_examples}"
        )
        return aggregated
    
    # For list/array based weights
    else:
        # Similar weighted averaging for non-dict weights
        weighted_sum = None
        for i, weight in enumerate(weight_list):
            num_examples = num_examples_list[i]
            if weighted_sum is None:
                weighted_sum = weight * num_examples
            else:
                weighted_sum += weight * num_examples
        
        return weighted_sum / total_examples


def run_aggregation(round_obj):
    """
    Main aggregation pipeline.
    
    Args:
        round_obj: Round model instance
        
    Returns:
        Aggregation result dict
    """
    logger.info(f"Starting aggregation for round {round_obj.round_number}")
    
    result = aggregate_updates(round_obj)
    
    if result['status'] == 'success':
        # Save new global model
        try:
            aggregated_weights = result.pop('aggregated_weights')
            save_new_model_version(round_obj, aggregated_weights)
            logger.info(f"Round {round_obj.round_number} aggregation completed successfully")
        except Exception as e:
            logger.error(f"Failed to save new model version: {e}")
            result['status'] = 'partial_failure'
            result['reason'] = f'Aggregation OK but model save failed: {e}'
    
    return result


def save_new_model_version(round_obj, aggregated_weights):
    """
    Save aggregated weights as new model version with proper FL lifecycle.
    
    FIX 1: Load previous global model
    FIX 2: Apply aggregated weights
    FIX 3: Save new model version
    FIX 4: Deactivate old model
    FIX 5: Activate new model
    FIX 6: Attach model to round
    """
    from .models import ModelVersion
    
    try:
        # FIX 1: Load previous global model
        latest_model = ModelVersion.objects.filter(is_active=True).first()
        
        if not latest_model:
            raise Exception("No active global model found - cannot continue FL aggregation")
        
        logger.info(f"Loading previous global model v{latest_model.version} for round {round_obj.round_number}")
        
        # Load weights from previous model
        try:
            global_weights = deserialize_weights(latest_model.model_data)
        except Exception as e:
            logger.error(f"Failed to deserialize previous model weights: {e}")
            raise
        
        # FIX 2: Apply aggregated weights
        # Merge with previous model weights
        if isinstance(global_weights, dict) and isinstance(aggregated_weights, dict):
            # Update dict with aggregated weights (PyTorch state_dict style)
            updated_weights = global_weights.copy()
            updated_weights.update(aggregated_weights)
        else:
            # For non-dict weights, use aggregated directly
            updated_weights = aggregated_weights
        
        logger.info(f"Applied aggregated weights to previous model for round {round_obj.round_number}")
        
        # FIX 3: Save NEW model version with proper versioning
        # Extract version parts and increment
        version_parts = latest_model.version.split('.')
        try:
            major = int(version_parts[0])
            minor = int(version_parts[1]) if len(version_parts) > 1 else 0
            patch = int(version_parts[2]) if len(version_parts) > 2 else 0
        except (ValueError, IndexError):
            major, minor, patch = 1, 0, 0
        
        # Increment patch version for each round
        patch += 1
        new_version = f"{major}.{minor}.{patch}"
        
        # Serialize the updated model
        model_data = serialize_weights(updated_weights)
        
        new_model = ModelVersion.objects.create(
            version=new_version,
            description=f"Aggregated from round {round_obj.round_number} (previous: v{latest_model.version})",
            model_data=model_data,
            is_active=False
        )
        
        logger.info(f"Created new model version {new_version}")
        
        # FIX 1: Enforce SINGLE ACTIVE MODEL with atomic transaction
        # Deactivate ALL models and then activate only the new one
        with transaction.atomic():
            # Deactivate all existing models
            ModelVersion.objects.all().update(is_active=False)
            
            # Activate ONLY the new model (single source of truth)
            new_model.is_active = True
            new_model.save()
            logger.info(f"Enforced single active model: v{new_version}")
        
        # FIX 3: Attach Model to Round (STRICT LINK) + FIX 6: Update status
        # Update both to ensure round is strictly linked to the aggregated model
        round_obj.model_version = new_model  # Point to aggregated model as final model
        round_obj.aggregated_model_version = new_model
        round_obj.status = 'completed'  # Mark round as completed after successful aggregation
        round_obj.save()
        logger.info(f"Linked round {round_obj.round_number} to aggregated model v{new_version}")
        logger.info(f"Round {round_obj.round_number} status updated to completed")
        
        return new_model
        
    except Exception as e:
        logger.error(f"Error in save_new_model_version: {e}")
        raise


def export_to_onnx(model, input_shapes, output_path):
    """
    Export PyTorch model to ONNX format.
    
    Args:
        model: PyTorch model instance
        input_shapes: Tuple of input shapes for dummy input
        output_path: Path to save ONNX file
    """
    if not HAS_ML_LIBS:
        logger.warning("PyTorch not available - ONNX export runs on Celery worker only")
        return False
    
    try:
        # Create dummy inputs
        dummy_text = torch.randn(1, input_shapes[0])
        dummy_wear = torch.randn(1, input_shapes[1])
        
        # Export
        torch.onnx.export(
            model,
            (dummy_text, dummy_wear),
            output_path,
            input_names=['text_features', 'wearable_features'],
            output_names=['prediction'],
            dynamic_axes={
                'text_features': {0: 'batch_size'},
                'wearable_features': {0: 'batch_size'},
                'prediction': {0: 'batch_size'}
            },
            verbose=False
        )
        logger.info(f"Model exported to ONNX: {output_path}")
        return True
    except Exception as e:
        logger.error(f"ONNX export failed: {e}")
        return False


def validate_client_update(update):
    """Validate client update integrity and format."""
    from .models import ClientUpdate
    
    errors = []
    
    # Check weight size (10MB max)
    MAX_WEIGHT_SIZE = 10 * 1024 * 1024
    if len(update.weight_delta) > MAX_WEIGHT_SIZE:
        errors.append(f"Weight size too large ({len(update.weight_delta)} > {MAX_WEIGHT_SIZE})")
    
    # Check hash
    computed_hash = hashlib.sha256(update.weight_delta).hexdigest()
    if computed_hash != update.parameters_hash:
        errors.append("Hash mismatch")
    
    # Check examples > 0
    if update.num_examples <= 0:
        errors.append("Invalid num_examples")
    
    # Check metrics in valid range if present
    if update.local_loss is not None and update.local_loss < 0:
        errors.append("Invalid local_loss (negative)")
    if update.local_accuracy is not None and not (0 <= update.local_accuracy <= 1):
        errors.append("local_accuracy must be in [0, 1]")
    
    # Try deserialize weights
    try:
        deserialize_weights(update.weight_delta)
    except Exception as e:
        errors.append(f"Cannot deserialize weights: {e}")
    
    if not errors:
        update.status = 'validated'
        update.validated_at = timezone.now()
        update.save()
        return True, None
    
    return False, "; ".join(errors)
