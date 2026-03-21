# RAG Upgrade Checklist

## Purpose
这份清单用于把当前项目里的 RAG 能力，从“已经能讲、能跑的应用型 RAG”，继续升级成“面试里更有说服力的工程化 RAG”。

目标不是把项目改成“纯 RAG 系统”，而是让现有这条：

`research -> retrieval -> enrichment -> NoteDocument`

更像一条完整、可评估、可解释、可维护的生产级链路。

---

## Current Baseline

当前已具备的基础：

- 混合召回：
  - 向量检索
  - 全文检索
  - RRF 融合
- Self-query 风格过滤
- 在线搜证
- 图片检索
- Redis 热缓存 / 热点预热
- 检索结果已经能回流到 `NoteDocument`
- 有基础回归测试

对应代码：

- [`rag_service.py`](/root/XHS-Forge/AI_Frontend_IDE/app/services/rag_service.py)
- [`vector_db.py`](/root/XHS-Forge/AI_Frontend_IDE/app/services/vector_db.py)
- [`research_agent.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/research_agent.py)
- [`search_enricher.py`](/root/XHS-Forge/AI_Frontend_IDE/app/services/search_enricher.py)
- [`trend_pipeline.py`](/root/XHS-Forge/AI_Frontend_IDE/app/services/trend_pipeline.py)
- [`test_rag_pipeline.py`](/root/XHS-Forge/tests/test_rag_pipeline.py)

---

## Upgrade Goal

把当前 RAG 提升到下面这几个面试关键词都能讲得顺的程度：

- ingestion
- retrieval policy
- hybrid retrieval
- rerank
- grounding / citation
- eval
- observability
- freshness / cache strategy

---

## Phase 1: Ingestion

### Goal
补齐“知识是怎么进库的”这条链。

### Why it matters
很多项目会说自己有 RAG，但说不清：

- 数据从哪来
- 怎么切块
- metadata 怎么设计
- 什么内容值得入库

这会让 RAG 显得像“只接了一个向量库”。

### Minimum tasks

1. 增加清晰的知识入库入口
- 支持：
  - 产品规格
  - 地点信息
  - 趋势话题
  - 外部搜证结果

2. 设计 chunk 策略
- 至少明确：
  - chunk 大小
  - overlap
  - 标题是否拼接进 chunk
  - 列表类数据与正文类数据是否分开

3. 设计 metadata
- 至少包含：
  - `doc_type`
  - `entity_name`
  - `brand`
  - `city`
  - `category`
  - `source`
  - `updated_at`
  - `trust_level`

4. 写一份 ingest 文档
- 让面试时能说清：
  - “检索质量为什么不是随机的”

### Suggested files

- `app/services/rag_ingestion.py`
- `app/services/rag_chunking.py`
- `docs/RAG_INGESTION.md`

---

## Phase 2: Retrieval Policy

### Goal
把“怎么检索”从隐式逻辑提升成正式策略层。

### Why it matters
现在项目已经有 hybrid retrieval，但还可以更明确地表达：

- 什么问题走私域库
- 什么问题走在线搜证
- 什么问题两者都走
- 什么问题需要带 filter

### Minimum tasks

1. 增加 retrieval policy helper
- 输出：
  - `use_private_kb`
  - `use_live_search`
  - `use_hybrid`
  - `use_filters`
  - `target_doc_types`

2. 让 `research_agent` 和 `rag_service` 共享这层策略

3. 把策略摘要打进 trace
- 至少在 Inspector 里能看到：
  - 这轮为什么走 hybrid
  - 为什么带 city/brand filter

### Suggested files

- `app/services/retrieval_policy.py`

---

## Phase 3: Rerank

### Goal
在 hybrid retrieval 后增加轻量 rerank。

### Why it matters
这是把“会检索”升级成“会优化检索质量”的关键。

### Minimum tasks

1. 先做轻 rerank
- 可基于：
  - metadata 规则
  - chunk 标题命中
  - entity 精确命中
  - doc_type 偏好

2. 再考虑小模型 rerank
- 如果成本允许，可加一个 cheap rerank pass

3. 在 trace 中展示：
  - raw top-k
  - reranked top-k

### Suggested files

- `app/services/reranker.py`

---

## Phase 4: Citation

### Goal
把“检索到了什么”真正挂回最终输出。

### Why it matters
这是面试里最容易拉开差距的一层。  
很多项目有 retrieval，但没有真正 grounding。

### Minimum tasks

1. 检索结果保留 source metadata
- 不只保留 `page_content`

2. 在 `retrieved_knowledge` 里补 citation 结构
- 至少包含：
  - `source_id`
  - `title`
  - `snippet`
  - `url`
  - `doc_type`

3. 把 citation 显示到：
- `AgentInspector`
- 重点 block hover
- 事实绑定说明

4. 区分：
- “直接引用检索结果”
- “模型整理后得出的摘要”

### Suggested files

- `app/core/schema.py`
- `app/api/workspace.py`
- `ai-frontend-ide/src/components/chat/AgentInspector.vue`

---

## Phase 5: Eval

### Goal
给 RAG 一套正式评测，而不是只靠主观感觉。

### Why it matters
如果你能讲清 RAG eval，项目档次会明显提高。

### Minimum tasks

1. 建一小套 gold queries
- 至少覆盖：
  - 产品问答
  - 地点问答
  - 混合检索
  - 事实冲突
  - 无命中

2. 定义最小指标
- `top_k_hit`
- `source_recall`
- `citation_coverage`
- `no_result_precision`

3. 写自动回归脚本

### Suggested files

- `tests/test_rag_eval.py`
- `docs/RAG_EVAL.md`

---

## Phase 6: Observability

### Goal
让 RAG 过程在 UI 和 trace 里可见。

### Why it matters
你现在已经有很强的观察性底子，这层很适合继续补。

### Minimum tasks

1. 在 `turn_trace` 中增加：
- retrieval policy
- refined query
- raw hits
- reranked hits
- chosen citations

2. Inspector 直接显示：
- query refinement
- filters
- top hits
- chosen citations
- no-hit reason

3. 为异常情况单独提示：
- 低召回
- 低证据覆盖
- 无命中 fallback

---

## Phase 7: Freshness

### Goal
把缓存与热知识更新机制讲得更完整。

### Why it matters
你现在已经有热点预热和缓存，这是很好的亮点，但还可以再工程化一点。

### Minimum tasks

1. 给缓存增加 TTL / freshness 策略说明

2. 区分：
- 热门缓存
- 会话级缓存
- 私域库长期知识

3. 在 trace 中显示：
- cache hit
- stale hit
- live refresh

---

## Best Resume Story

如果这套做完，你在简历/面试里可以更自然地说：

> 我做的不是简单的“向量库问答”，而是一条带混合召回、策略路由、在线搜证、缓存预热、文档级 grounding 和前端可观察性的 RAG 链路，并把它和长期可编辑的 `NoteDocument` 工作流打通了。

---

## Suggested Execution Order

如果只做最值的一版，顺序建议是：

1. Ingestion
2. Retrieval policy
3. Citation
4. Eval
5. Observability
6. Rerank
7. Freshness

---

## Final Principle

不要把后续升级理解成“给项目加一个更复杂的搜索模块”。  
真正值钱的是把 RAG 收成：

- 有输入标准
- 有检索策略
- 有引用落点
- 有评估指标
- 有可观察性

这样它才会从“会搜”升级成“可工程化交付”。
