# Component Manifest Semantic Mapping

## Purpose
这份文档把“积木语义职责”进一步落到 `component_manifest` 应该承载的字段上。

它回答的是：

1. 语义角色如何映射到 manifest
2. 当前 manifest 哪些字段已经对
3. 哪些字段后续还应该继续增强

配套文档：
- [`BLOCK_SEMANTIC_ROLES.md`](/root/XHS-Forge/docs/BLOCK_SEMANTIC_ROLES.md)
- [`MODERN_AGENT_TARGET_SYSTEM.md`](/root/XHS-Forge/docs/MODERN_AGENT_TARGET_SYSTEM.md)

## Manifest Design Rules

### Rule 1: Manifest describes capability, not prompt behavior
manifest 应描述组件能力，而不是在 prompt 里暗塞业务规则。

### Rule 2: Semantic role is primary
`type` 是实现名，`semantic_role` 才是业务层真正关心的语义标识。

### Rule 3: Builder, resolver, renderer share the same source
以下模块都应围绕同一份 manifest 工作：
- outline resolver
- component builder
- verifier
- frontend renderer
- html renderer

## Required Fields

### Stable fields
这些字段已经是正式主骨架的一部分：

- `type`
- `label`
- `semantic_role`
- `supported_scenarios`
- `aliases`
- `required_props`
- `optional_props`
- `editable_targets`
- `fact_binding_support`
- `asset_support`
- `theme_slots`
- `frontend_renderer`
- `html_renderer`
- `quick_actions`

### Recommended next fields
这些字段后续继续做会更现代，但不要求本轮立刻落代码：

- `intent_aliases`
  - 用于 block intent 与 query hint 的更稳映射
- `evidence_kind`
  - 如 `parameter / score / location / quote`
- `content_mode`
  - 如 `hero / narrative / summary / interactive`
- `trust_surface`
  - 这个块默认适合怎么显示来源和 caution
- `builder_contract`
  - 比 `required_props/optional_props` 更细的 contract 摘要

## Current Mapping

### `CoverSwiper`
- `semantic_role`: `hero_media`
- `editable_targets`: `image_urls`
- `asset_support`: `required`
- `fact_binding_support`: `false`
- Manifest interpretation:
  - 这是主视觉容器，不是“数码图卡”

### `TitleBlock`
- `semantic_role`: `heading`
- `editable_targets`: `title`, `subtitle`
- `asset_support`: `none`
- `fact_binding_support`: `false`
- Manifest interpretation:
  - 这是叙事入口，不是风格装饰

### `StoryText`
- `semantic_role`: `narrative_text`
- `editable_targets`: `paragraphs`, `paragraphs[n]`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是最稳定的正文容器，必须支持长期局部编辑

### `ProductSpecCard`
- `semantic_role`: `evidence_summary`
- `editable_targets`: `core_features`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是“证据摘要块”，而不应只服务产品参数

### `RadarChartBlock`
- `semantic_role`: `score_overview`
- `editable_targets`: `dimensions`, `scores`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是多维度评价块，而不是单纯图表

### `VersusCard`
- `semantic_role`: `comparison`
- `editable_targets`: `title`, `proText`, `conText`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是对比语义块，而不是“红黑 PK 视觉模板”

### `PollBlock`
- `semantic_role`: `interactive_opinion`
- `editable_targets`: `question`, `option_a`, `option_b`
- `fact_binding_support`: `false`
- Manifest interpretation:
  - 这是互动/站队语义块，而不是假投票系统

### `LocationBlock`
- `semantic_role`: `location_info`
- `editable_targets`: `poi_name`, `location`
- `fact_binding_support`: `true`
- `asset_support`: `optional`
- Manifest interpretation:
  - 这是地点事实块，不是单纯地图按钮

### `WeatherPolaroid`
- `semantic_role`: `ambience_snapshot`
- `editable_targets`: `desc`, `weather`, `temperature`, `time`
- Manifest interpretation:
  - 这是氛围增强块，属于辅助语义

### `QuoteBlock`
- `semantic_role`: `quote_highlight`
- `editable_targets`: `quote`, `author`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是引用高亮块

### `TimelineBlock`
- `semantic_role`: `timeline`
- `editable_targets`: `events`
- `fact_binding_support`: `true`
- Manifest interpretation:
  - 这是时间序列块

## Resolver Policy

resolver 不应直接“记住组件名”，而应按下面顺序工作：

1. 先读 `block_intents`
2. 再看 manifest 的 `semantic_role`
3. 再结合：
   - `supported_scenarios`
   - `asset_support`
   - `fact_binding_support`
4. 最后选具体 `type`

示例：

- `hero_media` + `has_images=true` -> `CoverSwiper`
- `hero_media` + `has_images=false` -> `WeatherPolaroid`
- `evidence_summary` + `seeding_weight>=0.6` -> `RadarChartBlock`
- `evidence_summary` + default -> `ProductSpecCard`

## Builder Policy

builder 应把 manifest 当成 contract，而不是当作文档说明。

builder 输入至少应显式包含：
- `component_type`
- `semantic_role`
- `required_props`
- `optional_props`
- `editable_targets`
- `asset_support`
- `fact_binding_support`
- 局部 `facts/assets/planner_policy` 摘要

builder 输出必须满足：
- 只能落回 manifest 允许字段
- 不得越权发明新字段
- 缺失字段交给 fallback/verifier 收口

## Upgrade Priorities

### Priority A: High-value semantic blocks
先提升这些高频跨场景角色：

1. `hero_media`
2. `comparison`
3. `interactive_opinion`
4. `score_overview`

### Priority B: Strengthen trust surfaces
manifest 后续最值得补的是让这些角色的可信展示方式更明确：
- `evidence_summary`
- `score_overview`
- `narrative_text`
- `location_info`

## Final Principle
对这个项目来说，现代化不意味着隐藏积木，而意味着：

- agent 负责决定“要什么语义块”
- manifest 负责定义“这个块能做什么”
- resolver/builder 负责稳定落地
- renderer 负责把同一语义块在不同场景下展示得更好
