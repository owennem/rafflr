import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
import logging
import asyncio
from contextlib import asynccontextmanager

from app.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)


class SMTPConnectionPool:
    """
    Connection pool for SMTP connections.
    Reuses connections to avoid overhead of creating new connections for each email.
    """

    def __init__(self, max_connections: int = 5, connection_timeout: int = 30):
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self._pool: asyncio.Queue = asyncio.Queue(maxsize=max_connections)
        self._created_connections = 0
        self._lock = asyncio.Lock()

    async def _create_connection(self) -> aiosmtplib.SMTP:
        """Create a new SMTP connection."""
        smtp = aiosmtplib.SMTP(
            hostname=settings.smtp_host,
            port=settings.smtp_port,
            timeout=self.connection_timeout
        )
        await smtp.connect()
        await smtp.starttls()
        await smtp.login(settings.smtp_user, settings.smtp_password)
        return smtp

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool or create a new one."""
        connection = None

        # Try to get an existing connection from the pool
        try:
            connection = self._pool.get_nowait()
            # Test if connection is still valid
            try:
                await connection.noop()
            except Exception:
                # Connection is stale, close it and create new one
                try:
                    await connection.quit()
                except Exception:
                    pass
                connection = await self._create_connection()
        except asyncio.QueueEmpty:
            # No available connections, create new one if under limit
            async with self._lock:
                if self._created_connections < self.max_connections:
                    connection = await self._create_connection()
                    self._created_connections += 1

            # If at limit, wait for a connection to be returned
            if connection is None:
                connection = await asyncio.wait_for(
                    self._pool.get(),
                    timeout=self.connection_timeout
                )

        try:
            yield connection
        finally:
            # Return connection to pool
            if connection:
                try:
                    self._pool.put_nowait(connection)
                except asyncio.QueueFull:
                    # Pool is full, close the connection
                    try:
                        await connection.quit()
                    except Exception:
                        pass
                    async with self._lock:
                        self._created_connections -= 1

    async def close_all(self):
        """Close all connections in the pool."""
        while not self._pool.empty():
            try:
                connection = self._pool.get_nowait()
                await connection.quit()
            except Exception:
                pass
        async with self._lock:
            self._created_connections = 0


# Global connection pool (lazy initialized)
_smtp_pool: Optional[SMTPConnectionPool] = None


def get_smtp_pool() -> SMTPConnectionPool:
    """Get or create the SMTP connection pool."""
    global _smtp_pool
    if _smtp_pool is None:
        _smtp_pool = SMTPConnectionPool()
    return _smtp_pool


class EmailService:
    @staticmethod
    async def send_email(to_email: str, subject: str, html_content: str) -> bool:
        """Send an email using SMTP with connection pooling."""
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
            pool = get_smtp_pool()
            async with pool.get_connection() as smtp:
                await smtp.send_message(message)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            # Fallback to direct send if pool fails
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
            except Exception as fallback_error:
                logger.error(f"Fallback email send also failed: {fallback_error}")
                return False

    @staticmethod
    async def send_2fa_code(to_email: str, username: str, code: str, action: str = "login") -> bool:
        """Send 2FA verification code for login or registration."""
        action_text = "log in to" if action == "login" else "complete registration for"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Your Verification Code</h1>
            <p>Hi {username},</p>
            <p>Use this code to {action_text} your Rafflr account:</p>
            <div style="background-color: #F3F4F6; padding: 30px; border-radius: 12px; margin: 30px 0; text-align: center;">
                <span style="font-size: 36px; font-weight: bold; letter-spacing: 8px; color: #1F2937;">{code}</span>
            </div>
            <p style="color: #666; font-size: 14px;">This code will expire in 10 minutes.</p>
            <p style="color: #666; font-size: 14px;">If you didn't request this code, please ignore this email or contact support if you have concerns.</p>
            <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 30px 0;">
            <p style="color: #9CA3AF; font-size: 12px;">For your security, never share this code with anyone.</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        subject = f"Your Rafflr verification code: {code}"
        return await EmailService.send_email(to_email, subject, html_content)

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

    @staticmethod
    async def send_raffle_ending_soon(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int,
        hours_remaining: int
    ) -> bool:
        """Notify user that a raffle they entered is ending soon."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #F59E0B;">Raffle Ending Soon!</h1>
            <p>Hi {username},</p>
            <p>A raffle you've entered is ending in <strong>{hours_remaining} hours</strong>:</p>
            <div style="background-color: #FEF3C7; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #F59E0B;">
                <h2 style="color: #1F2937; margin: 0;">{listing_title}</h2>
            </div>
            <p>Don't miss out! You can still buy more tickets to increase your chances of winning.</p>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    View Raffle
                </a>
            </p>
            <p>Good luck!</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Ending soon: {listing_title}", html_content)

    @staticmethod
    async def send_new_listing_notification(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int,
        ticket_price: float,
        seller_username: str
    ) -> bool:
        """Notify user about a new raffle listing."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">New Raffle Alert!</h1>
            <p>Hi {username},</p>
            <p>Check out this new raffle that just went live:</p>
            <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #1F2937; margin: 0 0 10px 0;">{listing_title}</h2>
                <p style="margin: 5px 0; color: #6B7280;">by {seller_username}</p>
                <p style="margin: 10px 0 0 0;">
                    <span style="color: #4F46E5; font-size: 24px; font-weight: bold;">${ticket_price:.2f}</span>
                    <span style="color: #6B7280;"> per ticket</span>
                </p>
            </div>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    Enter Now
                </a>
            </p>
            <p>Best,<br>The Rafflr Team</p>
            <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 30px 0;">
            <p style="color: #9CA3AF; font-size: 12px;">
                You're receiving this because you have new listing notifications enabled.
                <a href="{settings.frontend_url}/dashboard/profile" style="color: #6B7280;">Manage preferences</a>
            </p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"New raffle: {listing_title}", html_content)

    @staticmethod
    async def send_ticket_purchase_reminder(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int,
        tickets_remaining: int
    ) -> bool:
        """Remind user about a raffle that's almost sold out."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #EC4899;">Almost Sold Out!</h1>
            <p>Hi {username},</p>
            <p>A raffle you viewed is almost sold out:</p>
            <div style="background-color: #FDF2F8; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #EC4899;">
                <h2 style="color: #1F2937; margin: 0 0 10px 0;">{listing_title}</h2>
                <p style="margin: 0; color: #BE185D; font-weight: bold;">Only {tickets_remaining} tickets left!</p>
            </div>
            <p>Don't miss your chance to enter!</p>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #EC4899; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    Get Tickets Now
                </a>
            </p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Almost sold out: {listing_title}", html_content)

    @staticmethod
    async def send_listing_created(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int,
        ticket_price: float,
        max_tickets: int,
        deadline: str = None
    ) -> bool:
        """Notify seller that their raffle has been created successfully."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"
        deadline_text = f"<p style='margin: 5px 0;'><strong>Ends:</strong> {deadline}</p>" if deadline else ""

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">Your Raffle is Live!</h1>
            <p>Hi {username},</p>
            <p>Great news! Your raffle has been created and is now live:</p>
            <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #4F46E5;">
                <h2 style="color: #1F2937; margin: 0 0 15px 0;">{listing_title}</h2>
                <p style="margin: 5px 0;"><strong>Ticket Price:</strong> ${ticket_price:.2f}</p>
                <p style="margin: 5px 0;"><strong>Total Tickets:</strong> {max_tickets}</p>
                {deadline_text}
            </div>
            <p>Share your raffle to start selling tickets!</p>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    View Your Raffle
                </a>
            </p>
            <div style="background-color: #FEF3C7; padding: 15px; border-radius: 8px; margin: 20px 0;">
                <p style="margin: 0; color: #92400E; font-size: 14px;">
                    <strong>Tip:</strong> Share your raffle link on social media to reach more potential buyers!
                </p>
            </div>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Your raffle is live: {listing_title}", html_content)

    @staticmethod
    async def send_ticket_entry_confirmation(
        to_email: str,
        username: str,
        listing_title: str,
        listing_id: int,
        quantity: int,
        total_amount: float,
        tickets_sold: int,
        max_tickets: int,
        user_total_tickets: int
    ) -> bool:
        """Send detailed ticket purchase confirmation with odds information."""
        listing_url = f"{settings.frontend_url}/listings/{listing_id}"
        odds_percentage = (user_total_tickets / tickets_sold * 100) if tickets_sold > 0 else 0

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
            <h1 style="color: #4F46E5;">You're In the Draw!</h1>
            <p>Hi {username},</p>
            <p>Your ticket purchase has been confirmed. Good luck!</p>
            <div style="background-color: #F3F4F6; padding: 20px; border-radius: 8px; margin: 20px 0;">
                <h2 style="color: #1F2937; margin: 0 0 15px 0;">{listing_title}</h2>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: #6B7280;">Tickets Purchased:</span>
                    <strong>{quantity}</strong>
                </div>
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: #6B7280;">Amount Paid:</span>
                    <strong>${total_amount:.2f}</strong>
                </div>
                <hr style="border: none; border-top: 1px solid #E5E7EB; margin: 15px 0;">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span style="color: #6B7280;">Your Total Tickets:</span>
                    <strong style="color: #4F46E5;">{user_total_tickets}</strong>
                </div>
                <div style="display: flex; justify-content: space-between;">
                    <span style="color: #6B7280;">Current Winning Odds:</span>
                    <strong style="color: #10B981;">{odds_percentage:.1f}%</strong>
                </div>
            </div>
            <div style="background-color: #ECFDF5; padding: 15px; border-radius: 8px; margin: 20px 0; border-left: 4px solid #10B981;">
                <p style="margin: 0; color: #065F46; font-size: 14px;">
                    <strong>Progress:</strong> {tickets_sold} of {max_tickets} tickets sold
                </p>
            </div>
            <p style="margin: 30px 0;">
                <a href="{listing_url}"
                   style="background-color: #4F46E5; color: white; padding: 12px 24px;
                          text-decoration: none; border-radius: 6px;">
                    View Raffle
                </a>
            </p>
            <p style="color: #6B7280; font-size: 14px;">Want to increase your chances? You can buy more tickets anytime before the draw!</p>
            <p>Best,<br>The Rafflr Team</p>
        </body>
        </html>
        """

        return await EmailService.send_email(to_email, f"Entry confirmed: {listing_title}", html_content)
