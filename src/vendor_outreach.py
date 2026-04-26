from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
VENDORS_PATH = DATA_DIR / "vendors.csv"

VENDOR_COLUMNS = [
    "id",
    "company_name",
    "website",
    "email",
    "phone",
    "category",
    "source_url",
    "source_type",
    "contact_status",
    "last_contacted",
    "next_action",
    "notes",
]

ALLOWED_CONTACT_STATUSES = {
    "new",
    "email_drafted",
    "email_sent",
    "follow_up_needed",
    "replied",
    "interested",
    "not_interested",
    "opted_out",
    "listed",
}

ALLOWED_SOURCE_TYPES = {
    "website",
    "facebook_page",
    "facebook_group",
    "google_search",
    "manual",
}


class VendorOutreachError(Exception):
    """Raised when vendor outreach data cannot be loaded or updated."""


def ensure_vendors_file() -> None:
    VENDORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not VENDORS_PATH.exists() or VENDORS_PATH.stat().st_size == 0:
        pd.DataFrame(columns=VENDOR_COLUMNS).to_csv(
            VENDORS_PATH, index=False, encoding="utf-8"
        )


def load_vendors() -> pd.DataFrame:
    ensure_vendors_file()
    try:
        df = pd.read_csv(VENDORS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=VENDOR_COLUMNS)

    missing_columns = [column for column in VENDOR_COLUMNS if column not in df.columns]
    if missing_columns:
        raise VendorOutreachError(
            "vendors.csv is missing required columns: " + ", ".join(missing_columns)
        )

    return df[VENDOR_COLUMNS].fillna("")


def save_vendors(df: pd.DataFrame) -> None:
    missing_columns = [column for column in VENDOR_COLUMNS if column not in df.columns]
    if missing_columns:
        raise VendorOutreachError(
            "Vendor data is missing required columns: " + ", ".join(missing_columns)
        )

    VENDORS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[VENDOR_COLUMNS].to_csv(VENDORS_PATH, index=False, encoding="utf-8")


def validate_contact_status(contact_status: str) -> None:
    if contact_status not in ALLOWED_CONTACT_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_CONTACT_STATUSES))
        raise VendorOutreachError(f"Invalid contact_status: {contact_status}. Allowed: {allowed}")


def validate_source_type(source_type: str) -> None:
    if source_type not in ALLOWED_SOURCE_TYPES:
        allowed = ", ".join(sorted(ALLOWED_SOURCE_TYPES))
        raise VendorOutreachError(f"Invalid source_type: {source_type}. Allowed: {allowed}")


def next_vendor_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def add_vendor(
    company_name,
    website="",
    email="",
    phone="",
    category="",
    source_url="",
    source_type="manual",
    contact_status="new",
    last_contacted="",
    next_action="",
    notes="",
) -> int:
    validate_source_type(source_type)
    validate_contact_status(contact_status)

    df = load_vendors()
    vendor_id = next_vendor_id(df)
    new_vendor = {
        "id": vendor_id,
        "company_name": company_name,
        "website": website,
        "email": email,
        "phone": phone,
        "category": category,
        "source_url": source_url,
        "source_type": source_type,
        "contact_status": contact_status,
        "last_contacted": last_contacted,
        "next_action": next_action,
        "notes": notes,
    }

    df = pd.concat([df, pd.DataFrame([new_vendor])], ignore_index=True)
    save_vendors(df)
    return vendor_id


def update_vendor_status(
    vendor_id,
    contact_status,
    last_contacted=None,
    next_action=None,
    notes=None,
) -> None:
    validate_contact_status(contact_status)
    try:
        vendor_id_value = int(vendor_id)
    except (TypeError, ValueError) as error:
        raise VendorOutreachError("vendor_id must be an integer.") from error

    df = load_vendors()
    vendor_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = vendor_ids == vendor_id_value
    if not matches.any():
        raise VendorOutreachError(f"Vendor id not found: {vendor_id_value}")

    df.loc[matches, "contact_status"] = contact_status
    if last_contacted is not None:
        df.loc[matches, "last_contacted"] = last_contacted
    if next_action is not None:
        df.loc[matches, "next_action"] = next_action
    if notes is not None:
        df.loc[matches, "notes"] = notes

    save_vendors(df)


def get_vendors_by_status(contact_status) -> pd.DataFrame:
    validate_contact_status(contact_status)
    df = load_vendors()
    return df[df["contact_status"] == contact_status].copy()


def get_vendor(vendor_id: int) -> dict:
    df = load_vendors()
    vendor_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = df[vendor_ids == int(vendor_id)]
    if matches.empty:
        raise VendorOutreachError(f"Vendor id not found: {vendor_id}")

    return matches.iloc[0].to_dict()


def generate_vendor_email(vendor_id, template_type="initial") -> dict:
    if template_type not in {"initial", "follow_up"}:
        raise VendorOutreachError("template_type must be initial or follow_up.")

    vendor = get_vendor(int(vendor_id))
    company_name = vendor["company_name"] or "貴公司"
    category = vendor["category"] or "二手儀器與檢測設備"

    if template_type == "initial":
        subject = f"ZeroGrav 二手儀器設備曝光合作邀請 - {company_name}"
        body = f"""您好，{company_name} 團隊您好：

我們是 ZeroGrav，正在建立一個二手儀器設備的集中式曝光平台，協助買家更容易找到量測儀器、檢測設備與相關二手設備供應資訊。

我們留意到貴公司公開資訊中有販售或提供「{category}」相關設備，因此想邀請貴公司評估是否將部分設備同步刊登到 ZeroGrav。刊登可免費開始，不會取代貴公司原有官網、Facebook 或既有銷售管道，而是多一個讓潛在買家看見設備的曝光入口。

若您願意，我們可以先協助整理並刊登 3-5 筆設備資訊。買家後續可依照貴公司指定方式聯絡，例如電話、Email、LINE 或官網表單；ZeroGrav 不會承諾成交，也不會誇大流量，只希望用低成本方式協助設備多一個被搜尋與詢問的機會。

若方便的話，歡迎回覆可刊登的設備資料或適合聯繫的窗口，我們會再協助整理下一步。

若不方便收到後續聯繫，回覆「不需聯繫」即可，我們會停止後續通知。
"""
    else:
        subject = f"ZeroGrav 免費設備刊登合作追蹤 - {company_name}"
        body = f"""您好，{company_name} 團隊您好：

先前曾與貴公司聯繫，想簡短追蹤是否有機會協助貴公司將二手儀器、量測儀器或檢測設備刊登到 ZeroGrav。

ZeroGrav 的定位是二手儀器設備集中式曝光平台，可作為貴公司原官網與既有社群管道以外的補充曝光入口。刊登可免費開始，也不會取代原公司官網或既有銷售流程；買家仍可依照貴公司指定方式聯絡。

如果您願意先小量測試，我們可以協助刊登 3-5 筆設備資訊，再依實際詢問狀況評估是否持續。ZeroGrav 不承諾成交，也不誇大流量，重點是用低壓、可控的方式增加設備被看見的機會。

若目前有適合刊登的設備，歡迎回覆設備清單或聯絡窗口，我們再協助整理。

若不方便收到後續聯繫，回覆「不需聯繫」即可，我們會停止後續通知。
"""

    return {"subject": subject, "body": body}
