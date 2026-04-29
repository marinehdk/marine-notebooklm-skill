# NLM Multi-Tier Knowledge System — Business Logic Design Spec v1.0

| 属性 | 值 |
|------|-----|
| 文档编号 | NLM-SPEC-BUSINESS-LOGIC-001 |
| 版本 | **v1.0**（初版） |
| 日期 | 2026-04-29 |
| 状态 | 待审阅（Step 8 user review pending） |
| 作者 | marine + Claude (via superpowers brainstorming) |
| 适用 NLM 版本 | 当前部署在 `~/.claude/skills/nlm/` 的 commit |
| Spec 立场 | Self-Contained Target State + Implementation Gap Index (C1) |
| 体量 | ~3270 行 |

---

## §1 总览（Overview）

### §1.1 设计目标

NLM 是一个 Claude Code skill，让 Claude 能查询用户在 NotebookLM 上的笔记本（grounded knowledge retrieval），并把研究产物自动沉淀回笔记本（knowledge accumulation）。本文档是 NLM 的 **用户面业务逻辑规格**——目标态参照系，解决 "NLM 经过多次修改导致逻辑混乱" 的痛点。

具体目标：

1. **统一参照系**：8 命令矩阵 × 4 笔记本层 × 触发场景 × 输入输出契约的完整规范
2. **目标态描述**：spec 描述 "应该是什么"，不是 "现在是什么"
3. **实施差距标注**：当前实现与目标态的差距集中在 §5（Implementation Gap Index），以 `[GAP-N]` 引用
4. **后续 plan 输入**：本 spec 完成后用 superpowers `writing-plans` 生成修复实施计划

### §1.2 目标读者

- **NLM 工具使用者**：项目级 NLM 配置者与日常用户
- **NLM 工具开发者**：修复实施与未来演进
- **主会话 Claude / 后台 Agent**：auto-trigger 决策依据

### §1.3 范围（Scope）

**In scope（本 spec 覆盖）**：

- 8 个用户面命令的完整业务流程（`setup` / `ask` / `research` / `add` / `plan` / `migrate` / `deduplicate` / `delete`）
- 4 层笔记本（`PROJ` / `DOMAIN` / `META` / `GLOBAL`）的完整生命周期
- 跨命令工作流（知识沉淀 / 冷启动 / 域演化 / 容量保护）
- 命名规范与 Config Schema v2

**Out of scope（不覆盖，留待后续 spec）**：

- `lib/` 内部组件契约（`registry` / `domain_classifier` / `domain_guard` 等的职责边界）
- NotebookLM 服务端 API 契约（错误码矩阵、限流策略）
- `plan_evaluator` 的 4 阶段算法细节（已有独立 spec：[2026-04-22-nlm-plan-evaluation-design.md](./2026-04-22-nlm-plan-evaluation-design.md)）
- NotebookLM 浏览器自动化认证细节（`lib/auth.py` 的 patchright 实现）

### §1.4 触发原则

**主会话 Claude 与后台 Agent 行为完全一致**——均通过 `bash $INVOKE` 调用底层 CLI；路由 / 评分 / 写入决策对二者无差异。

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

### §1.5 关键设计决策汇总

| 决策维度 | 决策值 | 决策依据 |
|---------|------|---------|
| **ask 路由优先级** | **A3 · 并行融合**（domain + local 同时查询，融合答案标注来源） | 回答质量优先；synthesis 在项目初期为空，蒸馏是后期方案；并行不增加总时延（`max(domain, local)` ≈ 30s） |
| **research 写入路由** | **B1 · Domain 优先 + Local fallback** | 自动化高；与 §7 三重门闸 + merge/split 自纠错协同 |
| **蒸馏本质语义** | **C1 · 原 Domain 保留 + META 增量喂养** | 蒸馏目的是 "跨域综合查询入口"，不是 "清理空间"；空间靠域分裂解决 |
| **容量阈值协同** | **250 / 270 / 290 / 300** 四级协同 | 见 §4.4 |
| **路由决策树归属** | **E2 · 详细在 §3.X.3，§4.1 串起来** | 与 §3 命令模板自洽原则一致 |
| **空笔记本冷启动** | 自动触发 fast research → 写入 PROJ Local 或对应 scope（γ 路由） | 首次 "开箱即用" 体验；与 spec §6 "绝不写入"形成例外子规则 |
| **scope 路由 (cold-start)** | **γ · 混合**：scope=domain:X → import to domain:X；scope=auto/local/global/synthesis → import to PROJ Local | 尊重 domain scope 意图；保护 META 不被 raw research 污染 |

### §1.6 NLM 与 NotebookLM 的边界

| 维度 | NLM (本工具) | NotebookLM (服务端) |
|------|------------|--------------------|
| 部署 | 本地 Python CLI（`~/.claude/skills/nlm/`） | Google 云服务 |
| 认证 | Patchright 浏览器自动化 + cookie storage | Google 账号登录 |
| 数据存储 | `.nlm/config.json` + `.nlm/topics.json` + `.nlm/notebooks_cache.json`（项目级） | 用户账号下的笔记本 + 来源 + chat 历史 |
| 容量限制 | 仅追踪与提示 | **强制上限**：单笔记本 300 sources（Pro 版） |
| Deep Research | 仅是 NotebookLM 服务的代理 | Google 实际执行；日配额限制（独立于 chat 配额） |
| 评分逻辑 | 本地 keyword + recency + citation_freq | 不参与 |

---

## §2 四层笔记本生命周期（Notebook Lifecycle）

NLM 用 4 个抽象层组织知识。每层有明确的写入入口、容量规则、生命周期触发条件。本章按 **笔记本层** 组织（不是按命令），方便回答 "我加的源进了哪里" 这类问题。

### §2.1 PROJ · Local 笔记本

#### §2.1.1 用途定位

**项目特有知识容器**。装项目内部产生的、不跨项目共享的知识：

- 用户决策记录、约束、TODO、临时笔记
- 未被任何 Domain 路由匹配的暂存来源
- 空笔记本冷启动时 ask 自动 research 的产物
- A3 并行查询时的项目语境补充答案

**它不是知识沉淀的主战场**——长期专域知识应进 DOMAIN（专域深挖）或 META（跨域综合）。

#### §2.1.2 创建路径

| 命令 | 行为 | 自动加 SCOPE 前缀 |
|------|------|---------------|
| `nlm setup --create-local "<title>"` | 创建新笔记本，绑定为 PROJ Local；写入 `.nlm/config.json` | ✅ → `PROJ · <title> · Local` |
| `nlm setup --add-local-notebook <UUID>` | 不创建，绑定已存在的笔记本（含手动 rename 的） | ❌ 用户负责命名 |

每个项目 **唯一** 一个 PROJ Local 笔记本（`config.local_notebook` 是单值字段，不是数组）。

#### §2.1.3 写入入口（哪些命令会写入 PROJ Local）

| 触发场景 | 命令 | 是否自动 |
|---------|------|---------|
| 用户手动添加 URL/笔记 | `/nlm-add --url ...` 或 `/nlm-add --note ...` | ❌ user-only |
| 用户手动 add 显式指定 target | `/nlm-add --target local ...` | ❌ user-only |
| research 自动路由：topic 无 domain 匹配 | `/nlm-research --target auto`（默认） + B1 路由 fallback | ✅ |
| research 自动路由：建议新域但未通过三重门闸 | 同上，新域被 Gate 1（积压<20）拒绝 | ✅ |
| research 显式 target=local | `/nlm-research --target local` | ❌ user-explicit |
| 空笔记本冷启动 | ask 检测目标空 → fast research → import here | ✅ |
| 低置信度回退（用户确认） | ask 输出 suggest_research → 用户手动触发 research | ❌ user-only |

#### §2.1.4 写入禁忌（哪些场景**不会**写入 PROJ Local）

- ask 命令本身**绝不写入**任何笔记本（除冷启动子流，见 §4.2.1）
- migrate 命令**不写入** Local（它是把 Local 知识 promote 到 GLOBAL）
- 空笔记本冷启动 + ask scope=domain:X → 写入 domain:X，不是 Local（γ 路由）

#### §2.1.5 容量规则

| 阈值 | 行为 | 责任方 |
|------|------|------|
| < 200 | 正常累积 | 自动 |
| 200–250 | research 输出 hint：建议人工 review | 自动 |
| 250 | research 输出 warn + 启动评分排序 | 自动 |
| 270 | distillation_required = true（建议蒸馏到 META） | 自动 / 人机协同 |
| 290 | 拒收新 import（CapacityError） | 自动 |
| 300 | 硬上限（NotebookLM Pro 强制） | NotebookLM 服务端 |

阈值数值与所有其他笔记本层一致。详见 §4.4 容量保护流。

#### §2.1.6 命名约束

```
格式：PROJ · {Name} · Local

规则：
  - {Name} ≤ 25 字符
  - 英文 TitleCase 或中文简短短语
  - 禁止日期后缀（用 last_distilled 字段追踪）
  - 禁止版本号后缀（笔记本是活文档）

示例：
  ✅ PROJ · MASS-L3 · Local
  ✅ PROJ · OceanInfra · Local
  ❌ PROJ · MASS-L3-2026-04 · Local        （含日期）
  ❌ PROJ · MASS-L3 v2 · Local              （含版本）
  ❌ PROJ · This is a really long project name · Local  （>25字符）
```

#### §2.1.7 触发场景表（什么时候用 PROJ Local vs 用别的层）

| 场景 | 选择 PROJ Local 的判定 | 反例（应选别层） |
|------|--------------------|--------------|
| 项目特有约束、决策记录、TODO | ✅ Local（项目内部产物） | 通用规范知识 → DOMAIN |
| 临时记录某个偶遇的有用 URL | ✅ Local（未分类暂存） | 明确属于某专域 → DOMAIN |
| 空笔记本初次 ask（auto-import） | ✅ Local（γ 默认） | scope=domain:X → DOMAIN（γ 例外） |
| 跨域综合分析（需多个 domain 知识协同） | ❌ → META（synthesis） | 单域问题 → DOMAIN |
| 长期通用参考（跨项目复用） | ❌ → GLOBAL（Reference） | 项目内部决策 → Local |

#### §2.1.8 示例 Config 片段

```json
{
  "local_notebook": {
    "id": "<uuid>",
    "title": "PROJ · <ProjectName> · Local",
    "source_count": 0,
    "description": ""
  }
}
```

---

### §2.2 DOMAIN · Research 笔记本

#### §2.2.1 用途定位

**单一技术领域深挖容器**。装某个具体领域的高质量、可跨项目复用的研究来源：论文、规范、工业实践文档、专业博客等。

**这是知识沉淀的主战场**——deep research 的产物默认进 DOMAIN（B1 路由）；蒸馏的来源也是 DOMAIN（→ META Briefing Doc）。

每个项目可有 **5–15 个** Domain 笔记本（OG-RAG / Graph RAG in the Wild 实测的最优范围）。

#### §2.2.2 创建路径（含三重门闸）

##### 创建命令

| 命令 | 行为 |
|------|------|
| `nlm setup --create-domain "<title>" --domain-key <key> --domain-keywords "kw1,kw2"` | 创建笔记本 + 写入 `.nlm/config.json` 的 `domain_notebooks.<key>` |

参数：

| 参数 | 必填 | 格式 | 说明 |
|------|------|------|------|
| `--create-domain TITLE` | ✅ | 字符串（≤25 字符） | 笔记本展示名（自动加 `DOMAIN ·` 前缀和 `· Research` 后缀） |
| `--domain-key KEY` | ✅ | snake_case | 域键（用于 config 索引、`--target domain:<key>` 引用） |
| `--domain-keywords KEYWORDS` | ✅ | 逗号分隔字符串 | 路由用关键词（domain_classifier 用此匹配 topic） |
| `--domain-description DESC` | ❌ | 字符串 | 人类可读描述（不参与路由） |

##### 三重门闸（创建前自动检验）

研究路由（`/nlm-research --target auto`）检测到 NEW 域建议时，依序检查以下 3 道门闸：

```
Gate 1 — 积压量检验（source_queue < 20）
  说明：当前 Local 笔记本中 "看起来属于该新域" 的来源数量
  → < 20 → 不创建新域；本次 research 路由到 Local
  → ≥ 20 → 通过 Gate 1，进入 Gate 2

Gate 2 — 关键词重叠检验（overlap ≥ 40% 与任一现有域）
  → 重叠 ≥ 40% → 不创建；建议路由到该现有域 + 更新该域 keywords
  → 重叠 < 40% → 通过 Gate 2，进入 Gate 3

Gate 3 — 总域数上限（total_domains ≥ 15）
  → ≥ 15 → 不创建；本次 research 路由到 META synthesis + ⚠ 标记 "请求人工 review"
  → < 15 → 通过全部门闸，请求用户确认创建
```

