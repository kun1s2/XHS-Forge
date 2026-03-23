# XHS-Forge Modern Agent Target System

## Goal
把 XHS-Forge 收敛成一个符合现代 agent 开发范式的产品系统，而不是“到处都是 agent”的 demo。

最终目标不是“纯 `create_agent` 项目”，而是：

- 只把真正需要决策的节点保留为 `create_agent`
- 把其余部分收成 `resolver / compiler / verifier / renderer / binder`
- 让业务语义、状态协议、组件协议、可信链和资产链都成为一等公民

一句话主故事：

> 一个可长期编辑、可回滚分支、可追踪事实来源的社交笔记创作工作台。

## Core Principles

### 1. Agent 只做决策，不做漫游式执行
- agent 负责理解、规划、编辑决策
- agent 不应长期承担“自由调用一堆工具碰碰运气”的角色
- 可结构化的动作尽量沉到确定性执行层

### 2. 协议优先于 prompt
- `NoteDocument` 是文档主协议
- `component_manifest` 是组件能力主协议
- `planner_output / planner_policy` 是策略主协议
- prompt 只是消费这些协议，不再反向主导系统结构

### 3. 业务层输出语义，不直接输出组件名
- 业务层先决定 `semantic intents`
- 系统层再把 intent 映射到具体组件
- 用户说的是“证据块/互动块/叙事块”，不是 `VersusCard/PollBlock`

### 4. 可信与素材不是附属功能
- 事实冲突、确认、来源展示、保守表达属于正式业务层
- 资产绑定、封面绑定、复用图、锁图属于正式业务层

### 5. 可观察性是正式能力
- `turn_trace`
- `inspector_summary`
- `frontend observation`
- `agent_backends`
- 最新日志和 HTML 产物

这些不是调试边角，而是产品和工程稳定性的正式组成部分。

## Layered Architecture

系统最终分成 4 层。

### 1. Business Layer
回答“产品到底在做什么”。

#### 业务场景
- `seeding`
- `travel`
- `daily_share`

#### 业务策略
- `scenario policy`
- `tone policy`
- `layout policy`
- `asset policy`
- `fact policy`
- `theme policy`

#### 业务语义能力
- `hero_media`
- `heading`
- `narrative_text`
- `evidence_summary`
- `comparison`
- `interactive_opinion`
- `location_info`
- `ambience_snapshot`
- `quote_highlight`
- `timeline`

#### 可信与素材规则
- 冲突事实怎么处理
- 什么时候保守表达
- 什么时候采用已确认事实
- 素材如何入池、设封面、复用、锁定、绑定到 block

这一层的核心是：

> 业务层决定“要什么”，而不是“用哪个 Vue 组件名”。

### 2. Agent Decision Layer
回答“该怎么做”。

最终只保留少数真正需要决策的 agent 节点，并统一到 `create_agent`。

#### `intent_agent`
职责：
- 网关判断
- 输出：
  - `task_type`
  - `edit_scope`
  - `scenario_scores`
  - `needs_research`
  - `needs_assets`
  - `risk_flags`

要求：
- 不做重策划
- 不决定页面结构
- 越瘦越好

#### `planner_agent`
职责：
- 融合混合场景
- 生成策略和 block intents

输出：
- `planner_output`
- `planner_policy`
- `block_intents`

要求：
- 只做页面策略层决策
- 不直接创建组件 payload

#### `note_editor_agent`
职责：
- 处理开放式编辑请求
- 输出结构化动作

要求：
- 优先走结构化 action
- 尽量少保留自由工具循环
- 目标识别优先依赖：
  - `NoteDocument`
  - `component_manifest`
  - `planner_policy`
  - 最后才是少量 heuristics

#### Optional: `research_agent`
如果保留，应仅负责研究步骤选择与资料编排，不直接承担页面创作主脑职责。

### 3. Deterministic Execution Layer
回答“如何稳定落地”。

这一层不应该继续 agent 化。

#### `outline_resolver`
职责：
- 从 `block_intents` 映射具体组件
- 决定大纲结构的稳定落地方式

它是对早期 `outline_resolver` / ReAct 大纲脑的替代方向。

#### `component_builder_contract_layer`
职责：
- 约束每个组件的 props 结构
- 调用 builder worker
- 应用 fallback 和 contract enforcement

注意：
- builder 允许使用 LLM worker
- 但其外围必须由 schema/contract 兜住

#### `theme_compiler`
职责：
- 根据主题策略输出稳定视觉 token
- 不再自由生成任意 CSS AST

#### `document_verifier`
职责：
- 检查结果是否可接受
- 检查空结果、过度漂移、内容未改样式却改了、结构缺失等问题

#### `document_renderer`
职责：
- 统一文档到预览/导出的解释层

#### `fact_binding_layer`
职责：
- 冲突处理
- 已确认事实继承
- 字段级来源绑定
- 保守表达

#### `asset_binding_layer`
职责：
- 素材入池
- 封面绑定
- `used_by_blocks`
- `role`
- `locked`
- `source_reason`

#### `workspace_mutation_layer`
职责：
- 回滚
- 分叉
- 选区
- 封面设置
- 资产导入
- 事实确认

