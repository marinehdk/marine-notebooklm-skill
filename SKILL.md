---
name: nlm
description: >
  Query NotebookLM notebooks for knowledge grounded in your curated sources.
  USE when: uncertain about a concept/API/pattern; user asks "what does my notebook say";
  evaluating 2+ technical options with evidence; dispatched as parallel research subagent.
  DO NOT USE for: general web search (use firecrawl); local file search (use grep);
  code generation without knowledge lookup need.
  WRITE ops (research --add-sources, add, migrate, setup): only on explicit user request.
allowed-tools:
  - Bash
---

# nlm — NotebookLM Skill

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

## Session start: check auth once

```bash
$INVOKE setup --auth
```
If `authenticated: false` → tell user to run `notebooklm login` in terminal and retry.

## ask — Quick knowledge query

```bash
$INVOKE ask --question "<question>" --project-path "." --scope auto --format json
```

Output: `{ answer, confidence, source_notebook, citations[] }`

**Auto-routing:** `--scope auto` queries local notebook first; if confidence is `low` or `not_found`, falls back to global notebooks.

**On confidence:**
- `high` / `medium` → use the answer
- `low` → use but warn user to verify
- `not_found` → tell user honestly; suggest `/nlm-research`

## plan — Evidence-based option comparison

```bash
$INVOKE plan --question "<decision>" --options "A,B,C" [--criteria "x,y,z"] --project-path "."
```

Output: `{ recommendation, rationale, matrix, raw_answers }`

## research — Deep research (TWO MODES)

**Read-only (Agent may auto-trigger for parallel dispatch):**
```bash
$INVOKE research --topic "<topic>" --depth fast --no-add-sources --project-path "."
```

**With source import (user-triggered only — writes to notebook):**
```bash
$INVOKE research --topic "<topic>" --depth fast --add-sources --project-path "."
```

Research takes 30–120s. Do not timeout prematurely.

## add — Manual write to local notebook

```bash
$INVOKE add --url "<URL>" --project-path "."
$INVOKE add --note "<insight>" --title "<title>" --project-path "."
```

**User-triggered only.** Never auto-invoke.

## setup — Project initialization

```bash
# 1. Auth (first time only)
$INVOKE setup --auth

# 2. List all notebooks in your account
$INVOKE setup --notebook-list

# 3. Create or bind notebooks for this project (4-tier architecture):
#    PROJ · Local: project-specific knowledge (one per project)
$INVOKE setup --create-local "MASS-L3"
#    or bind existing: $INVOKE setup --add-local-notebook <UUID>

#    DOMAIN · Research: single-topic deep research (5–15 per project)
$INVOKE setup --create-domain "COLAV Algorithms" \
              --domain-key colav_algorithms \
              --domain-keywords "collision avoidance,COLREGs,MPC,path planning"

#    META · Synthesis: cross-domain briefings (one per project)
$INVOKE setup --create-synthesis "MASS-L3 Research"

#    GLOBAL · Reference: cross-project stable knowledge (bind from existing)
$INVOKE setup --add-global-notebook <UUID>

# 4. Check current config
$INVOKE setup --status
```

Run once per project (or when adding a new tier). Config saved to `.nlm/config.json`.

## delete — Remove a source from local notebook

```bash
$INVOKE delete --url "https://example.com/article" --project-path "."
$INVOKE delete --source-id "<id>" --project-path "."
```

**User-triggered only.** Never auto-invoke.

## deduplicate — Remove duplicate URL sources

```bash
$INVOKE deduplicate --project-path "."
```

**User-triggered only.** Removes duplicate URL sources from the local notebook, keeping the oldest per URL.

## migrate — Promote knowledge to global notebook

```bash
$INVOKE migrate --content "<knowledge>" --target-global "<domain>" --title "<title>"
```

**User-triggered only. Requires explicit confirmation before running.**

## Error handling

- `"error": "No notebooks configured"` → run `setup` first
- `confidence: not_found` → notebook lacks relevant content, suggest research
- Research timeout → NotebookLM API is slow, wait up to 180s before reporting failure
