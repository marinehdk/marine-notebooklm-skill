---
name: nlm-setup
description: >
  初始化和管理项目的 NotebookLM 配置：绑定本地、域、综合和全局笔记本。
  当用户说"初始化 NotebookLM"、"配置笔记本"、"绑定 notebook"、"创建域笔记本"、
  "setup nlm"、"这个项目用哪个笔记本"时触发。
  Do NOT use for: querying notebooks (use nlm-ask), authentication only (use nlm setup --auth).
allowed-tools:
  - Bash
---

# nlm-setup — 项目笔记本配置

```bash
INVOKE="bash $HOME/.claude/skills/nlm/scripts/invoke.sh"
```

## 命令速查

### 认证
| 命令 | 作用 |
|------|------|
| `$INVOKE setup --auth` | 首次 Google 认证 |
| `$INVOKE setup --reauth` | 重新认证 |

### 状态与列表
| 命令 | 作用 |
|------|------|
| `$INVOKE setup` | 查看当前完整配置（零 API），含域笔记本和综合笔记本 |
| `$INVOKE setup --status` | 显式查询当前绑定状态（零 API） |
| `$INVOKE setup --notebook-list` | 列出账号下所有笔记本（24h 缓存） |
| `$INVOKE setup --notebook-list --refresh` | 强制从 API 重新拉取列表 |

### 绑定现有笔记本
| 命令 | 作用 |
|------|------|
| `$INVOKE setup --add-local-notebook <UUID>` | 绑定为项目本地笔记本（PROJ 层） |
| `$INVOKE setup --add-global-notebook <UUID> [UUID2...]` | 追加全局参考笔记本（GLOBAL 层） |

### 创建新笔记本
| 命令 | 作用 |
|------|------|
| `$INVOKE setup --create-local "<PROJ · Name · Local>"` | 新建项目本地笔记本 |
| `$INVOKE setup --create-global "<GLOBAL · Name · Reference>"` | 新建全局参考笔记本 |
| `$INVOKE setup --create-domain "<DOMAIN · Name · Research>" --domain-key <key> --domain-keywords "kw1,kw2"` | 新建域笔记本（DOMAIN 层） |
| `$INVOKE setup --create-synthesis "<META · Name · Synthesis>"` | 新建综合笔记本（META 层） |

## 笔记本命名规范

**格式：`{SCOPE} · {Name} · {Type}`**

| SCOPE | 用途 | Type |
|-------|------|------|
| `PROJ` | 当前项目特有知识 | `Local` |
| `DOMAIN` | 单一技术领域深挖，可跨项目共享 | `Research` |
| `META` | 跨域综合，来源为蒸馏文档 | `Synthesis` |
| `GLOBAL` | 全局通用参考，长期维护 | `Reference` |

示例：
- `PROJ · MASS-L3 · Local`
- `DOMAIN · Navigation Algorithms · Research`
- `META · ASV Research · Synthesis`
- `GLOBAL · Maritime Engineering · Reference`

## 创建域笔记本（--create-domain）

```bash
$INVOKE setup \
  --create-domain "DOMAIN · Navigation Algorithms · Research" \
  --domain-key navigation_algorithms \
  --domain-keywords "path planning,collision avoidance,COLREGS,LiDAR,SLAM" \
  --domain-description "路径规划、避碰、COLREGS、感知融合、控制律"
```

**参数说明：**
- `--domain-key`: snake_case 唯一键，用于路由（如 `navigation_algorithms`）
- `--domain-keywords`: 逗号分隔关键词，驱动自动路由（keyword matching）
- `--domain-description`: 可选，便于理解用途

域笔记本创建后，`/nlm-research --target auto` 会自动将匹配话题的来源路由至该域。

## 创建综合笔记本（--create-synthesis）

```bash
$INVOKE setup --create-synthesis "META · ASV Research · Synthesis"
```

综合笔记本（META 层）用于跨域综合查询。其来源来自各域笔记本的 Briefing Doc 蒸馏文档，而非原始研究来源。

## 标准初始化流程

### Step 1 — 展示笔记本列表

```bash
$INVOKE setup --notebook-list
```

以 Markdown 表格展示 `table`（必须包含 `#`、`UUID`、`Title`、`Sources`、`Created`）。

### Step 2 — 绑定本地笔记本

用户选择或新建：
```bash
$INVOKE setup --add-local-notebook <UUID>
# 或
$INVOKE setup --create-local "PROJ · <项目名> · Local"
```

### Step 3 — 绑定域笔记本（可选，按需创建）

```bash
$INVOKE setup --create-domain "DOMAIN · <领域名> · Research" \
  --domain-key <key> --domain-keywords "kw1,kw2,kw3"
```

### Step 4 — 绑定综合笔记本（可选，当跨域研究积累到一定程度时）

```bash
$INVOKE setup --create-synthesis "META · <项目名> · Synthesis"
```

### Step 5 — 绑定全局参考笔记本（可选）

```bash
$INVOKE setup --add-global-notebook <UUID>
```

## 状态输出示例

`$INVOKE setup` 返回：
```json
{
  "local_notebook": {"id": "...", "title": "PROJ · MASS-L3 · Local"},
  "global_notebooks": [...],
  "synthesis_notebook": {"id": "...", "name": "META · ASV Research · Synthesis"},
  "domain_notebooks": {
    "navigation_algorithms": {
      "id": "...", "name": "DOMAIN · Navigation Algorithms · Research",
      "keywords": ["path planning", "COLREGS"], "source_count": 45
    }
  }
}
```

## 缓存说明

- 笔记本列表缓存 24 小时于 `.nlm/notebooks_cache.json`
- 若缓存过期，`--notebook-list` 自动刷新
- 需立即获取最新数据：`--notebook-list --refresh`

## 错误处理

| 错误 | 处理方式 |
|------|---------|
| `"authenticated: false"` | 先运行 `$INVOKE setup --auth` |
| `"error": "cache_missing"` | 先运行 `--notebook-list` 生成缓存 |
| `--domain-key required` | 创建域笔记本时必须提供 `--domain-key` 和 `--domain-keywords` |
| `"Domain already exists"` | 该域已配置，无需重复创建 |
| `"Synthesis notebook already configured"` | 综合笔记本已存在 |
