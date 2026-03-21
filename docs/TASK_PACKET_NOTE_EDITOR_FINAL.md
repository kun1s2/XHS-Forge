# Task Packet: Note Editor Final

## Goal
把 `note_editor` 收成最终版结构化主脑，而不是“结构化优先 + 开放式 fallback”的混合体。

## Mandatory Outcomes
- 空画布创建走结构化 `CanvasCreationOutput`
- 局部编辑走结构化 `LocalNoteEditOutput`
- 整页编辑走结构化 `GlobalCanvasEditOutput`
- 局部新增与整页新增支持相对位置插入
- 目标识别优先依赖：
  - `NoteDocument` block 元数据
  - `component_manifest`
  - `planner_policy`
  - 最后才是少量词表
- 正式 runtime 固定上报：
  - `note_editor: structured_function_calling`

## Remaining Work
- 继续把低频、模糊但仍属编辑的请求压进结构化动作，而不是重新引入开放式 fallback
- 补节点级测试，证明：
  - 常见编辑请求不会触发开放式 fallback
  - 非空画布的兜底路径也只会返回结构化 backend

## Acceptance
- `note_editor_node.py` 中不再存在正式执行路径上的 `create_controlled_agent(...)`
- `agent_backends` 中 `note_editor` 不再返回 `langgraph_create_react_agent`
- 对以下场景有测试：
  - 首版创建
  - 局部编辑
  - 局部新增
  - 整页重写段落
  - 整页新增
  - 相对位置插入
  - 参数卡可信编辑
  - 模糊编辑请求的结构化兜底

## 补充进展：整页新增已支持语义锚点插入（2026-03-20）
- 新增 `_resolve_global_append_anchor_id(...)`，允许 `append_block` 在没有显式 `block_id/block_index` 时，依赖 `NoteDocument + planner_policy` 去解析“互动那块/证据那块/正文那块”等抽象锚点。
- 这让整页新增进一步摆脱对模型显式补全锚点字段的依赖，更接近真正的结构化编辑器。
- 对应回归已补：`test_apply_global_edit_plan_appends_structured_block_after_semantic_anchor`。

## 补充进展：语义锚点新增已进入节点级主链覆盖（2026-03-20）
- 已新增节点级回归：`test_note_editor_node_uses_structured_global_append_path_with_semantic_anchor`。
- 现在“在互动那块后面补一个参数卡”这类请求，不只是 helper 能做，正式 `note_editor_node(...)` 主链也已确认会走结构化整页新增路径。

## 补充进展：结构化移动已支持语义锚点（2026-03-20）
- 已新增 `_extract_move_subject_query(...)` 与 `_resolve_global_move_target_index(...)`。
- 现在“把互动那块放到标题后面”这类请求，正式主链已经能通过 `NoteDocument + planner_policy` 解析目标块、锚点块和前后关系，而不必要求模型自己计算索引。
- 节点级与纯函数级回归均已补齐。


## 补充进展：局部结构化移动已支持语义锚点且不再被作用域保护回退（2026-03-20）
- `_apply_local_edit_plan(...)` 现在已支持基于抽象锚点解析 `move_block` 的目标位置。
- `_restrict_local_edit_scope(...)` 在 `action == "move_block"` 时会保留新的 `blocks` 顺序，同时继续锁住其他旧区块的数据和样式不被误改。
- 对应纯函数级与节点级回归都已补齐，确保“把这个放到标题后面”这类局部请求正式走结构化主链。
