"""Opt-in live smoke: consumes Codex allowance, no You.com/Platform keys."""
import json
import os
from pathlib import Path
import tempfile
import unittest

from test_codex_backend import backend


@unittest.skipUnless(os.getenv("STORM_RUN_CODEX_LIVE") == "1", "Set STORM_RUN_CODEX_LIVE=1 to consume Codex allowance")
class LiveCodexTests(unittest.TestCase):
    def test_generation_search_and_saved_evidence(self):
        m = backend()
        client = m.CodexClient(model=os.getenv("STORM_MODEL") or None)
        lm = m.CodexLM(client)
        answer = lm("只回覆這段文字：繁體中文 UTF-8 [2]")[0]
        self.assertIn("繁體中文", answer)
        self.assertIn("[2]", answer)
        with tempfile.TemporaryDirectory() as folder:
            sources = m.CodexRM(client, folder, k=1)("Python official documentation UTF-8 text files")
            self.assertTrue(sources, "Codex must return at least one authentic web-search result")
            source = sources[0]
            provenance = source["meta"]["provenance"][0]
            evidence = json.loads((Path(folder) / provenance["evidence_file"]).read_text(encoding="utf-8"))
            urls = [raw.get("url") for item in evidence["search_items"] for raw in item.get("results", [])]
            self.assertIn(source["url"], urls)
            self.assertTrue(source["snippets"][0])


if __name__ == "__main__":
    unittest.main()
