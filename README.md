# nlm — NotebookLM Skill for Claude Code

Query your curated NotebookLM notebooks for grounded knowledge during coding, without breaking your flow. Supports a three-tier multi-notebook architecture for large-scale research projects.

## Quick Start

### 1. Authenticate (first time only)
```bash
/nlm-setup --auth
```
Opens your **real Chrome browser** at `notebooklm.google.com`. Session saved to `~/.notebooklm/storage_state.json`.

### 2. Initialize your project (once per project)
```bash
/nlm-setup
```
Lists your NotebookLM notebooks → select one → saves config to `<project>/.nlm/config.json`.

### 3. Start querying and researching
```bash
/nlm-ask What navigation algorithm does the notebook recommend?
/nlm-research COLREGS collision avoidance for ASV
/nlm-plan Should we use A* or RRT for path planning?
```

---

## Three-Tier Architecture

For large research projects where a single 300-source notebook isn't enough.

```
L3  GLOBAL · {Domain} · Reference       (cross-project universal knowledge)
         ↑ distillation
L2  META · {Project} · Synthesis         (cross-domain synthesis)
         ↑ distillation
L1  DOMAIN · {Topic} · Research          (single-domain deep research, 300 sources each)
    PROJ · {Project} · Local             (project-specific notes)
```

### Notebook Naming Convention

**Format: `{SCOPE} · {Name} · {Type}`**

| SCOPE | Purpose | Type |
|-------|---------|------|
| `PROJ` | Project-specific knowledge | `Local` |
| `DOMAIN` | Single-domain deep research | `Research` |
| `META` | Cross-domain synthesis (sources = Briefing Docs) | `Synthesis` |
| `GLOBAL` | Universal long-term reference | `Reference` |

Examples:
- `PROJ · MASS-L3 · Local`
- `DOMAIN · Navigation Algorithms · Research`
- `META · ASV Research · Synthesis`
- `GLOBAL · Maritime Engineering · Reference`

---

## Available Skills

### `/nlm-ask` — Query notebooks for grounded answers

**Triggered by:** Main session Claude or background Agent.  
**Writes:** Nothing — always read-only.

```bash
/nlm-ask What does the notebook say about COLREGS Rule 8?
/nlm-ask How should I implement collision avoidance here?
```

**`--scope` routing:**

| Scope | Behavior |
|-------|----------|
| `auto` | Classify question → domain → local → global → synthesis |
| `local` | Project local notebook only |
| `global` | Route among global notebooks (Haiku-ranked) |
| `synthesis` | META synthesis notebook |
| `domain:<key>` | Specific domain notebook (e.g. `domain:navigation_algorithms`) |

**Output:**
```json
{
  "answer": "...",
  "confidence": "high|medium|low|not_found",
  "answered_by": ["domain:navigation_algorithms", "local"],
  "citations": [...],
  "suggest_research": false
}
```

When `suggest_research: true`, run `/nlm-research` on the topic first, then re-ask.

---

### `/nlm-research` — Research + knowledge accumulation

**Triggered by:** Main session Claude or background Agent.  
**Writes:** Sources into the correct notebook (determined by `--target auto`).

```bash
# Research + auto-route sources to matching domain notebook
/nlm-research COLREGS collision avoidance maritime autonomous vessel

# Read-only research (no source import — for subagent dispatch)
/nlm-research --no-add-sources underwater acoustic communication

# Explicit domain routing
/nlm-research --target domain:navigation_algorithms path planning RRT*
```

**`--target` routing:**

| Target | Behavior |
|--------|----------|
| `auto` | Classify topic → domain notebook; no match → local; new domain → advisory only |
| `local` | Project local notebook |
| `synthesis` | META synthesis notebook |
| `domain:<key>` | Specific domain notebook |

**Auto-routing flow:**
```
Topic classified → domain matched → import to domain notebook
                 → no domain match (low score) → import to local
                 → new domain suggested → import to local + output domain_suggestion
```

**Output includes new routing fields:**
```json
{
  "target_notebook": "domain:navigation_algorithms",
  "sources_imported": 8,
  "notebook_source_count": 53,
  "domain_suggestion": null,
  "merge_suggestions": [],
  "split_suggestions": []
}
```

When `domain_suggestion` is present, run `/nlm-setup --create-domain` to register the new domain.

---

### `/nlm-setup` — Configure notebooks

**Trigger:** User only.

```bash
# View full configuration (all tiers)
/nlm-setup

# Authenticate
/nlm-setup --auth
/nlm-setup --reauth

# List and bind notebooks
/nlm-setup --notebook-list
/nlm-setup --add-local-notebook <UUID>
/nlm-setup --create-local "PROJ · My Project · Local"

# Create domain notebook (L1 DOMAIN tier)
/nlm-setup \
  --create-domain "DOMAIN · Navigation Algorithms · Research" \
  --domain-key navigation_algorithms \
  --domain-keywords "path planning,collision avoidance,COLREGS,LiDAR,SLAM"

# Create synthesis notebook (L2 META tier)
/nlm-setup --create-synthesis "META · ASV Research · Synthesis"

# Add global reference notebook (L3 GLOBAL tier)
/nlm-setup --add-global-notebook <UUID>
```

---

### `/nlm-plan` — Evidence-based option comparison

```bash
/nlm-plan Should we use A* or RRT for ASV path planning?
/nlm-plan FastDDS vs Zenoh for middleware?
```

