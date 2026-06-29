# SPDX-License-Identifier: AGPL-3.0-or-later
"""
maild — Email Service
=====================
Local email integration via IMAP/SMTP.
Reads from your existing email account, sends via SMTP.
Credentials stored in ~/.clawos/config.yaml under the mail section.
"""
import logging
from dataclasses import dataclass, asdict

log = logging.getLogger("maild")


@dataclass
class EmailMessage:
    id: str
    sender: str
    subject: str
    body: str = ""
    date: str = ""
    read: bool = False
    starred: bool = False
    folder: str = "INBOX"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MailConfig:
    imap_host: str = ""
    imap_port: int = 993
    smtp_host: str = ""
    smtp_port: int = 587
    username: str = ""
    password: str = ""
    use_ssl: bool = True

    @classmethod
    def load(cls) -> "MailConfig":
        """Load mail config from ClawOS config."""
        try:
            from clawos_core.config import load
            cfg = load()
            mail = cfg.get("mail", {})
            return cls(
                imap_host=mail.get("imap_host", ""),
                imap_port=mail.get("imap_port", 993),
                smtp_host=mail.get("smtp_host", ""),
                smtp_port=mail.get("smtp_port", 587),
                username=mail.get("username", ""),
                password=mail.get("password", ""),
                use_ssl=mail.get("use_ssl", True),
            )
        except (ImportError, Exception):
            return cls()


def check_mail(config: MailConfig | None = None, folder: str = "INBOX", limit: int = 20) -> list[EmailMessage]:
    """Check email via IMAP."""
    cfg = config or MailConfig.load()
    if not cfg.imap_host or not cfg.username:
        return []

    try:
        import imaplib
        import email as email_lib
        from email.header import decode_header

        conn = imaplib.IMAP4_SSL(cfg.imap_host, cfg.imap_port) if cfg.use_ssl else imaplib.IMAP4(cfg.imap_host, cfg.imap_port)
        conn.login(cfg.username, cfg.password)
        conn.select(folder, readonly=True)

        _, msg_ids = conn.search(None, "ALL")
        messages = []
        for mid in msg_ids[0].split()[-limit:]:
            _, data = conn.fetch(mid, "(RFC822)")
            if not data or not data[0]:
                continue
            raw = data[0][1]
            msg = email_lib.message_from_bytes(raw)

            # Decode subject
            subject_parts = decode_header(msg.get("Subject", ""))
            subject = ""
            for part, enc in subject_parts:
                if isinstance(part, bytes):
                    subject += part.decode(enc or "utf-8", errors="replace")
                else:
                    subject += part

            # Decode sender
            from_parts = decode_header(msg.get("From", ""))
            sender = ""
            for part, enc in from_parts:
                if isinstance(part, bytes):
                    sender += part.decode(enc or "utf-8", errors="replace")
                else:
                    sender += part

            # Get body
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode("utf-8", errors="replace")
                        break
            else:
                body = msg.get_payload(decode=True).decode("utf-8", errors="replace") if msg.get_payload(decode=True) else ""

            messages.append(EmailMessage(
                id=mid.decode(),
                sender=sender.strip(),
                subject=subject.strip(),
                body=body[:5000],
                date=msg.get("Date", ""),
                read=False,
                folder=folder,
            ))

        conn.logout()
        return list(reversed(messages))

    except ImportError:
        log.warning("imaplib not available")
        return []
    except Exception as exc:
        log.error("IMAP check failed: %s", exc)
        return []


def send_mail(to: str, subject: str, body: str, config: MailConfig | None = None) -> bool:
    """Send email via SMTP."""
    cfg = config or MailConfig.load()
    if not cfg.smtp_host or not cfg.username:
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = cfg.username
        msg["To"] = to

        if cfg.use_ssl:
            conn = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)
            conn.starttls()
        else:
            conn = smtplib.SMTP(cfg.smtp_host, cfg.smtp_port)

        conn.login(cfg.username, cfg.password)
        conn.sendmail(cfg.username, [to], msg.as_string())
        conn.quit()
        return True

    except Exception as exc:
        log.error("SMTP send failed: %s", exc)
        return False