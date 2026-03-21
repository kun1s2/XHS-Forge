# Block Semantic Roles

## Purpose
这份文档用于把当前积木库从“UI 名称”重新翻译成“跨场景语义角色”。

目标不是定义组件长什么样，而是回答：

1. 这个 block 在产品里本质上负责什么
2. 它适合承接什么内容
3. 它不该被误用成什么
4. 后续升级时应该优先增强什么能力

核心原则：

- 场景开放，语义稳定
- planner 决定语义目标，resolver 决定组件
- 组件升级围绕语义职责，而不是围绕单一垂直场景

## Core Mapping

### `CoverSwiper`
- Semantic role: `hero_media`
- Responsibility:
  - 承接页面最强视觉入口
  - 提供封面图、情绪图、主视觉组图
- Suitable for:
  - 数码主图
  - 旅行照片组
  - 探店氛围图
  - 日常分享封面
- Should not become:
  - 只为数码产品设计的图集组件
  - 只负责“横向可滚动”而无轮播语义的假封面
- Upgrade priority:
  - 真轮播交互
  - 指示器/切换控制
  - 更强的 caption / source 支持

### `TitleBlock`
- Semantic role: `heading`
- Responsibility:
  - 承接标题、导语、副标题
  - 建立页面主叙事入口
- Suitable for:
  - 开篇标题
  - 对比结论标题
  - 攻略主题标题
- Should not become:
  - 只能放一句口号的装饰字卡
- Upgrade priority:
  - 标题层级表达
  - 副标题和标签支持

### `StoryText`
- Semantic role: `narrative_text`
- Responsibility:
  - 承接正文、讲述、解释、补充说明
  - 作为最稳定的通用文本容器
- Suitable for:
  - 数码体验
  - 旅行记录
  - 探店感受
  - 观点表达
- Should not become:
  - 万能兜底垃圾桶
- Upgrade priority:
  - 段落级编辑
  - 事实绑定显示
  - 更好的阅读节奏

### `ProductSpecCard`
- Semantic role: `evidence_summary`
- Responsibility:
  - 承接关键信息摘要、事实条目、参数/清单
- Suitable for:
  - 产品参数
  - 路线清单
  - 店铺信息摘要
  - 事实要点
- Should not become:
  - 只服务数码评测的专用“参数卡”
- Upgrade priority:
  - 更通用的字段命名
  - 结论化信息分层
  - fact binding 展示

### `RadarChartBlock`
- Semantic role: `score_overview`
- Responsibility:
  - 承接多维度评价与证据概览
- Suitable for:
  - 产品维度评分
  - 地点/服务体验维度
  - 风格/感受维度
- Should not become:
  - 没有解释的静态图示
- Upgrade priority:
  - 维度解释
  - 结论摘要
  - 证据感更强的显示

### `VersusCard`
- Semantic role: `comparison`
- Responsibility:
  - 承接对比、站队、优劣势并列
- Suitable for:
  - A/B 产品对比
  - 两条路线对比
  - 两家店对比
  - 两种风格/方案对比
- Should not become:
  - 左右两坨纯文字堆砌
- Upgrade priority:
  - 核心结论
  - 双侧要点
  - 移动端上下堆叠可读性

### `PollBlock`
- Semantic role: `interactive_opinion`
- Responsibility:
  - 承接互动、站队、投票、偏好表达
- Suitable for:
  - 数码站队
  - 探店选择
  - 路线偏好
  - 穿搭/审美偏好
- Should not become:
  - 伪真实投票系统
- Upgrade priority:
  - 更诚实的演示态
  - 更好的选项层级
  - 轻量互动反馈

### `LocationBlock`
- Semantic role: `location_info`
- Responsibility:
  - 承接地点、地址、位置事实
- Suitable for:
  - POI
  - 城市/区域
  - 行程节点
- Should not become:
  - 只有一个外链按钮的简陋地图壳
- Upgrade priority:
  - 更稳的地点摘要
  - 更柔和的交互方式

### `WeatherPolaroid`
- Semantic role: `ambience_snapshot`
- Responsibility:
  - 承接氛围、天气、瞬间感受、生活感
- Suitable for:
  - 旅行氛围
  - 日常分享
  - 气候/时间提示
- Should not become:
  - 主叙事骨架组件
- Upgrade priority:
  - 保持轻量装饰定位

### `QuoteBlock`
- Semantic role: `quote_highlight`
- Responsibility:
  - 承接引用、金句、摘录、高亮观点
- Suitable for:
  - 用户评价
  - 关键结论
  - 人设化表达
- Should not become:
  - 长正文替代品
- Upgrade priority:
  - 引用来源
  - 句子级事实/来源展示

### `TimelineBlock`
- Semantic role: `timeline`
- Responsibility:
  - 承接时间线、步骤流、旅程轨迹
- Suitable for:
  - 行程安排
  - 体验步骤
  - 事件顺序
- Should not become:
  - 任意列表的替代品
- Upgrade priority:
  - 更清晰的阶段感
  - 可选事实绑定

## Product Rules

### Rule 1: Semantic first
planner 和业务层应先输出语义 block intent，而不是直接输出组件名。

### Rule 2: Scenario should style, not redefine
场景应该影响：
- tone
- layout bias
- asset bias
- theme preset

场景不应重新定义 block 的基础语义。

### Rule 3: Upgrade by cross-scenario value
后续组件升级优先级应按“跨场景复用价值”排序，而不是按“某个单一垂直场景使用频率”排序。

## Immediate Priorities

最值得继续升级的不是“再加新块”，而是提升这些跨场景高价值语义块：

1. `CoverSwiper` -> `hero_media`
2. `VersusCard` -> `comparison`
3. `PollBlock` -> `interactive_opinion`
4. `RadarChartBlock` -> `score_overview`

## Relationship To Manifest
这份文档回答的是“为什么要有这些 block”。

下一层落地则应进入 manifest：
- `semantic_role`
- `editable_targets`
- `fact_binding_support`
- `asset_support`
- `supported_scenarios`

对应设计见 [`COMPONENT_MANIFEST_SEMANTIC_MAPPING.md`](/root/XHS-Forge/docs/COMPONENT_MANIFEST_SEMANTIC_MAPPING.md)。
