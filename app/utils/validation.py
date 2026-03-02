"""Input validation and sanitization utilities for security."""
import re
import html
from urllib.parse import urlparse
from typing import Optional
from pydantic import field_validator, model_validator
import bleach


# Allowed URL schemes for images
ALLOWED_URL_SCHEMES = {"http", "https"}

# Maximum field lengths
MAX_USERNAME_LENGTH = 50
MAX_EMAIL_LENGTH = 254
MAX_PASSWORD_LENGTH = 128
MAX_TITLE_LENGTH = 200
MAX_DESCRIPTION_LENGTH = 5000
MAX_URL_LENGTH = 2048
MAX_SEARCH_LENGTH = 100

# Username pattern: alphanumeric, underscores, hyphens, 3-50 chars
USERNAME_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{3,50}$")

# Dangerous patterns to reject
DANGEROUS_PATTERNS = [
    re.compile(r"<script", re.IGNORECASE),
    re.compile(r"javascript:", re.IGNORECASE),
    re.compile(r"data:", re.IGNORECASE),
    re.compile(r"vbscript:", re.IGNORECASE),
    re.compile(r"on\w+\s*=", re.IGNORECASE),  # onclick, onerror, etc.
]


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitize a string input by:
    - Stripping leading/trailing whitespace
    - Truncating to max length
    - Escaping HTML entities
    """
    if not value:
        return value

    # Strip whitespace and truncate
    value = value.strip()[:max_length]

    # Escape HTML entities for safety
    return html.escape(value)


def sanitize_html(value: str, max_length: int = 5000) -> str:
    """
    Sanitize HTML content, allowing only safe tags.
    Useful for description fields where basic formatting may be allowed.
    """
    if not value:
        return value

    # Define allowed tags and attributes
    allowed_tags = ["p", "br", "strong", "em", "ul", "ol", "li"]
    allowed_attrs = {}

    # Clean and truncate
    value = bleach.clean(value.strip()[:max_length], tags=allowed_tags, attributes=allowed_attrs, strip=True)

    return value


def validate_username(username: str) -> str:
    """Validate username format and length."""
    if not username:
        raise ValueError("Username is required")

    username = username.strip()

    if len(username) < 3:
        raise ValueError("Username must be at least 3 characters")

    if len(username) > MAX_USERNAME_LENGTH:
        raise ValueError(f"Username must be at most {MAX_USERNAME_LENGTH} characters")

    if not USERNAME_PATTERN.match(username):
        raise ValueError("Username can only contain letters, numbers, underscores, and hyphens")

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(username):
            raise ValueError("Invalid username")

    return username


def validate_password(password: str) -> str:
    """Validate password strength."""
    if not password:
        raise ValueError("Password is required")

    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters")

    # Check for at least one letter and one number
    if not re.search(r"[a-zA-Z]", password):
        raise ValueError("Password must contain at least one letter")

    if not re.search(r"\d", password):
        raise ValueError("Password must contain at least one number")

    return password


def validate_image_url(url: Optional[str]) -> Optional[str]:
    """
    Validate and sanitize image URL.
    Returns None for empty/invalid URLs.
    """
    if not url:
        return None

    url = url.strip()

    if not url:
        return None

    if len(url) > MAX_URL_LENGTH:
        raise ValueError(f"URL must be at most {MAX_URL_LENGTH} characters")

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(url):
            raise ValueError("Invalid URL")

    # Parse and validate URL
    try:
        parsed = urlparse(url)
    except Exception:
        raise ValueError("Invalid URL format")

    # Validate scheme
    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise ValueError("URL must use http or https")

    # Validate host exists
    if not parsed.netloc:
        raise ValueError("Invalid URL: no host specified")

    return url


def validate_title(title: str) -> str:
    """Validate and sanitize listing title."""
    if not title:
        raise ValueError("Title is required")

    title = title.strip()

    if len(title) < 3:
        raise ValueError("Title must be at least 3 characters")

    if len(title) > MAX_TITLE_LENGTH:
        raise ValueError(f"Title must be at most {MAX_TITLE_LENGTH} characters")

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(title):
            raise ValueError("Invalid title content")

    # Escape HTML for safety
    return html.escape(title)


def validate_description(description: Optional[str]) -> Optional[str]:
    """Validate and sanitize description."""
    if not description:
        return None

    description = description.strip()

    if not description:
        return None

    if len(description) > MAX_DESCRIPTION_LENGTH:
        raise ValueError(f"Description must be at most {MAX_DESCRIPTION_LENGTH} characters")

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(description):
            raise ValueError("Invalid description content")

    # Escape HTML for safety
    return html.escape(description)


def validate_search_query(query: Optional[str]) -> Optional[str]:
    """Validate and sanitize search query."""
    if not query:
        return None

    query = query.strip()

    if not query:
        return None

    if len(query) > MAX_SEARCH_LENGTH:
        query = query[:MAX_SEARCH_LENGTH]

    # Check for dangerous patterns
    for pattern in DANGEROUS_PATTERNS:
        if pattern.search(query):
            return None  # Silently ignore malicious search queries

    # Remove special characters that could cause issues
    # Allow alphanumeric, spaces, and basic punctuation
    query = re.sub(r"[^\w\s\-.,']", "", query)

    return query


def validate_price(price: float) -> float:
    """Validate price value."""
    if price <= 0:
        raise ValueError("Price must be greater than 0")

    if price > 1000000:  # Max $1M
        raise ValueError("Price exceeds maximum allowed value")

    # Round to 2 decimal places
    return round(price, 2)


def validate_quantity(quantity: int, max_quantity: int = 1000) -> int:
    """Validate quantity value."""
    if quantity < 1:
        raise ValueError("Quantity must be at least 1")

    if quantity > max_quantity:
        raise ValueError(f"Quantity must be at most {max_quantity}")

    return quantity


def validate_page(page: int) -> int:
    """Validate pagination page number."""
    if page < 1:
        return 1

    if page > 10000:  # Reasonable max
        return 10000

    return page
