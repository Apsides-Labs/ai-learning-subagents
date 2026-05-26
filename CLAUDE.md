# CLAUDE.md

Project: AI Learning Subagents — marketing-agent system for Draft and Arc.

## What this is

A multi-agent system that researches market opportunities, plans SEO-optimized articles, drafts them, fact-checks them, opens PRs to the blog repo, and measures how published articles perform.

## Starting point for SEO context

Before doing SEO work, read `docs/playbooks/seo/00-overview.md`. It points at the rest of the playbook.

## Key invariants

- The `tools/` package re-exports the research-agent's legacy tools (`jina_reader`, `tavily_search_tool`, `list_codebase_files`, `read_codebase_file`). New tools (e.g., DataForSEO) go in `tools/dataforseo.py`.
- All file writes that the system depends on (calendar JSON, measurement brief) go through `services.file_service.atomic_write_text`. Don't bypass this.
- The DataForSEO client is a process-scoped singleton (`services.dataforseo_client.get_client()`). The cost tracker on it enforces per-run caps.
- Measurement numbers are deterministic — they never go through an LLM. Only prose verdicts and action priorities are LLM-generated.

## Where to read next

- Design spec: `docs/superpowers/specs/2026-05-19-seo-measurement-integration-design.md`
- Implementation plan: `docs/superpowers/plans/2026-05-20-seo-measurement-implementation.md`
- SEO playbook: `docs/playbooks/seo/00-overview.md`
