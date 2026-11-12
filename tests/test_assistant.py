import json
import os
import unittest
from unittest import mock

from helpdesk.assistant import HelpdeskAssistant, redact
from helpdesk.evaluate import evaluate
from helpdesk.retriever import BM25, Chunk, tokenize
from helpdesk.triage import NaiveBayes, priority

NO_KEYS = {k: "" for k in ("OPENAI_API_KEY", "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT")}


class RetrieverTests(unittest.TestCase):
    def test_tokenize_removes_stopwords_and_stems(self):
        self.assertEqual(tokenize("The printers are printing"), ["printer", "print"])

    def test_bm25_ranks_relevant_chunk_first(self):
        chunks = [Chunk("a", "VPN", "Steps", "restart the vpn client"),
                  Chunk("b", "Printer", "Steps", "clear the print queue")]
        self.assertEqual(BM25(chunks).search("vpn not working")[0][0].doc_id, "a")


class GuardrailTests(unittest.TestCase):
    def test_redacts_pii_and_passwords(self):
        out = redact("email me at jo@x.com or 713-555-1212, password: hunter2, ssn 123-45-6789")
        for secret in ("jo@x.com", "713-555-1212", "hunter2", "123-45-6789"):
            self.assertNotIn(secret, out)

    @mock.patch.dict(os.environ, NO_KEYS)
    def test_out_of_scope_hands_off_to_human(self):
        ans = HelpdeskAssistant().ask("what's on the cafeteria menu")
        self.assertEqual(ans.mode, "handoff")
        self.assertFalse(ans.grounded)
        self.assertEqual(ans.sources, [])

    @mock.patch.dict(os.environ, NO_KEYS)
    def test_pii_placeholder_does_not_skew_retrieval(self):
        ans = HelpdeskAssistant().ask("I'm locked out, my email is jane@contoso.com")
        self.assertTrue(ans.sources[0].startswith("Password Reset and Account Lockout"))
        self.assertNotIn("jane@contoso.com", ans.question)


class GenerationTests(unittest.TestCase):
    @mock.patch.dict(os.environ, NO_KEYS)
    def test_extractive_answer_cites_source(self):
        ans = HelpdeskAssistant().ask("windows wants a bitlocker recovery key")
        self.assertEqual(ans.mode, "extractive")
        self.assertIn("BitLocker", ans.sources[0])

    @mock.patch.dict(os.environ, {"AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com",
                                  "AZURE_OPENAI_API_KEY": "test", "OPENAI_API_KEY": ""})
    def test_azure_openai_path_sends_grounded_prompt(self):
        captured = {}

        class FakeResp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return json.dumps({"choices": [{"message": {"content": "1. Do X [1]"}}]}).encode()

        def fake_urlopen(req, timeout):
            captured["url"], captured["body"] = req.full_url, json.loads(req.data)
            return FakeResp()

        with mock.patch("urllib.request.urlopen", fake_urlopen):
            ans = HelpdeskAssistant().ask("VPN says certificate not trusted")
        self.assertEqual(ans.mode, "azure-openai")
        self.assertIn("/openai/deployments/", captured["url"])
        user_msg = captured["body"]["messages"][1]["content"]
        self.assertIn("[1] VPN Not Connecting", user_msg)


class TriageTests(unittest.TestCase):
    def test_naive_bayes_learns_categories(self):
        nb = NaiveBayes().fit(["vpn down", "wifi drop", "printer jam", "toner empty"],
                              ["network", "network", "hardware", "hardware"])
        self.assertEqual(nb.predict("vpn won't connect")[0], "network")

    def test_priority_rules(self):
        self.assertEqual(priority("I clicked a link and entered my password")[0], "P1")
        self.assertEqual(priority("I'm locked out")[0], "P2")
        self.assertEqual(priority("please install visio")[0], "P4")


class EvaluationGate(unittest.TestCase):
    """Quality gate: CI fails if retrieval or triage quality regresses."""

    @mock.patch.dict(os.environ, NO_KEYS)
    def test_quality_thresholds(self):
        r = evaluate(verbose=False)
        self.assertGreaterEqual(r["retrieval_hit@3"], 0.95)
        self.assertGreaterEqual(r["retrieval_mrr"], 0.9)
        self.assertEqual(r["out_of_scope_handoff_rate"], 1.0)
        self.assertGreaterEqual(r["triage_category_accuracy"], 0.85)


if __name__ == "__main__":
    unittest.main()
