---
name: nlm-add
description: Manually add a URL source or text note to any NLM notebook (local/synthesis/domain). User-triggered only.
allowed-tools:
  - Bash
---

# nlm-add

Add a URL or text note to your project's local NotebookLM notebook. User-triggered only — never auto-run.

## Parameters

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `--url` | URL | — | Web page to add as a source |
| `--note` | text | — | Text content to save as a note |
| `--title` | text | `"Note"` | Title for the note (only with `--note`) |
| `--target` | `local\|synthesis\|domain:<key>` | `local` | Destination notebook |
| `--project-path` | path | `$(pwd)` | Project root containing `.nlm/config.json` |

Provide either `--url` or `--note`. If neither is given, ask the user: "Add a URL or a text note? Please provide the content."

## Usage

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"

# Add a web URL to local notebook (default)
$INVOKE add --url "<URL>" --project-path "."

# Add a text note to local notebook
$INVOKE add --note "<content>" --title "<title>" --project-path "."

# Add Briefing Doc to META · Synthesis (distillation workflow)
$INVOKE add --note "<Briefing Doc content>" \
             --title "COLAV Algorithms Briefing 2026-04" \
             --target synthesis --project-path "."

# Add URL directly to a domain notebook
$INVOKE add --url "https://imo.org/colregs" \
             --target domain:maritime_regulations --project-path "."
```

## Output

```json
// URL added successfully
{"status": "ok", "type": "url", "target": "local", "source": {"id": "...", "title": "..."}}

// URL already exists in notebook (silently skipped)
{"status": "skipped", "reason": "already_exists", "target": "local", "source": {"id": "...", "title": "..."}}

// Note added successfully
{"status": "ok", "type": "note", "target": "synthesis", "note": {"id": "...", "title": "..."}}
```

If `status` is `skipped`, inform the user the URL is already in the notebook — no action needed.
