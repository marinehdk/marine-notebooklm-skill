# NLM Multi-Tier Knowledge System — Design Spec v1.0

**Status:** Implemented  
**Date:** 2026-04-28  
**Confidence:** 🟢 High (based on OG-RAG arxiv:2412.15235, ACL 2025 Hierarchical RAG, Dynamic Taxonomy Construction OpenReview, Graph RAG in the Wild)

---

## 1. Design Goals & Constraints

| Constraint | Value |
|------------|-------|
| Sources per notebook | 300 (Pro) |
| Max notebooks | 500 (Pro, tested) |
| Target domain count | **5–15** (Graph RAG in the Wild production benchmark) |
| Trigger method | Main session Claude AND background Agent — **identical bash invoke** |
| New domain creation threshold | ≥ 20 sources (OG-RAG granularity principle) |

---

## 2. Three-Tier Architecture

```
┌──────────────────────────────────────────────────────┐
│  L3  GLOBAL · {Domain} · Reference                   │
│      Cross-project universal knowledge, stable        │
└──────────────────────────┬───────────────────────────┘
                           │ distillation input
┌──────────────────────────▼───────────────────────────┐
│  L2  META · {Project} · Synthesis                    │
│      Cross-domain synthesis; sources = Briefing Docs │
└───┬──────────────┬──────────────┬───────────────┬────┘
    │distil        │distil        │distil         │distil
┌───▼──────┐ ┌────▼──────┐ ┌────▼──────┐  ┌─────▼────┐
│L1 DOMAIN·│ │L1 DOMAIN· │ │L1 PROJ·   │  │L1 DOMAIN·│
│Nav Algo· │ │Regulations│ │MASS-L3·   │  │...       │
│Research  │ │·Research  │ │Local      │  │          │
│(深度挖掘) │ │(深度挖掘)  │ │(项目特定)  │  │          │
└──────────┘ └───────────┘ └───────────┘  └──────────┘
```

---

## 3. Notebook Naming Convention

**Format: `{SCOPE} · {Name} · {Type}`**

| SCOPE | Purpose | Type |
|-------|---------|------|
| `PROJ` | Project-specific knowledge, not shared | `Local` |
| `DOMAIN` | Single-domain deep research, sharable | `Research` |
| `META` | Cross-domain synthesis, sources = distilled docs | `Synthesis` |
| `GLOBAL` | Universal long-term reference | `Reference` |

Rules:
- Name segment ≤ 25 chars, TitleCase English or concise Chinese
- No date suffixes (use `last_distilled` field)
- No version suffixes (notebooks are living documents)

---

## 4. Config Schema v2 (`.nlm/config.json`)

```json
{
  "local_notebook": {
    "id": "<uuid>",
    "title": "PROJ · MASS-L3 · Local",
    "source_count": 0
  },
  "global_notebooks": [
    {"id": "<uuid>", "title": "GLOBAL · Maritime Engineering · Reference"}
  ],
  "synthesis_notebook": {
    "id": "<uuid>",
    "name": "META · ASV Research · Synthesis",
    "source_count": 0,
    "last_distilled": null
  },
  "domain_notebooks": {
    "navigation_algorithms": {
      "id": "<uuid>",
      "name": "DOMAIN · Navigation Algorithms · Research",
      "description": "路径规划、避碰、COLREGS、感知融合、控制律",
      "keywords": ["path planning", "collision avoidance", "COLREGS", "LiDAR", "SLAM"],
      "source_count": 0,
      "last_distilled": null
    }
  }
}
```

---

## 5. Domain Granularity Control

**Principle (OG-RAG):** A domain = a set of questions answerable by the same source pool, not a topic category.

**Target:** 5–15 domain notebooks (Graph RAG in the Wild production data).

### 5.1 Three-Gate Creation Policy

```
When a new domain is requested:

Gate 1 — Minimum source queue (source_count < 20)
  → Route to local; accumulate more sources first

Gate 2 — Keyword overlap with existing domain (overlap ≥ 40%)
  → Route to closest existing domain; suggest keyword update

Gate 3 — Total domain cap (total_domains ≥ 15)
  → Route to synthesis; flag for manual review

All gates pass → Create domain (user confirmation required)
```

Implemented in: `scripts/lib/domain_guard.py::check_new_domain()`

### 5.2 Merge Trigger

Two domains A + B: keyword_overlap ≥ 40% AND combined_sources < 200  
→ Output `merge_suggestions` in research response

### 5.3 Split Trigger

Domain A: source_count > 200  
→ Output `split_suggestions` in research response

---

## 6. Domain Classification Engine

**File:** `scripts/lib/domain_classifier.py`

No external LLM calls. Pure local keyword matching.

```
classify_domain(text, project_path) → routing_decision

Routing decisions:
  domain_key   — matched domain (score ≥ 0.25)
  "local"      — low confidence (0.10 ≤ score < 0.25)
  "NEW:<name>" — no match (score < 0.10) → suggest new domain
```

