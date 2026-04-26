import argparse
import csv
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
PROMPTS_DIR = BASE_DIR / "prompts"
OUTPUT_DIR = BASE_DIR / "outputs" / "generated_prompts"
TOPICS_PATH = DATA_DIR / "topics.csv"

REQUIRED_TOPIC_FIELDS = [
    "id",
    "topic",
    "category",
    "target_audience",
    "intent",
    "cta",
    "status",
]

TEMPLATES = {
    "seo-article": "seo_article_prompt.md",
    "facebook-page-post": "facebook_page_post_prompt.md",
    "facebook-group-post": "facebook_group_post_prompt.md",
    "seller-reply": "seller_reply_prompt.md",
    "image-card-copy": "image_card_copy_prompt.md",
}


class ArticleGeneratorError(Exception):
    """Raised when prompt generation cannot complete with a clear user-facing reason."""


def read_topics() -> list[dict[str, str]]:
    if not TOPICS_PATH.exists():
        raise ArticleGeneratorError(f"CSV 不存在：{TOPICS_PATH}")

    with TOPICS_PATH.open("r", encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if not reader.fieldnames:
            raise ArticleGeneratorError(f"CSV 是空檔，缺少欄位：{TOPICS_PATH}")

        missing_fields = [
            field for field in REQUIRED_TOPIC_FIELDS if field not in reader.fieldnames
        ]
        if missing_fields:
            raise ArticleGeneratorError(
                "topics.csv 缺少必要欄位：" + ", ".join(missing_fields)
            )

        return list(reader)


def find_topic(topic_id: int) -> dict[str, str]:
    topics = read_topics()
    topic_id_text = str(topic_id)

    for topic in topics:
        if topic["id"] == topic_id_text:
            return topic

    raise ArticleGeneratorError(f"找不到 topic id：{topic_id}")


def render_template(template_text: str, topic: dict[str, str]) -> str:
    replacements = {
        "{topic}": topic["topic"],
        "{category}": topic["category"],
        "{target_audience}": topic["target_audience"],
        "{intent}": topic["intent"],
        "{cta}": topic["cta"],
    }

    rendered = template_text
    for placeholder, value in replacements.items():
        rendered = rendered.replace(placeholder, value)

    return rendered


def build_metadata(topic: dict[str, str]) -> str:
    return "\n".join(
        [
            "---",
            f"topic_id: {topic['id']}",
            f"topic: {topic['topic']}",
            f"category: {topic['category']}",
            f"target_audience: {topic['target_audience']}",
            f"intent: {topic['intent']}",
            f"cta: {topic['cta']}",
            "---",
            "",
        ]
    )


def generate_prompts_for_topic(topic_id: int) -> list[str]:
    topic = find_topic(topic_id)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    generated_paths = []
    for output_name, template_filename in TEMPLATES.items():
        template_path = PROMPTS_DIR / template_filename
        if not template_path.exists():
            raise ArticleGeneratorError(f"Prompt template 不存在：{template_path}")

        template_text = template_path.read_text(encoding="utf-8")
        content = build_metadata(topic) + render_template(template_text, topic)
        output_path = OUTPUT_DIR / f"topic-{topic['id']}-{output_name}.md"
        output_path.write_text(content, encoding="utf-8")
        generated_paths.append(str(output_path))

    return generated_paths


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate prompt markdown files.")
    parser.add_argument("--topic-id", type=int, required=True)
    args = parser.parse_args()

    try:
        generated_paths = generate_prompts_for_topic(args.topic_id)
    except ArticleGeneratorError as error:
        print(f"Error: {error}")
        return 1

    for path in generated_paths:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
