# Task 15: End-to-End Verification Guide

This document specifies how to verify that the nlm skill works correctly in Claude Code runtime, including:
1. Direct skill invocation via `/nlm-ask`
2. Agent auto-triggering on knowledge uncertainty
3. Parallel research dispatch for complex queries

All prior tasks (1-14) are complete: commands implemented, tests passing, wrapper code verified.

---

## Test Setup & Prerequisites

Before running verification tests, ensure:

### 1. Authentication
The skill requires valid NotebookLM authentication. Verify once:

```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh setup --auth
```

Expected output:
```json
{
  "status": "ok",
  "authenticated": true
}
```

If `authenticated: false`, run:
```bash
notebooklm login
```

Then retry the auth check.

### 2. Test Project Configuration
Create or select a test project with `.nlm/config.json`:

```bash
# Option A: Create test project from scratch
mkdir -p /tmp/nlm-test
cd /tmp/nlm-test

# Option B: Use existing project with .nlm directory
cd ~/my-project  # any directory with .nlm/config.json
```

The config file should contain:
```json
{
  "notebook_id": "<your-notebook-uuid>",
  "notebook_name": "Test Notebook",
  "created_at": "2026-04-20"
}
```

If config is missing, run setup in your project:
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh setup --project-path .
```

### 3. Fresh Claude Code Session
To verify Claude Code integration, you must:
1. Close all Claude Code instances
2. Reopen Claude Code in your test project directory (or any directory with a `.nlm/config.json`)
3. This ensures clean context for testing auto-trigger behavior

---

## Test 1: Direct Skill Invocation

**Purpose:** Verify `/nlm-ask` works as a slash command in Claude Code.

### Step 1a: Invoke the skill

In Claude Code, type:
```
/nlm-ask What is the main topic of this notebook?
```

### Step 1b: Verify output format

Expected response:
- **Direct answer** from the notebook content
- **Confidence level** stated (high/medium/low/not_found)
- **Source notebook** referenced (e.g., "Test Notebook (local)")
- **Citations** if available (optional, depends on notebook content)

Example expected output:
```
The main topic of this notebook appears to be Python async programming patterns and best practices.

Confidence: high
Source: Test Notebook (local)
Citations:
  - AsyncIO Patterns (source)
  - Async/Await Guide (source)
```

### Step 1c: Success criteria

- [ ] Skill invoked without user typing "nlm" explicitly
- [ ] Answer is grounded in notebook content (not generic)
- [ ] Confidence level is explicitly stated
- [ ] Response is clear and actionable

---

## Test 2: Agent Auto-Triggering on Knowledge Uncertainty

**Purpose:** Verify Claude auto-invokes `nlm ask` when it detects knowledge uncertainty.

### Step 2a: Trigger with a conceptual question

In Claude Code, ask:
```
I'm unsure about the best way to handle async errors in Python. 
Can you help me understand the options?
```

Or in Chinese (to test multilingual detection):
```
我不确定应该用 asyncio 还是 threading，帮我查一下
```

Translation: "I'm unsure about asyncio vs threading, help me check"

### Step 2b: Verify auto-trigger behavior

Expected behavior:
- Claude recognizes the **knowledge uncertainty pattern** (phrases like "unsure", "不确定", "help me check", "查一下")
- Claude **automatically invokes** `nlm ask` or `nlm plan` WITHOUT the user mentioning "nlm"
- Claude returns an **augmented answer** that includes:
  - Grounded answer from notebook
  - Confidence level
  - Alternative options if applicable

### Step 2c: Verify decision tree

Claude should use this logic:

| Question Type | Command |
|---------------|---------|
| "I'm unsure about X" (concept) | `nlm ask` |
| "Which is better, A or B?" (choice) | `nlm plan` |
| "Help me understand X vs Y" (comparison) | `nlm plan` (with options) |
| "How do I do X?" (how-to) | `nlm ask` |
| "What's the best practice?" (recommendation) | `nlm ask` or `nlm plan` |

### Step 2d: Success criteria

- [ ] Claude auto-triggers WITHOUT user saying "nlm" or "/" explicitly
- [ ] Decision tree routing is correct (ask vs plan based on question type)
- [ ] Answer includes confidence level from notebook
- [ ] User does NOT have to re-invoke or repeat the question

---

## Test 3: Parallel Research Dispatch

**Purpose:** Verify Claude can dispatch multiple subagents for parallel research tasks.

### Step 3a: Trigger parallel research

In Claude Code, ask:
```
Help me research these 3 areas in parallel:
1. FastAPI vs Flask
2. PostgreSQL vs SQLite
3. Docker vs bare metal