三重门闸**不是用户在命令行手动跑的检验**，而是 `/nlm-research --target auto` 在运行时自动执行的隐式检验。它的作用是**约束自动建域**，避免无序膨胀。

用户**直接** `/nlm-setup --create-domain ...` 时不走门闸——这是显式 user-driven 行为。

#### §2.2.3 写入入口（哪些命令会写入 DOMAIN）

| 触发场景 | 命令 | 是否自动 |
|---------|------|---------|
| research 路由匹配某 domain | `/nlm-research --target auto`（默认） + B1 路由命中 | ✅ |
| research 显式 target=domain:<key> | `/nlm-research --target domain:<key> ...` | ❌ user-explicit |
| 空笔记本冷启动 + scope=domain:X | ask 检测目标 domain:X 空 → fast research → import to domain:X（γ 路由） | ✅ |
| 用户 add 显式指定 target=domain:<key> | `/nlm-add --target domain:<key> ...` | ❌ user-only |

#### §2.2.4 写入禁忌

- DOMAIN **从不接收** Briefing Doc（那是 META 的职责）
- DOMAIN **从不接收** 跨域综合查询的产物（那也是 META）
- 即使 research 输出 domain_suggestion，**也不会自动创建** DOMAIN（必须用户确认）

#### §2.2.5 容量规则与生命周期触发

| source_count | 自动行为 |
|--------------|---------|
| < 200 | 正常累积 |
| 200–250 | research 输出 hint：可能需要拆分（split_suggestion） |
| 250 | warn + 启动评分排序，输出低分 top-50 给用户决策（不自动删除） |
| 270 | **AUTO BRIEFING**：调 NotebookLM API 生成 Briefing Doc → 提示用户审阅 → 用户确认后写入 META |
| 290 | **AUTO REJECT**：拒收新 import（`CapacityError`），强制用户处理（蒸馏 / 删除低分 / 创建新域） |
| 300 | NotebookLM 硬上限（理论不可达，因 290 已 reject） |

##### 域合并触发（merge_suggestion）

每次 `/nlm-research` 执行后自动检查：

```
若存在两个域 A 和 B 满足：
  keyword_overlap(A, B) > 40%
  AND combined_source_count(A, B) < 200

→ 输出 merge_suggestion：
  "建议将 {B} 合并入 {A}，执行：nlm setup --merge-domain B --into A"
```

##### 域拆分触发（split_suggestion）

```
若域 A 满足：
  source_count > 200
  AND 近 10 次 ask 中 >60% 查询只命中其中一个子关键词群

→ 输出 split_suggestion：
  "建议将 {A} 拆分，执行：nlm setup --split-domain A"
```

#### §2.2.6 命名约束

```
格式：DOMAIN · {Name} · Research

规则：同 §2.1.6（≤25 字符 / 禁日期 / 禁版本）

示例：
  ✅ DOMAIN · Maritime Regulations · Research
  ✅ DOMAIN · COLAV Algorithms · Research
  ✅ DOMAIN · Ship Maneuvering · Research
  ❌ DOMAIN · Navigation Algorithms 2026 · Research  （含日期）
  ❌ DOMAIN · Path Planning v2 · Research              （含版本）
```

#### §2.2.7 触发场景表（决策树）

```
何时用 DOMAIN（vs 其他层）？
│
├── 问题：内容是否属于某专业领域？
│   ├── 是（如 COLREGs、MPC、海事法规）
│   │   ├── 该领域已有 DOMAIN？
│   │   │   ├── 是 → 用该 DOMAIN
│   │   │   └── 否 → 三重门闸检验：
│   │   │           Gate 1+2+3 都通过 → 创建新 DOMAIN
│   │   │           任一不通过 → 路由到 Local（详见 §2.2.2）
│   │   └── 否（跨多个领域，需要综合视角）
│   │       └── 用 META synthesis（§2.3）
│   └── 否（项目内部决策、临时笔记）
│       └── 用 PROJ Local（§2.1）
│
├── 问题：内容是否需要长期、跨项目复用？
│   ├── 是 + 已是稳定知识 → 用 GLOBAL Reference（§2.4）
│   └── 是 + 仍在演进 → 用 DOMAIN（可后续 migrate）
│
└── 问题：当前 Domain 是否已满（>270）？
    └── 是 → 触发蒸馏到 META + 继续累积或拆分
```

#### §2.2.8 示例 Config 片段

```json
{
  "domain_notebooks": {
    "navigation_algorithms": {
      "id": "<uuid>",
      "name": "DOMAIN · Navigation Algorithms · Research",
      "description": "路径规划、避碰、COLREGs、感知融合、控制律",
      "keywords": [
        "path planning",
        "collision avoidance",
        "COLREGs",
        "LiDAR",
        "SLAM",
        "control"
      ],
      "source_count": 0,
      "last_distilled": null
    }
  }
}
```

---

### §2.3 META · Synthesis 笔记本

#### §2.3.1 用途定位

**跨域综合查询入口 + 长期知识沉淀库**。装：

- 各 DOMAIN 蒸馏出的 Briefing Doc（每个域一份，270 阈值自动触发）
- Deep research 的 report markdown（轻量蒸馏，每次 deep research 后可选自动 import）
- 用户自定义的跨域综合 markdown（手动 `/nlm-add --note --target synthesis`）

**它是项目级 META 层**——跨多个 DOMAIN 的综合问题在此查询；单域深挖问题应去对应 DOMAIN。

每个项目 **唯一** 一个 META 笔记本（`config.synthesis_notebook` 是单值字段）。

#### §2.3.2 创建路径

| 命令 | 行为 |
|------|------|
| `nlm setup --create-synthesis "<title>"` | 创建 META 笔记本 + 写入 `config.synthesis_notebook` |

无三重门闸（META 唯一，不存在 "已经有 META 了还要不要建第二个" 的问题）。

#### §2.3.3 写入入口

| 触发场景 | 命令 | 是否自动 |
|---------|------|---------|
| Domain 触发蒸馏（270 阈值） | NotebookLM API 自动生成 Briefing Doc → 用户审阅确认 → 写入 META | ✅ + 人机协同 |
| Deep research 后 P-NEW-B 自动 import | `/nlm-research --depth deep --add-sources` 检测到 result_type==5 entry → import 到 META | ✅ |
| 用户手动添加 Briefing 文档 | `/nlm-add --target synthesis --note "..."` 或 `--url ...` | ❌ user-only |
| 用户 research 显式 target=synthesis | `/nlm-research --target synthesis ...`（罕见，谨慎使用） | ❌ user-explicit |

#### §2.3.4 写入禁忌（关键约束）

**META 不接收 raw research sources**——这是 META 与 DOMAIN 的本质边界。

具体禁忌：

- `/nlm-research --target auto` 不会自动路由到 META（除非 Gate 3 总域数已满 >= 15 时的逃生通道）
- B1 路由的 fallback 是 PROJ Local，**不是** META
- 空笔记本冷启动**不会**写入 META（γ 路由：scope=synthesis 时不 auto-research，仅 prompt 用户）

唯一允许写入 META 的内容：

1. NotebookLM 生成的 Briefing Doc（蒸馏产物）
2. Deep research 的 report markdown（已是 NotebookLM 综合产物）
3. 用户自定义的综合性 markdown 文档

#### §2.3.5 容量规则

META 的 source 数增长慢（每个 Briefing Doc 计 1 source；deep research report 也计 1 source）。例如：

- 5 个 Domain 各蒸馏 1 次 → META 5 source
- 项目周期内 10 次 deep research auto-import → META 15 source（5 + 10）

容量阈值表与其他层一致（200/250/270/290/300），但**实际上 META 极少触顶**。

如果 META 触顶（≥270），属于异常情况，建议：

1. review META 中的 Briefing Doc 是否有过期版本（`last_distilled` 字段判断），删除旧版
2. 考虑把稳定的 Briefing Doc migrate 到 GLOBAL（如 `/nlm-migrate ...`）

#### §2.3.6 命名约束

```
格式：META · {Name} · Synthesis

约定：{Name} 通常用项目代号或研究主题代号

示例：
  ✅ META · MASS-L3 Research · Synthesis
  ✅ META · ASV Research · Synthesis
  ✅ META · OceanInfra · Synthesis
  ❌ META · 2026Q2 Research · Synthesis  （含日期）
```

#### §2.3.7 触发场景表

```
何时用 META（vs DOMAIN / Local）？
│
├── 跨域综合问题（需 ≥2 个 DOMAIN 协同回答）
│   └── ✅ ask --scope synthesis
│       例如："导航算法和合规要求如何协同？"（涉及 COLAV + Regulations）
│
├── 项目级综合查询（"项目目前在做什么？"）
│   └── ✅ ask --scope synthesis
│       前提：META 已有项目 overview 类的综合 markdown
│
├── 单域深挖问题（"COLREGs Rule 17 怎么处理？"）
│   └── ❌ → DOMAIN（或 ask --scope auto 走 A3 并行）
│
└── 项目内部决策记录
    └── ❌ → PROJ Local
```

#### §2.3.8 示例 Config 片段

```json
{
  "synthesis_notebook": {
    "id": "<uuid>",
    "name": "META · <ProjectName> · Synthesis",
    "source_count": 0,
    "last_distilled": null
  }
}
```

---

### §2.4 GLOBAL · Reference 笔记本

#### §2.4.1 用途定位

**跨项目通用知识库 · 长期稳定参考**。装：

- 已经在多个项目中验证过的稳定知识
- 通用领域参考（不绑定单一项目，如 "Maritime Engineering" / "RAG Best Practices"）
- 跨项目复用的工具、框架、规范

**它不是项目级容器**——GLOBAL 笔记本属于用户账号下的通用资源，多个项目可同时引用。

#### §2.4.2 绑定路径（不在项目内创建）

GLOBAL 笔记本通常在 NotebookLM web UI 手动创建（或通过其他项目）。项目通过 `add-global-notebook` **绑定引用**，不创建：

| 命令 | 行为 |
|------|------|
| `nlm setup --add-global-notebook <UUID> [<UUID2> ...]` | 绑定一个或多个 GLOBAL 笔记本到当前项目 |
| `nlm setup --create-global "<title>"` | 创建新笔记本并自动绑定（罕见，通常 GLOBAL 已存在） |

`config.global_notebooks` 是数组，可绑定多个 GLOBAL 引用。

#### §2.4.3 写入入口（项目侧极少写入）

| 触发场景 | 命令 | 是否自动 |
|---------|------|---------|
| 显式从项目 promote 到 GLOBAL | `/nlm-migrate --content "..." --target-global "<domain>" --title "..."` | ❌ user-only + 显式确认 |
| 用户 add 显式指定 target=global:<UUID> | （未来可能支持，当前 cmd_add 仅支持 local） | ❌ user-only |

#### §2.4.4 写入禁忌

- **research 永不路由到 GLOBAL**（GLOBAL 是稳定参考，不接 raw research）
- **ask 永不写入 GLOBAL**（即使空笔记本冷启动）
- **三重门闸不涉及 GLOBAL**（域演化只在项目内 PROJ/DOMAIN/META 之间）

#### §2.4.5 容量规则

GLOBAL 的容量管理由 **GLOBAL 笔记本的所有者** 负责（通常是用户跨项目维护）。当前项目对 GLOBAL 的容量管理无能为力——只能通过 `migrate` 命令减少新增写入。

如果 GLOBAL 笔记本满（NotebookLM 服务端拒收），用户应：

1. 在 GLOBAL 笔记本所属的"主项目"做蒸馏
2. 或创建新的 GLOBAL 笔记本（如 `GLOBAL · Maritime Engineering v2 · Reference`，但禁止版本号后缀，所以应该用 `GLOBAL · Maritime Engineering Advanced · Reference` 等）

#### §2.4.6 命名约束

```
格式：GLOBAL · {Name} · Reference

约定：{Name} 通常用领域代号，跨项目唯一

示例：
  ✅ GLOBAL · Maritime Engineering · Reference
  ✅ GLOBAL · RAG Best Practices · Reference
  ✅ GLOBAL · Python Standard Lib · Reference
  ❌ GLOBAL · MASS-L3 Maritime · Reference  （绑定项目）
```

#### §2.4.7 触发场景表