#### `checkpoint / rollback / fork runtime`
职责：
- 持久化
- 历史恢复
- 分支管理

### 4. Protocol & State Layer
回答“系统围绕什么对象持续演化”。

#### `NoteDocument`
系统主对象。

建议结构：
- `document_meta`
- `theme`
- `blocks`
- `assets`
- `fact_bindings`
- `provenance`
- `ui_state`

#### `component_manifest`
组件唯一真相源。

至少定义：
- `type`
- `label`
- `semantic_role`
- `supported_scenarios`
- `required_props`
- `optional_props`
- `editable_targets`
- `fact_binding_support`
- `asset_support`
- `theme_slots`
- `frontend_renderer`
- `html_renderer`
- `quick_actions`

#### 运行时观察协议
- `turn_trace`
- `inspector_summary`
- `agent_backends`
- `node_prompts`
- `frontend observation`

## Final Node Matrix

### 最终保留为 `create_agent`
- `intent_agent`
- `planner_agent`
- `note_editor_agent`
- 可选轻量 `research_agent`

### 最终改成确定性模块
- `outline_resolver`
- `theme_compiler`
- `document_verifier`
- `document_renderer`
- `fact_binding_layer`
- `asset_binding_layer`
- `workspace_mutation_layer`
- `checkpoint/fork/rollback runtime`

### 最终应该被弱化或删除的旧形态
- 重 ReAct 的 `outline_resolver`
- 让模型漫游画布工具的老式布局脑
- 纯 prompt 驱动、职责与其他层重叠的历史节点

## Business Layer Design

### 场景不是系统分叉点，而是策略输入
系统不应继续采用：

- “识别到 `travel` 就切整套 prompt 和工具”

应改成：

- `scenario_scores`
- `scenario policy`

例如：

```json
{
  "scenario_scores": {
    "travel": 0.68,
    "seeding": 0.44,
    "daily_share": 0.31
  }
}
```

然后由 `planner_agent` 输出：

- `tone_policy`
- `layout_policy`
- `asset_policy`
- `fact_policy`
- `theme_policy`

### 业务语义先于组件
例如：
- “对比观点” -> `comparison`
- “证据总结” -> `evidence_summary`
- “互动站队” -> `interactive_opinion`

然后由 resolver 决定：
- `comparison` -> `VersusCard`
- `interactive_opinion` -> `PollBlock`
- `evidence_summary` -> `ProductSpecCard` 或 `RadarChartBlock`

## Request Flow

### 新建页面
`user input`
-> `intent_agent`
-> `planner_agent`
-> `outline_resolver`
-> `component builder`
-> `theme_compiler`
-> `document_verifier`
-> `document_renderer`

### 局部编辑/整页编辑
`user input + selection + NoteDocument`
-> `intent_agent`
-> `note_editor_agent`
-> structured action
-> `workspace_mutation_layer`
-> `document_verifier`
-> `document_renderer`

### 素材/可信链旁路
始终并挂：
- `fact_binding_layer`
- `asset_binding_layer`
- `trace/inspector`

## What Modern Means Here

本项目里的“现代 agent 开发范式”具体意味着：

### 是这些
- 少量强约束 agent
- 结构化输出
- 明确状态协议
- manifest 驱动
- planner 驱动
- 可观察性内建
- 可信链与资产链正式建模
- 渐进迁移而不是大爆破

### 不是这些
- 整个项目所有节点都改成 agent
- 为了“看起来高级”继续拆更多 agent
- 让模型长期自由漫游工具箱
- 把 schema、verifier、renderer 这种稳定层也交给模型

## Remaining Upgrade Direction

如果继续往这个目标推进，最值得的后续方向是：

### 1. 继续去 ReAct 化
- 把 `outline_resolver` 彻底收成确定性大纲解析器
- 让大纲层完全围绕 `block_intents + manifest`

### 2. 继续强化 builder contract
- 让 `component_builder` 更少依赖大 prompt
- 更强地围绕 component schema 和 contract 工作

### 3. 继续强化字段级可信绑定
- 让更多 block/field 直接绑定 fact
- 不只是后处理 metadata

### 4. 继续强化业务层 policy
- 让场景、可信、资产都更多以 policy 形式工作
- 少写死在 prompt 中

## Interview Version

如果面试官问“你们项目最后采用什么 agent 架构”，建议表述为：

> 我们最后没有把整个系统做成“到处都是 agent”的形态，而是收成了一个现代的 agentic system：少量 `create_agent` 节点负责决策，比如意图网关、页面规划和开放式编辑；其余部分，比如组件解析、主题编译、文档校验、渲染、事实绑定和素材绑定，都收成确定性模块。  
> 这样做的好处是，系统既保留了 agent 在开放输入上的灵活性，又不会让核心产品协议被模型自由漂移。

## Final Target

最终交付形态不是“纯 `create_agent` 项目”，而是：

> 一个以 `NoteDocument` 为主协议、以 `component_manifest` 为能力真相源、以少量 `create_agent` 为决策脑、以大量确定性模块为执行层的现代 agent 产品系统。
