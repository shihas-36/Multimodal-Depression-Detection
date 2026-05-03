from django.urls import path
from .views import (
    register_device, get_latest_model, get_current_round, get_round_status,
    submit_update, get_device_profile, create_round, close_round, trigger_aggregation,
    refresh_token, get_update_receipt, test_task
)

app_name = 'fl_core'

urlpatterns = [
    # Device endpoints
    path('devices/register/', register_device, name='register_device'),
    path('devices/refresh-token/', refresh_token, name='refresh_token'),
    path('devices/profile/', get_device_profile, name='device_profile'),
    
    # Model endpoints
    path('model/latest/', get_latest_model, name='get_latest_model'),
    
    # Round endpoints
    path('rounds/current/', get_current_round, name='get_current_round'),
    path('rounds/<int:round_id>/status/', get_round_status, name='get_round_status'),
    path('rounds/create/', create_round, name='create_round'),
    path('rounds/<int:round_id>/close/', close_round, name='close_round'),
    path('rounds/<int:round_id>/aggregate/', trigger_aggregation, name='trigger_aggregation'),
    
    # Update endpoints
    path('updates/submit/', submit_update, name='submit_update'),
    path('updates/<uuid:update_id>/receipt/', get_update_receipt, name='get_update_receipt'),
    
    # Test endpoints
    path('test-task/', test_task, name='test_task'),
]
