import unittest
from datetime import datetime, timedelta, timezone

from deduplicator import deduplicate_items
from filters import filter_by_keywords, filter_recent
from main import select_diverse


class PipelineCoreTests(unittest.TestCase):
    def test_tracking_urls_are_deduplicated(self):
        items = [{"title": "A", "url": "https://x.test/demo?utm_source=a"},
                 {"title": "B", "url": "https://x.test/demo?utm_source=b"}]
        self.assertEqual(len(deduplicate_items(items)), 1)

    def test_old_items_are_removed(self):
        old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
        self.assertEqual(filter_recent([{"published_at": old}], 24), [])

    def test_good_code_case_scores_high(self):
        item = {"source": "github", "title": "three.js WebGPU shader art", "content": "GLSL particles"}
        result = filter_by_keywords([item], minimum_score=20)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]["has_code"])

    def test_selection_keeps_source_diversity(self):
        items = ([{"id": f"g{i}", "source": "github"} for i in range(10)] +
                 [{"id": "m1", "source": "mastodon"}])
        selected = select_diverse(items, 3, per_source=1)
        self.assertEqual({item["source"] for item in selected}, {"github", "mastodon"})


if __name__ == "__main__":
    unittest.main()
