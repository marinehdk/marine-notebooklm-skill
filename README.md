# nlm — NotebookLM Skill for Claude Code

Query your curated NotebookLM notebooks for grounded knowledge during coding, without breaking your flow.

## Quick Start

### 1. Authenticate (first time only)
```bash
/nlm-setup --auth
```
Opens your **real Chrome browser** at `notebooklm.google.com`. If you're already logged into Google in Chrome, no password needed — just wait for the page to load and authentication is saved automatically.

Session is stored at `~/.notebooklm/storage_state.json` and reused silently on all future calls.

### 2. Initialize your project (once per project)
```bash
/nlm-setup
```
Lists your NotebookLM notebooks → select one as local → optionally add global reference notebooks → saves config to `<project>/.nlm/config.json`.

### 3. Start querying
```bash
/nlm-ask What is the main pattern used in this codebase?
/nlm-plan Should we use Redis or in-memory cache?
/nlm-research Deep dive on async/await patterns
```

---

## 8 Available Skills

### `/nlm-ask` — Quick knowledge query
**When to use:** Uncertain about a concept, API usage, or architecture decision.  
**Auto-trigger:** Yes — when Claude encounters knowledge gaps during coding.

```bash
/nlm-ask What does the notebook say about error handling patterns?
/nlm-ask How should I implement caching here?
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "..." \
  --project-path "$(pwd)" \
  --scope auto \
  --on-low-confidence research \
  --format json
```

**Parameters:**

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The question to ask |
| `--scope` | `auto\|local\|global` | `auto` | `auto` = local first, then fallback to global |
| `--on-low-confidence` | `prompt\|research\|silent` | `research` | `research` = auto fast-research + import + retry; `prompt` = attach hint only; `silent` = return as-is |
| `--format` | `json\|text` | `json` | Output format |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

**Output:**
```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "source_notebook_id": "6c20d15e-...",
  "source_notebook_title": "My Project Notebook",
  "citations": [{"citation_number": 1, "text": "..."}],
  "auto_researched": true,
  "next_action": {
    "type": "suggest_research",
    "message": "...",
    "command": "nlm research --topic \"...\" --add-sources --project-path \".\""
  }
}
```

`auto_researched` is present when `--on-low-confidence research` triggered an automatic research + import cycle.  
`next_action` is only present when confidence is `low`/`not_found` and auto-research was attempted but still insufficient.

**Handling results:**

| confidence | `auto_researched` | `next_action` present? | Action |
|------------|-------------------|------------------------|--------|
| `high` / `medium` | — | No | Use answer directly |
| any | `true` | No | Sources auto-imported; answer reflects new content — use directly |
| `low` / `not_found` | — | Yes (`suggest_research`) | Auto-research ran but still low confidence; tell user, offer manual follow-up |

**Scope modes:**
- `auto` (default) — Local notebook first; falls back to global on low/not_found
- `local` — Project notebook only
- `global` — Global domain notebooks only

---

### `/nlm-plan` — Evidence-based option comparison
**When to use:** Evaluating 2+ technical options ("should we use X or Y?").  
**Auto-trigger:** Yes — when user compares options.

```bash
/nlm-plan Should we refactor with Strategy or Decorator pattern?
/nlm-plan Monolith vs microservices for this use case?
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh plan \
  --question "..." \
  --options "Option A,Option B" \
  --criteria "performance,maintainability" \
  --max-research 3 \
  --project-path "$(pwd)"
```

**Parameters:**

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--question` | text | required | The decision being evaluated |
| `--options` | `"A,B,C"` | required | Comma-separated options to compare |
| `--criteria` | `"x,y,z"` | optional | Evaluation criteria (auto-proposed if omitted) |
| `--max-research` | integer | `3` | Max research calls allowed |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

**Output:**
```json
{
  "recommendation": "Option A",
  "composite_scores": {"Option A": 4.2, "Option B": 3.0},
  "matrix": {
    "Option A": {
      "performance": {"score": 5, "reasoning": "..."},
      "cost": {"score": 3, "reasoning": "...", "evidence_gap": true}
    },
    "Option B": {
      "performance": {"score": 3, "reasoning": "..."},
      "cost": {"score": 2, "reasoning": "..."}
    }
  },
  "rationale": "Option A scored highest overall (4.2 vs 3.0)...",
  "research_used": 2,
  "max_research": 3,
  "evidence_gaps": ["Option B / cost"]
}
```

**Score scale:**

| Score | Meaning |
|-------|---------|
| 5 | Excellent |
| 4 | Good |
| 3 | Average |
| 2 | Below average |
| 1 | Poor |

**Research escalation:** When notebook evidence is low confidence for an option, `nlm-plan` automatically runs research (fast → deep if still insufficient). `research_used` shows calls made; `evidence_gaps` lists option/criterion pairs uncovered within `--max-research`.

**Field reference:**

| Field | Always present | Description |
|-------|---------------|-------------|
| `recommendation` | ✅ | Option with highest composite score |
| `composite_scores` | ✅ | Per-option mean of valid scores (1 decimal) |
| `matrix` | ✅ | Per-option, per-criterion scores and reasoning |
| `rationale` | ✅ | One-sentence justification for recommendation |
| `research_used` | ✅ | Number of research calls made |
| `max_research` | ✅ | The `--max-research` cap used |
| `evidence_gaps` | ✅ | List of `"option / criterion"` pairs with no evidence |
| `evidence_gap` | On matrix entry | Research cap exhausted before covering this pair |
| `parse_warning` | On matrix entry | Score format not parseable; score=null |

---

### `/nlm-research` — Deep research with automatic source import
**When to use:** Investigate a topic and add found sources to your notebook.  
**Auto-trigger:** Yes (default `--add-sources`). Use `--no-add-sources` only for read-only lookups.

```bash
/nlm-research Redis caching patterns
/nlm-research --topic "Kubernetes networking" --depth deep
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh research \
  --topic "..." \
  --depth fast|deep \
  --add-sources \
  --project-path "$(pwd)"
