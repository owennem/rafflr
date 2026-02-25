import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """Send an email using SMTP."""
        if not settings.smtp_user or not settings.smtp_password:
            logger.warning("SMTP not configured, skipping email send")
            return False

        message = MIMEMultipart("alternative")
        message["From"] = settings.smtp_user
        message["To"] = to_email
        message["Subject"] = subject

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        try:
            await aiosmtplib.send(
                message,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                start_tls=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    @staticmethod
    async def send_verification_email(to_email: str, username: str, verification_token: str) -> bool:
        """Send email verification link."""
        verification_url = f"{settings.frontend_url}/auth/verify?token={verification_token}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Welcome to Rafflr!</h1>
            <p>Hi {username},</p>
            <p>Thanks for signing up! Please verify your email address by clicking the button below:</p>
            <p style="margin: 30px 0;">
                <a href="{verification_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    Verify Email
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="color: #666;">{verification_url}</p>
            <p>If you didn't sign up for Rafflr, you can ignore this email.</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, "Verify your Rafflr account", html_content)

    @staticmethod
    async def send_password_reset_email(to_email: str, reset_token: str) -> bool:
        """Send password reset link."""
        reset_url = f"{settings.frontend_url}/auth/reset-password?token={reset_token}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Password Reset</h1>
            <p>You requested a password reset for your Rafflr account.</p>
            <p>Click the button below to reset your password:</p>
            <p style="margin: 30px 0;">
                <a href="{reset_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    Reset Password
                </a>
            </p>
            <p>Or copy and paste this link into your browser:</p>
            <p style="color: #666;">{reset_url}</p>
            <p>This link will expire in 1 hour.</p>
            <p>If you didn't request this reset, you can ignore this email.</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, "Reset your Rafflr password", html_content)

    @staticmethod
    async def send_winner_notification(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int
    ) -> bool:
        """Notify user they won a raffle."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Congratulations, You Won!</h1>
            <p>Hi {username},</p>
            <p>Great news! You've won the raffle for:</p>
            <h2 style="color: #1F2937; margin: 20px 0;">{listing_title}</h2>
            <p>The seller will be in touch with you shortly to arrange delivery.</p>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    View Listing
                </a>
            </p>
            <p>Thank you for using Rafflr!</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"You won: {listing_title}!", html_content)

    @staticmethod
    async def send_purchase_confirmation(
        to_email: str,
        username: str,
        listing_title: str,
        quantity: int,
        total_amount: float
    ) -> bool:
        """Send purchase confirmation email."""
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Purchase Confirmed!</h1>
            <p>Hi {username},</p>
            <p>Your ticket purchase has been confirmed:</p>
            <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 5px 0;"><strong>Raffle:</strong> {listing_title}</p>
                <p style="margin: 5px 0;"><strong>Tickets:</strong> {quantity}</p>
                <p style="margin: 5px 0;"><strong>Total:</strong> ${total_amount:.2f}</p>
            </div>
            <p>Good luck in the draw!</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Tickets purchased for {listing_title}", html_content)

    @staticmethod
    async def send_seller_draw_notification(
        to_email: str,
        username: str,
        listing_title: str,
        winner_username: str
    ) -> bool:
        """Notify seller that their raffle has been drawn."""
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Your Raffle Has Been Drawn!</h1>
            <p>Hi {username},</p>
            <p>The raffle for your listing has been drawn:</p>
            <h2 style="color: #1F2937; margin: 20px 0;">{listing_title}</h2>
            <p>The winner is: <strong>{winner_username}</strong></p>
            <p>Please contact the winner to arrange delivery of the item.</p>
            <p>Thank you for using Rafflr!</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Winner selected for {listing_title}", html_content)
