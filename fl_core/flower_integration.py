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
import numpy as np
import torch
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg
import logging

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
    Federated Averaging (FedAvg) aggregation.
    
    Args:
        round_obj: Round model instance
        
    Returns:
        dict with aggregated weights, status, metrics
    """
    from .models import ClientUpdate
    
    # Get valid updates
    updates = round_obj.client_updates.filter(status__in=['received', 'validated'])
    
    if not updates.exists():
        logger.warning(f"No valid updates for round {round_obj.round_number}")
        return {
            'status': 'failed',
            'reason': 'No valid client updates',
            'participating_count': 0
        }
    
    try:
        # Collect weight deltas
        all_deltas = []
        all_weights = []
        total_examples = 0
        
        for update in updates:
            delta = deserialize_weights(update.weight_delta)
            all_deltas.append(delta)
            all_weights.append(delta)  # In FedAvg, we treat update as new weights
            total_examples += update.num_examples
        
        # Simple averaging (FedAvg)
        aggregated_weights = fedavg_aggregate(all_weights)
        
        # Update metrics
        metrics = round_obj.metrics
        metrics.participating_clients = updates.count()
        metrics.avg_local_loss = updates.values_list('local_loss', flat=True).aggregate(
            avg=Avg('local_loss')
        )['avg']
        metrics.avg_local_accuracy = updates.values_list('local_accuracy', flat=True).aggregate(
            avg=Avg('local_accuracy')
        )['avg']
        metrics.aggregation_time_ms = 1000  # Placeholder
        metrics.save()
        
        return {
            'status': 'success',
            'participating_count': updates.count(),
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
            'participating_count': updates.count()
        }


def fedavg_aggregate(weight_list):
    """
    Simple FedAvg: average all weights element-wise.
    
    Args:
        weight_list: List of weight dicts/arrays from clients
        
    Returns:
        Aggregated weights in same format
    """
    if not weight_list:
        raise ValueError("No weights to aggregate")
    
    # For dict-based weights (PyTorch state_dict style)
    if isinstance(weight_list[0], dict):
        aggregated = {}
        for key in weight_list[0].keys():
            weights_for_key = [w[key] for w in weight_list]
            aggregated[key] = np.mean(weights_for_key, axis=0)
        return aggregated
    
    # For list/array based weights
    else:
        return np.mean(weight_list, axis=0)


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
    """Save aggregated weights as new model version."""
    from .models import ModelVersion
    from untitled30 import FusionModel  # Import your model class
    
    # Create new model version
    new_version = f"{round_obj.model_version.version.split('.')[0]}.{round_obj.round_number}"
    
    # Optionally, reconstruct model and save as both PyTorch and ONNX
    # This is a simplified placeholder
    model_data = serialize_weights(aggregated_weights)
    
    new_model = ModelVersion.objects.create(
        version=new_version,
        description=f"Aggregated from round {round_obj.round_number}",
        is_active=False  # Activate manually after validation
    )
    
    logger.info(f"Created new model version {new_version}")
    return new_model


def export_to_onnx(model, input_shapes, output_path):
    """
    Export PyTorch model to ONNX format.
    
    Args:
        model: PyTorch model instance
        input_shapes: Tuple of input shapes for dummy input
        output_path: Path to save ONNX file
    """
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
