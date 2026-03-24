from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from pydantic import ValidationError
import logging

from app.database import get_db
from app.services.auth import (
    AuthService, get_current_user, set_auth_cookie, clear_auth_cookie
)
from app.services.email import EmailService
from app.schemas.user import UserCreate
from app.models.user import User
from app.templates_config import templates
from app.utils.validation import (
    validate_username,
    validate_password,
    MAX_USERNAME_LENGTH,
    MAX_EMAIL_LENGTH,
    MAX_PASSWORD_LENGTH,
)
from app.utils.rate_limit import get_rate_limit_key

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_rate_limit_key)
logger = logging.getLogger(__name__)


@router.get("/register", response_class=HTMLResponse)
async def register_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("auth/register.html", {"request": request})


@router.post("/register")
@limiter.limit("5/minute")  # Max 5 registration attempts per minute per IP
async def register(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(..., max_length=MAX_EMAIL_LENGTH),
    username: str = Form(..., max_length=MAX_USERNAME_LENGTH),
    password: str = Form(..., max_length=MAX_PASSWORD_LENGTH),
    db: Session = Depends(get_db)
):
    # Validate and sanitize inputs
    email = email.strip().lower()[:MAX_EMAIL_LENGTH]
    username = username.strip()[:MAX_USERNAME_LENGTH]
    password = password[:MAX_PASSWORD_LENGTH]

    # Validate username format
    try:
        username = validate_username(username)
    except ValueError as e:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": str(e)},
            status_code=400
        )

    # Validate password strength
    try:
        validate_password(password)
    except ValueError as e:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": str(e)},
            status_code=400
        )

    existing_email = AuthService.get_user_by_email(db, email)
    if existing_email:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Email already registered"},
            status_code=400
        )

    existing_username = AuthService.get_user_by_username(db, username)
    if existing_username:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Username already taken"},
            status_code=400
        )

    try:
        user_data = UserCreate(email=email, username=username, password=password)
        user = AuthService.create_user(db, user_data)
    except ValidationError as e:
        # Extract first error message from Pydantic validation
        error_msg = str(e.errors()[0]["msg"]) if e.errors() else "Invalid input"
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": error_msg},
            status_code=400
        )
    except Exception as e:
        logger.error(f"Registration error: {e}")
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "An error occurred during registration. Please try again."},
            status_code=500
        )

    # Generate 2FA code for registration verification
    code = AuthService.create_2fa_code(db, user, action="registration")
    background_tasks.add_task(
        EmailService.send_2fa_code,
        user.email,
        user.username,
        code,
        "registration"
    )

    return templates.TemplateResponse(
        "auth/verify_2fa.html",
        {
            "request": request,
            "email": user.email,
            "user_id": user.id,
            "action": "registration"
        }
    )


@router.get("/verify", response_class=HTMLResponse)
async def verify_email(request: Request, token: str, db: Session = Depends(get_db)):
    user = AuthService.verify_user_email(db, token)
    if user:
        return templates.TemplateResponse(
            "auth/verify_success.html",
            {"request": request}
        )
    return templates.TemplateResponse(
        "auth/verify_failed.html",
        {"request": request, "error": "Invalid or expired verification link"},
        status_code=400
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, user: User = Depends(get_current_user)):
    if user:
        return RedirectResponse(url="/dashboard", status_code=302)
    return templates.TemplateResponse("auth/login.html", {"request": request})


@router.post("/login")
@limiter.limit("5/minute")  # Max 5 login attempts per minute per IP
async def login(
    request: Request,
    response: Response,
    background_tasks: BackgroundTasks,
    email: str = Form(..., max_length=MAX_EMAIL_LENGTH),
    password: str = Form(..., max_length=MAX_PASSWORD_LENGTH),
    db: Session = Depends(get_db)
):
    # Sanitize inputs
    email = email.strip().lower()[:MAX_EMAIL_LENGTH]
    password = password[:MAX_PASSWORD_LENGTH]

    # Basic validation
    if not email or not password:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Email and password are required"},
            status_code=400
        )

    user = AuthService.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=400
        )

    # Check if user is verified
    if not user.is_verified:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Please verify your email first. Check your inbox for a verification code."},
            status_code=400
        )

    # Generate 2FA code for login
    code = AuthService.create_2fa_code(db, user, action="login")
    background_tasks.add_task(
        EmailService.send_2fa_code,
        user.email,
        user.username,
        code,
        "login"
    )

    return templates.TemplateResponse(
        "auth/verify_2fa.html",
        {
            "request": request,
            "email": user.email,
            "user_id": user.id,
            "action": "login"
        }
    )


