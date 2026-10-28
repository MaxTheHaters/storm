"""Real DSPy contract test; no model calls. Install project dependencies to run."""
import importlib.util
import unittest
from unittest.mock import patch

from test_codex_backend import backend


@unittest.skipUnless(importlib.util.find_spec("dspy"), "DSPy 2.4.9 is not installed")
class DSPyContractTests(unittest.TestCase):
    def test_predict_extracts_chinese_answer_with_citations(self):
        import dspy

        m = backend()
        client = m.CodexClient(command="codex")
        with patch.object(client, "complete", return_value={
            "text": "臺灣半導體研究的來源[2]。", "usage": {}, "thread_id": "fixture", "search_items": []
        }):
            lm = m.CodexLM(client)
            with dspy.settings.context(lm=lm):
                prediction = dspy.Predict("topic -> answer")(topic="臺灣半導體")
            self.assertEqual(prediction.answer, "臺灣半導體研究的來源[2]。")

    def test_chain_of_thought_extracts_answer_after_reasoning(self):
        import dspy

        m = backend()
        client = m.CodexClient(command="codex")
        with patch.object(client, "complete", return_value={
            "text": "Reasoning: 依照已提供的研究來源作答。\n\nAnswer: 可追溯的事實[2]。",
            "usage": {}, "thread_id": "fixture", "search_items": []
        }):
            with dspy.settings.context(lm=m.CodexLM(client)):
                prediction = dspy.ChainOfThought("topic -> answer")(topic="研究主題")
            self.assertEqual(prediction.answer, "可追溯的事實[2]。")


if __name__ == "__main__":
    unittest.main()
