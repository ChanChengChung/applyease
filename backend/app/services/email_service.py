from __future__ import annotations

import json
import os
import smtplib
import ssl
import uuid
from email.message import EmailMessage
from pathlib import Path

from app.config import settings


class MailDeliveryError(RuntimeError):
    pass


def _message(recipient: str, subject: str, text: str) -> EmailMessage:
    message = EmailMessage()

    message["From"] = settings.mail_from

    message["To"] = recipient

    message["Subject"] = subject

    message.set_content(text)

    return message


def _write_file(recipient: str, subject: str, text: str) -> None:
    directory = Path(settings.mail_file_dir)

    directory.mkdir(parents=True, exist_ok=True, mode=0o700)

    try:
        os.chmod(directory, 0o700)

    except OSError:
        pass
    destination = directory / f"{uuid.uuid4()}.json"

    destination.write_text(
        json.dumps({"to": recipient, "subject": subject, "text": text}, ensure_ascii=False),
        encoding="utf-8",
    )

    try:
        os.chmod(destination, 0o600)

    except OSError:
        pass


def deliver_account_email(recipient: str, subject: str, text: str) -> None:

    if settings.mail_delivery_mode == "disabled":

        return

    if settings.mail_delivery_mode == "file":

        try:
            _write_file(recipient, subject, text)

            return

        except OSError as exc:

            raise MailDeliveryError("Local mail delivery failed") from exc

    try:

        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=15) as client:

            if settings.smtp_starttls:
                client.starttls(context=ssl.create_default_context())

            if settings.smtp_username:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(_message(recipient, subject, text))

    except (OSError, smtplib.SMTPException) as exc:

        raise MailDeliveryError("SMTP delivery failed") from exc
