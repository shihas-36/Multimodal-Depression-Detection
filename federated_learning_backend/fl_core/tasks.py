"""
Celery tasks for federated learning operations.
"""

from celery import shared_task
import logging
from django.utils import timezone
from .models import Round, ClientUpdate, RoundMetrics
from .aggregation import run_aggregation, validate_client_update

logger = logging.getLogger(__name__)


@shared_task
def auto_close_round(round_id):
    """
    Auto-close round after deadline.
    
    Args:
        round_id: ID of round to close
    """
    try:
        round_obj = Round.objects.get(id=round_id)
        
        if round_obj.status != 'active':
            logger.warning(f"Round {round_id} is not active, skipping close")
            return
        
        round_obj.status = 'closed'
        round_obj.closed_at = timezone.now()
        round_obj.save()
        
        logger.info(f"Round {round_id} auto-closed")
        
        # Trigger aggregation if enough clients participated
        # Uses trigger_aggregation_task for centralized execution (FIX 2)
        participating = round_obj.client_updates.filter(
            status__in=['received', 'validated']
        ).count()
        
        if participating >= round_obj.min_clients:
            trigger_aggregation_task.delay(round_id)
        else:
            logger.warning(
                f"Round {round_id} closed but insufficient clients ({participating}/{round_obj.min_clients})"
            )
    except Round.DoesNotExist:
        logger.error(f"Round {round_id} not found")
    except Exception as e:
        logger.error(f"Error closing round {round_id}: {e}")


@shared_task
def trigger_aggregation_task(round_id):
    """
    Centralized aggregation task - ONLY execution point for aggregation.
    Implements duplicate prevention with locking mechanism.
    
    Args:
        round_id: ID of round to aggregate
    
    FIX 2: Single execution point
    FIX 3: Prevent duplicate execution
    FIX 4: Lock with aggregating status
    """
    logger.info(f"🚀 TASK EXECUTED: trigger_aggregation_task for round {round_id}")
    round_obj = None
    
    try:
        round_obj = Round.objects.get(id=round_id)
        
        # If already aggregated, we still want to ensure a NEXT round exists
        if round_obj.status == 'aggregated' or round_obj.status == 'failed':
            logger.info(f"Round {round_id} already processed. Ensuring next round exists.")
            create_next_round(round_obj)
            return {"status": "skipped_already_processed"}

        # Set locking status
        round_obj.aggregation_status = 'in_progress'
        round_obj.save()
        
        # Run aggregation logic
        result = run_aggregation(round_obj)
        
        # Mark current round as finished regardless of 'success' or 'failed'
        # so the system doesn't get stuck.
        round_obj.status = 'aggregated'
        round_obj.aggregation_status = 'completed'
        round_obj.ended_at = timezone.now()
        round_obj.save()

    except Exception as e:
        logger.error(f"Critical error in task for round {round_id}: {e}")
        if round_obj:
            round_obj.status = 'failed'
            round_obj.save()
    
    finally:
        # ALWAYS attempt to create the next round here
        if round_obj:
            new_round = create_next_round(round_obj)
            if new_round:
                return {"status": "finished", "next_round_id": new_round.id}
            return {"status": "finished", "next_round_note": "already_exists_or_failed"}
    return {"status": "error", "reason": "round_not_found"}



@shared_task
def validate_pending_updates():
    """
    Validate pending client updates (e.g., check hashes, deserialize).
    Runs periodically.
    """
    pending_updates = ClientUpdate.objects.filter(status='pending')[:100]
    
    validated_count = 0
    failed_count = 0
    
    for update in pending_updates:
        try:
            is_valid, error_msg = validate_client_update(update)
            if is_valid:
                validated_count += 1
            else:
                update.status = 'failed'
                update.save()
                failed_count += 1
                logger.warning(f"Update {update.update_id} validation failed: {error_msg}")
        except Exception as e:
            update.status = 'failed'
            update.save()
            failed_count += 1
            logger.error(f"Error validating update {update.update_id}: {e}")
    
    logger.info(f"Validation task completed: {validated_count} validated, {failed_count} failed")


@shared_task
def cleanup_old_rounds(days=30):
    """
    Archive or delete old completed rounds.
    
    Args:
        days: Number of days before cleanup
    """
    from datetime import timedelta
    cutoff_date = timezone.now() - timedelta(days=days)
    
    old_rounds = Round.objects.filter(
    status__in=['completed', 'aggregated'],
    ended_at__lt=cutoff_date
)
    
    count = old_rounds.count()
    old_rounds.delete()
    
    logger.info(f"Cleaned up {count} old rounds prior to {cutoff_date}")


@shared_task
def periodic_health_check():
    """
    Periodic health check of FL system.
    """
    try:
        # Check recent rounds
        recent_rounds = Round.objects.filter(
            created_at__gte=timezone.now() - timezone.timedelta(hours=1)
        )
        
        active_rounds = recent_rounds.filter(status='active').count()
        completed_rounds = recent_rounds.filter(status='completed').count()
        pending_updates = ClientUpdate.objects.filter(status='pending').count()
        
        logger.info(
            f"Health Check: active_rounds={active_rounds}, "
            f"completed_rounds={completed_rounds}, pending_updates={pending_updates}"
        )
        
        return {
            'active_rounds': active_rounds,
            'completed_rounds': completed_rounds,
            'pending_updates': pending_updates
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")

from .models import ModelVersion


def create_next_round(previous_round):
    """
    Automatically create next FL round after successful aggregation.
    Guaranteed creation of the next FL round.
    """
    next_round_number = previous_round.round_number + 1
    
    # 1. Check if it already exists (to prevent duplicates)
    existing = Round.objects.filter(round_number=next_round_number).first()
    if existing:
        logger.info(f"⏭️ Round {next_round_number} already exists. ID: {existing.id}")
        return existing

    # 2. Determine which model to use
    # If aggregation failed, use the model from the previous round so the chain continues
    model_to_use = previous_round.aggregated_model_version or previous_round.model_version

    try:
        new_round = Round.objects.create(
            round_number=next_round_number,
            model_version=model_to_use,
            status='active',
            min_clients=previous_round.min_clients,
            max_clients=previous_round.max_clients,
            started_at=timezone.now(),
        )
        
        logger.info(f"✅ SUCCESS: Created Round {new_round.round_number} (ID: {new_round.id})")
        return new_round

    except Exception as e:
        logger.error(f"❌ FAILED to create next round: {e}")
        return None
