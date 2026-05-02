from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta
import uuid


class Device(models.Model):
    """Mobile client device registration and metadata."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
    ]
    
    device_id = models.UUIDField(unique=True, default=uuid.uuid4)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='devices', null=True, blank=True)
    device_name = models.CharField(max_length=255)
    device_type = models.CharField(max_length=50)  # iOS, Android
    os_version = models.CharField(max_length=50)
    app_version = models.CharField(max_length=20)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    last_seen = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.device_name} ({self.device_id})"


class ModelVersion(models.Model):
    """Global model versioning and artifact storage."""
    version = models.CharField(max_length=20, unique=True)  # e.g., "1.0.0"
    description = models.TextField(blank=True)
    model_file = models.FileField(upload_to='models/')
    onnx_file = models.FileField(upload_to='models/onnx/', null=True, blank=True)
    model_data = models.BinaryField(null=True, blank=True, help_text="Serialized model weights (state_dict)")
    is_active = models.BooleanField(default=False)  # Current production model
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Model v{self.version}"


class Round(models.Model):
    """Federated learning round lifecycle."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('active', 'Active'),
        ('closed', 'Closed'),
        ('aggregated', 'Aggregated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]
    
    round_number = models.IntegerField(unique=True)
    model_version = models.ForeignKey(ModelVersion, on_delete=models.PROTECT, help_text="Initial model for this round")
    aggregated_model_version = models.ForeignKey(ModelVersion, on_delete=models.SET_NULL, null=True, blank=True, related_name='aggregated_rounds', help_text="Model version created from this round's aggregation")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    min_clients = models.IntegerField(default=3)
    max_clients = models.IntegerField(default=100)
    started_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    ended_at = models.DateTimeField(null=True, blank=True)
    aggregation_status = models.CharField(
        max_length=50, 
        default='pending',
        help_text="pending, in_progress, completed, failed"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-round_number']
    
    def __str__(self):
        return f"Round {self.round_number} - {self.status}"


class ClientUpdate(models.Model):
    """Client federated update submission."""
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('received', 'Received'),
        ('validated', 'Validated'),
        ('aggregated', 'Aggregated'),
        ('failed', 'Failed'),
    ]
    
    update_id = models.UUIDField(unique=True, default=uuid.uuid4)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='updates')
    round = models.ForeignKey(Round, on_delete=models.CASCADE, related_name='client_updates')
    num_examples = models.IntegerField()
    local_loss = models.FloatField(null=True, blank=True)
    local_accuracy = models.FloatField(null=True, blank=True)
    weight_delta = models.BinaryField(help_text="Serialized FULL model weights (state_dict) from client local training")
    parameters_hash = models.CharField(max_length=64, help_text="SHA256 hash of parameters")
    dp_clip_norm = models.FloatField(null=True, blank=True)
    dp_noise_scale = models.FloatField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    validated_at = models.DateTimeField(null=True, blank=True)
    is_valid = models.BooleanField(default=True, help_text="Passed validation during aggregation")
    validation_error = models.TextField(null=True, blank=True, help_text="Validation error details if failed")
    
    class Meta:
        unique_together = ('device', 'round')
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"Update {self.update_id} - {self.status}"


class RoundMetrics(models.Model):
    """Aggregated metrics for each round."""
    round = models.OneToOneField(Round, on_delete=models.CASCADE, related_name='metrics')
    total_clients = models.IntegerField(default=0)
    participating_clients = models.IntegerField(default=0)
    avg_local_loss = models.FloatField(null=True, blank=True)
    avg_local_accuracy = models.FloatField(null=True, blank=True)
    global_loss = models.FloatField(null=True, blank=True)
    global_accuracy = models.FloatField(null=True, blank=True)
    aggregation_time_ms = models.IntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Metrics for Round {self.round.round_number}"


class DeviceToken(models.Model):
    """API tokens for device authentication with expiry."""
    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name='token')
    token = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(default=timezone.now, help_text="Token expiration time")
    last_used = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    def is_expired(self):
        """Check if token has expired."""
        return timezone.now() > self.expires_at
    
    def __str__(self):
        return f"Token for {self.device.device_name}"
