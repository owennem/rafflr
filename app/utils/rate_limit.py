"""Rate limiting utilities with user-aware key functions."""
from typing import Optional
from fastapi import Request
from slowapi.util import get_remote_address


def get_rate_limit_key(request: Request) -> str:
    """
    Get a rate limit key that combines IP address and user ID (if authenticated).
    This provides better protection against:
    - Multiple accounts from the same IP (by also tracking user ID)
    - Single account from multiple IPs (by tracking both)
    """
    ip_address = get_remote_address(request)

    # Try to get user ID from request state (set by auth middleware)
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        return f"{ip_address}:user:{user_id}"

    return ip_address


def get_user_rate_limit_key(request: Request) -> str:
    """
    Get a rate limit key based on user ID only (for authenticated routes).
    Falls back to IP address if user is not authenticated.
    """
    user_id = getattr(request.state, "user_id", None)

    if user_id:
        return f"user:{user_id}"

    return get_remote_address(request)


def get_ip_rate_limit_key(request: Request) -> str:
    """
    Get a rate limit key based on IP address only.
    Standard approach for unauthenticated routes.
    """
    return get_remote_address(request)
