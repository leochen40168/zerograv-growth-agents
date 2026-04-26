from datetime import datetime
from pathlib import Path
import re

import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONTENT_REVIEWS_PATH = DATA_DIR / "content_reviews.csv"

REVIEW_COLUMNS = [
    "id",
    "draft_path",
    "topic_id",
    "content_type",
    "status",
    "reviewer",
    "review_notes",
    "created_at",
    "updated_at",
]

ALLOWED_REVIEW_STATUSES = {
    "draft",
    "needs_review",
    "approved",
    "needs_rewrite",
    "published",
    "archived",
}

KNOWN_CONTENT_TYPES = {
    "seo-article": "seo_article",
    "facebook-page-post": "facebook_page_post",
    "facebook-group-post": "facebook_group_post",
    "seller-reply": "seller_reply",
    "image-card-copy": "image_card_copy",
}


class ReviewQueueError(Exception):
    """Raised when content review queue operations cannot complete."""


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def now_text() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_reviews_file() -> None:
    CONTENT_REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CONTENT_REVIEWS_PATH.exists() or CONTENT_REVIEWS_PATH.stat().st_size == 0:
        pd.DataFrame(columns=REVIEW_COLUMNS).to_csv(
            CONTENT_REVIEWS_PATH, index=False, encoding="utf-8"
        )


def load_reviews() -> pd.DataFrame:
    ensure_reviews_file()

    try:
        df = pd.read_csv(CONTENT_REVIEWS_PATH)
    except pd.errors.EmptyDataError:
        df = pd.DataFrame(columns=REVIEW_COLUMNS)

    missing_columns = [column for column in REVIEW_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ReviewQueueError(
            "content_reviews.csv is missing required columns: "
            + ", ".join(missing_columns)
        )

    return df[REVIEW_COLUMNS].fillna("")


def save_reviews(df: pd.DataFrame) -> None:
    missing_columns = [column for column in REVIEW_COLUMNS if column not in df.columns]
    if missing_columns:
        raise ReviewQueueError(
            "review data is missing required columns: " + ", ".join(missing_columns)
        )

    CONTENT_REVIEWS_PATH.parent.mkdir(parents=True, exist_ok=True)
    df[REVIEW_COLUMNS].to_csv(CONTENT_REVIEWS_PATH, index=False, encoding="utf-8")


def validate_status(status: str) -> None:
    if status not in ALLOWED_REVIEW_STATUSES:
        allowed = ", ".join(sorted(ALLOWED_REVIEW_STATUSES))
        raise ReviewQueueError(f"Invalid review status: {status}. Allowed: {allowed}")


def next_review_id(df: pd.DataFrame) -> int:
    if df.empty:
        return 1

    ids = pd.to_numeric(df["id"], errors="coerce").dropna()
    if ids.empty:
        return 1

    return int(ids.max()) + 1


def infer_draft_metadata(draft_path: Path) -> dict:
    match = re.match(r"draft-topic-(\d+)-(.+)\.md$", draft_path.name)
    if not match:
        raise ReviewQueueError(f"Cannot infer topic/content type from: {draft_path.name}")

    topic_id = int(match.group(1))
    content_slug = match.group(2)
    content_type = KNOWN_CONTENT_TYPES.get(content_slug, content_slug.replace("-", "_"))
    return {"topic_id": topic_id, "content_type": content_type}


def scan_drafts(drafts_dir="outputs/drafts") -> list[int]:
    drafts_path = resolve_path(drafts_dir)
    if not drafts_path.exists():
        return []

    df = load_reviews()
    existing_paths = set(df["draft_path"].astype(str))
    created_ids = []

    for draft_file in sorted(drafts_path.glob("*.md")):
        draft_path = str(draft_file)
        if draft_path in existing_paths:
            continue

        metadata = infer_draft_metadata(draft_file)
        review_id = next_review_id(df)
        timestamp = now_text()
        new_review = {
            "id": review_id,
            "draft_path": draft_path,
            "topic_id": metadata["topic_id"],
            "content_type": metadata["content_type"],
            "status": "needs_review",
            "reviewer": "",
            "review_notes": "",
            "created_at": timestamp,
            "updated_at": timestamp,
        }
        df = pd.concat([df, pd.DataFrame([new_review])], ignore_index=True)
        existing_paths.add(draft_path)
        created_ids.append(review_id)

    save_reviews(df)
    return created_ids


def update_review_status(review_id, status, reviewer="", review_notes="") -> None:
    validate_status(status)

    try:
        review_id_value = int(review_id)
    except (TypeError, ValueError) as error:
        raise ReviewQueueError("review_id must be an integer") from error

    df = load_reviews()
    review_ids = pd.to_numeric(df["id"], errors="coerce")
    matches = review_ids == review_id_value
    if not matches.any():
        raise ReviewQueueError(f"Review item not found: {review_id_value}")

    df.loc[matches, "status"] = status
    df.loc[matches, "reviewer"] = reviewer
    df.loc[matches, "review_notes"] = review_notes
    df.loc[matches, "updated_at"] = now_text()
    save_reviews(df)


def get_reviews_by_status(status) -> pd.DataFrame:
    validate_status(status)
    df = load_reviews()
    return df[df["status"] == status].copy()


def get_reviews_by_topic(topic_id) -> pd.DataFrame:
    df = load_reviews()
    topic_ids = pd.to_numeric(df["topic_id"], errors="coerce")
    return df[topic_ids == int(topic_id)].copy()
