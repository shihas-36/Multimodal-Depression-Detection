from django.contrib import admin
from .models import Device, ModelVersion, Round, ClientUpdate, RoundMetrics, DeviceToken


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['device_name', 'device_type', 'status', 'last_seen', 'created_at']
    list_filter = ['status', 'device_type', 'created_at']
    search_fields = ['device_name', 'device_id']
    readonly_fields = ['device_id', 'created_at', 'last_seen']


@admin.register(ModelVersion)
class ModelVersionAdmin(admin.ModelAdmin):
    list_display = ['version', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['version', 'description']
    readonly_fields = ['created_at', 'updated_at']


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ['round_number', 'status', 'aggregation_status', 'started_at', 'ended_at']
    list_filter = ['status', 'aggregation_status', 'created_at']
    search_fields = ['round_number']
    readonly_fields = ['created_at', 'started_at', 'closed_at', 'ended_at']
    
    fieldsets = (
        ('Round Info', {
            'fields': ('round_number', 'model_version', 'status')
        }),
        ('Clients', {
            'fields': ('min_clients', 'max_clients')
        }),
        ('Status', {
            'fields': ('aggregation_status', 'started_at', 'closed_at', 'ended_at')
        }),
        ('Metadata', {
            'fields': ('created_at',)
        }),
    )


@admin.register(ClientUpdate)
class ClientUpdateAdmin(admin.ModelAdmin):
    list_display = ['device', 'round', 'status', 'num_examples', 'submitted_at']
    list_filter = ['status', 'submitted_at', 'round__round_number']
    search_fields = ['device__device_name', 'update_id']
    readonly_fields = ['update_id', 'submitted_at', 'validated_at']
    
    fieldsets = (
        ('Submission', {
            'fields': ('update_id', 'device', 'round')
        }),
        ('Data', {
            'fields': ('num_examples', 'local_loss', 'local_accuracy')
        }),
        ('Privacy', {
            'fields': ('dp_clip_norm', 'dp_noise_scale'),
            'classes': ('collapse',)
        }),
        ('Validation', {
            'fields': ('parameters_hash', 'status', 'submitted_at', 'validated_at')
        }),
    )


@admin.register(RoundMetrics)
class RoundMetricsAdmin(admin.ModelAdmin):
    list_display = ['round', 'participating_clients', 'avg_local_accuracy']
    list_filter = ['created_at']
    readonly_fields = ['created_at']
    
    def has_add_permission(self, request):
        return False


@admin.register(DeviceToken)
class DeviceTokenAdmin(admin.ModelAdmin):
    list_display = ['device', 'is_active', 'created_at', 'last_used']
    list_filter = ['is_active', 'created_at', 'last_used']
    search_fields = ['device__device_name', 'token']
    readonly_fields = ['created_at', 'token']
    
    def has_add_permission(self, request):
        return False