---

### `/nlm-add` — Add knowledge manually

```bash
/nlm-add --url "https://example.com/paper"
/nlm-add --note "Key insight: COLREGS Rule 8 requires..." --title "COLREGS Notes"
```

---

### `/nlm-migrate` — Promote to global notebook

```bash
/nlm-migrate \
  --content "ESKF outperforms EKF for..." \
  --target-global "maritime-engineering" \
  --title "Sensor Fusion Findings"
```

---

## Domain Granularity Control

The system automatically tracks domain health and suggests adjustments.

**Optimal range:** 5–15 domain notebooks (production benchmark from Graph RAG in the Wild).

**Three-gate creation policy** — when `/nlm-research --target auto` finds a new domain:

| Gate | Condition | Action |
|------|-----------|--------|
| 1 | `source_count < 20` | Route to local; accumulate more first |
| 2 | keyword overlap ≥ 40% with existing domain | Route to existing domain |
| 3 | `total_domains ≥ 15` | Route to synthesis; review existing domains |

**Automatic suggestions** (appear in `/nlm-research` output):
- `merge_suggestions` — two domains with >40% keyword overlap + combined < 200 sources
- `split_suggestions` — domain with > 200 sources
- `domain_suggestion` — new domain detected (advisory; create with `/nlm-setup --create-domain`)

---

## Distillation Workflow (when a domain notebook > 270 sources)

1. In NotebookLM UI: generate **Briefing Document** for the full domain notebook
2. Download/copy the text
3. Add to synthesis notebook as a distilled source:
   ```bash
   INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
   $INVOKE add --note "<Briefing Doc content>" \
               --title "Navigation Algorithms Briefing 2026-04" \
               --target synthesis \
               --project-path "."
   ```

This converts 300 raw sources into a single high-signal document in the META layer.

---

## Auto-trigger Rules

| Skill | Auto-trigger? | When |
|-------|--------------|------|
| `/nlm-ask` | ✅ Yes | Knowledge uncertainty during coding |
| `/nlm-plan` | ✅ Yes | User evaluates 2+ options |
| `/nlm-research --no-add-sources` | ✅ Yes | Read-only subagent dispatch |
| `/nlm-research --add-sources` | ❌ No | User-triggered (writes) |
| `/nlm-add` | ❌ No | User-triggered (writes) |
| `/nlm-setup` | ❌ No | User-triggered (configuration) |
| `/nlm-migrate` | ❌ No | User-triggered (writes globally) |

---

## Config Schema v2 (`.nlm/config.json`)

```json
{
  "local_notebook": {
    "id": "<uuid>", "title": "PROJ · MASS-L3 · Local", "source_count": 0
  },
  "global_notebooks": [
    {"id": "<uuid>", "title": "GLOBAL · Maritime Engineering · Reference"}
  ],
  "synthesis_notebook": {
    "id": "<uuid>", "name": "META · ASV Research · Synthesis",
    "source_count": 0, "last_distilled": null
  },
  "domain_notebooks": {
    "navigation_algorithms": {
      "id": "<uuid>",
      "name": "DOMAIN · Navigation Algorithms · Research",
      "description": "路径规划、避碰、COLREGS、感知融合",
      "keywords": ["path planning", "collision avoidance", "COLREGS", "LiDAR"],
      "source_count": 0,
      "last_distilled": null
    }
  }
}
```

---

## Troubleshooting

| Error | Fix |
|-------|-----|
| `No notebooks configured` | Run `/nlm-setup` |
| `confidence: not_found` + `suggest_research: true` | Run `/nlm-research --topic "..."` first |
| `Not authenticated` | Run `/nlm-setup --auth` |
| Session expired | Run `/nlm-setup --reauth` |
| `domain_suggestion` in research output | Run `/nlm-setup --create-domain` to register new domain |
| `merge_suggestions` in output | Run `nlm setup --merge-domain ... --into ...` (future) |

---

## File Structure

```
~/.claude/skills/nlm/
├── README.md
├── docs/
│   └── DESIGN_SPEC_V1.md           # Full design spec
├── scripts/
│   ├── invoke.sh                    # Wrapper (venv + entry)
│   ├── nlm.py                       # Main CLI (9 commands)
│   └── lib/
│       ├── client.py               # NotebookLM API wrapper
│       ├── registry.py             # Config I/O (v1 + v2 schema)
│       ├── domain_classifier.py    # Keyword-based topic→domain routing
│       ├── domain_guard.py         # Three-gate creation guard + merge/split
│       ├── notebook_router.py      # Claude Haiku global notebook ranking
│       ├── confidence_handler.py   # Low-confidence post-processing
│       ├── topic_tracker.py        # Relevance scoring profile
│       ├── plan_evaluator.py       # Option comparison
│       └── auth.py                 # Chrome auth via patchright
├── skills/
│   ├── nlm-ask/SKILL.md
│   ├── nlm-research/SKILL.md
│   ├── nlm-setup/SKILL.md
│   ├── nlm-plan/SKILL.md
│   ├── nlm-add/SKILL.md
│   └── nlm-migrate/SKILL.md
└── .venv/

<project-root>/.nlm/
├── config.json          # Notebook bindings (v2 schema with domain_notebooks)
├── topics.json          # Topic profile for relevance scoring
└── notebooks_cache.json # 24h notebook metadata cache
```
