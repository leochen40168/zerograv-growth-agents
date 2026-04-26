from datetime import datetime
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
SELLER_LEADS_PATH = DATA_DIR / "seller_leads.csv"

LEAD_COLUMNS = [
    "id",
    "date",
    "name",
    "source",
    "equipment_type",
    "brand",
    "model",
    "location",
    "contact_method",
    "contact_value",
    "asking_price",
    "condition",
    "status",
    "next_action",
    "notes",
]

ALLOWED_LEAD_STATUSES = {
    "new",
    "contacted",
    "info_requested",
    "qualified",
    "listed",
    "closed",
    "lost",
}


class LeadTrackerError(Exception):
    """Raised when seller lead data cannot be loaded or updated."""


def ensure_leads_file() -> None:
    SELLER_LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not SELLER_LEADS_PATH.exists() or SELLER_LEADS_PATH.stat().st_size == 0:
        pd.DataFrame(columns=LEAD_COLUMNS).to_csv(
            SELLER_LEADS_PATH, index=False, encoding="utf-8"
        )


def load_leads() -> pd.DataFrame:
    ensure_leads_file()

    try:
        df = pd.read_csv(SELLER_LEADS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=LEAD_COLUMNS)

    missing_columns = [column for column in LEAD_COLUMNS if column not in df.columns]
    if missing_columns:
        raise LeadTrackerError(
            "seller_leads.csv 缺少必要欄位：" + ", ".join(missing_columns)
        )

    return df[LEAD_COLUMNS].fillna("")


def save_leads(df: pd.DataFrame) -> None:
    missing_columns = [column for column in LEAD_COLUMNS if column not in df.columns]
    if missing_columns:
        raise LeadTrackerError("Lead 資料缺少必要欄位：" + ", ".join(missing_columns))

    SELLER_LEADS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[LEAD_COLUMNS].to_csv(SELLER_LEADS_PATH, index=False, encoding="utf-8")


def validate_status(status: str) -> None:
    if status not in ALLOWED_LEAD_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_LEAD_STATUSES))
        raise LeadTrackerError(f"不合法 status：{status}。允許值：{allowed}")


def validate_date(date: str) -> None:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as error:
        raise LeadTrackerError("date 必須使用 YYYY-MM-DD 格式") from error


def next_lead_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def add_lead(
    date,
    name,
    source,
    equipment_type,
    brand="",
    model="",
    location="",
    contact_method="",
    contact_value="",
    asking_price="",
    condition="",
    status="new",
    next_action="",
    notes="",
) -> int:
    date_text = str(date)
    validate_date(date_text)
    validate_status(status)

    df = load_leads()
    lead_id = next_lead_id(df)
    new_lead = {
        "id": lead_id,
        "date": date_text,
        "name": name,
        "source": source,
        "equipment_type": equipment_type,
        "brand": brand,
        "model": model,
        "location": location,
        "contact_method": contact_method,
        "contact_value": contact_value,
        "asking_price": asking_price,
        "condition": condition,
        "status": status,
        "next_action": next_action,
        "notes": notes,
    }

    df = pd.concat([df, pd.DataFrame([new_lead])], ignore_index=True)
    save_leads(df)
    return lead_id


def update_lead_status(lead_id, status, next_action=None, notes=None) -> None:
    validate_status(status)

    try:
        lead_id_value = int(lead_id)
    except (TypeError, ValueError) as error:
        raise LeadTrackerError("lead_id 必須是整數") from error

    df = load_leads()
    lead_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = lead_ids == lead_id_value

    if not matches.any():
        raise LeadTrackerError(f"找不到 lead id：{lead_id_value}")

    df.loc[matches, "status"] = status
    if next_action is not None:
        df.loc[matches, "next_action"] = next_action
    if notes is not None:
        df.loc[matches, "notes"] = notes

    save_leads(df)


def get_leads_by_status(status) -> pd.DataFrame:
    validate_status(status)
    df = load_leads()
    return df[df["status"] == status].copy()


def get_new_leads() -> pd.DataFrame:
    return get_leads_by_status("new")


def get_leads_by_source(source) -> pd.DataFrame:
    df = load_leads()
    return df[df["source"] == source].copy()
