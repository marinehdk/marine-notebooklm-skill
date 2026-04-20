# nlm — NotebookLM Skill for Claude Code

Query curated NotebookLM notebooks for grounded knowledge during coding without breaking context.

## Quick Start

### 1. Authenticate (first time only)
```bash
/nlm-auth
```
Opens your Google account login in a browser. Creates `~/.nlm/auth.json` for all projects.

### 2. Initialize your project (once per project)
```bash
/nlm-setup
```
Lists your NotebookLM notebooks → you select one as the project's local notebook. Saves config to `.nlm/config.json`.

### 3. Start asking questions
```bash
/nlm-ask What is the main pattern used in this codebase?
/nlm-plan Should we use React or Vue?
/nlm-research Deep dive on async/await patterns
```

---

## 7 Available Skills

### `/nlm-auth` — Authenticate with Google
**When:** First time setup, or to switch accounts.  
**User action:** Triggers Google login in browser.  
**Output:** Saves credentials to `~/.nlm/auth.json` (shared across projects).

```bash
# Direct invocation
bash ~/.claude/skills/nlm/scripts/invoke.sh setup --auth
```

---

### `/nlm-ask` — Quick knowledge query
**When:** Uncertain about a concept, API usage, or architecture decision.  
**Auto-trigger:** Yes — when Claude encounters knowledge gaps.  
**User-invoked example:**

```bash
/nlm-ask What does the notebook say about error handling patterns?
/nlm-ask How should I implement caching here?
```

**Behind the scenes (bash command):**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh ask \
  --question "..." \
  --project-path "." \
  --scope auto \
  --format json
```

**Output:**
```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "source_notebook": "local|global",
  "citations": [...]
}
```

**Confidence levels:**
- `high` / `medium` → Use the answer directly
- `low` → Use but tell user to verify
- `not_found` → Notebook has no relevant content; suggest `/nlm-research`

**Scope modes:**
- `auto` (default) — Queries local notebook first; falls back to global if low/not found confidence
- `local` — Project notebook only
- `global` — Domain knowledge notebook only

---

### `/nlm-plan` — Evidence-based option comparison
**When:** Evaluating 2+ technical options (e.g., "use X or Y?").  
**Auto-trigger:** Yes — when user compares options.  
**User-invoked example:**

```bash
/nlm-plan Should we refactor with Strategy or Decorator pattern?
/nlm-plan Monolith vs microservices for this use case?
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh plan \
  --question "..." \
  --options "Option A,Option B,Option C" \
  --criteria "performance,maintainability" \
  --project-path "."
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
**When:** Need to investigate a topic and add sources to your notebook.  
**Auto-trigger:** Yes, but ONLY for read-only mode (`--no-add-sources`).  
**User-triggered mode:** Only when explicitly requested with `--add-sources`.

**Read-only (parallel dispatch, no side effects):**
```bash
/nlm-research --topic "Redis caching patterns" --depth fast
```

**With import (user-triggered only — writes to notebook):**
```bash
/nlm-research --topic "Kubernetes networking" --add-sources
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh research \
  --topic "..." \
  --depth fast|deep \
  --add-sources \
  --project-path "."
```

**Parameters:**
- `--depth fast` — 60 second timeout, quick results
- `--depth deep` — 180 second timeout, thorough research
- `--add-sources` — Import found URLs to local notebook (user-triggered only)
- `--no-add-sources` — Return report without modifying notebook

**Output:**
```json
{
  "status": "completed",
  "topic": "...",
  "report": "Research summary...",
  "sources": ["URL1", "URL2", ...],
  "sources_imported": 3,
  "add_sources": true
}
```

---

### `/nlm-add` — Add knowledge to local notebook
**When:** Found a useful resource or insight to save.  
**Trigger:** User only (explicit request).  
**Never auto-triggered.**

**Add a URL:**
```bash
/nlm-add --url "https://example.com/article"
```

**Add a text note:**
```bash
/nlm-add --note "Key insight: Always validate at system boundaries" --title "Input Validation"
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh add \
  --url "..." \
  --note "..." \
  --title "..." \
  --project-path "."
```

---

### `/nlm-setup` — Initialize or reconfigure project
**When:** First time in a project, or to change notebooks.  
**Trigger:** User only.  
**One-time per project.**

**Interactive setup (lists your notebooks):**
```bash
/nlm-setup
```
→ Choose a notebook → Saves to `.nlm/config.json`

**Direct notebook binding:**
```bash
/nlm-setup --notebook-id "<your-notebook-uuid>"
```

**Create new notebook:**
```bash
/nlm-setup --create "Project Research Notes"
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh setup \
  --project-path "." \
  --notebook-id "<uuid>" \
  --create "Title"
```

**Output:**
```json
{
  "project_name": "my-project",
  "local_notebook_id": "abc123",
  "global_notebook_ids": ["ref1", "ref2"],
  "config_saved": true
}
```

---

### `/nlm-migrate` — Promote knowledge to global notebook
**When:** Found domain knowledge in your project that other projects should reuse.  
**Trigger:** User only (requires explicit confirmation).  
**Never auto-triggered.**

**Example:**
```bash
/nlm-migrate \
  --content "Rate limiting should be implemented at API gateway, not per-service" \
  --target-global "backend-patterns" \
  --title "Rate Limiting Architecture"
```

**Behind the scenes:**
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh migrate \
  --content "..." \
  --target-global "domain-name" \
  --title "..." \
  --project-path "."
