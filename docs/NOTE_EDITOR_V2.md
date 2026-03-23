# Note Editor V2

`Note Editor V2` 指的是当前仓库里已经落地的编辑主线：把自然语言修改请求收进统一的 `NoteDocument` 协议，而不是再走旧的页面 DSL 或多条分裂编辑链。

## 当前定位

- `intent_agent` 负责判断这轮是不是编辑请求，以及是局部改还是全局改。
- `note_editor_agent` 负责把自然语言请求转成结构化编辑动作。
- `verify_note_node` 负责收口和保护输出。
- `document_renderer` 负责把更新后的 `NoteDocument` 渲染到前端。

当前最稳定的编辑链可以概括成：

`intent -> note_editor -> verify -> document_renderer`

## 关键文件

- [`note_editor_node.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
- [`note_editor_support.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_support.py)
- [`note_editor_prompts.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_prompts.py)
- [`verify_note_node.py`](../AI_Frontend_IDE/app/agents/nodes/verify_note_node.py)
- [`note_tools.py`](../AI_Frontend_IDE/app/tools/note_tools.py)
- [`graph.py`](../AI_Frontend_IDE/app/agents/graph.py)

## 输入与上下文

`Note Editor V2` 不再直接吃旧 DSL，而是围绕这些上下文包工作：

- `document_summary`
- `selection_context`
- `policy_summary`
- `fact_summary`
- `asset_summary`
- `evidence_slice`

这些上下文由：

- [`context_engineering.py`](../AI_Frontend_IDE/app/core/context_engineering.py)
- [`component_manifest.py`](../AI_Frontend_IDE/app/core/component_manifest.py)

统一提供。

## 输出形态

当前编辑器输出的是结构化编辑动作，最终只回写 `note_document`。典型动作包括：

- 更新标题或正文
- 定位并改写某个 block
- 在指定位置插入 block
- 调整页面主题
- 结合 grounding / citation 更新 block 字段

## 为什么叫 V2

相对于旧方案，V2 的核心变化是：

- 不再围绕旧 DSL 执行
- 不再让 `intent` 和 `outline` 一起承担编辑策划
- 编辑动作以 `NoteDocument` 为唯一正式目标
- 上下文工程和提示词工程已统一进正式基础设施

## 推荐阅读顺序

1. [`graph.py`](../AI_Frontend_IDE/app/agents/graph.py)
2. [`note_editor_node.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
3. [`note_editor_support.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_support.py)
4. [`note_editor_prompts.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_prompts.py)
5. [`context_engineering.py`](../AI_Frontend_IDE/app/core/context_engineering.py)
6. [`component_manifest.py`](../AI_Frontend_IDE/app/core/component_manifest.py)

