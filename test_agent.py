import concurrent.futures
import json
import tempfile
import unittest
from unittest.mock import patch
from datetime import datetime, timedelta, timezone
from pathlib import Path
import agent


class PublicationSafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        self.clock = patch.object(agent, "datetime", wraps=datetime)
        mocked_datetime = self.clock.start()
        mocked_datetime.now.side_effect = lambda tz=None: self.now.astimezone(tz) if tz else self.now.replace(tzinfo=None)
        self.config = {"account": "test_account", "timezone": "Europe/London", "publishing_enabled": True,
                       "production_content_ready": True, "daily_limit": 1}
        (self.root / "config.json").write_text(json.dumps(self.config))
        (self.root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nfixture")

    def tearDown(self):
        self.clock.stop()
        self.temp.cleanup()

    def add(self, suffix="1", **overrides):
        post = {"account": "test_account", "caption": "test caption " + suffix, "assets": ["image.png"],
                "scheduled_at": (self.now - timedelta(minutes=1)).isoformat(),
                "kind": "production", "slot": suffix, "ready": True}
        post.update(overrides)
        path = self.root / (suffix + ".json")
        path.write_text(json.dumps(post))
        return agent.enqueue(self.root, path)["id"]

    def test_concurrent_workers_claim_only_once(self):
        identifier = self.add()
        def attempt():
            try:
                agent.claim(self.root, identifier)
                return True
            except ValueError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempt(), range(2)))
        self.assertEqual(results.count(True), 1)

    def test_pause_is_rechecked_before_final_click(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        self.config["publishing_enabled"] = False
        (self.root / "config.json").write_text(json.dumps(self.config))
        with self.assertRaisesRegex(ValueError, "paused"):
            agent.check(self.root, identifier)

    def test_uncertain_outcome_cannot_be_retried(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        agent.uncertain(self.root, identifier)
        with self.assertRaisesRegex(ValueError, "reconcile"):
            agent.claim(self.root, identifier)

    def test_changed_media_blocks_publication(self):
        identifier = self.add()
        (self.root / "image.png").write_bytes(b"\x89PNG\r\n\x1a\nchanged")
        with self.assertRaisesRegex(ValueError, "changed"):
            agent.claim(self.root, identifier)

    def test_daily_limit_counts_inflight_jobs(self):
        first, second = self.add("1"), self.add("2")
        agent.claim(self.root, first)
        with self.assertRaisesRegex(ValueError, "Daily limit"):
            agent.claim(self.root, second)

    def test_scheduled_future_job_is_not_published_early(self):
        identifier = self.add(scheduled_at=(self.now + timedelta(hours=1)).isoformat())
        with self.assertRaisesRegex(ValueError, "not due"):
            agent.claim(self.root, identifier)

    def test_one_time_technical_test_is_not_repeated(self):
        self.add("1", kind="technical_test")
        with self.assertRaisesRegex(ValueError, "one-time"):
            self.add("2", kind="technical_test")

    def test_success_requires_reopened_post_evidence(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        evidence = {"url": "https://www.instagram.com/p/TEST_ID/", "verified_account": "test_account",
                    "publication_success_observed": True, "permalink_reopened_and_verified": False}
        filename = self.root / "evidence.json"
        filename.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(ValueError, "reopened"):
            agent.record(self.root, identifier, filename)
        evidence["permalink_reopened_and_verified"] = True
        filename.write_text(json.dumps(evidence))
        self.assertEqual(agent.record(self.root, identifier, filename)["status"], "PUBLISHED")

    def test_daily_tick_waits_for_brand_material(self):
        self.config["production_content_ready"] = False
        (self.root / "config.json").write_text(json.dumps(self.config))
        result = agent.tick(self.root)
        self.assertFalse(result["browser_action_required"])
        self.assertEqual(result["result"], "waiting_for_formal_brand_content")

    def test_daily_tick_reuses_the_same_due_job(self):
        identifier = self.add()
        for _ in range(2):
            result = agent.tick(self.root)
            self.assertEqual(result["post_id"], identifier)
        self.assertEqual(len(agent.status(self.root)["posts"]), 1)

    def test_daily_tick_blocks_an_uncertain_previous_submission(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        agent.uncertain(self.root, identifier)
        result = agent.tick(self.root)
        self.assertFalse(result["browser_action_required"])
        self.assertEqual(result["posts"][0]["status"], "VERIFY_REQUIRED")

    def test_final_gate_blocks_a_job_that_has_expired(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        yesterday = (self.now - timedelta(days=1)).date().isoformat()
        with agent.database(self.root) as db:
            db.execute("UPDATE posts SET local_date=? WHERE id=?", (yesterday, identifier))
        with self.assertRaisesRegex(ValueError, "Expired"):
            agent.check(self.root, identifier)

    def test_init_is_paused_and_never_overwrites_configuration(self):
        new_root = self.root / "fresh"
        result = agent.initialize(new_root, "example_account")
        self.assertFalse(result["publishing_enabled"])
        with self.assertRaises(FileExistsError):
            agent.initialize(new_root, "another_account")
        self.assertEqual(agent.configuration(new_root)["account"], "example_account")

    def test_unapproved_production_manifest_cannot_be_enqueued(self):
        with self.assertRaisesRegex(ValueError, "ready=true"):
            self.add(ready=False)

    def test_string_false_is_not_accepted_as_publication_evidence(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        evidence = {"url": "https://www.instagram.com/p/TEST_ID/", "verified_account": "test_account",
                    "publication_success_observed": "false", "permalink_reopened_and_verified": True}
        filename = self.root / "evidence.json"
        filename.write_text(json.dumps(evidence))
        with self.assertRaisesRegex(ValueError, "verified"):
            agent.record(self.root, identifier, filename)

    def test_post_url_must_be_a_canonical_instagram_permalink(self):
        identifier = self.add()
        agent.claim(self.root, identifier)
        for url in ("https://example.com/p/TEST_ID/", "https://user:pass@www.instagram.com/p/TEST_ID/",
                    "https://www.instagram.com/p/TEST_ID/?tracking=value"):
            filename = self.root / "evidence.json"
            filename.write_text(json.dumps({"url": url}))
            with self.assertRaisesRegex(ValueError, "permalink"):
                agent.record(self.root, identifier, filename)


if __name__ == "__main__":
    unittest.main()
