from fastapi import APIRouter, Depends, HTTPException, status, Request, Response, Form, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.database import get_db
from app.services.auth import (
    AuthService, get_current_user, set_auth_cookie, clear_auth_cookie
)
from app.services.email import EmailService
from app.schemas.user import UserCreate
from app.models.user import User
from app.templates_config import templates

router = APIRouter(prefix="/auth", tags=["auth"])
limiter = Limiter(key_func=get_remote_address)


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
    email: str = Form(...),
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
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

    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "Password must be at least 8 characters"},
            status_code=400
        )

    try:
        user_data = UserCreate(email=email, username=username, password=password)
        user = AuthService.create_user(db, user_data)
    except Exception as e:
        import logging
        logging.error(f"Registration error: {e}")
        return templates.TemplateResponse(
            "auth/register.html",
            {"request": request, "error": "An error occurred during registration. Please try again."},
            status_code=500
        )

    background_tasks.add_task(
        EmailService.send_verification_email,
        user.email,
        user.username,
        user.verification_token
    )

    return templates.TemplateResponse(
        "auth/register_success.html",
        {"request": request, "email": email}
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
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    user = AuthService.authenticate_user(db, email, password)
    if not user:
        return templates.TemplateResponse(
            "auth/login.html",
            {"request": request, "error": "Invalid email or password"},
            status_code=400
        )

    access_token = AuthService.create_access_token(data={"sub": str(user.id)})
    redirect = RedirectResponse(url="/dashboard", status_code=302)
    set_auth_cookie(redirect, access_token, request)
    return redirect


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
async def reset_password(
    request: Request,
    token: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db)
):
    if len(password) < 8:
        return templates.TemplateResponse(
            "auth/reset_password.html",
            {"request": request, "token": token, "error": "Password must be at least 8 characters"},
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
