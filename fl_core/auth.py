from rest_framework.authentication import TokenAuthentication
from rest_framework import permissions
from django.utils import timezone

from .models import DeviceToken


class DeviceAuthentication(TokenAuthentication):
    """Custom token auth using DeviceToken model."""
    keyword = 'Bearer'
    
    def get_model(self):
        return DeviceToken


class IsDeviceAuthenticated(permissions.BasePermission):
    """Check if request is from a registered device with valid token."""
    
    def has_permission(self, request, view):
        auth = request.META.get('HTTP_AUTHORIZATION', '').split()
        if len(auth) != 2 or auth[0] != 'Bearer':
            return False
        
        try:
            token = DeviceToken.objects.get(token=auth[1], is_active=True)
            request.device = token.device
            token.last_used = timezone.now()
            token.save(update_fields=['last_used'])
            return True
        except DeviceToken.DoesNotExist:
            return False