Use NotebookLM for research and give me a comparison report.
```

Or in Chinese:
```
帮我并行调研这三个方向：
(1) FastAPI vs Flask
(2) PostgreSQL vs SQLite
(3) Docker vs bare metal

用 NotebookLM 出报告。
```

### Step 3b: Verify parallel dispatch

Expected behavior:
- Claude recognizes **3+ parallel research topics** in the question
- Claude dispatches **3 subagents** (or one agent per topic)
- Each subagent runs: `research --no-add-sources --topic "FastAPI vs Flask"`
- Each subagent completes research within 120 seconds
- No sources are added to notebook (--no-add-sources flag used)

### Step 3c: Verify report synthesis

Expected output:
- [ ] All 3 research reports are collected and displayed
- [ ] Reports are synthesized into a single comparison summary
- [ ] Each report includes:
  - Research topic
  - Key findings
  - Comparison matrix (if applicable)
  - Confidence level
- [ ] No duplicate or overlapping research

### Step 3d: Success criteria

- [ ] All 3 subagents complete within 120 seconds
- [ ] Parallel execution is visible (subagents run concurrently)
- [ ] Final report is well-organized and readable
- [ ] Sources are NOT added to notebook (--no-add-sources enforced)

---

## Test 4: Integration with Claude Code UX

**Purpose:** Verify skill integrates smoothly with Claude Code environment.

### Step 4a: Test in different project contexts

Try the skill in different contexts:
1. Project with `.nlm/config.json` (local notebook)
2. Fresh directory without config (should prompt setup)
3. Nested subdirectory (should find config in parent)

### Step 4b: Verify error handling

Test error cases:
```
# This should fail gracefully
/nlm-ask What do you think?
# (No local notebook configured)
```

Expected error:
```
No local notebook configured. Run:
  bash ~/.claude/skills/nlm/scripts/invoke.sh setup --project-path .

