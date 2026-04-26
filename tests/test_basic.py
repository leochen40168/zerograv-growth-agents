import tempfile
import unittest
from pathlib import Path


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
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = Path(tmpdir) / "sample.txt"
            temp_path.write_text("ok", encoding="utf-8")
            self.assertEqual(temp_path.read_text(encoding="utf-8"), "ok")


if __name__ == "__main__":
    unittest.main()
