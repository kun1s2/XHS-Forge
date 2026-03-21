# RAG Data Model

XHS-Forge 的 RAG 只存“页面生成与编辑所依赖的依据层知识”，不存最终页面成品。

## 核心知识类型

### 1. Trend KB
- 用途：系统预热热点、争议点、近期高频话题
- 特点：时效强、TTL 短
- 典型字段：
  - `doc_type=trend`
  - `entity_name`
  - `scenario`
  - `source`
  - `source_scope`
  - `updated_at`
  - `expires_at`

### 2. Fact KB
- 用途：稳定事实、规格、地点、官方资料
- 特点：复用价值高、TTL 长
- 典型字段：
  - `doc_type=fact`
  - `entity_name`
  - `category`
  - `source`
  - `trust_level`
  - `updated_at`
  - `expires_at`

### 3. Opinion Summary KB
- 用途：蒸馏后的口碑摘要、争议点、优缺点
- 特点：不存海量原始评论，只存高价值摘要和可引用证据
- 典型字段：
  - `doc_type=opinion_summary`
  - `entity_name`
  - `source_scope=review`
  - `snippet`
  - `trust_level`
  - `updated_at`

### 4. Pattern KB
- 用途：场景化经验知识、比较维度、证据组织框架
- 特点：最稳定、TTL 最长
- 典型字段：
  - `doc_type=pattern`
  - `scenario`
  - `category`
  - `content`
  - `updated_at`

## 通用 metadata

每条知识记录至少带：
- `record_id`
- `doc_type`
- `entity_name`
- `scenario`
- `category`
- `source`
- `source_scope`
- `source_title`
- `query`
- `title`
- `snippet`
- `content`
- `trust_level`
- `ingest_mode`
- `updated_at`
- `expires_at`
- `ttl_seconds`

## 明确不入库的内容

- 最终 `NoteDocument`
- 临时 workflow 状态
- 页面 patch / trace
- 纯样式与 UI 数据
- 未蒸馏的海量原始评论

## 设计原则

- KB 是依据层，不是成品库
- 只存高复用、可追溯、可刷新知识
- 优先保留来源与时间，而不是堆更多文本
