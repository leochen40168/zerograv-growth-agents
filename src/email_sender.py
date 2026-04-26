import os
import smtplib
from datetime import date
from email.message import EmailMessage
from email.utils import formataddr
from pathlib import Path

import pandas as pd

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False

import vendor_outreach


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
EMAIL_OUTREACH_LOG_PATH = DATA_DIR / "email_outreach_log.csv"

EMAIL_LOG_COLUMNS = [
    "id",
    "date",
    "vendor_id",
    "email",
    "template_type",
    "subject",
    "status",
    "error_message",
]

ALLOWED_EMAIL_STATUSES = {"drafted", "sent", "failed", "skipped"}


class EmailSenderError(Exception):
    """Raised when vendor email outreach cannot send safely."""


def ensure_email_log_file() -> None:
    EMAIL_OUTREACH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not EMAIL_OUTREACH_LOG_PATH.exists() or EMAIL_OUTREACH_LOG_PATH.stat().st_size == 0:
        pd.DataFrame(columns=EMAIL_LOG_COLUMNS).to_csv(
            EMAIL_OUTREACH_LOG_PATH, index=False, encoding="utf-8"
        )


def load_email_log() -> pd.DataFrame:
    ensure_email_log_file()
    try:
        df = pd.read_csv(EMAIL_OUTREACH_LOG_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=EMAIL_LOG_COLUMNS)

    missing_columns = [column for column in EMAIL_LOG_COLUMNS if column not in df.columns]
    if missing_columns:
        raise EmailSenderError(
            "email_outreach_log.csv is missing required columns: " + ", ".join(missing_columns)
        )

    return df[EMAIL_LOG_COLUMNS].fillna("")


def save_email_log(df: pd.DataFrame) -> None:
    missing_columns = [column for column in EMAIL_LOG_COLUMNS if column not in df.columns]
    if missing_columns:
        raise EmailSenderError(
            "Email log data is missing required columns: " + ", ".join(missing_columns)
        )

    EMAIL_OUTREACH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[EMAIL_LOG_COLUMNS].to_csv(EMAIL_OUTREACH_LOG_PATH, index=False, encoding="utf-8")


def next_log_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def append_email_log(
    vendor_id,
    email,
    template_type,
    subject,
    status,
    error_message="",
) -> int:
    if status not in ALLOWED_EMAIL_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_EMAIL_STATUSES))
        raise EmailSenderError(f"Invalid email status: {status}. Allowed: {allowed}")

    df = load_email_log()
    log_id = next_log_id(df)
    row = {
        "id": log_id,
        "date": date.today().isoformat(),
        "vendor_id": vendor_id,
        "email": email,
        "template_type": template_type,
        "subject": subject,
        "status": status,
        "error_message": error_message,
    }
    df = pd.concat([df, pd.DataFrame([row])], ignore_index=True)
    save_email_log(df)
    return log_id


def load_email_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    return {
        "smtp_host": os.getenv("EMAIL_SMTP_HOST", ""),
        "smtp_port": os.getenv("EMAIL_SMTP_PORT", "587"),
        "smtp_username": os.getenv("EMAIL_SMTP_USERNAME", ""),
        "smtp_password": os.getenv("EMAIL_SMTP_PASSWORD", ""),
        "from_name": os.getenv("EMAIL_FROM_NAME", "ZeroGrav"),
        "from_address": os.getenv("EMAIL_FROM_ADDRESS", ""),
        "daily_limit": os.getenv("EMAIL_DAILY_LIMIT", "20"),
        "send_enabled": os.getenv("EMAIL_SEND_ENABLED", "false"),
    }


def require_send_enabled(config: dict) -> None:
    if str(config.get("send_enabled", "")).lower() != "true":
        raise EmailSenderError("Email sending is disabled. Set EMAIL_SEND_ENABLED=true to send.")


def require_smtp_config(config: dict) -> None:
    required = [
        "smtp_host",
        "smtp_port",
        "smtp_username",
        "smtp_password",
        "from_address",
    ]
    missing = [key for key in required if not str(config.get(key, "")).strip()]
    if missing:
        raise EmailSenderError("Missing SMTP email settings: " + ", ".join(missing))

    try:
        int(config["smtp_port"])
    except (TypeError, ValueError) as error:
        raise EmailSenderError("EMAIL_SMTP_PORT must be an integer.") from error

    try:
        int(config["daily_limit"])
    except (TypeError, ValueError) as error:
        raise EmailSenderError("EMAIL_DAILY_LIMIT must be an integer.") from error


def count_sent_today() -> int:
    log = load_email_log()
    today = date.today().isoformat()
    return int(((log["date"].astype(str) == today) & (log["status"] == "sent")).sum())


def require_daily_limit(config: dict) -> None:
    daily_limit = int(config["daily_limit"])
    if count_sent_today() >= daily_limit:
        raise EmailSenderError(f"Daily email limit reached: {daily_limit}")


def send_email(to_email: str, subject: str, body: str) -> dict:
    config = load_email_config()
    require_send_enabled(config)
    require_smtp_config(config)
    require_daily_limit(config)

    if not str(to_email).strip():
        raise EmailSenderError("to_email is required.")

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((config["from_name"], config["from_address"]))
    message["To"] = to_email
    message.set_content(body)

    with smtplib.SMTP(config["smtp_host"], int(config["smtp_port"])) as smtp:
        smtp.starttls()
        smtp.login(config["smtp_username"], config["smtp_password"])
        smtp.send_message(message)

    return {"status": "sent", "email": to_email, "subject": subject}


def validate_vendor_can_send(vendor: dict) -> None:
    status = str(vendor.get("contact_status", ""))
    if status in {"opted_out", "not_interested", "email_sent", "listed"}:
        raise EmailSenderError(f"Vendor contact_status prevents sending: {status}")
    if not str(vendor.get("email", "")).strip():
        raise EmailSenderError("Vendor email is required before sending.")
    if not str(vendor.get("source_url", "")).strip():
        raise EmailSenderError("Vendor source_url is required before sending.")


def send_vendor_email(vendor_id: int, template_type="initial") -> dict:
    vendor = vendor_outreach.get_vendor(int(vendor_id))
    subject = ""
    try:
        validate_vendor_can_send(vendor)
        email = vendor_outreach.generate_vendor_email(vendor_id, template_type=template_type)
        subject = email["subject"]
        result = send_email(vendor["email"], email["subject"], email["body"])
    except Exception as error:
        if not isinstance(error, EmailSenderError):
            error = EmailSenderError(str(error))
        append_email_log(
            vendor_id,
            vendor.get("email", ""),
            template_type,
            subject,
            "failed",
            str(error),
        )
        raise error

    append_email_log(vendor_id, vendor["email"], template_type, subject, "sent")
    vendor_outreach.update_vendor_status(
        vendor_id,
        "email_sent",
        last_contacted=date.today().isoformat(),
    )
    return result
