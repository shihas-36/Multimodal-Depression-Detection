"""
Aggregation Module - NumPy-based Federated Averaging

This module handles:
- Safe deserialization of client weights (JSON + base64)
- FedAvg aggregation with proper weighted averaging
- Model versioning and storage
- Comprehensive validation and error handling

SECURITY: Uses JSON + base64 instead of unsafe pickle
PERFORMANCE: NumPy-native operations, no external deps
"""

import json
import base64
import hashlib
import numpy as np
from io import BytesIO
from django.conf import settings
from django.utils import timezone
from django.db.models import Avg
from django.db import transaction
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# SERIALIZATION (Safe, no pickle)
# ============================================================================

def serialize_weights_to_npz(weights_dict):
    """
    Serialize weights dict to NPZ (NumPy compressed) format.
    
    Args:
        weights_dict: dict of {key: numpy.ndarray}
        
    Returns:
        bytes: compressed NPZ data
        
    Advantages:
    - Native NumPy format
    - Compressed
    - Safe (no code execution)
    - Efficient for numeric data
    """
    bio = BytesIO()
    np.savez_compressed(bio, **weights_dict)
    bio.seek(0)
    return bio.read()


def deserialize_weights_from_npz(data_bytes):
    """
    Deserialize NPZ data back to weights dict.
    
    Args:
        data_bytes: raw bytes from client
        
    Returns:
        dict of {key: numpy.ndarray}
        
    Raises:
        ValueError: if NPZ is invalid
    """
    try:
        bio = BytesIO(data_bytes)
        with np.load(bio, allow_pickle=False) as npz_file:
            # Convert NPZ to regular dict
            weights_dict = {key: npz_file[key] for key in npz_file.files}
        return weights_dict
    except Exception as e:
        logger.error(f"Failed to deserialize weights from NPZ: {e}")
        raise ValueError(f"Invalid weight delta format: {str(e)}")


# ============================================================================
# VALIDATION
# ============================================================================

def validate_weights_structure(weights_dict, expected_keys=None):
    """
    Validate weight structure for consistency.
    
    Args:
        weights_dict: dict to validate
        expected_keys: optional set of required keys
        
    Returns:
        tuple: (is_valid: bool, error_msg: str or None)
    """
    if not isinstance(weights_dict, dict):
        return False, f"Weights must be dict, got {type(weights_dict)}"
    
    if len(weights_dict) == 0:
        return False, "Weights dict is empty"
    
    # Validate all values are numpy arrays
    for key, value in weights_dict.items():
        if not isinstance(value, np.ndarray):
            return False, f"Weight '{key}' is {type(value)}, expected numpy.ndarray"
    
    # Check expected keys if provided
    if expected_keys is not None:
        if set(weights_dict.keys()) != expected_keys:
            missing = expected_keys - set(weights_dict.keys())
            extra = set(weights_dict.keys()) - expected_keys
            msg = ""
            if missing:
                msg += f"Missing keys: {missing}. "
            if extra:
                msg += f"Extra keys: {extra}."
            return False, msg.strip()
    
    return True, None


def validate_client_update(update):
    """
    Validate a single client update.
    
    Args:
        update: ClientUpdate model instance
        
    Returns:
        tuple: (is_valid: bool, error_msg: str or None)
    """
    try:
        # Check hash integrity
        computed_hash = hashlib.sha256(update.weight_delta).hexdigest()
        if computed_hash != update.parameters_hash:
            return False, "Hash mismatch - data corrupted"
        
        # Try to deserialize
        weights = deserialize_weights_from_npz(update.weight_delta)
        
        # Validate structure
        is_valid, error_msg = validate_weights_structure(weights)
        return is_valid, error_msg
        
    except Exception as e:
        return False, f"Deserialization error: {str(e)}"


# ============================================================================
# AGGREGATION (FedAvg - Correct FL Algorithm)
# ============================================================================

def fedavg_aggregate(weight_list, num_examples_list):
    """
    Federated Averaging (FedAvg) with importance weighting.
    
    Implements correct FedAvg algorithm:
    - Weighted averaging based on num_examples from each client
    - Prevents clients with less data from having equal influence
    - Formula: weighted_avg = sum(w_i * num_examples_i) / sum(num_examples_i)
    
    Args:
        weight_list: list of weight dicts, each {key: numpy.ndarray}
        num_examples_list: list of num_examples for each weight dict
        
    Returns:
        dict: aggregated weights in same format as inputs
        
    Raises:
        ValueError: if validation fails
        
    FIXES APPLIED:
    - FIX 1: Proper weighted averaging (not merge/update)
    - FIX 2: Handles single client (no averaging needed)
    - FIX 3: Key consistency validation
    - FIX 4: Division by zero prevention
    - FIX 5: Numeric type safety
    """
    if not weight_list:
        raise ValueError("No weights to aggregate")
    
    if len(weight_list) != len(num_examples_list):
        raise ValueError(f"Weight list ({len(weight_list)}) and num_examples list ({len(num_examples_list)}) length mismatch")
    
    # FIX 2: Single client case - return as-is, no averaging
    if len(weight_list) == 1:
        logger.info("Single client update, returning weights without averaging")
        return weight_list[0].copy()
    
    # FIX 4: Prevent division by zero
    total_examples = sum(num_examples_list)
    if total_examples == 0:
        raise ValueError("Sum of num_examples is zero - cannot perform weighted averaging")
    
    # FIX 3: Validate key consistency across all clients
    base_keys = set(weight_list[0].keys())
    for i, weights in enumerate(weight_list[1:], start=1):
        if set(weights.keys()) != base_keys:
            raise ValueError(
                f"Weight key mismatch at client {i}: "
                f"expected {base_keys}, got {set(weights.keys())}"
            )
    
    # FIX 1: Implement proper weighted averaging
    aggregated = {}
    
    for key in base_keys:
        weighted_sum = None
        
        for i, weights in enumerate(weight_list):
            weight = weights[key]
            num_examples = num_examples_list[i]
            
            # FIX 5: Ensure numeric types (prevent broadcasting issues)
            weight = np.asarray(weight, dtype=np.float32)
            
            # Weighted accumulation
            weighted = weight * (num_examples / total_examples)
            
            if weighted_sum is None:
                weighted_sum = weighted.copy()
            else:
                weighted_sum += weighted
        
        aggregated[key] = weighted_sum
    
    logger.info(f"FedAvg aggregation complete: {len(weight_list)} clients, {total_examples} total examples")
    return aggregated


