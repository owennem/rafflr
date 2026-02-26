from fastapi import Request
from fastapi.templating import Jinja2Templates
from markupsafe import Markup

# Shared templates instance
templates = Jinja2Templates(directory="app/templates")


def get_csrf_token(request: Request) -> str:
    """Get CSRF token from request state."""
    return getattr(request.state, "csrf_token", "")


def csrf_input(request: Request):
    """Return hidden input field with CSRF token."""
    token = getattr(request.state, "csrf_token", "")
    return Markup(f'<input type="hidden" name="csrf_token" value="{token}">')


# Add globals to templates
templates.env.globals["get_csrf_token"] = get_csrf_token
templates.env.globals["csrf_input"] = csrf_input