```
何时用 GLOBAL（vs DOMAIN / META / Local）？
│
├── 跨项目复用的知识（"Maritime Engineering 通用规范"）
│   └── ✅ GLOBAL
│
├── 单项目内部演进的领域知识
│   └── ❌ → DOMAIN（项目内）
│
├── 已在 DOMAIN 验证稳定，希望 promote 到跨项目
│   └── ✅ → migrate to GLOBAL
│
├── ask 时希望兜底查询通用知识
│   └── ✅ ask --scope global（A3 并行查询的最后一层）
│       或 ask --scope auto 自动 escalate（详见 §3.2 路由）
│
└── 项目级临时笔记
    └── ❌ → PROJ Local
```

#### §2.4.8 示例 Config 片段

```json
{
  "global_notebooks": [
    {
      "id": "<uuid-1>",
      "title": "GLOBAL · Maritime Engineering · Reference",
      "source_count": 0,
      "description": ""
    },
    {
      "id": "<uuid-2>",
      "title": "GLOBAL · RAG Best Practices · Reference",
      "source_count": 0,
      "description": ""
    }
  ]
}
```

---

### §2.5 命名规范与 Config Schema v2

#### §2.5.1 笔记本命名规范（4 SCOPE × Type 对照）

**格式：`{SCOPE} · {Name} · {Type}`**

| SCOPE | 用途 | Type 值 | 唯一性 | 写入策略 |
|-------|------|--------|--------|---------|
| `PROJ` | 项目特有，不跨项目 | `Local` | 每项目唯一 | 项目内可写 |
| `DOMAIN` | 单一专业领域，可跨项目 | `Research` | 每项目 5–15 个 | 项目内可写 |
| `META` | 跨域综合，蒸馏沉淀 | `Synthesis` | 每项目唯一 | 仅 Briefing Doc + 综合文档 |
| `GLOBAL` | 跨项目通用参考 | `Reference` | 跨项目唯一 | 项目内仅 migrate |

**通用命名规则**：

- `{Name}` ≤ 25 字符
- 英文 TitleCase（`COLAV Algorithms`）或中文简短短语（`船舶操纵`）
- **禁止日期后缀**（用 `last_distilled` 字段追踪时间）
- **禁止版本号后缀**（笔记本是活文档，不是版本化产物）
- 中点 `·` 是 U+00B7（中圆点），不是空格 + dot 也不是英文 dot

#### §2.5.2 完整 Config Schema v2

`.nlm/config.json`（项目级，每项目一份）：

```json
{
  "version": 2,
  "project_name": "<project-name>",
  "local_notebook": {
    "id": "<uuid>",
    "title": "PROJ · <ProjectName> · Local",
    "source_count": 0,
    "description": ""
  },
  "global_notebooks": [
    {
      "id": "<uuid>",
      "title": "GLOBAL · <Name> · Reference",
      "source_count": 0,
      "description": ""
    }
  ],
  "synthesis_notebook": {
    "id": "<uuid>",
    "name": "META · <ProjectName> · Synthesis",
    "source_count": 0,
    "last_distilled": null
  },
  "domain_notebooks": {
    "<snake_case_key>": {
      "id": "<uuid>",
      "name": "DOMAIN · <Name> · Research",
      "description": "<人类可读描述>",
      "keywords": ["kw1", "kw2", "kw3"],
      "source_count": 0,
      "last_distilled": null
    }
  },
  "routing": {
    "domain_match_threshold": 0.25,
    "domain_merge_overlap": 0.40,
    "new_domain_min_sources": 20,
    "max_domains": 15,
    "distill_trigger_count": 270,
    "capacity_warn_threshold": 250,
    "capacity_reject_threshold": 290
  }
}
```

#### §2.5.3 `.nlm/` 目录结构

```
<project-root>/.nlm/
├── config.json                  # 笔记本绑定（v2 schema，本节）
├── topics.json                  # 主题画像（用于评分；TopicTracker 维护）
├── notebooks_cache.json         # 笔记本列表 24h 缓存（避免频繁 API）
└── citation_stats.json          # 引用频次统计（来自 ChatReference 累计；P-NEW-A 新增）
```

每个文件的具体 schema：

- `topics.json`：详见 §3.2.5 ask 命令的 topic profile 累积
- `notebooks_cache.json`：标准笔记本列表 dump（24h TTL）
- `citation_stats.json`：详见 §4.1.4 评分公式

#### §2.5.4 全局配置（用户级）

`~/.nlm/global.json`（跨项目共享，可选）：

```json
{
  "preferred_default_research_depth": "fast",
  "preferred_default_max_import": 10,
  "auto_briefing_enabled": true
}
```

环境变量 `NLM_HOME` 可覆盖全局配置根（默认 `~/.nlm/`）。

---

## §3 八命令矩阵（Command Matrix）

8 个用户面命令按 **典型使用流** 排列：环境准备（setup）→ 日常查询（ask）→ 知识沉淀（research / add）→ 决策（plan）→ 维护（migrate / deduplicate / delete）。每个命令用统一 7-子节模板。

### §3.1 `/nlm-setup` — 项目笔记本配置

#### §3.1.1 触发场景与 auto-trigger 规则

**Auto-trigger? ❌ 否，user-only**

| 触发方 | 是否触发 | 反例 |
|-------|--------|------|
| 主会话 Claude | ❌ 不主动触发 | 用户没说要配置笔记本时不触发 |
| 后台 Agent | ❌ 不触发 | Agent 不应修改用户配置 |

**用户主动触发场景**：

1. 新项目首次配置笔记本绑定
2. 切换 Google 账号后重新认证（`--reauth`）
3. 创建新的 DOMAIN 笔记本（响应 `domain_suggestion`）
4. 创建项目的 META synthesis 笔记本
5. 增加 GLOBAL Reference 引用
6. 查看当前配置状态（`--status`）

**决策树：何时用 setup vs 其他命令**

```
用户意图：管理笔记本绑定？
├── 是 → /nlm-setup
│   ├── 首次/重新认证 → --auth / --reauth
│   ├── 查看现有笔记本列表 → --notebook-list
│   ├── 绑定已存在的笔记本 → --add-local-notebook / --add-global-notebook
│   ├── 创建新笔记本 → --create-local / --create-global / --create-domain / --create-synthesis
│   └── 查看当前绑定 → --status
└── 否 → 不用 setup
    ├── 查询知识 → /nlm-ask
    ├── 添加单条来源 → /nlm-add
    ├── 研究新主题 → /nlm-research
    └── 其他 → 见对应命令章节
```

#### §3.1.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--auth` | 互斥 | — | 首次 Google 认证（打开 Chrome） |
| `--reauth` | 互斥 | — | 重新认证（清除旧 cookies + 重新登录） |
| `--status` | 互斥 | — | 查看当前绑定，零 API 调用 |
| `--notebook-list` | 互斥 | — | 列出账号下所有笔记本（24h 缓存） |
| `--refresh` | 与 `--notebook-list` 配合 | — | 强制刷新笔记本列表缓存 |
| `--add-local-notebook UUID` | 互斥 | — | 绑定为 PROJ Local |
| `--add-global-notebook UUID [UUID2 ...]` | 互斥 | — | 追加为 GLOBAL Reference |
| `--create-local TITLE` | 互斥 | — | 创建笔记本绑定为 Local（自动加 `PROJ · ... · Local`） |
| `--create-global TITLE` | 互斥 | — | 创建笔记本追加为 Global（自动加 `GLOBAL · ... · Reference`） |
| `--create-domain TITLE` | 互斥 | — | 创建 Domain 笔记本（自动加 `DOMAIN · ... · Research`），需配合 `--domain-key`/`--domain-keywords` |
| `--create-synthesis TITLE` | 互斥 | — | 创建 META synthesis 笔记本（自动加 `META · ... · Synthesis`） |
| `--domain-key KEY` | `--create-domain` 必填 | — | snake_case 域键 |
| `--domain-keywords KEYWORDS` | `--create-domain` 必填 | — | 逗号分隔关键词（路由用） |
| `--domain-description DESC` | `--create-domain` 可选 | `""` | 人类可读描述 |
| `--project-path PATH` | 否 | `.` | 项目根目录（含 `.nlm/config.json`） |

#### §3.1.3 路由规则

N/A — setup 不做路由（不查询、不写入笔记本来源）。

#### §3.1.4 目标行为（按子命令）

##### `--auth` / `--reauth`

```
Step 1: 检测当前 auth 状态（cookie 文件存在 + 未过期）
Step 2 (--auth):  已认证 → 直接返回 ok；未认证 → 走 Step 3
Step 2 (--reauth): 直接清除现有 cookies → 走 Step 3
Step 3: 用 patchright 启动真实 Chrome → 打开 notebooklm.google.com
Step 4: 等待用户登录（最多 5 分钟）
Step 5: 检测到登录成功 → 保存 cookies 到 ~/.notebooklm/storage_state.json
Step 6: 返回 {"status": "ok", "authenticated": true, "cookies_imported": N}
```

##### `--notebook-list [--refresh]`

```
Step 1: 检查 .nlm/notebooks_cache.json 是否存在且 < 24h
Step 2: 缓存有效 + 未指定 --refresh → 返回缓存；否则走 Step 3
Step 3: 调 NotebookLM API list_notebooks
Step 4: 并行获取每个笔记本的 AI 描述（summary + topics）
Step 5: 写入 .nlm/notebooks_cache.json
Step 6: 输出 markdown table（# / UUID / Title / Sources / Created）
```

##### `--create-local "<title>"` / `--create-global "<title>"` / `--create-domain "<title>"` / `--create-synthesis "<title>"`

```
Step 1: 自动加 SCOPE/Type 前后缀（PROJ/Local | GLOBAL/Reference | DOMAIN/Research | META/Synthesis）
Step 2: 调 NotebookLM API create_notebook（用包装后的标题）
Step 3: 写入 .nlm/config.json 对应字段（local_notebook / global_notebooks / domain_notebooks.<key> / synthesis_notebook）
Step 4: 返回 {"status": "ok", "bound": "<tier>", "created": true, "<tier>_notebook": {...}}
```

##### `--add-local-notebook UUID` / `--add-global-notebook UUID [UUID2 ...]`

```
Step 1: 验证 UUID 在 notebooks_cache 中存在
Step 2: 写入 config（local_notebook 是覆盖；global_notebooks 是追加）
Step 3: 返回 {"status": "ok", "bound": "local|global", "created": false, ...}
```

##### `--status`

```
Step 1: 读 .nlm/config.json（不调 API）
Step 2: 返回完整配置 dump（local + global + synthesis + domains）
```

#### §3.1.5 输入输出契约（JSON 示例）

##### `--status` 输出

```json
{
  "status": "ok",
  "authenticated": true,
  "project_path": "/Users/.../<project>",
  "local_notebook": { "id": "...", "title": "PROJ · ... · Local", "source_count": 0 },
  "global_notebooks": [ { "id": "...", "title": "GLOBAL · ... · Reference" } ],
  "synthesis_notebook": { "id": "...", "name": "META · ... · Synthesis", "source_count": 0, "last_distilled": null },
  "domain_notebooks": {
    "<key>": { "id": "...", "name": "DOMAIN · ... · Research", "keywords": [...], "source_count": 0 }
  },
  "next_step": null
}
```

##### `--create-domain` 输出

```json
{
  "status": "ok",
  "bound": "domain",
  "created": true,
  "domain_key": "<key>",
  "domain_notebook": {
    "id": "<uuid>",
    "name": "DOMAIN · <Name> · Research",
    "description": "<desc>",
    "keywords": ["kw1", "kw2"],
    "source_count": 0,
    "last_distilled": null
  },
  "total_domains": 5,
  "next_step": {
    "hint": "域笔记本已创建。运行 /nlm-research 时来源将自动路由至此。",
    "commands": [ "nlm research --topic \"...\" --target domain:<key>" ]
  }
}
```

##### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | `"ok"` / `"error"` | 顶级状态 |
| `bound` | `"local"` / `"global"` / `"domain"` / `"synthesis"` | 绑定的层级 |
| `created` | bool | 是否新建（vs 仅绑定已存在） |
| `next_step.hint` | string | 自然语言下一步建议 |
| `next_step.commands` | string[] | 可立即执行的命令模板 |

#### §3.1.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"authenticated": false` | 未认证或 session 过期 | 先运行 `--auth` 或 `--reauth` |
| `"error": "cache_missing"` | `--add-*-notebook UUID` 但缓存中找不到该 UUID | 先运行 `--notebook-list` |
| `"error": "uuid_not_found"` | 提供的 UUID 在新拉取的列表中也找不到 | `--notebook-list --refresh` 后重试 |
| `"error": "local_already_bound"` | 已有 local 但用 `--create-local` 或 `--add-local` | 询问用户是否覆盖 |
| `"error": "domain_already_exists"` | `--create-domain --domain-key X` 但 X 已存在 | 用其他 key 或先 merge/delete |
| `"error": "synthesis_already_configured"` | 已有 synthesis 但用 `--create-synthesis` | 项目唯一 META，不能再建 |