# ============================================================================
# MAIN AGGREGATION WORKFLOW
# ============================================================================

def aggregate_updates(round_obj):
    """
    Main aggregation workflow for a round.
    
    Process:
    1. Retrieve all updates for the round
    2. Validate each update (hash, structure)
    3. Deserialize weights
    4. Run FedAvg aggregation
    5. Save aggregated model
    6. Update metrics
    
    Args:
        round_obj: Round model instance
        
    Returns:
        dict: result with status, metrics, aggregated_weights
        
    FIXES APPLIED:
    - FIX 1: Comprehensive validation
    - FIX 2: Separate valid/invalid updates
    - FIX 3: Handle no-valid-updates case
    - FIX 4: Log invalid updates
    - FIX 5: Mark invalid in database
    - FIX 6: Proper weight aggregation (not merge)
    """
    from .models import ClientUpdate, ModelVersion
    
    # Retrieve all updates for this round
    updates = round_obj.client_updates.filter(status__in=['received', 'validated'])
    
    if not updates.exists():
        logger.warning(f"No updates for round {round_obj.round_number}")
        return {
            'status': 'failed',
            'reason': 'No client updates found',
            'participating_count': 0
        }
    
    # FIX 1 + 2: Validate updates, separate valid and invalid
    valid_updates = []
    invalid_updates = []
    
    for update in updates:
        is_valid, error_msg = validate_client_update(update)
        
        if is_valid:
            valid_updates.append(update)
        else:
            # FIX 5: Mark invalid in database
            update.is_valid = False
            update.validation_error = error_msg
            update.save()
            invalid_updates.append((update.update_id, error_msg))
            # FIX 4: Log invalid update
            logger.warning(f"Invalid update {update.update_id}: {error_msg}")
    
    # FIX 3: Handle no valid updates case
    if not valid_updates:
        logger.error(f"No valid updates for aggregation in round {round_obj.round_number}")
        return {
            'status': 'failed',
            'reason': 'No valid updates for aggregation',
            'participating_count': 0,
            'invalid_count': len(invalid_updates)
        }
    
    try:
        # Collect weights and num_examples for aggregation
        all_weights = []
        num_examples_list = []
        
        for update in valid_updates:
            weights = deserialize_weights_from_npz(update.weight_delta)
            all_weights.append(weights)
            num_examples_list.append(update.num_examples)
        
        # Run FedAvg aggregation
        aggregated_weights = fedavg_aggregate(all_weights, num_examples_list)
        
        total_examples = sum(num_examples_list)
        
        # Save aggregated model as new ModelVersion
        aggregated_data = serialize_weights_to_npz(aggregated_weights)
        aggregated_hash = hashlib.sha256(aggregated_data).hexdigest()
        
        with transaction.atomic():
            # Create new model version
            new_version = ModelVersion.objects.create(
                version=f"{round_obj.model_version.version}.aggregated.{round_obj.round_number}",
                description=f"Aggregated model from round {round_obj.round_number}",
                model_data=aggregated_data,
                is_active=False  # Must be explicitly activated
            )
            
            # Link aggregated model to round
            round_obj.aggregated_model_version = new_version
            round_obj.save()
            
            logger.info(f"Created aggregated model version: {new_version.version}")
        
        # Update metrics
        metrics_query = round_obj.client_updates.filter(
            id__in=[u.id for u in valid_updates]
        ).aggregate(
            avg_loss=Avg('local_loss'),
            avg_accuracy=Avg('local_accuracy')
        )
        
        metrics = round_obj.metrics
        metrics.participating_clients = len(valid_updates)
        metrics.avg_local_loss = metrics_query['avg_loss']
        metrics.avg_local_accuracy = metrics_query['avg_accuracy']
        metrics.aggregation_time_ms = 0  # Can measure if needed
        metrics.save()
        
        return {
            'status': 'success',
            'participating_count': len(valid_updates),
            'invalid_count': len(invalid_updates),
            'total_examples': total_examples,
            'aggregated_model_version': new_version.version,
            'aggregated_model_hash': aggregated_hash,
            'metrics': {
                'avg_local_loss': metrics.avg_local_loss,
                'avg_local_accuracy': metrics.avg_local_accuracy,
                'total_examples': total_examples,
            }
        }
        
    except Exception as e:
        logger.error(f"Aggregation failed for round {round_obj.round_number}: {e}", exc_info=True)
        return {
            'status': 'failed',
            'reason': str(e),
            'participating_count': len(valid_updates),
            'invalid_count': len(invalid_updates)
        }


def run_aggregation(round_obj):
    """
    Public interface for running aggregation.
    
    This is the entry point called from tasks.py
    """
    return aggregate_updates(round_obj)
