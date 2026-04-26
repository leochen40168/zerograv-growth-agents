import argparse
import os
from pathlib import Path

try:
    import requests
except ModuleNotFoundError:
    class _RequestsFallback:
        def post(self, *_args, **_kwargs):
            raise RuntimeError("requests package is not installed")

    requests = _RequestsFallback()

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parent.parent


class WordPressDraftPublisherError(Exception):
    """Raised when a WordPress draft cannot be created."""


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_markdown_file(markdown_path: str) -> str:
    path = resolve_path(markdown_path)
    if not path.exists():
        raise WordPressDraftPublisherError(f"Markdown 檔案不存在：{path}")
    if not path.is_file():
        raise WordPressDraftPublisherError(f"Markdown 路徑不是檔案：{path}")

    return path.read_text(encoding="utf-8")


def parse_markdown_draft(markdown_content: str) -> dict:
    title = ""
    lines = markdown_content.splitlines()

    for index, line in enumerate(lines):
        stripped = line.strip().lstrip("-").strip()
        if stripped.startswith("SEO 標題"):
            _, separator, value = stripped.partition("：")
            if not separator:
                _, separator, value = stripped.partition(":")
            if value.strip():
                title = value.strip()
                break
            if index + 1 < len(lines) and lines[index + 1].strip():
                title = lines[index + 1].strip()
                break

    if not title:
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# "):
                title = stripped[2:].strip()
                break

    return {
        "title": title,
        "body": markdown_content,
    }


def get_wordpress_config() -> dict:
    load_dotenv(BASE_DIR / ".env")
    config = {
        "WORDPRESS_URL": os.getenv("WORDPRESS_URL", "").strip(),
        "WORDPRESS_USERNAME": os.getenv("WORDPRESS_USERNAME", "").strip(),
        "WORDPRESS_APP_PASSWORD": os.getenv("WORDPRESS_APP_PASSWORD", "").strip(),
    }
    missing = [key for key, value in config.items() if not value]
    if missing:
        raise WordPressDraftPublisherError(
            "缺少 WordPress 環境變數：" + ", ".join(missing)
        )
    return config


def build_posts_url(wordpress_url: str) -> str:
    base_url = wordpress_url.rstrip("/")
    if base_url.endswith("/wp-json/wp/v2/posts"):
        return base_url
    return f"{base_url}/wp-json/wp/v2/posts"


def create_wordpress_draft(markdown_path: str) -> dict:
    path = resolve_path(markdown_path)
    markdown_content = load_markdown_file(str(path))
    parsed = parse_markdown_draft(markdown_content)
    title = parsed["title"] or path.stem
    config = get_wordpress_config()

    payload = {
        "title": title,
        "content": parsed["body"],
        "status": "draft",
    }
    response = requests.post(
        build_posts_url(config["WORDPRESS_URL"]),
        json=payload,
        auth=(config["WORDPRESS_USERNAME"], config["WORDPRESS_APP_PASSWORD"]),
        timeout=30,
    )

    if not response.ok:
        raise WordPressDraftPublisherError(
            f"WordPress API 錯誤：HTTP {response.status_code} {response.text}"
        )

    return response.json()


def publish_drafts_for_topic(topic_id: int, drafts_dir="outputs/drafts") -> list[dict]:
    drafts_path = resolve_path(drafts_dir)
    if not drafts_path.exists():
        raise WordPressDraftPublisherError(f"找不到 drafts 資料夾：{drafts_path}")

    draft_files = sorted(drafts_path.glob(f"draft-topic-{topic_id}-*seo-article*.md"))
    if not draft_files:
        raise WordPressDraftPublisherError(
            f"找不到 topic id {topic_id} 的 SEO article draft。"
        )

    return [create_wordpress_draft(str(draft_file)) for draft_file in draft_files]


def main() -> int:
    parser = argparse.ArgumentParser(description="Create WordPress draft posts.")
    parser.add_argument("--markdown-path")
    parser.add_argument("--topic-id", type=int)
    args = parser.parse_args()

    if not args.markdown_path and args.topic_id is None:
        parser.error("請提供 --markdown-path 或 --topic-id")

    try:
        if args.markdown_path:
            responses = [create_wordpress_draft(args.markdown_path)]
        else:
            responses = publish_drafts_for_topic(args.topic_id)
    except WordPressDraftPublisherError as error:
        print(f"Error: {error}")
        return 1

    for response in responses:
        print(response)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
