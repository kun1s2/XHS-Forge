# Core Block Set Intent Mapping

## Purpose
这份文档把核心积木集合直接映射到：

1. planner 应输出什么 `block_intents`
2. resolver 如何选具体组件
3. manifest 至少要提供哪些字段

它是“业务语义 -> planner -> manifest -> component”的中间桥梁。

配套文档：
- [`CORE_BLOCK_SET.md`](./CORE_BLOCK_SET.md)
- [`BLOCK_SEMANTIC_ROLES.md`](./BLOCK_SEMANTIC_ROLES.md)
- [`COMPONENT_MANIFEST_SEMANTIC_MAPPING.md`](./COMPONENT_MANIFEST_SEMANTIC_MAPPING.md)

## Mapping Table

### `hero_media`
- Preferred component:
  - `CoverSwiper`
- Fallback:
  - `WeatherPolaroid`
- Planner should decide:
  - 是否需要主视觉
  - 是否有足够图片资产
  - 是否需要更强冲击力或更柔和氛围
- Manifest must provide:
  - `semantic_role=hero_media`
  - `asset_support`
  - `editable_targets=image_urls`
  - `theme_slots=hero`

### `heading`
- Preferred component:
  - `TitleBlock`
- Planner should decide:
  - 是否需要主标题、副标题、开篇标签
- Manifest must provide:
  - `semantic_role=heading`
  - `editable_targets=title/subtitle`
  - `theme_slots=heading`

### `narrative_text`
- Preferred component:
  - `StoryText`
- Planner should decide:
  - 正文密度
  - 叙事强度
  - 第一人称程度
- Manifest must provide:
  - `semantic_role=narrative_text`
  - `editable_targets=paragraphs`
  - `fact_binding_support=true`
  - `theme_slots=body/verified/caution`

### `evidence_summary`
- Preferred component:
  - `ProductSpecCard`
- Conditional alternative:
  - `RadarChartBlock`
- Planner should decide:
  - 这是更适合列表摘要，还是更适合多维评价
- Manifest must provide:
  - `semantic_role=evidence_summary`
  - `fact_binding_support=true`
  - `editable_targets`
  - `trust_surface`

### `score_overview`
- Preferred component:
  - `RadarChartBlock`
- Planner should decide:
  - 是否真有多维打分需求
  - 维度数
  - 是否需要证据解释
- Manifest must provide:
  - `semantic_role=score_overview`
  - `required_props=dimensions/scores`
  - `fact_binding_support=true`

### `comparison`
- Preferred component:
  - `VersusCard`
- Planner should decide:
  - 是否需要明确对比关系
  - 是否更适合 AB 并列还是 pros/cons
- Manifest must provide:
  - `semantic_role=comparison`
  - `editable_targets=title/proText/conText`
  - `fact_binding_support=true`

### `interactive_opinion`
- Preferred component:
  - `PollBlock`
- Planner should decide:
  - 是否值得加互动
  - 互动强度
  - 选项数量与语气
- Manifest must provide:
  - `semantic_role=interactive_opinion`
  - `editable_targets=question/options`
  - `theme_slots=interactive`

### `location_info`
- Preferred component:
  - `LocationBlock`
- Planner should decide:
  - 是否地点信息足够重要
  - 是否需要挂在页面主链上
- Manifest must provide:
  - `semantic_role=location_info`
  - `fact_binding_support=true`
  - `asset_support=optional`

## Planner Guidance

planner 不该直接输出组件名，应该输出类似下面的 block intents：

- `hero_media`
- `heading`
- `narrative_text`
- `evidence_summary`
- `score_overview`
- `comparison`
- `interactive_opinion`
- `location_info`

同时 planner policy 应补充：

- `importance`
- `tone_bias`
- `interaction_bias`
- `evidence_level`
- `asset_need`

## Resolver Guidance

resolver 的核心工作不是“创作”，而是：

1. 看 `block_intents`
2. 看 manifest
3. 看场景分数/资产/事实状态
4. 选最稳的具体组件

这意味着：
- 组件选择应尽量确定性
- 不需要再次做重策划

## Builder Guidance

builder 不该自己重新理解场景，而应接收：

- `component_type`
- `semantic_role`
- `content_brief`
- `editable_targets`
- `asset_support`
- `fact_binding_support`
- `facts/assets/planner_policy` 摘要

然后只在 contract 内填 props。

## Final Principle

真正稳定的链路应该是：

`core block set`
-> `block_intents`
-> `manifest contract`
-> `resolver`
-> `builder`

而不是：

`用户输入`
-> `直接猜组件名`
-> `直接拼页面`

这也是为什么核心积木集合要先定义成语义角色，而不是 UI 花名册。
