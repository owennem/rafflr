from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
import secrets
import hashlib


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Prevent clickjacking - page cannot be embedded in iframes
        response.headers["X-Frame-Options"] = "DENY"

        # Prevent MIME type sniffing
        response.headers["X-Content-Type-Options"] = "nosniff"

        # Enable XSS filter in browsers
        response.headers["X-XSS-Protection"] = "1; mode=block"

        # Control referrer information sent with requests
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"

        # Restrict browser features
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"

        # Content Security Policy - restrict resource loading
        # Allowing Tailwind CDN, HTMX, and inline scripts for Tailwind config
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.tailwindcss.com https://unpkg.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data:; "
            "font-src 'self' https:; "
            "connect-src 'self' https://js.stripe.com; "
            "frame-src https://js.stripe.com https://hooks.stripe.com; "
        )

        return response


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection using double-submit cookie pattern.
    For state-changing requests (POST, PUT, DELETE), validates that
    the CSRF token in the form matches the one in the cookie.
    """

    CSRF_COOKIE_NAME = "csrf_token"
    CSRF_FIELD_NAME = "csrf_token"
    SAFE_METHODS = {"GET", "HEAD", "OPTIONS", "TRACE"}
    EXEMPT_PATHS = {"/payments/webhook"}  # Stripe webhook needs to be exempt

    async def dispatch(self, request: Request, call_next):
        # Generate CSRF token if not present
        csrf_token = request.cookies.get(self.CSRF_COOKIE_NAME)
        if not csrf_token:
            csrf_token = secrets.token_urlsafe(32)

        # Store token in request state for templates
        request.state.csrf_token = csrf_token

        # Validate CSRF for unsafe methods
        if request.method not in self.SAFE_METHODS:
            # Skip validation for exempt paths
            if request.url.path not in self.EXEMPT_PATHS:
                # Get token from form data or header
                form_token = None

                # Try to get from form data
                content_type = request.headers.get("content-type", "")
                if "application/x-www-form-urlencoded" in content_type or "multipart/form-data" in content_type:
                    try:
                        form = await request.form()
                        form_token = form.get(self.CSRF_FIELD_NAME)
                    except Exception:
                        pass

                # Also check header (for AJAX requests)
                if not form_token:
                    form_token = request.headers.get("X-CSRF-Token")

                cookie_token = request.cookies.get(self.CSRF_COOKIE_NAME)

                # Validate tokens match
                if not form_token or not cookie_token or not secrets.compare_digest(form_token, cookie_token):
                    from fastapi.responses import HTMLResponse
                    return HTMLResponse(
                        content="<h1>403 Forbidden</h1><p>CSRF token validation failed.</p>",
                        status_code=403
                    )

        response = await call_next(request)

        # Detect if running over HTTPS (production)
        is_secure = (
            request.url.scheme == "https" or
            request.headers.get("x-forwarded-proto") == "https"
        )

        # Set CSRF cookie
        response.set_cookie(
            key=self.CSRF_COOKIE_NAME,
            value=csrf_token,
            httponly=False,  # JavaScript needs to read this for AJAX
            samesite="lax",
            secure=is_secure,  # True in production with HTTPS
            max_age=3600  # 1 hour
        )

        return response


def setup_security_middleware(app: FastAPI, allowed_hosts: list[str] = None):
    """Configure all security middleware for the application."""

    # Add security headers
    app.add_middleware(SecurityHeadersMiddleware)

    # Add CSRF protection
    app.add_middleware(CSRFMiddleware)

    # Add trusted host validation (prevents host header attacks)
    if allowed_hosts:
        app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)
