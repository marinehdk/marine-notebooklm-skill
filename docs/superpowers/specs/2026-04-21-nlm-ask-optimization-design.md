# nlm-ask 优化设计

**Date:** 2026-04-21  
**Status:** Approved  
**Scope:** `cmd_ask` 智能路由 + 低置信处理 + SKILL.md 更新

---

## 背景

当前 `/nlm-ask` 的问题：

1. **路由盲目**：`auto` scope 固定查 local → 低置信再查 global，不考虑哪个 global notebook 最相关
2. **置信度处理缺失**：低置信时原样返回，Claude 和用户都不知道该怎么办
3. **SKILL.md 指导不足**：Claude 不清楚何时触发、拿到低置信结果后如何处理
4. **`domain_router.py` 未接入**：已有的领域路由模块从未被 `cmd_ask` 调用

---

## 架构

```
cmd_ask
  │
  ├─ 1. RouteNotebooks(question, cache)        ← 新增
  │      └─ Claude Haiku 根据 summary+topics 返回排序后的 UUID 列表
  │         降级：标题关键词字符串匹配
  │
  ├─ 2. QueryInOrder(ranked_uuids, question)
  │      └─ 依序调用 client.ask()，置信度达标即停
  │
  └─ 3. ConfidenceHandler(result, mode)        ← 新增
         ├─ high/medium → 直接返回
         ├─ low/not_found + mode=prompt  → 附 next_action hint
         └─ low/not_found + mode=research → fast research → 重查 → 降为 prompt
```

---

## 文件变更

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `scripts/lib/client.py` | 修改 | 新增 `get_description(nb_id)` 包装；`list_notebooks()` 并行拉取 description |
| `scripts/lib/notebook_router.py` | 新建 | Claude Haiku 路由逻辑；降级到标题关键词匹配 |
| `scripts/lib/confidence_handler.py` | 新建 | `prompt` / `research` / `silent` 三种模式 |
| `scripts/nlm.py` → `cmd_ask` | 修改 | 接入路由层 + 置信度处理；新增 `--on-low-confidence` 参数 |
| `scripts/nlm.py` → `cmd_setup` | 修改 | `--notebook-list --refresh` 时并行拉取 description 写入 cache |
| `skills/nlm-ask/SKILL.md` | 修改 | 参数文档 + 自动触发规则 + 结果处理规则 |
| `scripts/lib/domain_router.py` | 退役 | 不再调用，待后续删除 |

---

## 第一节：Metadata 缓存

### Refresh 流程

`--notebook-list --refresh` 时：

1. `client.list_notebooks()` 拉取基础列表（已有逻辑）
2. `asyncio.gather()` 并行对所有笔记本调用 `client.notebooks.get_description(nb_id)`
3. 合并写入 `notebooks_cache.json`

单本失败时设 `summary: "", topics: []`，不阻断整体。34 本并行预计 5-10s。

### Cache 记录结构

```json
{
  "#": 13,
  "UUID": "b6f5c3bb-8424-41f1-8691-0f5a3f854200",
  "Title": "SINAN-业务子系统层UKC设计",
  "Sources": 35,
  "Created": "2026-04-13",
  "summary": "本笔记本涵盖船舶UKC（龙骨下余量）计算方法，包括螺旋桨下沉、波浪响应、浅水效应等模型，适用于港口进出港决策支持。",
  "topics": [
    "How is squat effect calculated at different speeds?",
    "What safety margins apply for UKC in restricted waters?",
    "How does wave-induced motion affect UKC?"
  ]
}
```

- `summary`：取 `NotebookDescription.summary` 前 300 字
- `topics`：取 `NotebookDescription.suggested_topics[].question`，最多 5 条
- 不做额外 tags 提取，`summary + topics` 直接作为路由输入，人可读

### Cache 更新时机

- `--refresh` 时总是重拉（含 description）
- 24h 自动过期后下次 `--notebook-list` 触发重拉
- `cmd_ask` 只读 cache，不主动触发拉取；cache 缺失或无 description 字段时输出：

```json
{"error": "cache_missing_description", "hint": "Run: nlm setup --notebook-list --refresh"}
```

---

## 第二节：Claude 路由器

### `notebook_router.py`

**输入：** 问题文本 + cache 中所有笔记本的 metadata  
**输出：** `RouteResult`

```python
@dataclass
class RouteResult:
    ranked_ids: list[str]  # 最多 3 个，按相关度排序
    fallback_used: bool    # True = Claude 调用失败，用了降级策略
```

