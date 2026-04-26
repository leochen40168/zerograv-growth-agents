from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
CONTENT_TYPE_BY_FILENAME = {
    "seo-article": "website_article",
    "facebook-page-post": "facebook_page_post",
    "facebook-group-post": "facebook_group_post",
    "seller-reply": "seller_reply",
    "image-card-copy": "image_card_copy",
}


class WebsiteContentExporterError(Exception):
    """Raised when manual content export cannot complete."""


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_draft(markdown_path: str) -> str:
    path = resolve_path(markdown_path)
    if not path.exists():
        raise WebsiteContentExporterError(f"Draft file does not exist: {path}")
    if not path.is_file():
        raise WebsiteContentExporterError(f"Draft path is not a file: {path}")

    return path.read_text(encoding="utf-8")


def get_content_type(markdown_path: str | Path) -> str:
    filename = Path(markdown_path).name
    for marker, content_type in CONTENT_TYPE_BY_FILENAME.items():
        if marker in filename:
            return content_type
    raise WebsiteContentExporterError(f"Cannot determine content type from filename: {filename}")


def build_export_metadata(markdown_path: Path, content_type: str) -> str:
    return "\n".join(
        [
            "---",
            f"source_draft: {markdown_path}",
            f"export_type: {content_type}",
            "publish_method: manual_copy",
            "---",
            "",
        ]
    )


def export_draft(markdown_path: str, output_dir="outputs/exports") -> str:
    draft_path = resolve_path(markdown_path)
    draft_text = load_draft(str(draft_path))
    content_type = get_content_type(draft_path)

    export_dir = resolve_path(output_dir)
    export_dir.mkdir(parents=True, exist_ok=True)
    export_path = export_dir / f"export-{draft_path.name}"
    export_path.write_text(
        build_export_metadata(draft_path, content_type) + draft_text,
        encoding="utf-8",
    )
    return str(export_path)


def export_drafts_for_topic(
    topic_id: int,
    drafts_dir="outputs/drafts",
    output_dir="outputs/exports",
) -> list[str]:
    drafts_path = resolve_path(drafts_dir)
    if not drafts_path.exists():
        raise WebsiteContentExporterError(f"Drafts directory does not exist: {drafts_path}")

    draft_files = sorted(drafts_path.glob(f"draft-topic-{topic_id}-*.md"))
    if not draft_files:
        raise WebsiteContentExporterError(f"No draft files found for topic id {topic_id}.")

    return [
        export_draft(str(draft_file), output_dir=output_dir)
        for draft_file in draft_files
    ]