Or ask a question to auto-trigger global notebook search.
```

### Step 4c: Verify timeout handling

Test with a slow network or delayed response:
- Research operations should timeout gracefully after 180 seconds
- User should see clear timeout message, not hang indefinitely

### Step 4d: Success criteria

- [ ] Skill works in different project contexts
- [ ] Error messages are clear and actionable
- [ ] Timeouts are handled gracefully (no infinite hangs)
- [ ] No Claude Code crashes or exceptions

---

## Performance Expectations

| Operation | Expected Time | Success Criteria |
|-----------|----------------|------------------|
| `ask` (quick question) | 5-15 seconds | Responsive, under 30s |
| `plan` (2 options) | 10-20 seconds | Responsive, under 45s |
| `research --depth fast` | 30-60 seconds | Completes within 120s |
| `research --depth deep` | 60-120 seconds | Completes within 180s |
| Parallel dispatch (3 agents) | 60-120 seconds total | All agents finish within 180s |

---

## Cleanup Instructions

### Step 5a: Archive old skill (if present)

If an old skill exists at `~/.claude/skills/notebooklm-superpower`, archive it:

```bash
mv ~/.claude/skills/notebooklm-superpower ~/.claude/skills/notebooklm-superpower-archived
```

Verify archive:
```bash
ls -d ~/.claude/skills/notebooklm-superpower-archived
```

### Step 5b: Final git commit

In the nlm skill directory:

```bash
cd ~/.claude/skills/nlm
git add VERIFICATION.md
git commit -m "docs(nlm): add verification guide for Claude Code runtime"
```

Or if archiving the old skill:

```bash
cd ~/.claude/skills/nlm
git add VERIFICATION.md
git commit -m "feat(nlm): complete implementation — all commands verified, old skill archived"
```

---

## Verification Checklist

Copy this checklist and mark off each test as you complete it:

### Test 1: Direct Invocation
- [ ] `/nlm-ask` command works in Claude Code
- [ ] Answer is grounded in notebook
- [ ] Confidence level shown
- [ ] No generic or hallucinated content

### Test 2: Auto-Triggering
- [ ] Auto-triggers on "unsure" pattern
- [ ] Auto-triggers on "Which is better" pattern
- [ ] Correct command selected (ask vs plan)
- [ ] Works in English and Chinese
- [ ] Works without "/" or "nlm" mention

### Test 3: Parallel Research
- [ ] 3+ subagents dispatched
- [ ] Parallel execution visible
- [ ] All reports collected
- [ ] Reports synthesized
- [ ] --no-add-sources flag enforced

### Test 4: Integration & UX
- [ ] Works in different project contexts
- [ ] Error messages clear
- [ ] Timeouts handled gracefully
- [ ] No crashes or exceptions

### Test 5: Performance
- [ ] ask completes in <30s
- [ ] plan completes in <45s
- [ ] research completes in <180s
- [ ] Parallel dispatch completes in <180s

---

## Success Criteria Summary

The skill is **VERIFIED and READY FOR PRODUCTION** when:

1. ✅ **All 4 verification tests pass** (direct invocation, auto-trigger, parallel dispatch, integration)
2. ✅ **Performance expectations met** (no timeouts, responsive)
3. ✅ **Error handling robust** (clear messages, graceful degradation)
4. ✅ **Claude Code integration smooth** (no crashes, works across contexts)
5. ✅ **Documentation complete** (this VERIFICATION.md file committed)

---

## Troubleshooting

### Issue: `/nlm-ask` not recognized

**Solution:** Ensure the skill is registered in Claude Code:
```bash
ls ~/.claude/skills/nlm/SKILL.md
```

If missing, run:
```bash
cd ~/.claude/skills/nlm
git status
```

### Issue: "No notebooks configured"

**Solution:** Run setup:
```bash
bash ~/.claude/skills/nlm/scripts/invoke.sh setup --project-path .
```

### Issue: Research timeout after 60 seconds

**Solution:** This is normal for deep research. Wait up to 180 seconds. If it still fails, check NotebookLM service status or retry.

### Issue: Auto-trigger not working

**Solution:** Verify in a fresh Claude Code session. Auto-trigger detection is context-sensitive. Try rephrasing the question to include uncertainty cues like:
- "I'm unsure about..."
- "Help me understand..."
- "Which is better..."

### Issue: Parallel dispatch runs sequentially instead of parallel

**Solution:** Verify Claude is using subagents correctly. Check in Claude Code logs for agent dispatch messages. If using an older Claude Code version, subagent parallelization may be limited.

---

## Next Steps After Verification

Once all tests pass:

1. **Document findings** in a test report
2. **Archive old skill** (if applicable)
3. **Commit changes** to git
4. **Announce readiness** to team
5. **Schedule user training** (optional)
6. **Monitor production usage** for any edge cases

---

## Contact & Support

For questions or issues during verification:
- Check CLAUDE.md for quick reference
- Review SKILL.md for detailed command documentation
- Run tests in `/Users/marine/.claude/skills/nlm/tests/` for unit verification
- Check ~/.nlm/logs/ for detailed execution logs (if enabled)

---

**Version:** Task 15 Complete
**Last Updated:** 2026-04-20
**Status:** Ready for Verification
