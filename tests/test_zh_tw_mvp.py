import ast
import importlib.util
import pathlib
import os
from unittest.mock import patch
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]


def load_file(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_class(path, name):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == name)
    namespace = {"re": re}
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


class TopicTests(unittest.TestCase):
    def test_chinese_and_mixed_topics(self):
        validator = load_file(ROOT / "knowledge_storm" / "topic_validation.py")
        for topic in ["臺灣半導體產業", "生成式 AI 與教育", "Climate change"]:
            self.assertIsNone(validator.validate_topic(topic))

    def test_invalid_topics(self):
        validator = load_file(ROOT / "knowledge_storm" / "topic_validation.py")
        for topic in ["", "  ", "../secret", "a\\b", "x\x00y", "中" * 126, "CON"]:
            self.assertIsNotNone(validator.validate_topic(topic), topic)


class I18nTests(unittest.TestCase):
    def test_languages_and_interpolation(self):
        i18n = load_file(ROOT / "frontend" / "demo_light" / "i18n.py")
        self.assertEqual(i18n.translate("research", "zh-TW"), "開始研究")
        self.assertEqual(i18n.translate("research", "en"), "Research")
        self.assertIn("3", i18n.translate("page_count", "zh-TW", current=3, total=4))
        self.assertEqual(set(i18n.TRANSLATIONS["en"]), set(i18n.TRANSLATIONS["zh-TW"]))


class CitationTests(unittest.TestCase):
    def test_chinese_punctuation_and_citation_order(self):
        processor = load_class(ROOT / "knowledge_storm" / "utils.py", "ArticleTextProcessing")
        self.assertEqual(processor.remove_uncompleted_sentences_with_citations("這是事實。[2][1] 未完成"), "這是事實。[2][1]")
        self.assertEqual(processor.parse_citation_indices("證據[2][1]。"), [2, 1])

    def test_removes_only_unknown_citation_indices(self):
        processor = load_class(ROOT / "knowledge_storm" / "utils.py", "ArticleTextProcessing")
        self.assertEqual(processor.remove_invalid_citations("資料[2][8]，補充[1]。", {1, 2}), "資料[2]，補充[1]。")

    def test_grouped_citations_keep_order(self):
        processor = load_class(ROOT / "knowledge_storm" / "utils.py", "ArticleTextProcessing")
        self.assertEqual(processor.remove_uncompleted_sentences_with_citations("事實。[2,1]"), "事實。[2] [1]")

    def test_utf8_round_trip(self):
        import tempfile
        helper = load_class(ROOT / "knowledge_storm" / "utils.py", "FileIOHelper")
        with tempfile.TemporaryDirectory() as folder:
            path = str(pathlib.Path(folder) / "文章.txt")
            helper.write_str("繁體中文。[1]", path)
            self.assertEqual(helper.load_str(path), "繁體中文。[1]")


class PromptTests(unittest.TestCase):
    def test_research_signatures_preserve_sources_and_language(self):
        expected = {
            "persona_generator.py": ["GenPersona"],
            "knowledge_curation.py": ["AskQuestion", "AskQuestionWithPersona", "QuestionToQuery", "AnswerQuestion"],
            "outline_generation.py": ["WritePageOutline", "WritePageOutlineFromConv"],
            "article_generation.py": ["WriteSection"],
            "article_polish.py": ["WriteLeadSection", "PolishPage"],
        }
        for filename, names in expected.items():
            path = ROOT / "knowledge_storm" / "storm_wiki" / "modules" / filename
            tree = ast.parse(path.read_text(encoding="utf-8"))
            classes = {n.name: ast.get_docstring(n) for n in tree.body if isinstance(n, ast.ClassDef)}
            for name in names:
                with self.subTest(signature=name):
                    self.assertIn("Traditional Chinese", classes[name])
        self.assertIn("never invent", classes["WriteLeadSection"].lower())


