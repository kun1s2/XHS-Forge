# RAG Anti-Decay Strategy

RAG 的“腐化”指知识随着时间和运行不断变得不可信、不干净、不可控。

## 腐化来源

### 1. 过时
- 价格变动
- 营业时间变化
- 热点转移
- 旧结论过期

### 2. 噪声积累
- 营销文案混入
- 评论原文过碎过脏
- 重复记录越来越多

### 3. 冲突
- 多来源给出不同值
- 官方与口碑冲突
- 新旧版本信息冲突

### 4. 语义漂移
- 同一实体多个别名
- topic/tag 越存越乱

### 5. 蒸馏污染
- LLM 把不确定信息写死
- 总结过头丢失边界

## 防线设计

### 第一层：入库前筛选
- 无来源不入库
- 低复用不入库
- 纯噪声不入库
- 临时状态不入库

### 第二层：知识记录带时间与来源
- `source`
- `updated_at`
- `expires_at`
- `trust_level`

### 第三层：检索时 freshness / trust 校验
- stale 记录降权
- 冲突记录不直接作为强结论
- 低可信来源不放大

### 第四层：输出时保守表达
- 无命中：回退到普通生成
- 命中弱：降低语气强度
- 存在冲突：提示确认
- 记录过期：提示时效性

## TTL 建议

- `trend`: 6 小时
- `fact`: 30 天
- `opinion_summary`: 7 天
- `pattern`: 90 天

## 工程实现要点

- 同时保留 raw evidence 与 distilled summary
- 做 dedupe 与 freshness summary
- 记录 citation coverage / grounding score / source quality
- 在 Inspector 中直接展示 freshness、citation、recommendation

## 一句话原则

不要追求“知识库越大越好”，而要追求：

- 可复用
- 可追溯
- 可刷新
- 可保守
