import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import settings

log = logging.getLogger(__name__)


async def send_email(to: str, subject: str, body: str) -> None:
    """Send a plain-text email. Without SMTP configured (local dev, CI) the
    message is logged instead, so verification codes are still retrievable."""
    if not settings.SMTP_HOST:
        log.info("[email disabled] to=%s subject=%r\n%s", to, subject, body)
        return
    msg = EmailMessage()
    msg["From"] = settings.SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)
    try:
        await aiosmtplib.send(
            msg,
            hostname=settings.SMTP_HOST,
            port=settings.SMTP_PORT,
            username=settings.SMTP_USER or None,
            password=settings.SMTP_PASS or None,
            start_tls=True,
            timeout=10,
        )
    except (aiosmtplib.SMTPException, OSError):
        log.exception("failed to send email to %s", to)


async def send_verification_code(to: str, code: str) -> None:
    await send_email(
        to,
        "Your Pinstagram verification code",
        f"Your verification code is {code}. It expires in 15 minutes.",
    )
