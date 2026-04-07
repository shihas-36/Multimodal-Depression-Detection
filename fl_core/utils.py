"""
Utility functions for FL backend.
"""


def error_response(code, message, details=None):
    """
    FIX 2: Standard error response format for consistent API responses.
    
    Args:
        code: Machine-readable error code (e.g., 'INVALID_ROUND')
        message: Human-readable error message
        details: Optional dict with additional error details
        
    Returns:
        dict with standardized error format
        
    Example:
        error_response(
            'INVALID_ROUND',
            'Round is not active',
            {'round_id': 123}
        )
    """
    return {
        "status": "error",
        "code": code,
        "message": message,
        "details": details or {}
    }


def success_response(data, code="OK"):
    """
    Standard success response format for consistent API responses.
    
    Args:
        data: Response data dict
        code: Machine-readable success code (e.g., 'OK', 'CREATED')
        
    Returns:
        dict with standardized success format
    """
    return {
        "status": "success",
        "code": code,
        "data": data
    }