### Prompt 结构

```
You are a notebook router. Given a question and a list of notebooks,
return the UUIDs of the most relevant notebooks in order of relevance.

Question: {question}

Notebooks:
[1] UUID: b6f5c3bb-... | Title: SINAN-业务子系统层UKC设计
    Summary: 本笔记本涵盖船舶UKC计算方法...
    Topics: How is squat effect calculated? / What safety margins apply?

[2] ...

Reply with ONLY a JSON array of UUIDs, most relevant first. Include at most 3.
Example: ["b6f5c3bb-...", "8d64174a-..."]
```

### 实现参数

- 模型：`claude-haiku-4-5-20251001`（轻量分类，不需要 Sonnet）
- `max_tokens: 100`
- 调用方式：同步 `anthropic.Anthropic().messages.create()`（在 asyncio 外调用）
- 解析失败时 `fallback_used = True`

### 降级策略

Claude 调用失败（无 API key、超时、JSON 解析失败）时，退回标题关键词匹配：

1. 将问题按空格 + 标点分词，过滤停用词
2. 与每个笔记本标题做子字符串包含检查，计算命中词数
3. 按命中数降序排列，取前 3；零命中时返回原始列表顺序的前 3 个

### Scope 约束

| scope | 路由行为 |
|-------|----------|
| `local` | 跳过路由器，直接用 local notebook |
| `global` | 仅在 global notebooks 池里路由 |
| `auto` | 先路由 local（若有）；低置信时再路由 global |

当 local notebook 无 description（新建空本）时，`auto` 直接查 local 后路由 global。

---

## 第三节：低置信处理

### 新增参数

```
--on-low-confidence [prompt|research|silent]   默认: prompt
```

### 三种模式

| 模式 | 触发条件 | 行为 |
|------|----------|------|
| `prompt` | confidence = low / not_found | 正常返回答案，附加 `next_action` 字段 |
| `research` | confidence = low / not_found | 对 local notebook 触发 fast research → import sources → 重查；若仍低置信降为 prompt |
| `silent` | 任何 | 原样返回，无 hint（适合脚本批量调用） |

### `prompt` 模式输出

```json
{
  "answer": "...",
  "confidence": "low",
  "source_notebook": "local",
  "citations": [],
  "next_action": {
    "type": "suggest_research",
    "message": "本地笔记本对此问题置信度较低，建议通过 `/nlm-research` 补充相关资料后重试。",
    "command": "nlm research --topic \"<question>\" --add-sources --project-path \".\""
  }
}
```

### `research` 模式内部流程

```
低置信结果
  │
  ├─ client.research(local_nb_id, question, mode="fast")
  ├─ import_research_sources(local_nb_id, task_id, sources)
  ├─ client.ask(local_nb_id, question)          ← 重查
  └─ 结果附加 "auto_researched": true
     若仍低置信 → 降为 prompt 模式输出
```

`research` 模式仅对 local notebook 触发，不写入 global notebooks（全局只读策略不变）。

---

## 第四节：SKILL.md 更新

### 参数表（新增）

```markdown
| `--on-low-confidence` | `prompt\|research\|silent` | `prompt` | 低置信时的处理策略 |
```

### 自动触发规则

```markdown
## Auto-trigger

Call `nlm ask` when you encounter uncertainty about:
- Domain-specific concepts in this project (algorithms, specs, standards)
- Architecture decisions or design patterns documented in notebooks
- Technical terms you cannot confidently answer from the codebase alone

Do NOT call for: general programming questions, public API docs,
syntax questions, anything answerable from code in the current repo.
```

### 结果处理规则

```markdown
## Handling results

| confidence | next_action.type  | Action |
|------------|-------------------|--------|
| high/medium | —                | Use answer directly |
| low         | suggest_research | Tell user coverage is limited; offer to run `/nlm-research` |
| not_found   | suggest_research | Tell user notebook has no relevant content; suggest `/nlm-research` or `--scope global` |
| any         | — (auto_researched: true) | Note sources were auto-added; answer may reflect newly imported content |
```

---

## 不在本次范围内

- 向量嵌入 / 语义搜索（方案 A/C 的部分能力，后续可选）
- `domain_router.py` 的正式删除（退役但保留）
- `cmd_plan` / `cmd_research` 的路由优化（独立迭代）
- 批量 ask / 并发查询多笔记本（YAGNI）
