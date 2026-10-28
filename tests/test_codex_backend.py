"""Offline contracts for the Codex adapter; fixture captured from Codex CLI 0.165."""
import importlib.util
import ast
import copy
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def backend():
    spec = importlib.util.spec_from_file_location("codex_backend", ROOT / "knowledge_storm/codex_backend.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURE = (ROOT / "tests/fixtures/codex-search.jsonl").read_text(encoding="utf-8")


class CodexBackendTests(unittest.TestCase):
    def test_parses_real_tool_results_instead_of_final_message_links(self):
        m = backend()
        result = m.parse_codex_events(FIXTURE)
        self.assertEqual(len(result["search_items"]), 1)
        self.assertEqual(result["search_items"][0]["results"][0]["url"], "https://docs.python.org/3/tutorial/inputoutput.html?highlight=text+files")
        self.assertGreater(result["usage"]["input_tokens"], 0)

    def test_failed_or_incomplete_turn_never_returns_partial_answer(self):
        m = backend()
        for stream in ['{"type":"turn.failed","error":{"message":"quota"}}',
                       '{"type":"item.completed","item":{"type":"agent_message","text":"partial"}}',
                       'not-json']:
            with self.subTest(stream=stream), self.assertRaises(m.CodexBackendError):
                m.parse_codex_events(stream)

    def test_cli_forces_subscription_and_sends_prompt_via_stdin(self):
        m = backend()
        client = m.CodexClient(model="test-model", command="codex")
        completed = subprocess.CompletedProcess([], 0, stdout=FIXTURE, stderr="")
        with patch.object(m.subprocess, "run", return_value=completed) as run, patch.dict(os.environ, {"OPENAI_API_KEY":"secret", "CODEX_API_KEY":"secret"}):
            client.complete("研究中文與 AI", search=True)
        options = run.call_args.kwargs
        args = run.call_args.args[0]
        self.assertIn('forced_login_method="chatgpt"', args)
        self.assertIn('web_search="live"', args)
        self.assertIn("read-only", args)
        self.assertEqual(options["input"], "研究中文與 AI")
        self.assertNotIn("研究中文與 AI", args)
        self.assertNotIn("OPENAI_API_KEY", options["env"])
        self.assertNotIn("CODEX_API_KEY", options["env"])

    def test_cli_timeout_or_failure_has_no_api_fallback(self):
        m = backend()
        client = m.CodexClient(command="codex")
        for response in [subprocess.TimeoutExpired("codex", 1), FileNotFoundError()]:
            with patch.object(m.subprocess, "run", side_effect=response), self.assertRaises(m.CodexBackendError):
                client.complete("研究")
        with patch.object(m.subprocess, "run", return_value=subprocess.CompletedProcess([], 1, "", "private diagnostics")), self.assertRaises(m.CodexBackendError):
            client.complete("研究")

    def test_search_persists_exact_evidence_and_original_source_identity(self):
        m = backend()
        client = m.CodexClient(command="codex")
        with tempfile.TemporaryDirectory() as folder, patch.object(client, "complete", return_value=m.parse_codex_events(FIXTURE)):
            rm = m.CodexRM(client, output_dir=folder, k=2)
            results = rm("中文 UTF-8 搜尋")
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0]["title"], "7. Input and Output — Python 3.14.7 documentation")
            self.assertEqual(results[0]["url"], "https://docs.python.org/3/tutorial/inputoutput.html?highlight=text+files")
            provenance = results[0]["meta"]["provenance"][0]
            self.assertEqual(provenance["query"], "中文 UTF-8 搜尋")
            self.assertEqual(provenance["source_ref"], "turn0search0")
            saved = json.loads((Path(folder) / provenance["evidence_file"]).read_text(encoding="utf-8"))
            self.assertEqual(saved["search_items"][0]["results"][0]["snippet"], results[0]["snippets"][0])
            self.assertNotIn("reasoning", saved)

    def test_missing_tool_results_rejects_model_generated_urls(self):
        m = backend()
        text_only = m.parse_codex_events('\n'.join(json.dumps(x) for x in [
            {"type":"item.completed","item":{"type":"agent_message","text":"https://invented.example/paper"}},
            {"type":"turn.completed","usage":{}}]))
        with tempfile.TemporaryDirectory() as folder, patch.object(m.CodexClient, "complete", return_value=text_only):
            with self.assertRaises(m.CodexBackendError) as error:
                m.CodexRM(m.CodexClient(command="codex"), folder)("query")
            self.assertEqual(error.exception.code, "codex_search_evidence")

    def test_duplicate_urls_merge_evidence_and_exclusions_are_respected(self):
        m = backend()
        result = m.parse_codex_events(FIXTURE)
        item = result["search_items"][0]
        item["results"] = [item["results"][0], item["results"][0], item["results"][1]]
        with tempfile.TemporaryDirectory() as folder, patch.object(m.CodexClient, "complete", return_value=result):
            rm = m.CodexRM(m.CodexClient(command="codex"), folder, k=3)
            sources = rm(["中文", "English"], exclude_urls=[item["results"][1]["url"]])
            self.assertEqual(len(sources), 1)
            self.assertEqual({p["query"] for p in sources[0]["meta"]["provenance"]}, {"中文", "English"})

    def test_private_or_non_web_urls_are_rejected(self):
        m = backend()
        for url in ["file:///etc/passwd", "javascript:alert(1)", "http://127.0.0.1/a", "http://localhost/a", "https://user:pass@example.com/a"]:
            self.assertFalse(m.is_source_url(url), url)

    def test_lm_retains_dspy_contract_and_usage(self):
        m = backend()
        client = m.CodexClient(command="codex")
        with patch.object(client, "complete", return_value={"text":"繁體中文報告[2]。", "usage":{"input_tokens":10,"output_tokens":5}, "search_items":[],"thread_id":"test"}):
            lm = m.CodexLM(client)
            self.assertEqual(lm("寫報告"), ["繁體中文報告[2]。"])
            self.assertEqual(lm.get_usage_and_reset()[lm.model], {"prompt_tokens":10,"completion_tokens":5})
            self.assertEqual(lm.get_usage_and_reset()[lm.model]["prompt_tokens"], 0)
            self.assertEqual(lm.history[0]["outputs"], ["繁體中文報告[2]。"])

    def test_source_metadata_merges_queries_without_losing_first_evidence(self):
        m = backend()
        first = {"source_id": "same", "provenance": [{"query": "中文", "evidence_file": "one.json"}]}
        second = {"source_id": "same", "provenance": [{"query": "English", "evidence_file": "two.json"}]}
        merged = m.merge_source_metadata(first, second)
        self.assertEqual([p["query"] for p in merged["provenance"]], ["中文", "English"])
        self.assertEqual(len(first["provenance"]), 1)

    def test_information_table_keeps_each_turn_evidence_unchanged(self):
        m = backend()
        path = ROOT / "knowledge_storm/storm_wiki/modules/storm_dataclass.py"
        cls = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
                   if isinstance(n, ast.ClassDef) and n.name == "StormInformationTable")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "construct_url_to_info")
        method.decorator_list = []
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        namespace = {"copy": copy, "merge_source_metadata": m.merge_source_metadata}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, method], type_ignores=[])), str(path), "exec"), namespace)
        from types import SimpleNamespace
        first = SimpleNamespace(url="https://example.com/source", snippets=["原始摘錄"], meta={"provenance":[{"query":"中文"}]})
        second = SimpleNamespace(url=first.url, snippets=["second excerpt"], meta={"provenance":[{"query":"English"}]})
        table = namespace["construct_url_to_info"]([("one", [SimpleNamespace(search_results=[first])]),
                                                    ("two", [SimpleNamespace(search_results=[second])])])
        self.assertEqual(len(table[first.url].meta["provenance"]), 2)
        self.assertEqual(first.meta["provenance"], [{"query":"中文"}])
        self.assertEqual(first.snippets, ["原始摘錄"])

    def test_codex_research_without_sources_stops_before_article_generation(self):
        from types import SimpleNamespace
        m = backend()
        path = ROOT / "knowledge_storm/storm_wiki/engine.py"
        cls = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
                   if isinstance(n, ast.ClassDef) and n.name == "STORMWikiRunner")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "run_knowledge_curation_module")
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        class Files:
            @staticmethod
            def dump_json(data, path):
                Path(path).write_text(json.dumps(data), encoding="utf-8")
        namespace = {"os": os, "FileIOHelper": Files, "CodexBackendError": m.CodexBackendError}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, method], type_ignores=[])), str(path), "exec"), namespace)
        with tempfile.TemporaryDirectory() as folder:
            table = SimpleNamespace(url_to_info={}, dump_url_to_info=lambda path: Files.dump_json({}, path))
            runner = SimpleNamespace(
                topic="中文主題", article_output_dir=folder,
                args=SimpleNamespace(max_perspective=1),
                retriever=SimpleNamespace(rm=SimpleNamespace(requires_source_evidence=True)),
                storm_knowledge_curation_module=SimpleNamespace(research=lambda **kwargs: (table, [])))
            with self.assertRaises(m.CodexBackendError) as error:
                namespace["run_knowledge_curation_module"](runner)
            self.assertEqual(error.exception.code, "codex_no_sources")
            self.assertTrue((Path(folder) / "raw_search_results.json").exists())


if __name__ == "__main__":
    unittest.main()
