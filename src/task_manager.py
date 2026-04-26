from datetime import date as date_type
from datetime import datetime
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
POSTING_TASKS_PATH = DATA_DIR / "posting_tasks.csv"

TASK_COLUMNS = [
    "id",
    "date",
    "platform",
    "destination",
    "post_type",
    "topic_id",
    "status",
    "result_notes",
]

ALLOWED_STATUSES = {"pending", "generated", "reviewed", "published", "skipped"}


class TaskManagerError(Exception):
    """Raised when posting task data cannot be loaded or updated."""


def ensure_tasks_file() -> None:
    POSTING_TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not POSTING_TASKS_PATH.exists() or POSTING_TASKS_PATH.stat().st_size == 0:
        pd.DataFrame(columns=TASK_COLUMNS).to_csv(
            POSTING_TASKS_PATH, index=False, encoding="utf-8"
        )


def load_tasks() -> pd.DataFrame:
    ensure_tasks_file()

    try:
        df = pd.read_csv(POSTING_TASKS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=TASK_COLUMNS)

    missing_columns = [column for column in TASK_COLUMNS if column not in df.columns]
    if missing_columns:
        raise TaskManagerError(
            "posting_tasks.csv 缺少必要欄位：" + ", ".join(missing_columns)
        )

    return df[TASK_COLUMNS].fillna("")


def save_tasks(df: pd.DataFrame) -> None:
    missing_columns = [column for column in TASK_COLUMNS if column not in df.columns]
    if missing_columns:
        raise TaskManagerError("任務資料缺少必要欄位：" + ", ".join(missing_columns))

    POSTING_TASKS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[TASK_COLUMNS].to_csv(POSTING_TASKS_PATH, index=False, encoding="utf-8")


def validate_status(status: str) -> None:
    if status not in ALLOWED_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_STATUSES))
        raise TaskManagerError(f"不合法 status：{status}。允許值：{allowed}")


def validate_date(date: str) -> None:
    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError as error:
        raise TaskManagerError("date 必須使用 YYYY-MM-DD 格式") from error


def next_task_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def add_task(
    date,
    platform,
    destination,
    post_type,
    topic_id,
    status="pending",
    result_notes="",
) -> int:
    date_text = str(date)
    validate_date(date_text)
    validate_status(status)

    try:
        topic_id_value = int(topic_id)
    except (TypeError, ValueError) as error:
        raise TaskManagerError("topic_id 必須是整數") from error

    df = load_tasks()
    task_id = next_task_id(df)
    new_task = {
        "id": task_id,
        "date": date_text,
        "platform": platform,
        "destination": destination,
        "post_type": post_type,
        "topic_id": topic_id_value,
        "status": status,
        "result_notes": result_notes,
    }

    df = pd.concat([df, pd.DataFrame([new_task])], ignore_index=True)
    save_tasks(df)
    return task_id


def update_task_status(task_id, status, result_notes=None) -> None:
    validate_status(status)

    try:
        task_id_value = int(task_id)
    except (TypeError, ValueError) as error:
        raise TaskManagerError("task_id 必須是整數") from error

    df = load_tasks()
    task_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = task_ids == task_id_value

    if not matches.any():
        raise TaskManagerError(f"找不到 task id：{task_id_value}")

    df.loc[matches, "status"] = status
    if result_notes is not None:
        df.loc[matches, "result_notes"] = result_notes

    save_tasks(df)


def get_today_tasks() -> pd.DataFrame:
    today = date_type.today().isoformat()
    df = load_tasks()
    return df[df["date"].astype(str) == today].copy()


def get_tasks_by_status(status) -> pd.DataFrame:
    validate_status(status)
    df = load_tasks()
    return df[df["status"] == status].copy()
