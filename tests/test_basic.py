import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
TEST_TMP_DIR = ROOT / ".test_tmp"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from website_content_exporter import export_draft, export_drafts_for_topic, load_draft


@contextmanager
def temporary_directory():
    TEST_TMP_DIR.mkdir(exist_ok=True)
    path = TEST_TMP_DIR / str(uuid.uuid4())
    path.mkdir()
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class ProjectStructureTest(unittest.TestCase):
    def test_required_project_files_exist(self):
        root = Path(__file__).resolve().parent.parent
        required_paths = [
            root / "README.md",
            root / "requirements.txt",
            root / ".env.example",
            root / "src" / "app.py",
            root / "src" / "article_generator.py",
            root / "src" / "task_manager.py",
            root / "src" / "lead_tracker.py",
            root / "src" / "content_draft_generator.py",
            root / "src" / "wordpress_draft_publisher.py",
            root / "src" / "website_content_exporter.py",
            root / "src" / "daily_workflow.py",
            root / "src" / "review_queue.py",
            root / "src" / "metrics_tracker.py",
            root / "data" / "topics.csv",
            root / "data" / "posting_tasks.csv",
            root / "data" / "seller_leads.csv",
            root / "data" / "content_reviews.csv",
            root / "data" / "metrics.csv",
            root / "prompts" / "seo_article_prompt.md",
        ]
        for path in required_paths:
            self.assertTrue(path.exists(), f"Missing required path: {path}")

    def test_tests_can_use_temporary_directory(self):
        with temporary_directory() as tmpdir:
            temp_path = Path(tmpdir) / "sample.txt"
            temp_path.write_text("ok", encoding="utf-8")
            self.assertEqual(temp_path.read_text(encoding="utf-8"), "ok")


class WebsiteContentExporterTest(unittest.TestCase):
    def test_load_draft_markdown(self):
        with temporary_directory() as tmpdir:
            draft_path = Path(tmpdir) / "draft-topic-1-seo-article.md"
            draft_path.write_text("# Draft\n\nBody", encoding="utf-8")

            self.assertEqual(load_draft(str(draft_path)), "# Draft\n\nBody")

    def test_export_single_draft_with_metadata(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft-topic-1-facebook-page-post.md"
            output_dir = root / "exports"
            draft_path.write_text("Post body", encoding="utf-8")

            exported_path = Path(export_draft(str(draft_path), output_dir=str(output_dir)))
            exported_text = exported_path.read_text(encoding="utf-8")

            self.assertTrue(exported_path.exists())
            self.assertEqual(exported_path.name, "export-draft-topic-1-facebook-page-post.md")
            self.assertIn(f"source_draft: {draft_path}", exported_text)
            self.assertIn("export_type: facebook_page_post", exported_text)
            self.assertIn("publish_method: manual_copy", exported_text)
            self.assertIn("Post body", exported_text)

    def test_export_multiple_drafts_for_topic_id(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            drafts_dir = root / "drafts"
            output_dir = root / "exports"
            drafts_dir.mkdir()
            (drafts_dir / "draft-topic-2-seo-article.md").write_text("Article", encoding="utf-8")
            (drafts_dir / "draft-topic-2-facebook-group-post.md").write_text("Group", encoding="utf-8")
            (drafts_dir / "draft-topic-3-seo-article.md").write_text("Other", encoding="utf-8")

            exported_paths = export_drafts_for_topic(
                2,
                drafts_dir=str(drafts_dir),
                output_dir=str(output_dir),
            )

            self.assertEqual(len(exported_paths), 2)
            self.assertEqual(
                sorted(Path(path).name for path in exported_paths),
                [
                    "export-draft-topic-2-facebook-group-post.md",
                    "export-draft-topic-2-seo-article.md",
                ],
            )

    def test_export_does_not_call_facebook_or_wordpress_api(self):
        with temporary_directory() as tmpdir:
            root = Path(tmpdir)
            draft_path = root / "draft-topic-1-seo-article.md"
            output_dir = root / "exports"
            draft_path.write_text("Article body", encoding="utf-8")

            with patch("urllib.request.urlopen") as urlopen:
                exported_path = export_draft(str(draft_path), output_dir=str(output_dir))

            urlopen.assert_not_called()
            exported_text = Path(exported_path).read_text(encoding="utf-8")
            self.assertIn("export_type: website_article", exported_text)


if __name__ == "__main__":
    unittest.main()
