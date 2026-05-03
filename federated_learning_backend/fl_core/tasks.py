"""
Celery tasks for federated learning operations.
"""

from celery import shared_task
import logging
from django.utils import timezone
from .models import Round, ClientUpdate, RoundMetrics
from .aggregation import run_aggregation

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
    print("🚀 TASK EXECUTED: trigger_aggregation_task")
    logger.info(f"🚀 TASK EXECUTED: trigger_aggregation_task for round {round_id}")
    
    try:
        round_obj = Round.objects.get(id=round_id)
        
        if round_obj.status != 'closed':
            logger.warning(f"Round {round_id} is not closed, cannot aggregate")
            return {"status": "error", "reason": "round_not_closed"}
        
        # FIX 3: Check if already aggregated (idempotent)
        if round_obj.status == 'aggregated':
            logger.info(f"Round {round_id} already aggregated, skipping")
            return {"status": "already_aggregated", "round_id": round_id}
        
        # FIX 4: Use aggregating status as lock
        if round_obj.aggregation_status == 'in_progress':
            logger.warning(f"Round {round_id} aggregation already running")
            return {"status": "already_running", "round_id": round_id}
        
        logger.info(f"Starting aggregation for round {round_id}")
        
        # FIX 4: Lock - transition to aggregating state
        round_obj.aggregation_status = 'in_progress'
        round_obj.save()
        
        # Run aggregation
        result = run_aggregation(round_obj)
        
        if result.get('status') == 'success':
            # FIX 3 + 4: Mark as aggregated (prevent re-execution)
            round_obj.status = 'aggregated'
            round_obj.aggregation_status = 'completed'
            round_obj.ended_at = timezone.now()
            round_obj.save()
            
            logger.info(f"Round {round_id} aggregation completed successfully")
        else:
            round_obj.aggregation_status = 'failed'
            round_obj.save()
            logger.error(f"Round {round_id} aggregation failed: {result.get('reason')}")
        
        return result
    except Round.DoesNotExist:
        logger.error(f"Round {round_id} not found")
        return {"status": "error", "reason": "round_not_found"}
    except Exception as e:
        logger.error(f"Error aggregating round {round_id}: {e}")
        try:
            round_obj = Round.objects.get(id=round_id)
            round_obj.aggregation_status = 'failed'
            round_obj.save()
        except:
            pass
        return {"status": "error", "reason": str(e)}


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
        status='completed',
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
