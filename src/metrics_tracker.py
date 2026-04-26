from datetime import datetime
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
METRICS_PATH = DATA_DIR / "metrics.csv"

METRIC_COLUMNS = [
    "id",
    "date",
    "task_id",
    "topic_id",
    "platform",
    "content_type",
    "impressions",
    "reactions",
    "comments",
    "shares",
    "clicks",
    "messages",
    "leads",
    "listed_items",
    "notes",
]

NUMERIC_COLUMNS = [
    "impressions",
    "reactions",
    "comments",
    "shares",
    "clicks",
    "messages",
    "leads",
    "listed_items",
]


class MetricsTrackerError(Exception):
    """Raised when metrics data cannot be loaded or updated."""


def ensure_metrics_file() -> None:
    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not METRICS_PATH.exists() or METRICS_PATH.stat().st_size == 0:
        pd.DataFrame(columns=METRIC_COLUMNS).to_csv(
            METRICS_PATH, index=False, encoding="utf-8"
        )


def load_metrics() -> pd.DataFrame:
    ensure_metrics_file()

    try:
        df = pd.read_csv(METRICS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=METRIC_COLUMNS)

    missing_columns = [column for column in METRIC_COLUMNS if column not in df.columns]
    if missing_columns:
        raise MetricsTrackerError(
            "metrics.csv is missing required columns: " + ", ".join(missing_columns)
        )

    df = df[METRIC_COLUMNS].fillna("")
    for column in NUMERIC_COLUMNS:
        df[column] = pd.to_numeric(df[column], errors="coerce").fillna(0).astype(int)
    return df


def save_metrics(df: pd.DataFrame) -> None:
    missing_columns = [column for column in METRIC_COLUMNS if column not in df.columns]
    if missing_columns:
        raise MetricsTrackerError(
            "metrics data is missing required columns: " + ", ".join(missing_columns)
        )

    METRICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[METRIC_COLUMNS].to_csv(METRICS_PATH, index=False, encoding="utf-8")


def validate_date(date: str) -> None:
    try:
        datetime.strptime(str(date), "%Y-%m-%d")
    except ValueError as error:
        raise MetricsTrackerError("date must use YYYY-MM-DD format") from error


def next_metric_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def normalize_number(value) -> int:
    if value == "":
        return 0
    try:
        return int(value)
    except (TypeError, ValueError) as error:
        raise MetricsTrackerError(f"numeric metric value is invalid: {value}") from error


def add_metric(
    date,
    task_id="",
    topic_id="",
    platform="",
    content_type="",
    impressions=0,
    reactions=0,
    comments=0,
    shares=0,
    clicks=0,
    messages=0,
    leads=0,
    listed_items=0,
    notes="",
) -> int:
    date_text = str(date)
    validate_date(date_text)
    df = load_metrics()
    metric_id = next_metric_id(df)
    new_metric = {
        "id": metric_id,
        "date": date_text,
        "task_id": task_id,
        "topic_id": topic_id,
        "platform": platform,
        "content_type": content_type,
        "impressions": normalize_number(impressions),
        "reactions": normalize_number(reactions),
        "comments": normalize_number(comments),
        "shares": normalize_number(shares),
        "clicks": normalize_number(clicks),
        "messages": normalize_number(messages),
        "leads": normalize_number(leads),
        "listed_items": normalize_number(listed_items),
        "notes": notes,
    }

    df = pd.concat([df, pd.DataFrame([new_metric])], ignore_index=True)
    save_metrics(df)
    return metric_id


def update_metric(metric_id, **kwargs) -> None:
    try:
        metric_id_value = int(metric_id)
    except (TypeError, ValueError) as error:
        raise MetricsTrackerError("metric_id must be an integer") from error

    unknown_columns = [key for key in kwargs if key not in METRIC_COLUMNS]
    if unknown_columns:
        raise MetricsTrackerError("unknown metric columns: " + ", ".join(unknown_columns))

    df = load_metrics()
    metric_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = metric_ids == metric_id_value
    if not matches.any():
        raise MetricsTrackerError(f"Metric item not found: {metric_id_value}")

    for key, value in kwargs.items():
        if key == "id":
            raise MetricsTrackerError("id cannot be updated")
        if key == "date":
            validate_date(str(value))
        if key in NUMERIC_COLUMNS:
            value = normalize_number(value)
        df.loc[matches, key] = value

    save_metrics(df)


def get_metrics_by_topic(topic_id) -> pd.DataFrame:
    df = load_metrics()
    return df[df["topic_id"].astype(str) == str(topic_id)].copy()


def get_metrics_by_platform(platform) -> pd.DataFrame:
    df = load_metrics()
    return df[df["platform"] == platform].copy()


def top_value_by_leads(df: pd.DataFrame, column: str):
    if df.empty or column not in df.columns:
        return ""

    grouped = df.groupby(column, dropna=False)["leads"].sum()
    if grouped.empty:
        return ""

    grouped = grouped[grouped > 0]
    if grouped.empty:
        return ""

    return grouped.sort_values(ascending=False).index[0]


def summarize_metrics() -> dict:
    df = load_metrics()
    return {
        "total_impressions": int(df["impressions"].sum()) if not df.empty else 0,
        "total_reactions": int(df["reactions"].sum()) if not df.empty else 0,
        "total_comments": int(df["comments"].sum()) if not df.empty else 0,
        "total_clicks": int(df["clicks"].sum()) if not df.empty else 0,
        "total_messages": int(df["messages"].sum()) if not df.empty else 0,
        "total_leads": int(df["leads"].sum()) if not df.empty else 0,
        "total_listed_items": int(df["listed_items"].sum()) if not df.empty else 0,
        "top_platform_by_leads": top_value_by_leads(df, "platform"),
        "top_topic_by_leads": top_value_by_leads(df, "topic_id"),
    }