Algorithm:
1. Tokenize text (stop-word filtered, EN + ZH)
2. Score against each domain's `keywords` (bidirectional substring match)
3. score = matched_keywords / total_topic_tokens
4. Return routing based on thresholds

---

## 7. `/nlm-research` Specification

**Trigger:** Main session Claude or background Agent via `bash $INVOKE research`

```bash
nlm research --topic "<text>" [--depth fast|deep] [--target auto|local|synthesis|domain:<key>]
             [--add-sources] [--max-import N] [--min-relevance 0.1] [--project-path PATH]
```

### Source Routing Flow (--target auto)

```
classify_domain(topic) →
  domain_key  → route to domain notebook → import sources
  "local"     → route to local notebook → import sources
  "NEW:<name>"→ output domain_suggestion → route to local (advisory only)
  After import:
    update domain_notebooks[key].source_count in config
    check merge/split candidates → output in response
    if source_count > 270 → output new_notebook_suggestion
```

### Output Fields (new in v2)

| Field | Description |
|-------|-------------|
| `target_notebook` | Actual notebook used: `"domain:<key>"`, `"local"`, `"synthesis"` |
| `domain_suggestion` | Present when `--target auto` suggests new domain |
| `merge_suggestions` | List of domain pairs to merge (if applicable) |
| `split_suggestions` | List of overfull domains (if applicable) |

---

## 8. `/nlm-ask` Specification

**Trigger:** Main session Claude or background Agent via `bash $INVOKE ask`

```bash
nlm ask --question "<text>" [--scope auto|local|global|synthesis|domain:<key>]
        [--on-low-confidence prompt|research|silent] [--format json|text] [--project-path PATH]
```

**Constraint:** Never imports sources.

### Query Routing (--scope auto)

```
Phase 1: classify_domain(question) → target_domain_key
Phase 2a: if domain found → query domain notebook
Phase 2b: if low confidence or no domain → query local notebook
Phase 3: if still low confidence → route among global notebooks (Haiku-ranked)
Phase 4: if still low confidence → check synthesis notebook
```

### Output Fields (new in v2)

| Field | Description |
|-------|-------------|
| `answered_by` | List of notebooks queried, most specific first |
| `source_notebook` | Primary answering notebook |
| `suggest_research` | `true` when confidence low/not_found |

### When to use `/nlm-research` vs `/nlm-ask`

| Scenario | Use |
|----------|-----|
| Need high-quality answer from existing knowledge | `/nlm-ask` |
| Domain has no sources yet | `/nlm-research` first, then `/nlm-ask` |
| User explicitly requests research | `/nlm-research --add-sources` |
| Read-only subagent dispatch | `/nlm-research --no-add-sources` |

---

## 9. Setup Commands

```bash
# Create domain notebook
nlm setup --create-domain "DOMAIN · Navigation Algorithms · Research" \
          --domain-key navigation_algorithms \
          --domain-keywords "path planning,collision avoidance,COLREGS,LiDAR"

# Create synthesis notebook
nlm setup --create-synthesis "META · ASV Research · Synthesis"
```

---

## 10. Distillation Workflow (Manual, when source_count > 270)

When a domain notebook triggers `new_notebook_suggestion`:

1. In NotebookLM UI: generate **Briefing Document** for the domain notebook
2. Download as `.md` or copy text
3. Add to synthesis notebook:
   ```bash
   nlm add --note "<Briefing Doc content>" \
           --title "Navigation Algorithms Briefing 2026-04" \
           --project-path .
   # (after pointing to synthesis notebook via --target synthesis in future add command)
   ```
4. Update `last_distilled` in config manually (future: automated)

---

## 11. Implementation Summary

### New Files
- `scripts/lib/domain_classifier.py` — keyword-based topic→domain routing
- `scripts/lib/domain_guard.py` — three-gate creation guard + merge/split detection
- `docs/DESIGN_SPEC_V1.md` — this document

### Modified Files
- `scripts/lib/registry.py` — added `_resolve_synthesis_id()`, `_resolve_domain_notebooks()`, extended `find_notebook_ids()`
- `scripts/nlm.py` — updated `setup`, `research`, `ask` commands
- `skills/nlm-ask/SKILL.md` — updated parameters and routing docs
- `skills/nlm-research/SKILL.md` — updated parameters and source routing docs
- `skills/nlm-setup/SKILL.md` — new domain/synthesis commands, naming convention

### Routing Summary

```
/nlm-ask  (read-only)          /nlm-research (write)
    │                               │
    ▼ classify_domain()             ▼ classify_domain()
    │                               │
    ├─ domain found                 ├─ domain found → import to domain
    │   → domain nb (primary)       │
    │   → local (fallback)          ├─ no match (low score) → import to local
    │                               │
    ├─ no domain                    ├─ NEW:<name> → advisory only
    │   → local → global → synth   │   output domain_suggestion
    │                               │   import to local
    └─ suggest_research: true       └─ domain guard checks
       when low confidence             merge/split suggestions
```
