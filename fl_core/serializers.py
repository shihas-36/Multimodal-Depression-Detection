from rest_framework import serializers
from .models import Device, ModelVersion, Round, ClientUpdate, RoundMetrics, DeviceToken
import uuid
import secrets


class DeviceSerializer(serializers.ModelSerializer):
    device_id = serializers.UUIDField(read_only=True)
    
    class Meta:
        model = Device
        fields = [
            'device_id', 'device_name', 'device_type', 'os_version', 
            'app_version', 'status', 'last_seen', 'created_at'
        ]
        read_only_fields = ['device_id', 'last_seen', 'created_at']


class DeviceRegisterSerializer(serializers.Serializer):
    """Registration request from mobile app."""
    device_name = serializers.CharField(max_length=255)
    device_type = serializers.CharField(max_length=50)  # iOS, Android
    os_version = serializers.CharField(max_length=50)
    app_version = serializers.CharField(max_length=20)
    
    def create(self, validated_data):
        from datetime import timedelta
        from django.utils import timezone
        
        device = Device.objects.create(**validated_data)
        token = DeviceToken.objects.create(
            device=device,
            token=secrets.token_urlsafe(32),
            expires_at=timezone.now() + timedelta(hours=24)  # FIX 1: Token expires in 24 hours
        )
        return device, token


class ModelVersionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModelVersion
        fields = [
            'id', 'version', 'description', 'model_file', 'onnx_file', 
            'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['created_at', 'updated_at']


class RoundMetricsSerializer(serializers.ModelSerializer):
    class Meta:
        model = RoundMetrics
        fields = [
            'total_clients', 'participating_clients', 'avg_local_loss',
            'avg_local_accuracy', 'global_loss', 'global_accuracy',
            'aggregation_time_ms', 'created_at'
        ]
        read_only_fields = ['created_at']


class RoundSerializer(serializers.ModelSerializer):
    metrics = RoundMetricsSerializer(read_only=True)
    model_version = ModelVersionSerializer(read_only=True)
    
    class Meta:
        model = Round
        fields = [
            'id', 'round_number', 'model_version', 'status', 'min_clients',
            'max_clients', 'started_at', 'closed_at', 'ended_at',
            'aggregation_status', 'metrics', 'created_at'
        ]
        read_only_fields = [
            'id', 'started_at', 'closed_at', 'ended_at', 'metrics', 'created_at'
        ]


class ClientUpdateSerializer(serializers.ModelSerializer):
    update_id = serializers.UUIDField(read_only=True)
    
    class Meta:
        model = ClientUpdate
        fields = [
            'update_id', 'device', 'round', 'num_examples', 'local_loss',
            'local_accuracy', 'weight_delta', 'parameters_hash', 
            'dp_clip_norm', 'dp_noise_scale', 'status', 'submitted_at', 'validated_at'
        ]
        read_only_fields = [
            'update_id', 'status', 'submitted_at', 'validated_at'
        ]


class ClientUpdateSubmitSerializer(serializers.Serializer):
    """Request schema for client update submission."""
    round_id = serializers.IntegerField()
    num_examples = serializers.IntegerField(min_value=1)
    local_loss = serializers.FloatField(required=False, allow_null=True)
    local_accuracy = serializers.FloatField(required=False, allow_null=True)
    weight_delta = serializers.CharField()  # Base64 encoded binary - FULL model weights
    parameters_hash = serializers.CharField(max_length=64)
    model_version = serializers.CharField(max_length=20)  # Client model version for consistency check
    dp_clip_norm = serializers.FloatField(required=False, allow_null=True)
    dp_noise_scale = serializers.FloatField(required=False, allow_null=True)
    
    def validate_num_examples(self, value):
        """Validate num_examples is in valid range."""
        if value <= 0 or value > 10000:
            raise serializers.ValidationError(
                f"num_examples must be between 1 and 10000, got {value}"
            )
        return value


class RoundStatusSerializer(serializers.ModelSerializer):
    """Status response for round."""
    participating_devices = serializers.SerializerMethodField()
    
    class Meta:
        model = Round
        fields = [
            'id', 'round_number', 'status', 'min_clients', 'max_clients',
            'participating_devices', 'aggregation_status', 'started_at', 
            'closed_at', 'ended_at'
        ]
    
    def get_participating_devices(self, obj):
        return obj.client_updates.filter(status__in=['received', 'validated', 'aggregated']).count()
