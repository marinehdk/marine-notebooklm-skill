# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Repo Is

This is the **nlm skill** — a Claude Code skill that lets Claude query NotebookLM notebooks for grounded knowledge. It ships as a set of Claude Code skills (`/nlm-ask`, `/nlm-plan`, etc.) backed by a Python CLI.

The canonical skill source lives here; the deployed target is `~/.claude/skills/nlm/`.

---

## Development Setup

`requirements.txt` points to the GitHub source (not PyPI):
```
git+https://github.com/teng-lin/notebooklm-py.git
```

`scripts/invoke.sh` **auto-bootstraps** on first run: if `.venv` is missing it creates it and installs requirements automatically. No manual setup needed for users.

To set up a dev venv explicitly:
```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

---

## Running Tests

```bash
# Unit tests (no auth needed)
.venv/bin/python -m pytest tests/test_registry.py -v

# Integration / smoke tests (requires real auth + configured notebook)
.venv/bin/python -m pytest tests/test_cli.py -v

# Single test
.venv/bin/python -m pytest tests/test_cli.py::test_ask_scope_auto_format_json -v
```

Integration tests call the real NotebookLM API. They require a `.nlm/config.json` at `/tmp/nlm-test` and valid auth at `~/.notebooklm/storage_state.json`.

---

## Three-Way Sync Requirement

**Three locations must always be kept in sync:**

| Location | Role |
|----------|------|
| This repo (`~/Code/NotebookLM SKILL/marine-notebooklm-skill/`) | Source of truth — all edits go here first |
| `~/.claude/skills/` | Local runtime — what Claude Code actually loads |
| GitHub (`main` branch) | Remote backup + sharing |

**Workflow:** Edit here → deploy locally (see below) → commit + push to GitHub.
Never edit `~/.claude/skills/` directly; changes there will be lost on next deploy.

---

## Deploying to `~/.claude/skills/nlm/`

The skill must be synced to the Claude skills directory to be usable in Claude Code:

```bash
# Sync scripts/ and skills/ subdirectories (mirrors project → ~/.claude/skills/nlm/)
rsync -av --delete scripts/ ~/.claude/skills/nlm/scripts/
rsync -av --delete skills/  ~/.claude/skills/nlm/skills/

# Sync flat SKILL.md files to ~/.claude/skills/<skill-name>/
for skill in nlm-ask nlm-plan nlm-research nlm-add nlm-setup nlm-migrate; do
  cp skills/$skill/SKILL.md ~/.claude/skills/$skill/SKILL.md
done
# Top-level nlm skill
cp SKILL.md ~/.claude/skills/nlm/SKILL.md
```

---

## Architecture

```
scripts/
  invoke.sh         # Entry point: resolves symlinks, activates venv, calls nlm.py
  nlm.py            # CLI dispatcher — 6 subcommands: ask, plan, research, add, setup, migrate
  lib/
    client.py       # NotebookLM API wrapper (Playwright/patchright HTTP calls)
    registry.py     # Config: load/save local (.nlm/config.json) + global (~/.nlm/global.json); override root with NLM_HOME env var
    auth.py         # Cookie-based auth via real Chrome (patchright channel="chrome")
    auth_helper.py  # Shared auth utilities
    answer_analyzer.py   # Confidence scoring (high/medium/low/not_found)
    depth_decider.py     # Maps --depth fast/deep to timeouts
    domain_router.py     # auto-scope: local-first, escalate to global on low confidence
    notebook_registry.py # Notebook list cache
    project_detector.py  # Walk up dirs to find .nlm/config.json
    skill_context.py     # Shared runtime context
    source_selector.py   # Picks sources for research --add-sources
    card_writer.py       # Formats output cards

skills/
  nlm/              # Top-level SKILL.md (combined reference for Claude)
  nlm-ask/          # Per-subcommand SKILL.md files (these are what Claude Code loads)
  nlm-plan/
  nlm-research/
  nlm-add/
  nlm-setup/
  nlm-migrate/
```

**Two-tier notebook model:**
- **Local** — per-project `.nlm/config.json` with one `local_notebook_id`; read+write
- **Global** — `~/.nlm/global.json` with `global_notebook_ids[]`; read-only during dev

**Query routing (`--scope auto`):** `domain_router.py` queries local first; if confidence is `low` or `not_found`, falls back to global notebooks.

---

## Gotchas

- **`NLM_HOME`** — Set this env var to override the global config root (default `~/.nlm/`). Useful for isolated testing.
- **`tests/` is gitignored** — Tests exist in this repo but are not synced to the deployed skill at `~/.claude/skills/nlm/`. Run tests from this repo directory only.
- **`data/`** — Contains local dev artifacts (`auth_info.json`, `browser_state/`). Not part of the deployed skill.

---

## nlm — Quick Reference

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

| Intent | Command |
|--------|---------|
| Check auth | `$INVOKE setup --auth` |
| Quick question | `$INVOKE ask --question "..." --project-path "." --format json` |
| Compare options | `$INVOKE plan --question "..." --options "A,B" --project-path "."` |
| Research (default: adds sources) | `$INVOKE research --topic "..." --project-path "."` |
| Research (read-only) | `$INVOKE research --topic "..." --no-add-sources --project-path "."` |
| Add URL to notebook | `$INVOKE add --url URL --project-path "."` |
| Add note to notebook | `$INVOKE add --note "..." --title "..." --project-path "."` |
| Init project | `$INVOKE setup --project-path "."` |
| Migrate to global | `$INVOKE migrate --content "..." --target-global "domain"` |

## Auto-trigger rules

| Command | Auto-trigger? |
|--------|--------------|
| `ask` | ✅ Yes — on knowledge uncertainty |
| `plan` | ✅ Yes — when evaluating 2+ options |
| `research` (default: adds sources) | ✅ Yes — default behavior writes sources to local notebook |
| `research --no-add-sources` | ✅ Yes — when dispatched as subagent or user wants read-only |
| `add` | ❌ User only |
| `setup` | ❌ User only |
| `migrate` | ❌ User only |
