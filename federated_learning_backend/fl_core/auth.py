from rest_framework.authentication import TokenAuthentication
from rest_framework import permissions, exceptions
from django.utils import timezone

from .models import DeviceToken


class DeviceAuthentication(TokenAuthentication):
    """Custom token auth using DeviceToken model."""
    keyword = 'Bearer'
    
    def get_model(self):
        return DeviceToken
    
    def authenticate_credentials(self, key):
        """Override to use 'token' field instead of 'key'."""
        model = self.get_model()
        try:
            token = model.objects.select_related('device').get(token=key)
        except model.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid token.')
        
        if not token.is_active:
            raise exceptions.AuthenticationFailed('Token is inactive.')
        
        if token.is_expired():
            raise exceptions.AuthenticationFailed('Token has expired.')
        
        # Update last_used
        token.last_used = timezone.now()
        token.save(update_fields=['last_used'])
        
        return (token.device, token)


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
