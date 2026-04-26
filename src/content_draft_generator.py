import argparse
import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ModuleNotFoundError:
    def load_dotenv(*_args, **_kwargs):
        return False


BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_MODEL = "gpt-4.1-mini"


class ContentDraftGeneratorError(Exception):
    """Raised when content draft generation cannot complete."""


def resolve_path(path: str | Path) -> Path:
    path = Path(path)
    if path.is_absolute():
        return path
    return BASE_DIR / path


def load_prompt_file(prompt_path: str) -> str:
    path = resolve_path(prompt_path)
    if not path.exists():
        raise ContentDraftGeneratorError(f"Prompt 檔案不存在：{path}")
    if not path.is_file():
        raise ContentDraftGeneratorError(f"Prompt 路徑不是檔案：{path}")

    return path.read_text(encoding="utf-8")


def require_openai_api_key() -> str:
    load_dotenv(BASE_DIR / ".env")
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ContentDraftGeneratorError("缺少 OPENAI_API_KEY，請先在 .env 設定。")
    return api_key


def call_openai(prompt_text: str, model: str) -> str:
    require_openai_api_key()

    from openai import OpenAI

    client = OpenAI()
    response = client.responses.create(
        model=model,
        input=prompt_text,
    )
    output_text = getattr(response, "output_text", "")
    if not output_text:
        raise ContentDraftGeneratorError("OpenAI API 沒有回傳文字內容。")
    return output_text


def build_draft_metadata(prompt_path: Path) -> str:
    return "\n".join(
        [
            "---",
            f"source_prompt: {prompt_path}",
            "generated_by: openai",
            "review_status: draft",
            "---",
            "",
        ]
    )


def generate_draft_from_prompt(prompt_path: str, output_dir="outputs/drafts") -> str:
    prompt_file = resolve_path(prompt_path)
    prompt_text = load_prompt_file(str(prompt_file))
    output_path = resolve_path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    load_dotenv(BASE_DIR / ".env")
    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL)
    draft_text = call_openai(prompt_text, model)
    draft_path = output_path / f"draft-{prompt_file.name}"
    draft_path.write_text(
        build_draft_metadata(prompt_file) + draft_text,
        encoding="utf-8",
    )
    return str(draft_path)


def generate_drafts_for_topic(
    topic_id: int,
    prompts_dir="outputs/generated_prompts",
    output_dir="outputs/drafts",
) -> list[str]:
    prompts_path = resolve_path(prompts_dir)
    if not prompts_path.exists():
        raise ContentDraftGeneratorError(
            f"找不到 generated prompts 資料夾：{prompts_path}。請先執行 Generate Content Prompts。"
        )

    prompt_files = sorted(prompts_path.glob(f"topic-{topic_id}-*.md"))
    if not prompt_files:
        raise ContentDraftGeneratorError(
            f"找不到 topic id {topic_id} 的 generated prompts，請先執行 Generate Content Prompts。"
        )

    return [
        generate_draft_from_prompt(str(prompt_file), output_dir=output_dir)
        for prompt_file in prompt_files
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate content drafts from prompts.")
    parser.add_argument("--prompt-path")
    parser.add_argument("--topic-id", type=int)
    args = parser.parse_args()

    if not args.prompt_path and args.topic_id is None:
        parser.error("請提供 --prompt-path 或 --topic-id")

    try:
        if args.prompt_path:
            generated_paths = [generate_draft_from_prompt(args.prompt_path)]
        else:
            generated_paths = generate_drafts_for_topic(args.topic_id)
    except ContentDraftGeneratorError as error:
        print(f"Error: {error}")
        return 1

    for path in generated_paths:
        print(path)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
