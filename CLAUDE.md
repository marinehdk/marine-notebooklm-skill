# nlm — Quick Reference

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

| Intent | Command |
|--------|---------|
| Check auth | `$INVOKE setup --auth` |
| Quick question | `$INVOKE ask --question "..." --project-path "." --format json` |
| Compare options | `$INVOKE plan --question "..." --options "A,B" --project-path "."` |
| Research (read-only) | `$INVOKE research --topic "..." --no-add-sources --project-path "."` |
| Research + import | `$INVOKE research --topic "..." --add-sources --project-path "."` |
| Add URL to notebook | `$INVOKE add --url URL --project-path "."` |
| Add note to notebook | `$INVOKE add --note "..." --title "..." --project-path "."` |
| Init project | `$INVOKE setup --project-path "."` |
| Migrate to global | `$INVOKE migrate --content "..." --target-global "domain"` |

## Two-tier notebooks

- **Local** `.nlm/config.json` — project-specific, writable
- **Global** `~/.nlm/global.json` — domain knowledge, read-only during development

## Auto-trigger rules

| Command | Auto-trigger? |
|--------|--------------|
| `ask` | ✅ Yes — on knowledge uncertainty |
| `plan` | ✅ Yes — when evaluating 2+ options |
| `research --no-add-sources` | ✅ Yes — when dispatched as subagent |
| `research --add-sources` | ❌ User only |
| `add` | ❌ User only |
| `setup` | ❌ User only |
| `migrate` | ❌ User only |
