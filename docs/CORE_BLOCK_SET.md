# Core Block Set

## Purpose
这份文档定义当前项目**最值得长期保留和持续升级**的核心积木集合。

它不追求覆盖所有现有组件，而是回答：

1. 哪些 block 是长期主干
2. 哪些 block 只是辅助增强
3. 后续升级应该优先投在哪些 block 上

配套文档：
- [`BLOCK_SEMANTIC_ROLES.md`](/root/XHS-Forge/docs/BLOCK_SEMANTIC_ROLES.md)
- [`COMPONENT_MANIFEST_SEMANTIC_MAPPING.md`](/root/XHS-Forge/docs/COMPONENT_MANIFEST_SEMANTIC_MAPPING.md)
- [`CORE_BLOCK_SET_INTENT_MAPPING.md`](/root/XHS-Forge/docs/CORE_BLOCK_SET_INTENT_MAPPING.md)

## Selection Rules

核心积木必须同时满足下面几条里的多数：

- 跨场景复用率高
- 语义职责稳定
- 适合长期编辑
- 适合挂接事实/资产/trace
- 适合在面试演示里直接体现系统能力

## Core Block Set

### 1. `CoverSwiper`
- Semantic role: `hero_media`
- Why core:
  - 这是大多数页面的视觉入口
  - 对展示效果影响最大
- Best for:
  - 主图
  - 封面组图
  - 氛围图组
- Keep investing in:
  - 轮播体验
  - caption/source 支持
  - 更稳的移动端体验

### 2. `TitleBlock`
- Semantic role: `heading`
- Why core:
  - 每个页面都需要叙事入口
  - 是规划与内容组织的第一锚点
- Best for:
  - 标题
  - 副标题
  - 开篇导语

### 3. `StoryText`
- Semantic role: `narrative_text`
- Why core:
  - 最稳定的正文容器
  - 是局部编辑和长期编辑的关键落点
- Best for:
  - 体验讲述
  - 感受表达
  - 解释说明

### 4. `ProductSpecCard`
- Semantic role: `evidence_summary`
- Why core:
  - 适合承接结构化事实
  - 是可信链最重要的展示面之一
- Best for:
  - 参数摘要
  - 信息清单
  - 核心事实块

### 5. `RadarChartBlock`
- Semantic role: `score_overview`
- Why core:
  - 适合多维评价
  - 是“证据感”最强的展示块之一
- Best for:
  - 多维打分
  - 体验评估
  - 维度型总结

### 6. `VersusCard`
- Semantic role: `comparison`
- Why core:
  - 对比是高频表达任务
  - 很适合社交内容里的“站队”与“选择”
- Best for:
  - A/B 比较
  - 优缺点并列
  - 方案对比

### 7. `PollBlock`
- Semantic role: `interactive_opinion`
- Why core:
  - 互动是社交内容区别于普通页面的重要特征
  - 很适合演示 agent 的结构化编辑能力
- Best for:
  - 站队
  - 选择
  - 轻互动

### 8. `LocationBlock`
- Semantic role: `location_info`
- Why core:
  - 地点类信息是旅行/探店/路线内容的重要事实块
  - 能体现 block 与事实/资产/页面上下文的结合
- Best for:
  - POI
  - 地址
  - 行程节点

## Supporting Blocks

这些块可以保留，但不应成为主升级对象：

### `WeatherPolaroid`
- Role: `ambience_snapshot`
- Value:
  - 增强氛围
- Limitation:
  - 更偏装饰和生活感，不适合做主骨架

### `QuoteBlock`
- Role: `quote_highlight`
- Value:
  - 适合金句、摘录、评价
- Limitation:
  - 使用频率不如正文/对比/证据块稳定

### `TimelineBlock`
- Role: `timeline`
- Value:
  - 对旅行/步骤流有价值
- Limitation:
  - 场景依赖更强

## Immediate Upgrade Order

为了演示效果和产品完成度，接下来最值得继续升级的是：

1. `CoverSwiper`
2. `VersusCard`
3. `PollBlock`
4. `RadarChartBlock`

第二梯队：

5. `ProductSpecCard`
6. `LocationBlock`

## Product Principle

项目后续不应围绕“场景专属组件库”发展，而应围绕这套核心语义 block 发展：

- 同一套 block
- 不同场景权重
- 不同 theme 表现
- 不同 builder/事实/资产绑定细节

这才是现代 agent + 稳定协议层路线下最适合的积木策略。
