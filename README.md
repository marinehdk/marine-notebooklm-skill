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
Lists your NotebookLM notebooks → select one → saves config to `<project>/.nlm/config.json`.

### 3. Start querying
```bash
/nlm-ask What is the main pattern used in this codebase?
/nlm-plan Should we use Redis or in-memory cache?
/nlm-research Deep dive on async/await patterns
```

---

## 6 Available Skills

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
  --format json
```

**Output:**
```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "citations": [{"citation_number": 1, "text": "..."}]
}
```

**Confidence levels:**
| Level | Action |
|-------|--------|
| `high` / `medium` | Use the answer directly |
| `low` | Use with caution, tell user to verify |
| `not_found` | Notebook has no relevant content — suggest `/nlm-research` |

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
  --project-path "$(pwd)"
```

**Output:**
```json
{
  "recommendation": "Option A",
  "rationale": "Based on notebook evidence...",
  "matrix": {
    "Option A": {"performance": "high", "maintainability": "medium"},
    "Option B": {"performance": "medium", "maintainability": "high"}
  }
}
```

---

### `/nlm-research` — Deep research with optional import
**When to use:** Investigate a topic; optionally add found sources to notebook.  
**Auto-trigger:** Read-only mode only (`--no-add-sources`). Never auto-triggered with `--add-sources`.

**Read-only (no side effects):**
```bash
/nlm-research Redis caching patterns
```

**With import (explicit user request only — writes to notebook):**
```bash
/nlm-research --topic "Kubernetes networking" --add-sources
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh research \
  --topic "..." \
  --depth fast|deep \
  --add-sources | --no-add-sources \
  --project-path "$(pwd)"
```

**Parameters:**
- `--depth fast` — 60s timeout
- `--depth deep` — 180s timeout
- `--add-sources` — Import found URLs into local notebook (user-triggered only)
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

---

### `/nlm-setup` — Initialize or reconfigure project
**When to use:** First time in a project, changing notebooks, or re-authenticating.  
**Trigger:** User only.

```bash
# Authenticate (opens Chrome browser)
/nlm-setup --auth

# List notebooks and select one
/nlm-setup

# Direct binding
/nlm-setup --notebook-id "<uuid>"

# Create new notebook
/nlm-setup --create "Project Research Notes"

# Re-authenticate (clears saved session)
/nlm-setup --reauth
```

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
| `/nlm-research --no-add-sources` | ✅ Yes | Parallel subagent research dispatch |
| `/nlm-research --add-sources` | ❌ No | User-triggered only (writes to notebook) |
| `/nlm-add` | ❌ No | User-triggered only (writes to notebook) |
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
| `confidence: not_found` | Run `/nlm-research --topic "..." --add-sources` |
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
│   ├── nlm.py                  # Main CLI (6 commands)
│   └── lib/
│       ├── client.py           # NotebookLM API wrapper
│       ├── registry.py         # Notebook config manager
│       └── auth.py             # Chrome browser auth via patchright
├── skills/                     # Canonical SKILL.md sources
│   ├── nlm-ask/SKILL.md
│   ├── nlm-plan/SKILL.md
│   ├── nlm-research/SKILL.md
│   ├── nlm-add/SKILL.md
│   ├── nlm-setup/SKILL.md
│   └── nlm-migrate/SKILL.md
└── .venv/

~/.claude/skills/
├── nlm-ask/SKILL.md            # Flat skill (Claude Code invocable)
├── nlm-plan/SKILL.md
├── nlm-research/SKILL.md
├── nlm-add/SKILL.md
├── nlm-setup/SKILL.md
└── nlm-migrate/SKILL.md

~/.notebooklm/
├── storage_state.json          # Google auth cookies (shared across projects)
└── chrome_profile/             # Persistent Chrome profile for patchright

<project-root>/
└── .nlm/config.json            # { local_notebook_id, global_notebook_ids[] }
```