@router.get("/logout")
async def logout(response: Response):
    redirect = RedirectResponse(url="/", status_code=302)
    clear_auth_cookie(redirect)
    return redirect


@router.get("/forgot-password", response_class=HTMLResponse)
async def forgot_password_page(request: Request):
    return templates.TemplateResponse("auth/forgot_password.html", {"request": request})


@router.post("/forgot-password")
@limiter.limit("3/minute")  # Max 3 password reset requests per minute per IP
async def forgot_password(
    request: Request,
    background_tasks: BackgroundTasks,
    email: str = Form(...),
    db: Session = Depends(get_db)
):
    reset_token = AuthService.create_password_reset(db, email)
    if reset_token:
        background_tasks.add_task(
            EmailService.send_password_reset_email,
            email,
            reset_token
        )

    return templates.TemplateResponse(
        "auth/forgot_password_sent.html",
        {"request": request}
    )


@router.get("/reset-password", response_class=HTMLResponse)
async def reset_password_page(request: Request, token: str):
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token}
    )


@router.post("/reset-password")
@limiter.limit("5/minute")  # Rate limit password reset attempts
async def reset_password(
    request: Request,
    token: str = Form(..., max_length=128),
    password: str = Form(..., max_length=MAX_PASSWORD_LENGTH),
    db: Session = Depends(get_db)
):
    # Sanitize inputs
    token = token.strip()[:128]
    password = password[:MAX_PASSWORD_LENGTH]

    # Validate password strength
    try:
        validate_password(password)
    except ValueError as e:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "error": str(e)},
            status_code=400
        )

    success = AuthService.reset_password(db, token, password)
    if success:
        return templates.TemplateResponse(
            "auth/reset_password_success.html",
            {"request": request}
        )
    return templates.TemplateResponse(
        "auth/reset_password.html",
        {"request": request, "token": token, "error": "Invalid or expired reset link"},
        status_code=400
    )


@router.post("/verify-2fa")
@limiter.limit("10/minute")  # Rate limit 2FA verification attempts
async def verify_2fa(
    request: Request,
    user_id: int = Form(...),
    code: str = Form(..., max_length=6),
    action: str = Form(..., max_length=20),
    db: Session = Depends(get_db)
):
    # Sanitize inputs
    code = code.strip()[:6]
    action = action.strip()[:20]

    # Validate user_id
    if user_id < 1:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid verification request"},
            status_code=400
        )

    # Get user to display email in error case
    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid verification request"},
            status_code=400
        )

    # Verify the 2FA code
    verified_user = AuthService.verify_2fa_code(db, user_id, code)
    if not verified_user:
        return templates.TemplateResponse(
            "auth/verify_2fa.html",
            {
                "request": request,
                "email": user.email,
                "user_id": user_id,
                "action": action,
                "error": "Invalid or expired verification code"
            },
            status_code=400
        )

    # Create access token and log the user in
    access_token = AuthService.create_access_token(data={"sub": str(verified_user.id)})
    redirect = RedirectResponse(url="/listings?login=success", status_code=302)
    set_auth_cookie(redirect, access_token, request)
    return redirect


@router.post("/resend-2fa")
@limiter.limit("3/minute")  # Rate limit resend attempts
async def resend_2fa(
    request: Request,
    background_tasks: BackgroundTasks,
    user_id: int = Form(...),
    action: str = Form(..., max_length=20),
    db: Session = Depends(get_db)
):
    # Sanitize inputs
    action = action.strip()[:20]

    # Validate user_id
    if user_id < 1:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid request"},
            status_code=400
        )

    user = AuthService.get_user_by_id(db, user_id)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid request"},
            status_code=400
        )

    # Generate new 2FA code
    code = AuthService.create_2fa_code(db, user, action=action)
    background_tasks.add_task(
        EmailService.send_2fa_code,
        user.email,
        user.username,
        code,
        action
    )

    return templates.TemplateResponse(
        "auth/verify_2fa.html",
        {
            "request": request,
            "email": user.email,
            "user_id": user.id,
            "action": action,
            "success": "A new verification code has been sent to your email"
        }
    )