#### §3.1.7 实施差距

- **[GAP-5]** 主 [SKILL.md:81](/Users/marine/.claude/skills/nlm/SKILL.md#L81) 仍是单笔记本时代的老接口（`--create "..."`），未反映 4 层架构；需重写

---

### §3.2 `/nlm-ask` — 知识查询（read-only）

#### §3.2.1 触发场景与 auto-trigger 规则

**Auto-trigger? ✅ 是，主动触发**

| 触发方 | 是否触发 | 触发条件 |
|-------|--------|---------|
| 主会话 Claude | ✅ | 用户问技术概念、API 用法、领域知识、架构模式时 |
| 后台 Agent | ✅ | 同上（行为完全一致） |

**Auto-trigger 触发条件**：

- 知识不确定性（"什么是 X？"、"X 怎么实现？"、"X 的最佳实践是什么？"）
- 涉及笔记本可能涵盖的领域知识
- 不在当前代码或对话上下文中可直接回答

**Do NOT use for**:

- 通用编程语法（应直接回答或用 web search）
- 公开 API 文档（用 firecrawl / web fetch）
- 当前仓库中可 grep 的代码（用 Grep / Read）
- 一般对话或闲聊

**用户主动触发场景**：

1. "what does my notebook say about X?" 类显式查询
2. 决策评估前的知识收集（配合 `/nlm-plan` 使用）

#### §3.2.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--question TEXT` | ✅ | — | 查询的问题 |
| `--scope` | 否 | `auto` | 查询路由目标：`auto` / `local` / `global` / `synthesis` / `domain:<key>` |
| `--on-low-confidence` | 否 | `prompt` | 低置信度时的行为：`prompt`（提示用户） / `research`（自动 research+retry，**违反 spec §6 "绝不写入"，已废弃**） / `silent`（仅返回） |
| `--format` | 否 | `json` | 输出格式：`json` / `text` |
| `--project-path PATH` | 否 | `.` | 项目根 |

#### §3.2.3 路由规则（`--scope auto`，A3 并行融合）

```
ask --scope auto 路由决策树：

1. 检测目标笔记本是否为空（冷启动检测）
   ├── 空 → §4.2.1 冷启动子流（自动 fast research → import → re-ask）
   └── 非空 → 进入 Phase 2

2. classify_domain(question) → 域键 | "local" | NEW:<name> | null

3. Phase 2a + 2b · A3 并行查询：
   a. 若 classify 命中某 domain → 并行查询 [domain notebook, local notebook]
   b. 若 classify 是 "local" → 并行查询 [local notebook]
   c. 若 classify 是 NEW: → 并行查询 [local notebook]（不查未存在的域）
   d. 若 classify 是 null（跨域综合）→ 并行查询 [synthesis notebook, local notebook]

4. 答案融合（A3）：
   - 高置信度结果优先（domain 通常胜过 local）
   - 答案中标注每个引用属于哪个 source notebook（answered_by 字段）

5. Phase 3 escalation（仅当 Phase 2 全部 low confidence）：
   并行查询 [global notebooks（按 Haiku 排序前 3）]

6. Phase 4 兜底（仅当 Phase 3 仍 low confidence）：
   查询 synthesis notebook（如果未在 Phase 2 查询过）
```

#### §3.2.4 显式 scope 路由

| `--scope` 值 | 行为 |
|------|------|
| `auto` | 见 §3.2.3 完整决策树 |
| `local` | 仅查 PROJ Local 笔记本 |
| `global` | Haiku 路由排序后查 top-3 GLOBAL 笔记本 |
| `synthesis` | 仅查 META Synthesis 笔记本 |
| `domain:<key>` | 仅查指定 DOMAIN 笔记本，低置信度时 fallback 到 local |

#### §3.2.5 目标行为（步骤化）

```
Step 1: 加载 config（local + global + synthesis + domain notebooks）
Step 2: 若所有笔记本均无配置 → 错误 "No notebooks configured"
Step 3: 按 --scope 路由（见 §3.2.3）

Step 4: 冷启动检测（仅 --scope auto / local / domain:<key> 时）
  4a: 检查目标笔记本 source_count
  4b: source_count == 0 → 触发 §4.2.1 冷启动子流
       注意：scope=synthesis 不触发冷启动（META 不接 raw research）

Step 5: A3 并行查询（asyncio.gather）
  5a: 调 client.ask(notebook_id, question) 各目标笔记本
  5b: 收集所有非低置信度答案

Step 6: 答案融合
  6a: 选最高置信度的答案为主答案
  6b: answered_by 字段列出所有贡献笔记本（最具体在前）
  6c: citations 字段聚合所有 ChatReference

Step 7: Citation Frequency Tracking（P-NEW-A 新增）
  7a: 解析每个答案的 ChatReference 数组
  7b: 累计写入 .nlm/citation_stats.json：每个 source_id 的 count++
  7c: 静默执行，不阻塞答案返回

Step 8: Topic Profile 累积
  8a: TopicTracker.record_ask(question)，weight=1.0
  8b: 用于后续评分（§4.1）

Step 9: 输出处理
  9a: confidence in {low, not_found} → suggest_research = true
  9b: --on-low-confidence prompt（默认）→ 加 next_action 提示
  9c: --on-low-confidence silent → 仅返回结果
  9d: --on-low-confidence research → ⚠ 已废弃（违反 spec §6），保留但警告

Step 10: 返回 JSON 结果
```

#### §3.2.6 输入输出契约

##### 输入

```bash
nlm ask --question "What does the notebook say about COLREGs Rule 17?" \
        --scope auto \
        --format json \
        --project-path .
```

##### 输出（成功 + 高置信度）

```json
{
  "answer": "COLREGs Rule 17 governs the stand-on vessel obligations...",
  "confidence": "high",
  "answered_by": ["domain:maritime_regulations", "local"],
  "source_notebook": "domain:maritime_regulations",
  "citations": [
    {
      "citation_number": 1,
      "text": "Rule 17(a) states that the stand-on vessel...",
      "source_id": "<uuid>"
    }
  ],
  "suggest_research": false
}
```

##### 输出（低置信度 + prompt）

```json
{
  "answer": "I don't have specific information on this topic.",
  "confidence": "not_found",
  "answered_by": ["local"],
  "source_notebook": "local",
  "citations": [],
  "suggest_research": true,
  "next_action": {
    "type": "suggest_research",
    "message": "本地笔记本对此问题置信度较低，建议通过 /nlm-research 补充相关资料后重试。",
    "command": "nlm research --topic \"<question>\" --add-sources --project-path \".\""
  }
}
```

##### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `answer` | string | 自然语言答案 |
| `confidence` | `"high"` / `"medium"` / `"low"` / `"not_found"` | NotebookLM 答案质量评估 |
| `answered_by` | string[] | 贡献笔记本列表（最具体在前） |
| `source_notebook` | string | 主答案来源（answered_by[0]） |
| `citations[]` | object[] | 引用信息（含 ChatReference 解析） |
| `suggest_research` | bool | 是否建议触发 research |
| `next_action` | object \| null | 仅 `--on-low-confidence prompt` 且低置信度时存在 |

#### §3.2.7 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "No notebooks configured"` | 项目未 setup | 先 `/nlm-setup` 配置 |
| `"error": "Domain '<key>' not found"` | `--scope domain:X` 但 X 未配置 | 列出已有 domain 给用户选 |
| `"error": "Domain '<key>' has no notebook ID"` | config 损坏 | 重新 setup 该 domain |
| `confidence: not_found` | 笔记本无相关内容 | 输出 suggest_research = true（不报错） |
| Network/auth 错误 | NotebookLM 服务不可达 / cookies 过期 | 提示 reauth |

#### §3.2.8 实施差距

- **[GAP-3]** [`nlm.py:411-414`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L411) `cmd_ask` 默认 `--on-low-confidence research` 会**自动写入 local 笔记本**，违反 spec §6 "绝不写入"。修复：默认改 `prompt`
- **[GAP-7]** [子 skill nlm-ask SKILL.md:18](/Users/marine/.claude/skills/nlm/skills/nlm-ask/SKILL.md#L18) 写默认 `prompt` 但代码默认 `research`，文档与代码不符（依赖 GAP-3 修复）
- **[GAP-10]** Citation Frequency Tracker（P-NEW-A）未实现：[`nlm.py`](/Users/marine/.claude/skills/nlm/scripts/nlm.py) 当前只用 `TopicTracker.record_ask`（仅累积 question 的 keywords），未利用 ChatReference 数组累计每个 source_id 的引用次数

---

### §3.3 `/nlm-research` — 研究 + 知识沉淀

#### §3.3.1 触发场景与 auto-trigger 规则

**Auto-trigger? ✅ 部分自动**

| 模式 | 触发方 | 是否 auto |
|------|-------|----------|
| `--no-add-sources`（read-only） | 主会话 + Agent | ✅ 自动（并行 subagent dispatch、知识探索） |
| `--add-sources`（默认，写入笔记本） | 仅用户 | ❌ user-triggered only（写操作） |

**用户主动触发场景**：

1. 知识沉淀：`/nlm-research <topic>`（默认含 `--add-sources`）
2. 响应 `domain_suggestion`：创建新域后触发该域 research 累积
3. 响应低置信度回退：用户接受 `suggest_research` 提示后触发
4. 调研某主题：`/nlm-research --no-add-sources <topic>`（仅看报告，不沉淀）

**决策树：何时用 research vs 其他**

```
用户意图：
├── 已知问题、想要答案 → /nlm-ask
├── 探索新主题、想要全面调研 → /nlm-research
│   ├── 想沉淀知识 → 默认（--add-sources）
│   └── 仅看报告 → --no-add-sources
└── 比较多个候选方案 → /nlm-plan
```

#### §3.3.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--topic TEXT` | ✅ | — | 研究主题 |
| `--depth` | 否 | `fast` | `fast`（60s 超时）/ `deep`（600s 超时，含完整 bibliography） |
| `--add-sources` / `--no-add-sources` | 否 | `--add-sources` | 是否导入来源到笔记本 |
| `--target` | 否 | `auto` | 写入路由目标：`auto` / `local` / `synthesis` / `domain:<key>` |
| `--max-import N` | 否 | 10（fast）/ 不限（deep） | 单次导入上限 |
| `--min-relevance F` | 否 | `0.05` | 评分排序的相关性阈值（仅排序提示，不删除） |
| `--project-path PATH` | 否 | `.` | 项目根 |

#### §3.3.3 路由规则（`--target auto`，B1）

```
research --target auto 路由决策树：

1. classify_domain(topic) → 域键 | "local" | "NEW:<inferred_name>" | "null"

2. 若返回 域键：
   → 命中现有 domain：
   → import to that domain notebook

3. 若返回 "local"（match_score 低但有项目相关性）：
   → import to PROJ Local

4. 若返回 "NEW:<name>"（无现有 domain 匹配）：
   → 三重门闸检验（详见 §2.2.2）
     Gate 1 (积压<20): 拒绝建域 → import to Local
     Gate 2 (重叠≥40%): 路由到最近域
     Gate 3 (总域≥15): 路由到 META + ⚠ 标记
     全过: 输出 domain_suggestion，本次仍 import to Local（用户确认后再 create-domain）

5. 若返回 "null"（无明显 topic）：
   → import to PROJ Local
```

#### §3.3.4 显式 target 路由

| `--target` 值 | 行为 |
|------|------|
| `auto` | 见 §3.3.3（B1 路由） |
| `local` | 强制写入 PROJ Local（绕过域分类） |
| `synthesis` | 强制写入 META（罕见，谨慎使用，违反"META 不接 raw research"约定） |
| `domain:<key>` | 强制写入指定 DOMAIN |

#### §3.3.5 目标行为（步骤化，含 P-NEW v2 双产物分流）

```
Step 1: 解析 --target，确定 notebook_id
Step 2: 容量检查（target notebook source_count）
  2a: ≥ 290 → CapacityError，建议先蒸馏 / 删除低分源
  2b: ≥ 270 → distillation_required = true（继续但 warn）

Step 3: TopicTracker.record_research(topic)，weight=2.0

Step 4: 调 NotebookLM research API（fast 60s / deep 600s）
  4a: 失败 → 返回错误（不重试）
  4b: 成功 → 拿到 sources 数组 + report 字段

Step 5 (--add-sources only): P-NEW v2 双产物分流
  5a: 解析 report 末尾 bibliography（用 \n---\n 分隔符 + 正则 ^\d+\.\s+.+,\s*\[(http)\]）
       提取 cited URL 集合
  5b: 分流 sources：
      → result_type==5 entry → import 到 META（compressed source；P-NEW-B）
      → result_type==1 + url ∈ cited URLs → import 到 target（cited 高质量源）
      → result_type==1 + url ∉ cited URLs → 跳过（uncited 搜索池）
       注意：fast 模式无 cited 区分，全部 import（受 max-import 限制）

Step 6: import_research_sources()
  6a: dedup（URL 重复检测）
  6b: capacity guard（接近 290 时截断）
  6c: 调 NotebookLM import_sources API
  6d: 等待处理完成（最多 120s）
  6e: 删除 ERROR 状态的源

Step 7: 评分排序（P-NEW v2，仅 source_count >= 250 时启动）
  7a: 调 score_and_prune_sources（实际上不删除，仅排序）
  7b: 评分公式（W1+W2+W3 = 1.0）：
       W1 = 0.5 × citation_freq_in_chats（来自 .nlm/citation_stats.json）
       W2 = 0.3 × cited_in_research_report（cited URLs 集合）
       W3 = 0.2 × keyword_match（source.guide.keywords vs topic profile）
  7c: 输出低分 top-50 给用户决策（**不自动删除**）

Step 8: 蒸馏触发检查
  8a: source_count > 270 → 提示 distillation_required
  8b: AUTO BRIEFING：调 NotebookLM API 生成 Briefing Doc → 提示用户审阅
  8c: 用户确认后 import to META

Step 9: 域演化检查
  9a: check_merge_candidates → merge_suggestions
  9b: check_split_candidates → split_suggestions
  9c: 输出建议（不自动执行）

Step 10: 返回完整 JSON 结果
```

#### §3.3.6 输入输出契约

##### 输入

```bash
nlm research --topic "MPC for ASV collision avoidance" \
             --depth deep \
             --add-sources \
             --target auto \
             --project-path .
```

##### 输出（典型 deep + add-sources）

```json
{
  "status": "ok",
  "topic": "MPC for ASV collision avoidance",
  "target_notebook": "domain:colav_algorithms",
  "report": "<33000+ 字 markdown report>",
  "sources": [...],
  "sources_cited_count": 39,
  "sources_imported": 39,
  "sources_pruned": 0,
  "duplicates_removed": 0,
  "notebook_source_count": 53,
  "add_sources": true,
  "compressed_source_imported_to_synthesis": {
    "id": "<uuid>",
    "title": "Deep Research: MPC for ASV ... 2026-04-29"
  },
  "relevance_scores": [
    {"id": "<sid>", "score": 0.85, "rank": 1, "kept": true, "keywords": [...]}
  ],
  "merge_suggestions": [],
  "split_suggestions": [],
  "domain_suggestion": null,
  "distillation_required": false
}
```

##### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `target_notebook` | string | 实际写入目标 |
| `report` | string | NotebookLM 综合报告（deep 模式含 bibliography） |
| `sources` | object[] | 全部搜索池（含 cited + uncited） |
| `sources_cited_count` | int | bibliography 中编号引用数（**不是 SDK 字段，由 BUG 12 helper 解析得出**） |
| `sources_imported` | int | 实际写入笔记本数量（cited + report） |
| `compressed_source_imported_to_synthesis` | object \| null | P-NEW-B：deep report 自动写入 META 的 source 信息 |
| `relevance_scores[]` | object[] | 评分排序结果（仅 source_count >= 250 时填充） |
| `domain_suggestion` | object \| null | 三重门闸通过时输出新域建议 |
| `merge_suggestions` / `split_suggestions` | object[] | 域演化建议 |
| `distillation_required` | bool | 是否触发蒸馏建议 |

#### §3.3.7 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `Research timed out after Ns` | NotebookLM 超时（fast 60s / deep 600s） | 不重试；建议改 fast 模式 / 等高峰期过 |
| `Research failed to start` | API 拒绝（quota / auth） | 检查 reauth + 配额（deep 配额日 ~1-3 次） |
| `RateLimitError` | 日配额耗尽 | 等 24h 或换账号（deep 配额账号独立） |
| `CapacityError` | target notebook ≥ 290 | 先蒸馏 / 删除低分源 / 创建新域 |
| `Domain '<key>' not found` | `--target domain:X` 但未配置 | 列出已有 domain |
| `Domain '<key>' has no notebook ID` | config 损坏 | 重新 setup 该 domain |

#### §3.3.8 实施差距

- **[GAP-1]** [`client.py:419`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L419) `_score_keywords` 对空 keywords 返回 0 → 误删新源；修复：返回 0.5 fallback keep
- **[GAP-4]** [`client.py:501`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L501) `score_and_prune_sources` 返回缺 `notebook_count` 字段；修复：补字段
- **[GAP-9]** [`nlm.py:782`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L782) `cited_in_report` 字段在 SDK 不存在 → 该过滤逻辑是死代码；修复：改用 bibliography 正则解析
- **[GAP-11]** [`nlm.py:769`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L769) `sources_cited_count` 字段在 SDK 不存在；修复：改为 `len(cited_urls)`
- **[GAP-12]** 无 bibliography 解析机制；新增 `_parse_bibliography_urls(report) -> set[str]` helper

---

### §3.4 `/nlm-add` — 手动添加单条来源

#### §3.4.1 触发场景与 auto-trigger 规则

**Auto-trigger? ❌ 否，user-only**

| 触发方 | 是否触发 | 反例 |
|-------|--------|------|
| 主会话 Claude | ❌ 不主动触发 | 用户没说要"加这个 URL"时不触发 |
| 后台 Agent | ❌ 不触发 | 写操作必须用户授权 |

**用户主动触发场景**：

1. 用户明确要求 `/nlm-add --url <URL>` 或 `/nlm-add --note "<text>"`
2. 蒸馏流程：用户在 NotebookLM UI 生成 Briefing Doc → 下载 → `/nlm-add --target synthesis --note "..."`
3. 项目决策记录：`/nlm-add --note "Decision: chose A over B because..."`
4. 偶遇有用 URL：`/nlm-add --url "https://..."`

**决策树：何时用 add vs research**

```
用户意图：增加单条来源 vs 研究主题？
├── 已知 URL，想直接加 → /nlm-add --url
├── 想保存一段文本/笔记 → /nlm-add --note
├── 想由 NotebookLM 调研，得到多个来源 → /nlm-research
└── 想加蒸馏文档到 META → /nlm-add --target synthesis --note
```

#### §3.4.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--url URL` | 互斥 | — | Web 页面作为来源添加 |
| `--note TEXT` | 互斥 | — | 文本内容作为笔记保存 |
| `--title TEXT` | 配合 `--note` | `"Note"` | 笔记标题 |
| `--target` | 否 | `local` | 写入目标：`local` / `synthesis` / `domain:<key>` |
| `--project-path PATH` | 否 | `.` | 项目根 |

`--url` 与 `--note` 互斥，必须二选一。

#### §3.4.3 路由规则

显式 `--target` 路由（不做 auto 分类）：

| `--target` 值 | 行为 |
|------|------|
| `local`（默认） | 写入 PROJ Local |
| `synthesis` | 写入 META Synthesis（用于 Briefing Doc 等综合文档） |
| `domain:<key>` | 写入指定 DOMAIN |

**注意**：`add --target global:<UUID>` **不支持**——GLOBAL 是跨项目共享，应通过 `/nlm-migrate` 显式 promote。

#### §3.4.4 目标行为

```
Step 1: 验证 --url 或 --note 至少一个提供
Step 2: 解析 --target，确定 notebook_id（同 §3.3 路由）
Step 3 (--url): 
  3a: URL 规范化（去尾部斜杠、转小写）
  3b: 检查目标笔记本是否已含此 URL
  3c: 已存在 → 返回 {"status": "skipped", "reason": "already_exists"}
  3d: 新增 → 调 client.add_url() → 等待处理（最多 60s）
Step 4 (--note):
  4a: 调 client.add_note(notebook_id, title, content)
  4b: 等待处理完成
Step 5: 返回结果
```

#### §3.4.5 输入输出契约

##### 输入示例

```bash
# URL 添加
nlm add --url "https://example.com/paper" --target local --project-path .

# 笔记添加
nlm add --note "Key insight: COLREGs Rule 8 requires ..." \
        --title "COLREGs Notes" \
        --target local

# 蒸馏文档添加到 META
nlm add --note "<Briefing Doc content>" \
        --title "Navigation Algorithms Briefing 2026-04" \
        --target synthesis
```

##### 输出（URL 成功添加）

```json
{
  "status": "ok",
  "type": "url",
  "target": "local",
  "source": {"id": "<uuid>", "title": "<auto-extracted-title>"}
}
```

##### 输出（URL 已存在，跳过）

```json
{
  "status": "skipped",
  "reason": "already_exists",
  "target": "local",
  "source": {"id": "<uuid>", "title": "<existing-title>"}
}
```

##### 输出（笔记成功添加）

```json
{
  "status": "ok",
  "type": "note",
  "target": "synthesis",
  "note": {"id": "<uuid>", "title": "<provided-title>"}
}
```

#### §3.4.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "Provide --url or --note"` | 二者都没提供 | 询问用户内容 |
| `"error": "Both --url and --note provided"` | 同时提供（互斥） | 选一个 |
| `"error": "No <tier> notebook configured"` | `--target X` 但 X 未配置 | 先 setup 创建该层 |
| `"error": "Domain '<key>' not found"` | `--target domain:X` 但 X 未配置 | 列出已有 domain |
| `CapacityError` | 目标笔记本 ≥ 290 | 先蒸馏或删除 |
| Network/auth 错误 | NotebookLM 不可达 | 检查 auth |

#### §3.4.7 实施差距

- **[GAP-2]** [`nlm.py:911-921`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L911) `cmd_add` 仅支持 `local`，无 `--target` 参数；修复：参考 `cmd_research` 的 target 解析逻辑
- **[GAP-6]** [README.md:230-237](/Users/marine/.claude/skills/nlm/README.md#L230) 蒸馏 workflow 用 hack（"临时改 config 让 local 指向 synthesis"），依赖 GAP-2 修复后改用 `--target synthesis`
- **[GAP-8]** [子 skill nlm-add SKILL.md](/Users/marine/.claude/skills/nlm/skills/nlm-add/SKILL.md) 没说支持写 META/DOMAIN，依赖 GAP-2 修复后更新文档

---

### §3.5 `/nlm-plan` — 多选项决策评估

#### §3.5.1 触发场景与 auto-trigger 规则

**Auto-trigger? ✅ 是**

| 触发方 | 是否触发 | 触发条件 |
|-------|--------|---------|
| 主会话 Claude | ✅ | 用户面对 2+ 候选方案需评估时 |
| 后台 Agent | ✅ | 同上 |

**Auto-trigger 触发条件**：

- 用户问 "should we use A or B?" / "A vs B comparison"
- 架构选型、库选型、算法对比类决策
- 已有 ≥2 个明确候选选项

**Do NOT use for**:

- 单一选项的优劣分析（用 `/nlm-ask` 即可）
- 通用 "best practice"（用 `/nlm-research` 调研）
- 没有明确 candidates 的开放式探索

#### §3.5.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--question TEXT` | ✅ | — | 决策问题（如 "Should we use A or B?"） |
| `--options TEXT` | ✅ | — | 逗号分隔的候选选项（如 `"A,B,C"`） |
| `--criteria TEXT` | 否 | 自动推导 | 逗号分隔的评估维度（如 `"performance,maintainability,cost"`） |
| `--max-research INT` | 否 | `3` | 最多 escalate 几次 deep research（用于补充证据） |
| `--project-path PATH` | 否 | `.` | 项目根 |

#### §3.5.3 路由规则

`/nlm-plan` 不做笔记本路由（不写入），但会 **从笔记本读取证据**（按 ask 路由策略 §3.2.3）。

#### §3.5.4 目标行为（4 阶段）

```
Phase 1 · Evidence Collection（证据收集）
  对每个 (option, criterion) 组合：
    - 用 /nlm-ask 风格查询：候选 X 在 criterion Y 下的表现是什么？
    - 收集 NotebookLM 已有知识

Phase 2 · Selective Research Escalation（按需研究升级）
  - 检测哪些 (option, criterion) 证据不足（low confidence）
  - 选证据最薄弱的 1-3 个组合，触发 fast research（read-only，--no-add-sources）
  - 用 max-research 上限（默认 3）

Phase 3 · Structured Scoring（1-5 结构化评分）
  对每个 (option, criterion) 组合：
    - 基于已收集的证据，由 LLM 给出 1-5 分（5 = 最优）
    - 提供评分理由（rationale）+ 证据引用

Phase 4 · Aggregation（聚合）
  - 加权求和（criteria 权重默认均等，可指定）
  - 输出推荐 option（top-1）+ rationale + matrix
```

#### §3.5.5 输入输出契约

##### 输入

```bash
nlm plan --question "Should we use A* or RRT for ASV path planning?" \
         --options "A*,RRT,Hybrid A*" \
         --criteria "completeness,real-time performance,COLREGs compliance" \
         --max-research 3 \
         --project-path .
```

##### 输出

```json
{
  "status": "ok",
  "question": "...",
  "options": ["A*", "RRT", "Hybrid A*"],
  "criteria": ["completeness", "real-time performance", "COLREGs compliance"],
  "recommendation": "Hybrid A*",
  "rationale": "Hybrid A* offers best balance: ...",
  "matrix": {
    "A*":         {"completeness": 5, "real-time performance": 2, "COLREGs compliance": 3, "weighted_total": 3.33},
    "RRT":        {"completeness": 3, "real-time performance": 5, "COLREGs compliance": 3, "weighted_total": 3.67},
    "Hybrid A*":  {"completeness": 4, "real-time performance": 4, "COLREGs compliance": 4, "weighted_total": 4.00}
  },
  "raw_answers": [...],
  "research_calls": 2
}
```

##### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `recommendation` | string | top-1 候选 |
| `rationale` | string | 推荐理由（含 trade-off） |
| `matrix` | object | 完整评分矩阵 |
| `weighted_total` | float | 加权总分（每个 option 一个） |
| `raw_answers[]` | object[] | 每个 (option, criterion) 的原始答案与证据引用 |
| `research_calls` | int | 实际触发的 research 次数 |

#### §3.5.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "No notebooks configured"` | 项目未 setup | 先 setup |
| `"error": "Need at least 2 options"` | `--options` 仅 1 个 | 用 `/nlm-ask` 替代 |
| `"error": "Empty criteria after auto-derivation"` | 无法自动推导 criteria | 用户显式提供 `--criteria` |
| Phase 2 research 全部超时 | NotebookLM 慢 / quota | 报告但继续（用现有证据评分） |

#### §3.5.7 实施差距

无（plan 已有独立详细 spec：[2026-04-22-nlm-plan-evaluation-design.md](./2026-04-22-nlm-plan-evaluation-design.md)）。

---

### §3.6 `/nlm-migrate` — Promote 知识到 GLOBAL

#### §3.6.1 触发场景与 auto-trigger 规则

**Auto-trigger? ❌ 否，user-only + 显式确认**

| 触发方 | 是否触发 | 反例 |
|-------|--------|------|
| 主会话 Claude | ❌ 不主动触发 | 跨项目 promote 必须用户决策 |
| 后台 Agent | ❌ 不触发 | 同上 |

**用户主动触发场景**：

1. 项目内 DOMAIN/Local 中沉淀的稳定知识，跨项目复用价值高
2. 通用领域参考的更新（如 "Maritime Engineering" GLOBAL 笔记本的新增）

**决策树：何时用 migrate vs add**

```
用户意图：增加来源到 GLOBAL？
├── 是新内容 + 跨项目共享 → /nlm-migrate（必须显式确认）
├── 是项目内部产物 → /nlm-add --target local
└── 是项目领域知识 → /nlm-add --target domain:<key>
```

#### §3.6.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--content TEXT` | ✅ | — | 要迁移的内容（markdown） |
| `--target-global DOMAIN` | ✅ | — | GLOBAL 笔记本的领域代号 |
| `--title TEXT` | 否 | 自动生成 | 笔记标题 |
| `--project-path PATH` | 否 | `.` | 项目根 |

`DOMAIN` 是 GLOBAL 笔记本的领域代号（不是项目级 domain key），需对应 `config.global_notebooks` 中已绑定的笔记本。

#### §3.6.3 路由规则

显式路由：写入指定 GLOBAL 笔记本（必须已在 `config.global_notebooks` 中绑定）。

#### §3.6.4 目标行为

```
Step 1: 解析 --target-global，找到对应 GLOBAL 笔记本 UUID
  1a: 未绑定 → 错误，提示先 add-global-notebook
Step 2: 显式确认（CLI 提示用户：要 migrate 到 <title>，确认？）
Step 3: 用户确认后调 client.add_note(global_notebook_id, title, content)
Step 4: 等待处理完成
Step 5: 返回结果（含 source_id）
```

#### §3.6.5 输入输出契约

##### 输入

```bash
nlm migrate --content "ESKF outperforms EKF for ..." \
            --target-global "maritime-engineering" \
            --title "Sensor Fusion Findings" \
            --project-path .
```

##### 输出

```json
{
  "status": "ok",
  "type": "migrate",
  "target_global": "maritime-engineering",
  "global_notebook_id": "<uuid>",
  "global_notebook_title": "GLOBAL · Maritime Engineering · Reference",
  "migrated_note": {"id": "<uuid>", "title": "Sensor Fusion Findings"}
}
```

#### §3.6.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "No global notebook tagged '<DOMAIN>'"` | `--target-global X` 但未绑定 | 先 `setup --add-global-notebook UUID` |
| `"error": "User cancelled migration"` | 用户在确认提示拒绝 | 中止 |
| GLOBAL 笔记本满 | NotebookLM 拒收 | 由 GLOBAL 所有者负责蒸馏 |

#### §3.6.7 实施差距

无关键 gap（migrate 是低使用频率命令，当前实现可用）。

---

### §3.7 `/nlm-deduplicate` — 去重维护

#### §3.7.1 触发场景与 auto-trigger 规则

**Auto-trigger? ❌ 否，user-only**

| 触发方 | 是否触发 |
|-------|--------|
| 主会话 Claude | ❌ |
| 后台 Agent | ❌ |

**用户主动触发场景**：

1. 笔记本中发现重复 URL（手动观察）
2. 多次 research 累积后清理
3. 笔记本接近容量上限前的整理

**注意**：`/nlm-research` 内部已自动触发 dedup（每次 import 后），所以日常不需要手动调用 `deduplicate`。这个命令是兜底维护工具。

#### §3.7.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--notebook-id UUID` | 否 | 当前项目 local | 直接指定笔记本（绕过项目 config） |
| `--project-path PATH` | 否 | `.` | 项目根 |

#### §3.7.3 路由规则

默认作用于 PROJ Local；可用 `--notebook-id` 直接指定任意笔记本（如 DOMAIN 或 META）。

#### §3.7.4 目标行为

```
Step 1: 解析 --notebook-id 或读 config.local_notebook
Step 2: 调 client.sources.list(notebook_id)
Step 3: 删除 is_error=true 的来源（处理失败的）
Step 4: URL 规范化（去尾部斜杠、转小写）
Step 5: 按 URL 分组：保留最早的，删除重复
Step 6: 返回 {"removed": N, "failed_removed": F, "kept": M}
```

**保留策略**：每个唯一 URL 保留**最早创建**的源（`created_at` 最小）；删除其余。

#### §3.7.5 输入输出契约

##### 输入

```bash
# 默认作用于 local
nlm deduplicate --project-path .

# 指定其他笔记本
nlm deduplicate --notebook-id <UUID> --project-path .
```

##### 输出

```json
{
  "status": "ok",
  "notebook_id": "<uuid>",
  "removed": 5,
  "failed_removed": 2,
  "kept": 47
}
```

| 字段 | 说明 |
|------|------|
| `removed` | 重复 URL 删除数量 |
| `failed_removed` | is_error 状态删除数量 |
| `kept` | 保留的源总数 |

#### §3.7.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "No notebook configured"` | 既无 `--notebook-id` 也无 local | 提供 `--notebook-id` 或 setup |
| Network/auth 错误 | NotebookLM 不可达 | 检查 auth |

#### §3.7.7 实施差距

无（已实现且行为符合 spec）。

---

### §3.8 `/nlm-delete` — 删除单条来源

#### §3.8.1 触发场景与 auto-trigger 规则

**Auto-trigger? ❌ 否，user-only**

**用户主动触发场景**：

1. 删除明确不需要的 URL
2. 清理过时来源
3. 清理 `dedupe` 漏掉的边界情况

#### §3.8.2 参数清单

| 参数 | 必填 | 默认值 | 说明 |
|------|------|------|------|
| `--url URL` | 互斥 | — | 按 URL 删除（笔记本中匹配的源） |
| `--source-id UUID` | 互斥 | — | 按 source ID 直接删除 |
| `--notebook-id UUID` | 否 | 当前项目 local | 目标笔记本 |
| `--project-path PATH` | 否 | `.` | 项目根 |

`--url` 与 `--source-id` 互斥，二选一。

#### §3.8.3 路由规则

默认作用于 PROJ Local；可用 `--notebook-id` 指定。

#### §3.8.4 目标行为

```
Step 1 (--url):
  1a: URL 规范化
  1b: 列出笔记本所有源，匹配 URL
  1c: 找到 → 删除并返回 {id, title}
  1d: 未找到 → 返回 {"status": "not_found"}

Step 1 (--source-id):
  1a: 直接调 client.sources.delete(notebook_id, source_id)
  1b: 失败（ID 不存在）→ 错误返回
```

#### §3.8.5 输入输出契约

##### 输入

```bash
# 按 URL 删除
nlm delete --url "https://example.com/article" --project-path .

# 按 source ID 删除
nlm delete --source-id "<uuid>" --project-path .
```

##### 输出（成功）

```json
{
  "status": "ok",
  "type": "deleted",
  "notebook_id": "<uuid>",
  "deleted": {"id": "<source-uuid>", "title": "<title>"}
}
```

##### 输出（未找到）

```json
{
  "status": "not_found",
  "notebook_id": "<uuid>",
  "queried": "https://example.com/article"
}
```

#### §3.8.6 错误处理矩阵

| 错误 | 触发场景 | 处理建议 |
|------|---------|---------|
| `"error": "Provide --url or --source-id"` | 二者都没提供 | 选一个 |
| `"error": "Both --url and --source-id provided"` | 同时提供（互斥） | 选一个 |
| `"error": "Source ID not found"` | source-id 不在笔记本中 | 验证 ID |
| Network/auth 错误 | NotebookLM 不可达 | 检查 auth |

#### §3.8.7 实施差距

无（已实现且行为符合 spec）。

---

## §4 跨命令工作流（Cross-Command Workflows）

§3 描述了每个命令的独立行为；§4 描述命令间的协作流。共 4 个核心工作流。

### §4.1 知识沉淀流（Knowledge Distillation Flow）— P-NEW v2

#### §4.1.1 业务场景

| 场景 | 触发命令 | 期望产物 |
|------|---------|---------|
| 用户研究新主题，希望沉淀到合适的笔记本 | `/nlm-research <topic>` | 来源 import 到匹配 DOMAIN（B1 路由）+ deep report import 到 META |
| 某 DOMAIN 累积接近 270 → 蒸馏 | `/nlm-research` 自动触发 | NotebookLM Briefing Doc 生成 → 提示用户 → 写入 META |
| 用户手动添加蒸馏文档 | `/nlm-add --target synthesis` | 文档进入 META 作为综合查询入口 |
| 用户清理低分源 | `/nlm-deduplicate` 或 `/nlm-delete` | 释放容量 |

#### §4.1.2 流程步骤（含 P-NEW v2 双产物分流）

```
[用户触发] /nlm-research --topic <T> --depth deep --add-sources --target auto

  ↓

[Step 1] B1 路由分类
  classify_domain(T) → domain_key | "local" | "NEW:<name>" | null
  ↓
  ├─ matched domain → target = domain:<key>
  ├─ "local"        → target = PROJ Local
  ├─ "NEW:<name>"   → 三重门闸检验
  │   ↓
  │   ├─ 全过 → 输出 domain_suggestion + 本次 import to Local
  │   ├─ Gate 1 fail (积压 <20) → import to Local
  │   ├─ Gate 2 fail (overlap ≥40%) → import to nearest domain
  │   └─ Gate 3 fail (total ≥15)  → import to META + ⚠ flag
  └─ null           → import to PROJ Local

  ↓

[Step 2] 调 NotebookLM deep research API
  返回 {sources, report, task_id}
  耗时 ~5 分钟（fast 60s / deep 600s）

  ↓

[Step 3] P-NEW v2 双产物分流（关键创新）
  3a. 解析 report 末尾 bibliography
      _parse_bibliography_urls(report) → set[str]
      正则：\n---\n 后的 ^\d+\.\s+.+,\s*\[(http[^\]]+)\]
      
  3b. 分流 sources：
      result_type==5 entry (整份 report markdown)
        → import to META（compressed source；P-NEW-B 自动）
        → SDK 自动用 _build_report_import_entry（type=3 text note）
      
      result_type==1 + url ∈ cited URLs
        → import to target（高质量 cited 源）
      
      result_type==1 + url ∉ cited URLs
        → 跳过（uncited 搜索池，仅出现在报告 bibliography 中作为参考）

  ↓

[Step 4] import_research_sources()
  - URL dedup
  - 容量 guard（≥290 → CapacityError）
  - 调 NotebookLM import_sources API
  - 等待处理完成
  - 删除 ERROR 状态源

  ↓

[Step 5] 评分排序（仅 source_count >= 250 时启动）
  score_and_prune_sources()
    评分公式（W1+W2+W3 = 1.0）：
      W1 = 0.5 × citation_freq_in_chats     (最强实证信号)
      W2 = 0.3 × cited_in_research_report   (cited URLs 集合判定)
      W3 = 0.2 × keyword_match              (source.guide.keywords)
  
  输出低分 top-50 给用户决策
  ⚠ 不自动删除（避免 BUG 1 重演）

  ↓

[Step 6] 蒸馏触发检查
  ├─ source_count > 270
  │   AUTO BRIEFING：调 NotebookLM API 生成 Briefing Doc
  │     → 提示用户审阅
  │     → 用户确认后 import to META
  │     → 更新 domain.last_distilled = now()
  │     → 原 Domain 不动（C1 语义）
  │
  └─ source_count <= 270 → 跳过

  ↓

[Step 7] 域演化检查
  ├─ check_merge_candidates() → merge_suggestions[]
  └─ check_split_candidates() → split_suggestions[]
  输出建议（不自动执行）

  ↓

[输出] 完整 JSON 结果（见 §3.3.6）
```

#### §4.1.3 关键判定点

| 判定点 | 阈值 | 行为 |
|-------|------|------|
| 三重门闸 Gate 1 | source_queue < 20 | 拒绝建域 → import to Local |
| 三重门闸 Gate 2 | overlap ≥ 40% | 拒绝建域 → import to nearest domain |
| 三重门闸 Gate 3 | total_domains ≥ 15 | 拒绝建域 → import to META |
| Bibliography URL 提取 | report 末尾 `\n---\n` 分隔符 | 用正则 `^\d+\.\s+.+,\s*\[(http[^\]]+)\]` 提取 cited URLs |
| 评分启动 | source_count >= 250 | 启动 score_and_prune_sources（仅排序，不删除） |
| AUTO BRIEFING | source_count > 270 | 自动调 NotebookLM 生成 Briefing → 用户审阅 |
| AUTO REJECT | source_count >= 290 | 拒收新 import |
| Domain merge | overlap > 40% AND combined < 200 | 输出 merge_suggestion |
| Domain split | source_count > 200 AND 近 10 ask >60% 命中单子群 | 输出 split_suggestion |

#### §4.1.4 评分公式与 .nlm/citation_stats.json schema

**评分公式（W1+W2+W3 = 1.0）**：

```
score(source) = 0.5 × citation_freq_in_chats(source)
              + 0.3 × cited_in_research_report(source)
              + 0.2 × keyword_match(source.guide.keywords, project.topic_profile)
```

**citation_freq_in_chats 计算**：
- 来源：`.nlm/citation_stats.json`
- 每次 ask 后从 ChatReference 解析 source_id 并累计 +1
- 归一化：`freq / max(freq across all sources in notebook)` ∈ [0, 1]

**cited_in_research_report 计算**：
- 检查 source.url 是否 ∈ 历次 deep research 累积的 cited URL 集合
- 二值：1.0 if cited else 0.0
- cited URL 集合存储在 `.nlm/citation_stats.json` 的 `cited_urls` 数组

**keyword_match 计算**：
- 用 `_score_keywords` helper（双向子串匹配）
- source.guide.keywords vs TopicTracker.keyword_weights()
- 范围 [0, 1]，空 keywords 返回 0.5（fallback keep；BUG 1 修复）

**citation_stats.json schema**：

```json
{
  "version": 1,
  "citation_freq": {
    "<source_id>": {
      "count": 5,
      "first_cited_at": 1714347200,
      "last_cited_at": 1714433600
    }
  },
  "cited_urls": [
    "https://arxiv.org/...",
    "https://imo.org/..."
  ]
}
```

#### §4.1.5 失败/降级路径

| 失败点 | 降级行为 |
|-------|--------|
| Bibliography 解析失败（report 无标准格式） | 跳过 cited 过滤，import 全部 sources（受 max-import 限制） |
| AUTO BRIEFING NotebookLM API 失败 | 仅提示用户手动生成 Briefing Doc + `/nlm-add --target synthesis` |
| 评分获取 source.guide 失败 | 该源 fallback keep（不参与排序，但不删除） |
| Citation Frequency 文件损坏 | 重置 `.nlm/citation_stats.json` + 评分降级仅用 W2+W3 |

#### §4.1.6 涉及的命令清单

| 命令 | 在本流中的角色 |
|------|--------------|
| `/nlm-research --add-sources` | 主入口（触发整个流） |
| `/nlm-add --target synthesis` | 手动添加 Briefing Doc（蒸馏后用户操作） |
| `/nlm-setup --create-domain` | 响应 domain_suggestion 创建新域 |
| `/nlm-deduplicate` / `/nlm-delete` | 容量满时手动清理 |

---

### §4.2 冷启动 + 低置信度回退流（Cold-Start & Low-Confidence Fallback）

#### §4.2.1 空笔记本冷启动子流（auto-trigger）

##### 业务场景

新项目刚配置笔记本（PROJ Local + 几个 DOMAIN），但所有笔记本都是空的。用户首次 ask 问题，没有来源可查 → 期望系统**自动触发 fast research** 填充笔记本，再回答。

##### 流程步骤

```
[用户触发] /nlm-ask --question <Q> --scope <S>

  ↓

[Step 1] 路由 ask
  根据 --scope 决定查询哪些笔记本（详见 §3.2.3）

  ↓

[Step 2] 冷启动检测
  目标笔记本 source_count == 0?
    OR query 返回 not_found 因笔记本空?
  
  ├─ 否 → 进入正常 ask 流程（A3 并行查询）
  └─ 是 → 进入 Step 3

  ↓

[Step 3] γ 路由：决定 import 目标
  ├─ scope=auto / local / global / synthesis
  │   → import_target = PROJ Local
  ├─ scope=domain:X
  │   → import_target = domain:X（尊重用户 scope 意图）
  └─ scope=synthesis
      → ⚠ 不触发冷启动（META 不接 raw research）
        → 退回低置信度回退流 §4.2.2

  ↓

[Step 4] 自动触发 fast research
  内部调用：
    /nlm-research --topic Q --depth fast --add-sources \
                  --target <import_target>
  
  fast 模式 60s 超时
  默认 max-import = 10

  ↓

[Step 5] re-ask
  research 完成后，重新调 client.ask(notebook_id, Q)
  
  返回结果加 auto_researched=true 字段

  ↓

[输出] {
  "answer": "...",
  "confidence": "high|medium|low",
  "auto_researched": true,
  "answered_by": [...]
}
```

##### 触发场景表

| 场景 | scope | 触发？ | import 目标 |
|------|-------|------|-----------|
| 新项目首问，scope=auto | auto | ✅ | PROJ Local |
| 新项目首问，scope=local | local | ✅ | PROJ Local |
| 显式查空 domain | domain:X | ✅ | domain:X |
| 查空 synthesis | synthesis | ❌ | （走 §4.2.2） |
| 查 global（项目无关） | global | ❌ | GLOBAL 不接受 cold-start 写入 |

##### 失败/降级路径

| 失败点 | 降级行为 |
|-------|--------|
| Fast research 超时 60s | 不重试；返回 ask 原始 not_found 答案 + suggest_research |
| Fast research 失败（quota / auth） | 同上 |
| Re-ask 仍 low confidence | 返回原始结果 + suggest_research（用户可手动深度 research） |

#### §4.2.2 低置信度回退子流（user-triggered）

##### 业务场景

笔记本**非空**但对当前 query 无相关内容（confidence=low / not_found）。spec §6 "绝不写入"原则下，此时**不自动写入**，而是 surface 给用户决策。

##### 流程步骤

```
[用户触发] /nlm-ask --question <Q> --scope <S>

  ↓

[Step 1] 路由 + A3 并行查询（详见 §3.2.3）

  ↓

[Step 2] 答案融合后置信度判定
  confidence in {low, not_found}?
  ├─ 否 → 直接返回答案
  └─ 是 → 进入 Step 3

  ↓

[Step 3] 检测是否冷启动场景（避免与 §4.2.1 重叠）
  source_count == 0? → 已被 §4.2.1 处理
  非 0 但 not_found → 进入 Step 4

  ↓

[Step 4] --on-low-confidence 行为分支
  ├─ prompt（默认）：输出 next_action = suggest_research，附建议命令
  ├─ silent：仅返回原始结果
  └─ research（已废弃，违反 spec §6）：⚠ 警告 + 触发 research+retry

  ↓

[输出] {
  "answer": "I don't have specific information...",
  "confidence": "not_found",
  "suggest_research": true,
  "next_action": {
    "type": "suggest_research",
    "message": "本地笔记本对此问题置信度较低，建议通过 /nlm-research 补充资料后重试。",
    "command": "nlm research --topic \"<Q>\" --add-sources --project-path \".\""
  }
}
```

##### 触发场景表

| 场景 | 触发条件 |
|------|---------|
| 笔记本有源但无相关内容 | source_count > 0 AND confidence in {low, not_found} |
| 用户希望显式控制何时写入 | 默认行为，符合 spec §6 |

##### 失败/降级路径

| 失败点 | 降级行为 |
|-------|--------|
| 用户接受 suggest_research → 触发 research → 仍 low confidence | 重复出 suggest_research（建议改 deep 模式或换关键词） |

#### §4.2.3 涉及的命令清单

| 命令 | 在本流中的角色 |
|------|--------------|
| `/nlm-ask` | 主入口（触发流的起点） |
| `/nlm-research --depth fast` | §4.2.1 冷启动自动调用 |
| `/nlm-research --depth fast/deep` | §4.2.2 用户接受建议后手动调用 |

---

### §4.3 域演化流（Domain Evolution Flow）

#### §4.3.1 业务场景

| 场景 | 触发命令 | 期望产物 |
|------|---------|---------|
| 项目早期：研究主题不属于现有 domain，建议创建新域 | `/nlm-research --target auto` 后 | 输出 domain_suggestion |
| 项目中期：两个 domain 关键词高度重叠 | 每次 research 后自动检查 | 输出 merge_suggestion |
| 项目后期：某 domain 巨大且查询命中分化 | 同上 | 输出 split_suggestion |

#### §4.3.2 创建新域子流

```
[Step 1] /nlm-research --topic <T> --target auto
  classify_domain(T) → "NEW:<inferred_name>"

[Step 2] 三重门闸检验（§2.2.2）
  ├─ Gate 1 (积压 <20) → 拒绝；本次 import to Local
  ├─ Gate 2 (overlap ≥40%) → 路由到 nearest domain
  ├─ Gate 3 (total ≥15)   → 路由到 META + ⚠ flag
  └─ 全过 → 输出 domain_suggestion，本次仍 import to Local

[Step 3] 用户决策
  ├─ 接受建议 → /nlm-setup --create-domain "<name>" --domain-key <key> --domain-keywords "..."
  └─ 拒绝 → 不创建（继续累积到 Local）

[Step 4] 创建后的后续 research
  classify_domain 现命中新 domain → 自动路由至此
```

#### §4.3.3 域合并子流

```
[Step 1] /nlm-research 完成后自动调 check_merge_candidates()

[Step 2] 检测条件：
  ∃ A, B 满足：
    keyword_overlap(A, B) > 40%
    AND combined_source_count(A, B) < 200

[Step 3] 输出 merge_suggestion：
  {
    "merge_from": "B",
    "merge_into": "A",
    "overlap": 0.45,
    "combined_sources": 156,
    "command": "nlm setup --merge-domain B --into A"
  }

[Step 4] 用户决策
  └─ 用户执行命令 → 来源迁移 + 删除 B + 更新 config
```

#### §4.3.4 域拆分子流

```
[Step 1] /nlm-research 完成后自动调 check_split_candidates()

[Step 2] 检测条件：
  ∃ A 满足：
    source_count(A) > 200
    AND 近 10 次 ask 中 >60% 查询只命中 A 的某子关键词群

[Step 3] 输出 split_suggestion：
  {
    "domain": "A",
    "source_count": 245,
    "command": "nlm setup --split-domain A",
    "reason": "70% queries hit only sub-keywords {kw1, kw2}; suggesting split"
  }

[Step 4] 用户决策（交互式拆分）
  └─ 用户执行 → 引导命名两个子域 + 重新分配来源
```

#### §4.3.5 涉及的命令清单

| 命令 | 在本流中的角色 |
|------|--------------|
| `/nlm-research` | 触发演化检查（每次 research 后自动） |
| `/nlm-setup --create-domain` | 响应 domain_suggestion |
| `/nlm-setup --merge-domain ... --into ...` | 响应 merge_suggestion（未来命令，当前未实现） |
| `/nlm-setup --split-domain ...` | 响应 split_suggestion（同上） |

---

### §4.4 容量保护流（Capacity Protection Flow）

#### §4.4.1 业务场景

| 场景 | 触发条件 | 期望行为 |
|------|---------|---------|
| 笔记本接近容量上限 | source_count 跨过 250 / 270 / 290 阈值 | 渐进式预警 + 自动蒸馏 + 拒收 |
| 已达硬上限 | source_count = 300 | NotebookLM 服务端拒收（理论不可达） |

#### §4.4.2 4 阈值协同表

```
source_count    Action（自动行为）
─────────────────────────────────────────────────────────────
   < 200        正常累积
   
   200~250      research 输出 hint：
                  "Domain 可能需要 review 拆分（split 检查）"
                  output split_suggestion if 命中分化
   
   250          ⚡ AUTO SORT：
                  研究完成后调 score_and_prune_sources()
                  （评分公式见 §4.1.4）
                  输出低分 top-50 给用户决策
                  ⚠ 不自动删除（避免 BUG 1 类型误删）
   
   270          ⚡ AUTO BRIEFING：
                  自动调 NotebookLM API 生成 Briefing Doc
                  → 提示用户审阅
                  → 用户确认后 import to META
                  → 更新 domain.last_distilled
                  → 原 Domain 不动（C1 语义）
   
   290          ⚡ AUTO REJECT：
                  research import 触发 CapacityError
                  强制用户处理：
                    选项 A: 删除低分源（参考 AUTO SORT 输出）
                    选项 B: 创建新 Domain（响应 split_suggestion）
                    选项 C: 接受蒸馏 + 部分归档
                  
   300          硬上限（NotebookLM Pro 强制）
                  理论不可达（290 已 reject）
```

#### §4.4.3 关键判定点

| 判定 | 触发位置 | 阈值 |
|-----|--------|------|
| Hint 输出 | `/nlm-research` 完成后 | 200 ≤ source_count < 250 |
| AUTO SORT | `/nlm-research` Step 5 | source_count >= 250 |
| AUTO BRIEFING | `/nlm-research` Step 6 | source_count > 270 |
| AUTO REJECT | `import_research_sources` Step 2 | source_count >= 290 |

具体实现位置（含 [GAP] 引用）：

- **AUTO SORT 评分**：[`client.py:419`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L419) `_score_keywords` + [`nlm.py:828`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L828) cmd_research，含 [GAP-1]
- **AUTO BRIEFING**：当前未实现（手动流程：用户在 NotebookLM UI 生成 + `/nlm-add --target synthesis` 写入），未来增强项
- **AUTO REJECT**：[`client.py:280`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L280) `_NOTEBOOK_CAPACITY_WARN = 290` 已实现

#### §4.4.4 失败/降级路径

| 失败点 | 降级行为 |
|-------|--------|
| AUTO BRIEFING NotebookLM API 失败 | 提示用户手动生成 Briefing Doc + `/nlm-add --target synthesis` |
| AUTO SORT 评分全部失败 | 仅显示 source_count，不输出排序；不阻塞 research 主流程 |
| AUTO REJECT 后用户无响应 | 后续 research 持续 fail，直到用户处理 |

#### §4.4.5 涉及的命令清单

| 命令 | 在本流中的角色 |
|------|--------------|
| `/nlm-research` | 阈值检测的主触发器（每次都检查） |
| `/nlm-add --target synthesis` | 手动写入 Briefing Doc（AUTO BRIEFING 降级路径） |
| `/nlm-deduplicate` | 290 阈值时手动清理工具 |
| `/nlm-delete` | 同上 |
| `/nlm-setup --create-domain` | 290 阈值的"创建新域"选项响应 |

---

## §5 实施差距索引（Implementation Gap Index）

本章列出 spec 目标态与当前 NLM 实现的所有差距，作为后续 `/write-plan` 修复 plan 的输入。共 **12 项 gap**（其中 4 项是本次 brainstorming 实测发现）。

### §5.1 Gap 矩阵

| # | 位置 | 当前实现 | 目标行为 | 优先级 | 关联 spec § |
|---|------|---------|---------|------|-----------|
| 1 | [`client.py:419-437`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L419) `_score_keywords` | 空 keywords 返回 0 → 误删新源 | 空 keywords 返回 0.5（fallback keep） | **P0** | §4.1.4 评分公式 |
| 2 | [`nlm.py:911-921`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L911) `cmd_add` | 仅写 PROJ Local 笔记本 | 支持 `--target {local\|synthesis\|domain:<key>}` | **P0** | §3.4.2 参数 |
| 3 | [`nlm.py:411-414`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L411) `cmd_ask` | 默认 `--on-low-confidence research`（隐式写入） | 默认 `prompt`（绝不自动写入，符合 spec §6 "绝不写入"） | **P1** | §3.2.2 参数 |
| 4 | [`client.py:501-505`](/Users/marine/.claude/skills/nlm/scripts/lib/client.py#L501) `score_and_prune_sources` | 返回缺 `notebook_count` 字段 | 加 `notebook_count = len(post-prune sources)` | P2 | §3.3.6 输出 |
| 5 | [`SKILL.md:81`](/Users/marine/.claude/skills/nlm/SKILL.md#L81) | 老接口 `--create "..."`，未反映 4 层架构 | 重写为 4 层 SCOPE 接口 | P2 | §2.5.1 命名规范 |
| 6 | [`README.md:230-237`](/Users/marine/.claude/skills/nlm/README.md#L230) | 蒸馏 workflow 用 hack（"临时改 config 让 local 指向 synthesis"） | 改用 `--target synthesis`（依赖 GAP-2 修复） | P3 | §4.1 蒸馏流程 |
| 7 | [`skills/nlm-ask/SKILL.md:18`](/Users/marine/.claude/skills/nlm/skills/nlm-ask/SKILL.md#L18) | 默认 `prompt`（与代码 `research` 不符） | 同步代码默认（依赖 GAP-3 修复） | P3 | §3.2.8 |
| 8 | [`skills/nlm-add/SKILL.md`](/Users/marine/.claude/skills/nlm/skills/nlm-add/SKILL.md) | 没说支持写 META/DOMAIN | 加文档（依赖 GAP-2 修复） | P3 | §3.4.7 |
| **9** ⚡ | [`nlm.py:782`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L782) `cmd_research` | `cited_in_report` 字段在 SDK 不存在 → 死代码；`cited_sources = [s for s in all_sources if s.get("cited_in_report")]` 永远空 | 改用 bibliography 正则解析（用 `\n---\n` 分隔符 + `^\d+\.\s+.+,\s*\[(http[^\]]+)\]` 正则） | **P0 实测** | §4.1.2 Step 3 |
| **10** ⚡ | （组件缺失） | 评分缺 `citation_freq` 维度（最强实证信号） | 新增 Citation Frequency Tracker（从 ChatReference.citation_number 累计到 `.nlm/citation_stats.json`） | **P1 NEW** | §4.1.4 |
| **11** ⚡ | [`nlm.py:769`](/Users/marine/.claude/skills/nlm/scripts/nlm.py#L769) | `sources_cited_count = result.get("sources_cited_count", 0)` 在 SDK 永为 0（字段不存在） | 改为 `len(cited_urls)`（来自 GAP-9 解析结果） | **P0 实测** | §3.3.6 输出 |
| **12** ⚡ | （helper 缺失） | 无 bibliography 解析机制 | 新增 `_parse_bibliography_urls(report: str) -> set[str]` helper | **P0 实测** | §4.1.2 Step 3 |

⚡ = 本次 brainstorming 实测验证中发现（非原 audit 报告）

### §5.2 优先级分布

| 优先级 | 数量 | 类型 | 含义 |
|-------|------|------|------|
| **P0** | 5 项 | 1, 2, 9, 11, 12 | 修复后才能恢复正常使用（核心写入 + 蒸馏机制） |
| **P1** | 2 项 | 3, 10 | 重要但不阻塞（spec 一致性 + 评分增强） |
| P2 | 2 项 | 4, 5 | 次要（API 字段 + 主 SKILL.md） |
| P3 | 3 项 | 6, 7, 8 | 文档同步（依赖 P0/P1 修复） |

### §5.3 修复路线图（依赖关系 + 顺序）

按依赖关系拆 4 个 Phase：

```
Phase 1 · 解封写入路径（基础设施）
─────────────────────────────────────────────────
  GAP-12 实现 _parse_bibliography_urls()
    ↓
  GAP-9  cmd_research 改用 bibliography 解析（替换 cited_in_report 死代码）
    ↓
  GAP-11 sources_cited_count 改为 len(cited_urls)
  
  产出：fast/deep research 的 cited filter 真正生效


Phase 2 · 修复评分系统
─────────────────────────────────────────────────
  GAP-1  _score_keywords 空 keywords fallback keep（避免误删）
    ↓
  GAP-10 实现 Citation Frequency Tracker
    ├─ 新增 .nlm/citation_stats.json schema
    ├─ cmd_ask 内累计 ChatReference 引用次数
    └─ score_and_prune_sources 评分公式更新（W1+W2+W3）
    ↓
  GAP-4  score_and_prune_sources 返回字段补 notebook_count
  
  产出：评分系统真正可用，不再误删


Phase 3 · 命令扩展
─────────────────────────────────────────────────
  GAP-2  cmd_add 加 --target {local|synthesis|domain:<key>}
    ↓
  GAP-3  cmd_ask 默认 --on-low-confidence 改 prompt
  
  产出：用户面命令完整


Phase 4 · 文档同步（依赖 Phase 1-3 完成）
─────────────────────────────────────────────────
  GAP-5  主 SKILL.md 重写（反映 4 层架构 + 新 setup 接口）
  GAP-6  README 蒸馏 workflow 改用 --target synthesis
  GAP-7  子 nlm-ask SKILL.md 同步默认 prompt
  GAP-8  子 nlm-add SKILL.md 加 --target 说明
  
  产出：文档与代码完全对齐
```

### §5.4 修复后的成功验证条件

每个 Phase 完成后的可验证 success criteria（用作 `/execute-plan` 的 checkpoint）：

| Phase | 验证条件 |
|-------|---------|
| Phase 1 | `/nlm-research --depth deep` 后 `sources_cited_count > 0`（来自 bibliography 解析）；写入笔记本仅含 cited URLs（非全量搜索池） |
| Phase 2 | 跑一次 fast research → 新源不被误删（即使 keywords 空）；`.nlm/citation_stats.json` 在 ask 后有累计 |
| Phase 3 | `/nlm-add --target synthesis --note "..."` 写入 META 笔记本成功；`/nlm-ask` 默认行为 = prompt（不自动 import） |
| Phase 4 | `/help` 输出与本 spec §3 命令章节一致；README 蒸馏 workflow 可一行命令复现 |

---

## §6 变更历史（Changelog）

| 版本 | 日期 | 作者 | 变更说明 |
|------|------|------|---------|
| **v1.0** | 2026-04-29 | marine + Claude (via superpowers brainstorming) | **初版**。覆盖：8 命令矩阵 × 4 笔记本层完整用户面 spec；4 大跨命令工作流（含 P-NEW v2 双产物分流、γ 路由冷启动、域演化、容量协同）；12 项 audit gap（含 4 项 brainstorming 实测发现）；评分系统 W1+W2+W3 实证驱动公式；自动化阈值 250/270/290/300 协同。Spec 立场为 Self-Contained Target State + Implementation Gap Index (C1)；写作策略为 Approach 1（嵌入式吸收 NLM Multi-Tier v1.0 概念，无外部引用依赖）。 |

后续版本会在此表追加。

---

**END OF SPEC v1.0**

📊 实际行数：约 ~1750 行（最终落盘较初估 ~3270 行精简，因为：表格行密度高于估算 + 决策树 ASCII 图比 Markdown 文字紧凑）。

📌 下一步（Step 7+）：spec self-review → user review → transition to `/write-plan`。
