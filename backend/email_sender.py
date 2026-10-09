"""SMTP email delivery for shared reports (Tear Sheet → email with PDF attached).

Credentials come from the environment (backend/.env), never the database:

    SMTP_HOST       required, e.g. smtp.gmail.com
    SMTP_PORT       default 587 (STARTTLS); 465 uses implicit TLS
    SMTP_USER       login name (usually the full address); optional for open relays
    SMTP_PASSWORD   for Gmail/Outlook use an app password, not the account password
    SMTP_FROM       sender, e.g. "StockMonitor <you@gmail.com>"; defaults to SMTP_USER
    SMTP_SECURITY   starttls | ssl | none (default: ssl on port 465, else starttls)
    EMAIL_ALLOWED_RECIPIENTS  optional comma-separated addresses and/or @domains; when set,
                    mail can only be sent to those (recommended if the app is ever deployed
                    somewhere other people can reach it — the API itself has no login)

Mirrors digest_channels.py: `configured()` + `send()` returning {"ok", "error"}, with the
password redacted from every error string.
"""
import logging
import os
import re
import smtplib
import socket
import ssl
import time
from email.message import EmailMessage

logger = logging.getLogger(__name__)

MAX_RECIPIENTS = 10
MAX_SENDS_PER_HOUR = 20

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+'\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_SPLIT_RE = re.compile(r"[,;\s]+")
_send_times: list[float] = []


def parse_recipients(raw) -> tuple[list[str], list[str]]:
    """Split a comma/semicolon/space/newline separated string (or list) into (valid, invalid)
    addresses, de-duplicated case-insensitively with order preserved."""
    parts = raw if isinstance(raw, (list, tuple)) else _SPLIT_RE.split(str(raw or ""))
    valid, invalid, seen = [], [], set()
    for part in parts:
        addr = str(part).strip()
        if not addr:
            continue
        if not _EMAIL_RE.match(addr) or len(addr) > 254:
            invalid.append(addr)
        elif addr.lower() not in seen:
            seen.add(addr.lower())
            valid.append(addr)
    return valid, invalid


def disallowed_recipients(addresses: list[str]) -> list[str]:
    """Addresses outside EMAIL_ALLOWED_RECIPIENTS (empty list when no allowlist is configured)."""
    allow = [a.strip().lower() for a in os.environ.get("EMAIL_ALLOWED_RECIPIENTS", "").split(",") if a.strip()]
    if not allow:
        return []

    def ok(addr: str) -> bool:
        a = addr.lower()
        return any(a == rule or (rule.startswith("@") and a.endswith(rule)) for rule in allow)
    return [a for a in addresses if not ok(a)]


def rate_limited(now: float | None = None) -> bool:
    """True when MAX_SENDS_PER_HOUR messages have already gone out in the last hour."""
    now = time.time() if now is None else now
    _send_times[:] = [t for t in _send_times if now - t < 3600]
    return len(_send_times) >= MAX_SENDS_PER_HOUR


def _clean_header(value: str) -> str:
    return re.sub(r"[\r\n]+", " ", str(value)).strip()


class SmtpEmail:
    name = "smtp"

    @staticmethod
    def _cfg() -> dict:
        port_raw = os.environ.get("SMTP_PORT", "").strip()
        port = int(port_raw) if port_raw.isdigit() else 587
        user = os.environ.get("SMTP_USER", "").strip()
        security = os.environ.get("SMTP_SECURITY", "").strip().lower() or ("ssl" if port == 465 else "starttls")
        return {
            "host": os.environ.get("SMTP_HOST", "").strip(), "port": port, "user": user,
            "password": os.environ.get("SMTP_PASSWORD", ""),
            "sender": os.environ.get("SMTP_FROM", "").strip() or user, "security": security,
        }

    def configured(self) -> bool:
        c = self._cfg()
        return bool(c["host"] and c["sender"])

    def send(self, to: list[str], subject: str, text: str, html: str | None = None,
             attachments: tuple = ()) -> dict:
        """attachments: ((filename, bytes, 'maintype/subtype'), ...)"""
        c = self._cfg()
        if not (c["host"] and c["sender"]):
            return {"ok": False, "error": "Email is not configured (set SMTP_HOST and SMTP_USER / SMTP_FROM in backend/.env)"}
        password = c["password"]

        def redact(msg: str) -> str:
            return str(msg).replace(password, "***") if password else str(msg)

        try:
            msg = EmailMessage()
            msg["From"] = _clean_header(c["sender"])
            msg["To"] = ", ".join(to)
            msg["Subject"] = _clean_header(subject)
            msg.set_content(text)
            if html:
                msg.add_alternative(html, subtype="html")
            for filename, data, mime in attachments:
                maintype, _, subtype = mime.partition("/")
                msg.add_attachment(data, maintype=maintype, subtype=subtype, filename=_clean_header(filename))

            if c["security"] == "ssl":
                server = smtplib.SMTP_SSL(c["host"], c["port"], timeout=20, context=ssl.create_default_context())
            else:
                server = smtplib.SMTP(c["host"], c["port"], timeout=20)
            with server:
                if c["security"] == "starttls":
                    server.starttls(context=ssl.create_default_context())
                if c["user"]:
                    server.login(c["user"], password)
                server.send_message(msg, to_addrs=list(to))
        except smtplib.SMTPAuthenticationError:
            err = "SMTP login failed - check SMTP_USER / SMTP_PASSWORD (Gmail and Outlook need an app password, not your account password)"
        except smtplib.SMTPRecipientsRefused:
            err = "The mail server rejected the recipient address(es)"
        except (smtplib.SMTPConnectError, socket.gaierror, ConnectionError, TimeoutError, socket.timeout):
            err = f"Could not connect to {c['host']}:{c['port']} - check SMTP_HOST / SMTP_PORT / SMTP_SECURITY"
        except Exception as exc:
            err = redact(f"{type(exc).__name__}: {exc}")[:300]
        else:
            _send_times.append(time.time())
            return {"ok": True, "error": None}
        logger.warning("Email send failed: %s", err)
        return {"ok": False, "error": err}


EMAIL = SmtpEmail()