```

**Parameters:**
- `--depth fast` — 60s timeout
- `--depth deep` — 180s timeout
- `--add-sources` (default) — Import found URLs into local notebook automatically
- `--no-add-sources` — Return report only, no writes

---

### `/nlm-add` — Add knowledge to local notebook
**When to use:** Save a useful URL or text insight to your project notebook.  
**Trigger:** User only. Never auto-triggered.

```bash
/nlm-add --url "https://example.com/article"
/nlm-add --note "Key insight: Always validate at system boundaries" --title "Input Validation"
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh add \
  --url "..." \
  --project-path "$(pwd)"

bash ~/.claude/skills/nlm/scripts/invoke.sh add \
  --note "..." --title "..." \
  --project-path "$(pwd)"
```

**Output:**
```json
// URL added successfully
{"status": "ok", "type": "url", "source": {"id": "...", "title": "..."}}

// URL already exists (silently skipped — no duplicate added)
{"status": "skipped", "reason": "already_exists", "source": {"id": "...", "title": "..."}}

// Note added successfully
{"status": "ok", "type": "note", "note": {"id": "...", "title": "..."}}
```

---

### `/nlm-delete` — Delete a source from local notebook
**When to use:** Remove a specific source by URL or source ID.  
**Trigger:** User only. Never auto-triggered.

```bash
/nlm-delete --url "https://example.com/article"
/nlm-delete --source-id "abc123xyz"
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh delete \
  --url "..." \
  --project-path "$(pwd)"

bash ~/.claude/skills/nlm/scripts/invoke.sh delete \
  --source-id "..." \
  --project-path "$(pwd)"
```

**Output:**
```json
// Success
{"status": "ok", "deleted": {"id": "...", "title": "..."}}

// Not found
{"status": "not_found", "key": "https://..."}
```

URL matching is case-insensitive and ignores trailing slashes.

---

### `/nlm-deduplicate` — Remove duplicate sources from a notebook
**When to use:** Manually clean up duplicate URL sources in any notebook.  
**Trigger:** User only. Never auto-triggered.

> Note: `/nlm-research` already deduplicates automatically after each import. Use this skill for one-off manual cleanup.

```bash
/nlm-deduplicate
/nlm-deduplicate --notebook-id "6c20d15e-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**Behind the scenes:**
```bash
# Current project's notebook
bash ~/.claude/skills/nlm/scripts/invoke.sh deduplicate \
  --project-path "$(pwd)"

# Any notebook by ID (no project config needed)
bash ~/.claude/skills/nlm/scripts/invoke.sh deduplicate \
  --notebook-id "6c20d15e-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
```

**Parameters:**

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--notebook-id` | UUID | — | Target notebook directly (overrides `--project-path`) |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

**Output:**
```json
{"status": "ok", "notebook_id": "6c20d15e-...", "removed": 3, "kept": 12}
```

Keeps the oldest source per URL; deletes the rest.

---

### `/nlm-setup` — Initialize or reconfigure project
**When to use:** First time in a project, changing notebooks, or re-authenticating.  
**Trigger:** User only.

```bash
# View current binding (no API call)
/nlm-setup

# Authenticate (opens Chrome browser)
/nlm-setup --auth

# Re-authenticate (clears saved session)
/nlm-setup --reauth

# List all notebooks in account (24h cached)
/nlm-setup --notebook-list

# Force refresh notebook list
/nlm-setup --notebook-list --refresh

# Bind an existing notebook as local
/nlm-setup --add-local-notebook <UUID>

# Add one or more global reference notebooks
/nlm-setup --add-global-notebook <UUID1> <UUID2>

# Create new notebook and bind as local
/nlm-setup --create-local "Project Research Notes"

# Create new notebook and add as global
/nlm-setup --create-global "Domain Patterns"
```

**Standard init flow (3 steps):**
1. Run `--notebook-list` → presents a table with `#`, `UUID`, `Title`, `Sources`, `Created`
2. Select a notebook as local → run `--add-local-notebook <UUID>`
3. Optionally add global reference notebooks → run `--add-global-notebook <UUID1> ...`