```

---

## Two-Tier Notebook Architecture

### Local Notebook
- **Location:** `.nlm/config.json` (project root)
- **Scope:** Project-specific knowledge
- **Permissions:** Read + Write
- **Lifetime:** Same as project
- **Use for:** Project decisions, learnings, research findings

### Global Notebooks
- **Location:** `~/.nlm/global.json`
- **Scope:** Domain knowledge (shared across projects)
- **Permissions:** Read-only (during development)
- **Examples:** "backend-patterns", "react-patterns", "infrastructure"
- **Use for:** Reusable architecture, frameworks, best practices

### Query Routing
- **`--scope auto`** (default) — Queries local first; falls back to global if confidence is `low` or `not_found`
- **`--scope local`** — Project notebook only
- **`--scope global`** — Global notebooks only

---

## Auto-trigger Rules

| Command | Auto-trigger? | When |
|---------|--------------|------|
| `/nlm-ask` | ✅ Yes | Claude encounters knowledge uncertainty |
| `/nlm-plan` | ✅ Yes | User evaluates 2+ options ("should we use X or Y?") |
| `/nlm-research --no-add-sources` | ✅ Yes | Dispatched as parallel research subagent |
| `/nlm-research --add-sources` | ❌ No | User-triggered only (writes to notebook) |
| `/nlm-add` | ❌ No | User-triggered only (writes to notebook) |
| `/nlm-setup` | ❌ No | User-triggered only (configuration) |
| `/nlm-migrate` | ❌ No | User-triggered only (writes globally) |

---

## Use Cases & Examples

### "What's the codebase pattern for X?"
```bash
/nlm-ask What error handling pattern is used in this project?
```
→ Claude auto-triggers → notebook returns evidence → answer informs your code

### "Should we use X or Y?"
```bash
/nlm-plan Should we use dependency injection or factory pattern for services?
```
→ Claude auto-triggers → compares options with notebook evidence → recommendation

### "Deep research on a topic"
```bash
/nlm-research --topic "Event-driven architecture in microservices" --add-sources
```
→ NotebookLM researches → returns report + URLs → you review → sources added to notebook

### "Save a useful resource"
```bash
/nlm-add --url "https://refactoring.guru/design-patterns"
```
→ Added to local notebook → available in future `/nlm-ask` queries

### "Document project learning"
```bash
/nlm-add --note "We chose TypeScript for strict typing" --title "TypeScript Decision"
```
→ Saved to project notebook → grounds future decisions

### "Promote to global knowledge"
```bash
/nlm-migrate \
  --content "Always use dependency injection for testability" \
  --target-global "testing-patterns" \
  --title "DI for Testing"
```
→ Moved to global → reusable across projects

---

## Troubleshooting

### `error: "No notebooks configured"`
→ Run `/nlm-setup` to initialize the project

### `confidence: "not_found"`
→ Your notebook doesn't have relevant content  
→ Suggest: Run `/nlm-research --topic "..." --add-sources` to add sources

### `error: "No auth.json found"`
→ Run `/nlm-auth` to authenticate with Google

### Research times out (30–120 seconds)
→ NotebookLM API is slow; wait up to 180s before reporting failure  
→ Reduce scope if possible (try `--depth fast`)

### `error: "Project path not found"`
→ Ensure you're running commands from project root or specify `--project-path "/path/to/project"`

### Confidence too low
| Confidence | Action |
|-----------|--------|
| `high` | Use answer directly |
| `medium` | Use answer, but mention "verify this" |
| `low` | Don't use; suggest `/nlm-research` |
| `not_found` | Tell user honestly; suggest research |

---

## File Structure

```
~/.claude/skills/nlm/
├── SKILL.md                    # Trigger protocol (Claude Code sees this)
├── CLAUDE.md                   # Quick reference table
├── README.md                   # This file
├── VERIFICATION.md             # End-to-end testing guide
├── scripts/
│   ├── invoke.sh              # Wrapper (resolves symlinks, activates venv)
│   ├── nlm.py                 # Main CLI (6 commands)
│   └── lib/
│       ├── client.py          # NotebookLM client wrapper
│       ├── registry.py        # Notebook config manager
│       └── auth.py            # Authentication flow
├── skills/                     # 6 sub-skill SKILL.md files
│   ├── nlm-ask/SKILL.md
│   ├── nlm-plan/SKILL.md
│   ├── nlm-research/SKILL.md
│   ├── nlm-add/SKILL.md
│   ├── nlm-setup/SKILL.md
│   └── nlm-migrate/SKILL.md
├── tests/
│   └── test_cli.py            # Integration tests
└── .venv/                      # Python virtual environment
```

---

## Authentication & Config Files

### `~/.nlm/auth.json`
Google authentication token (shared across all projects).  
Created by `/nlm-auth`.

### `.nlm/config.json` (project root)
Project-specific configuration:
```json
{
  "project_name": "my-project",
  "local_notebook_id": "abc123...",
  "global_notebook_ids": ["ref1...", "ref2..."]
}
```
Created by `/nlm-setup`.

---

## Environment Variables

The skill uses system Python and its own virtual environment. No additional env vars needed.

If you need to debug:
```bash
# Check if NotebookLM package is installed
python3 -c "import notebooklm; print(notebooklm.__version__)"

# Run CLI directly
bash ~/.claude/skills/nlm/scripts/invoke.sh ask --question "test"
```

---

## Best Practices

1. **Initialize once** — Run `/nlm-setup` when starting a new project
2. **Curate sources** — Add high-quality sources to your local notebook
3. **Research when stuck** — Use `/nlm-research` to expand knowledge
4. **Promote reusable knowledge** — Use `/nlm-migrate` to share patterns
5. **Trust high confidence** — High/medium confidence answers are grounded in your sources
6. **Verify low confidence** — Low/not_found means limited notebook coverage

---

## See Also

- **SKILL.md** — Protocol & detailed command reference
- **CLAUDE.md** — Quick lookup table
- **VERIFICATION.md** — End-to-end testing checklist
- **NotebookLM** — https://notebooklm.google (create & curate sources)