class DemoTests(unittest.TestCase):
    def test_demo_defaults_to_codex_without_external_api_keys(self):
        from test_codex_backend import backend
        m = backend()
        path = ROOT / "frontend/demo_light/demo_util.py"
        node = next(n for n in ast.parse(path.read_text(encoding="utf-8")).body
                    if isinstance(n, ast.FunctionDef) and n.name == "set_storm_runner")
        models = []
        class Config:
            def __getattr__(self, name):
                return models.append
        class Args:
            def __init__(self, **kwargs):
                self.__dict__.update(kwargs)
        st = type("Streamlit", (), {"session_state": {}})()
        with __import__("tempfile").TemporaryDirectory() as folder:
            namespace = {"os": os, "get_demo_dir": lambda: folder,
                         "STORMWikiLMConfigs": Config, "STORMWikiRunnerArguments": Args,
                         "STORMWikiRunner": lambda *args: args, "st": st,
                         "CodexClient": m.CodexClient, "CodexLM": m.CodexLM, "CodexRM": m.CodexRM}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
            with patch.dict(os.environ, {}, clear=True):
                namespace["set_storm_runner"]()
        args, _, rm = st.session_state["runner"]
        self.assertIsInstance(rm, m.CodexRM)
        self.assertTrue(all(isinstance(model, m.CodexLM) for model in models))
        self.assertEqual(args.max_thread_num, 1)
        self.assertTrue(args.disable_related_topics)

    def test_reference_panel_uses_original_indices(self):
        path = ROOT / "frontend" / "demo_light" / "demo_util.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_display_references")
        class FakeStreamlit:
            messages = []
            def selectbox(self, label, options, format_func):
                self.options = options
                return options[-1]
            def markdown(self, value):
                self.messages.append(value)
        st = FakeStreamlit()
        namespace = {"st": st, "t": lambda key, **kwargs: key}
        exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
        namespace["_display_references"]({2: {"title": "two", "url": "https://two.test", "snippets": []}, 7: {"title": "seven", "url": "https://seven.test", "snippets": []}})
        self.assertEqual(st.options, [2, 7])
        self.assertTrue(any("https://seven.test" in m for m in st.messages))

    def test_runner_uses_environment_model_without_embedding_keys(self):
        path = ROOT / "frontend" / "demo_light" / "demo_util.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "set_storm_runner")
        models = []
        class Config:
            def __getattr__(self, name):
                return lambda model: models.append(model)
        class Args:
            def __init__(self, **kwargs):
                self.search_top_k = kwargs["search_top_k"]
        class Streamlit:
            session_state = {}
        with __import__("tempfile").TemporaryDirectory() as folder:
            namespace = {"os": os, "get_demo_dir": lambda: folder, "STORMWikiLMConfigs": Config,
                         "LitellmModel": lambda **kwargs: kwargs, "STORMWikiRunnerArguments": Args,
                         "YouRM": lambda **kwargs: kwargs, "STORMWikiRunner": lambda *args: args,
                         "st": Streamlit(), "t": lambda key: key}
            exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
            with patch.dict(os.environ, {"STORM_PROVIDER": "openai", "STORM_MODEL": "test-model", "YDC_API_KEY": "test-key"}, clear=True):
                namespace["set_storm_runner"]()
        self.assertEqual(len(models), 5)
        self.assertTrue(all(m["model"] == "openai/test-model" and "api_key" not in m for m in models))

    def test_last_valid_source_is_not_removed(self):
        path = ROOT / "knowledge_storm" / "storm_wiki" / "modules" / "storm_dataclass.py"
        tree = ast.parse(path.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "StormArticle")
        method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "update_section")
        future = ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0)
        processor = load_class(ROOT / "knowledge_storm" / "utils.py", "ArticleTextProcessing")
        namespace = {"re": re, "ArticleTextProcessing": processor}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[future, method], type_ignores=[])), str(path), "exec"), namespace)
        class Article:
            root = type("Root", (), {"section_name": "主題"})()
            def _merge_new_info_to_references(self, infos, keep):
                self.keep = keep
                return {2: 2}
            def insert_or_create_section(self, article_dict, **kwargs):
                self.result = article_dict
        article = Article()
        namespace["update_section"](article, "# 章節\n事實[2]，錯誤[3][0]。", [object(), object()])
        self.assertEqual(article.keep, [1])
        self.assertIn("[2]", str(article.result))
        self.assertNotIn("[3]", str(article.result))
        self.assertNotIn("[0]", str(article.result))


if __name__ == "__main__":
    unittest.main()