**Auth flow:** Uses `patchright` with `channel="chrome"` to launch your real Chrome browser. Google sees a genuine browser — no Bluetooth/passkey prompts. Session saved to `~/.notebooklm/storage_state.json`.

---

### `/nlm-migrate` — Promote knowledge to global notebook
**When to use:** Found domain knowledge in your project that other projects should reuse.  
**Trigger:** User only. Always confirms before writing.

```bash
/nlm-migrate \
  --content "Rate limiting should be implemented at API gateway, not per-service" \
  --target-global "backend-patterns" \
  --title "Rate Limiting Architecture"
```

---

## Auto-trigger Rules

| Command | Auto-trigger? | When |
|---------|--------------|------|
| `/nlm-ask` | ✅ Yes | Claude encounters knowledge uncertainty |
| `/nlm-plan` | ✅ Yes | User evaluates 2+ options |
| `/nlm-research` (default: `--add-sources`) | ✅ Yes | Default behavior; sources imported automatically |
| `/nlm-research --no-add-sources` | ✅ Yes | Read-only parallel subagent dispatch |
| `/nlm-add` | ❌ No | User-triggered only (writes to notebook) |
| `/nlm-delete` | ❌ No | User-triggered only (deletes from notebook) |
| `/nlm-deduplicate` | ❌ No | User-triggered only (manual cleanup) |
| `/nlm-setup` | ❌ No | User-triggered only (configuration) |
| `/nlm-migrate` | ❌ No | User-triggered only (writes globally) |

---

## Two-Tier Notebook Architecture

### Local Notebook (per project)
- **Config:** `<project-root>/.nlm/config.json`
- **Permissions:** Read + Write
- **Use for:** Project decisions, research findings, notes

### Global Notebooks (shared)
- **Config:** `~/.nlm/global.json`
- **Permissions:** Read-only during development
- **Use for:** Reusable domain knowledge across projects

### Query Routing
- `auto` (default) — Local first; escalates to global on `low`/`not_found`
- `local` — Project notebook only
- `global` — Global notebooks only

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No notebooks configured` | Run `/nlm-setup` |
| `confidence: not_found` | Run `/nlm-research --topic "..."` (sources auto-imported) |
| `Not authenticated` | Run `/nlm-setup --auth` |
| Session expired (7+ days) | Run `/nlm-setup --reauth` |
| Research timeout | Try `--depth fast` instead of `deep` |

---

## File Structure

```
~/.claude/skills/nlm/
├── README.md                   # This file
├── scripts/
│   ├── invoke.sh               # Wrapper (resolves symlinks, activates venv)
│   ├── nlm.py                  # Main CLI (8 commands)
│   └── lib/
│       ├── client.py           # NotebookLM API wrapper (Playwright/patchright)
│       ├── registry.py         # Config: local (.nlm/config.json) + global (~/.nlm/global.json)
│       ├── auth.py             # Cookie-based auth via real Chrome (patchright channel="chrome")
│       ├── auth_helper.py      # Shared auth utilities
│       ├── answer_analyzer.py  # Confidence scoring (high/medium/low/not_found)
│       ├── confidence_handler.py # --on-low-confidence logic (research/prompt/silent)
│       ├── depth_decider.py    # Maps --depth fast/deep to timeouts
│       ├── domain_router.py    # auto-scope: local-first, escalate to global on low confidence
│       ├── notebook_registry.py # Notebook list cache (24h TTL)
│       ├── notebook_router.py  # Routes ask queries across multiple global notebooks
│       ├── plan_evaluator.py   # 1-5 score matrix, composite scores, research escalation
│       ├── project_detector.py # Walk up dirs to find .nlm/config.json
│       ├── skill_context.py    # Shared runtime context
│       ├── source_selector.py  # Picks sources for research --add-sources
│       └── card_writer.py      # Formats output cards
├── skills/                     # Canonical SKILL.md sources
│   ├── nlm-ask/SKILL.md
│   ├── nlm-plan/SKILL.md
│   ├── nlm-research/SKILL.md
│   ├── nlm-add/SKILL.md
│   ├── nlm-delete/SKILL.md
│   ├── nlm-deduplicate/SKILL.md
│   ├── nlm-setup/SKILL.md
│   └── nlm-migrate/SKILL.md
└── .venv/

~/.claude/skills/
├── nlm-ask/SKILL.md            # Flat skill (Claude Code invocable)
├── nlm-plan/SKILL.md
├── nlm-research/SKILL.md
├── nlm-add/SKILL.md
├── nlm-delete/SKILL.md
├── nlm-deduplicate/SKILL.md
├── nlm-setup/SKILL.md
└── nlm-migrate/SKILL.md

~/.notebooklm/
├── storage_state.json          # Google auth cookies (shared across projects)
└── chrome_profile/             # Persistent Chrome profile for patchright

<project-root>/
└── .nlm/config.json            # { local_notebook_id, global_notebook_ids[] }
```
