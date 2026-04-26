from datetime import date as date_type
from pathlib import Path

import pandas as pd

import task_manager


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
TOPICS_PATH = DATA_DIR / "topics.csv"

REQUIRED_TOPIC_COLUMNS = [
    "id",
    "topic",
    "category",
    "target_audience",
    "intent",
    "cta",
    "status",
]

DAILY_TASK_TEMPLATES = [
    ("Website", "ZeroGrav Blog", "SEO文章"),
    ("Facebook粉專", "ZeroGrav 二手儀器交易平台", "粉專貼文"),
    ("Facebook社團", "台灣二手儀器設備交流", "社團討論文"),
]


class DailyWorkflowError(Exception):
    """Raised when the daily growth workflow cannot complete."""


def load_topics() -> pd.DataFrame:
    if not TOPICS_PATH.exists():
        raise DailyWorkflowError(f"topics.csv 不存在：{TOPICS_PATH}")

    try:
        df = pd.read_csv(TOPICS_PATH)
    except pd.errors.EmptyDataError as error:
        raise DailyWorkflowError("topics.csv 是空檔，缺少必要欄位。") from error

    missing_columns = [
        column for column in REQUIRED_TOPIC_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise DailyWorkflowError(
            "topics.csv 缺少必要欄位：" + ", ".join(missing_columns)
        )

    return df[REQUIRED_TOPIC_COLUMNS].fillna("")


def save_topics(df: pd.DataFrame) -> None:
    missing_columns = [
        column for column in REQUIRED_TOPIC_COLUMNS if column not in df.columns
    ]
    if missing_columns:
        raise DailyWorkflowError("topic 資料缺少必要欄位：" + ", ".join(missing_columns))

    TOPICS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(TOPICS_PATH, index=False, encoding="utf-8")


def get_pending_topics(limit=3) -> pd.DataFrame:
    df = load_topics()
    pending = df[df["status"] == "pending"].copy()
    return pending.head(int(limit))


def task_exists(tasks: pd.DataFrame, date: str, topic_id: int, platform: str, post_type: str) -> bool:
    if tasks.empty:
        return False

    topic_ids = pd.to_numeric(tasks["topic_id"], errors="coerce")
    matches = (
        (tasks["date"].astype(str) == date)
        & (topic_ids == int(topic_id))
        & (tasks["platform"].astype(str) == platform)
        & (tasks["post_type"].astype(str) == post_type)
    )
    return bool(matches.any())


def create_daily_tasks(date: str = None, topic_limit: int = 3) -> list[int]:
    task_date = date or date_type.today().isoformat()
    pending_topics = get_pending_topics(topic_limit)
    created_task_ids = []

    for topic in pending_topics.itertuples(index=False):
        topic_id = int(topic.id)
        for platform, destination, post_type in DAILY_TASK_TEMPLATES:
            current_tasks = task_manager.load_tasks()
            if task_exists(current_tasks, task_date, topic_id, platform, post_type):
                continue

            task_id = task_manager.add_task(
                task_date,
                platform,
                destination,
                post_type,
                topic_id,
                status="pending",
            )
            created_task_ids.append(task_id)

    return created_task_ids


def mark_topics_as_in_progress(topic_ids: list[int]) -> None:
    df = load_topics()
    normalized_ids = [int(topic_id) for topic_id in topic_ids]
    existing_ids = set(pd.to_numeric(df["id"], errors="coerce").dropna().astype(int))
    missing_ids = [topic_id for topic_id in normalized_ids if topic_id not in existing_ids]

    if missing_ids:
        raise DailyWorkflowError(
            "找不到 topic id：" + ", ".join(str(topic_id) for topic_id in missing_ids)
        )

    id_values = pd.to_numeric(df["id"], errors="coerce")
    matches = id_values.isin(normalized_ids) & (df["status"] == "pending")
    df.loc[matches, "status"] = "in_progress"
    save_topics(df)
