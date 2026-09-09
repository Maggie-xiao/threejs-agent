import unittest
import json
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from deduplicator import deduplicate_items
from filters import filter_by_keywords, filter_recent
from main import select_diverse
from report import write_reports


class PipelineCoreTests(unittest.TestCase):
    def test_tracking_urls_are_deduplicated(self):
        items = [{"title": "A", "url": "https://x.test/demo?utm_source=a"},
                 {"title": "B", "url": "https://x.test/demo?utm_source=b"}]
        self.assertEqual(len(deduplicate_items(items)), 1)

    def test_old_items_are_removed(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        self.assertEqual(filter_recent([{"published_at": old}], 24), [])

    def test_invalid_dates_are_removed(self):
        self.assertEqual(filter_recent([{"published_at": "not-a-date"}, {}], 24), [])

    def test_good_code_case_scores_high(self):
        item = {"source": "github", "title": "three.js WebGPU shader art", "content": "GLSL particles"}
        result = filter_by_keywords([item], minimum_score=20)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["has_code"])

    def test_code_sources_are_detected(self):
        for source in ("github", "gitlab", "npm"):
            result = filter_by_keywords([{"source": source, "title": "three.js shader"}])
            self.assertTrue(result[0]["has_code"], source)

    def test_selection_keeps_source_diversity(self):
        items = ([{"id": f"g{i}", "source": "github"} for i in range(10)] +
                 [{"id": "m1", "source": "mastodon"}])
        selected = select_diverse(items, 3, per_source=1)
        self.assertEqual({item["source"] for item in selected}, {"github", "mastodon"})

    def test_same_day_reports_are_merged(self):
        with tempfile.TemporaryDirectory() as directory:
            first = {"id": "one", "source": "github", "title": "One", "url": "https://one",
                     "analysis": {"recommendation_score": 7}}
            second = {"id": "two", "source": "bluesky", "title": "Two", "url": "https://two",
                      "analysis": {"recommendation_score": 8}}
            write_reports([first], directory)
            _, json_path, merged = write_reports([second], directory)
            self.assertEqual({item["id"] for item in merged}, {"one", "two"})
            self.assertEqual(len(json.loads(Path(json_path).read_text())), 2)


if __name__ == "__main__":
    unittest.main()
