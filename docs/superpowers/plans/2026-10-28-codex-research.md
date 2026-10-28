# Codex research integration

Goal: run STORM generation and web search using the local, ChatGPT-authenticated Codex CLI, with no You.com or Platform API key required in Codex mode.

Architecture: a dependency-light Codex client consumes official `codex exec --json` events. A language-model adapter implements the callable and usage/history contracts consumed by DSPy 2.4.9. A retrieval adapter accepts only tool-returned search results, stores search evidence, and returns the existing STORM source dictionaries. Generated URLs without tool evidence are rejected. Existing API mode remains available by explicit provider selection.

Constraints: use `feat/zh-tw-mvp` and Draft PR #1; no merge. Use read-only isolated Codex runs, ChatGPT authentication, bounded execution, and no automatic API fallback. Never copy credentials. Preserve the original URL, title, snippets, search query, tool item ID, timestamp and evidence file through conversation and reference exports. Do not claim full E2E coverage without executing it.

Tasks:
- [x] Write failing tests for JSONL completion/failure, authentic tool results, malformed/missing results, and source persistence.
- [x] Implement `knowledge_storm/codex_backend.py`: client, LM adapter, retriever, usage/history and source audit files.
- [x] Connect the minimal demo to Codex by default; serialize Codex requests and disable model-suggested Wikipedia fetches in Codex mode.
- [x] Preserve provenance on repeated sources and show it in the reference panel. Cover URL deduplication, query retention and source identity.
- [x] Update bilingual errors, startup docs and an opt-in live smoke test. Run the full offline suite, a bounded real Codex test, compilation and whitespace checks.
- [x] Update the existing remote feature branch and Draft PR with exact verification and limitations.

Review focus: CLI versions without structured search results must fail explicitly; quota/auth failures must not become empty successful reports; model-generated URLs must not enter references; concurrent calls must not mix evidence; local provenance metadata must survive STORM's source deduplication and per-section retrieval.
