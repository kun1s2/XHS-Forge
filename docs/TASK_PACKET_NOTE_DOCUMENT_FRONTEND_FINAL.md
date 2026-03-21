# Task Packet: NoteDocument Frontend Final

## Goal
让前端真正以 `NoteDocument` 为主协议，legacy `pageData/styleData` 只留在 store 兼容层内。

## Mandatory Outcomes
- store 是唯一兼容层
- 预览、Inspector、素材库、回滚恢复、结果回执都优先使用 `NoteDocument`
- block 渲染优先只吃 `node.props/node.style`
- 组件内不再手写 `NoteDocument -> legacy` 兼容逻辑

## Remaining Work
- 继续收掉零散的 `pageData/styleData` 显式读取
- 继续把 hover payload、选中块、封面、场景标签、patch tracks 统一通过 store 派生值暴露
- 保证 legacy fallback 集中且可删除

## Acceptance
- 前端 build 通过
- `PreviewIframe`、`ChatPanel`、`AgentInspector`、核心 renderer 不再散落 legacy 推导
- workspace 恢复与回滚恢复在 `NoteDocument` 主协议下稳定

## 补充进展：主协议契约追平（2026-03-20）
- `NoteDocumentBlock` 的 schema 已补齐 richer block metadata，避免前端继续站到 `NoteDocument` 时只在运行时有字段、在正式契约层却缺位。
- 当前 block 正式字段至少包括：`label`、`semantic_role`、`editable_targets`、`asset_support`、`fact_binding_support`、`props`、`style`。
- 这一步的意义是：后续继续删除 legacy `pageData/styleData` 依赖时，前端可以更放心地把 block 能力信息直接建立在 `NoteDocument` 上，而不是继续散落在运行时 helper 和注释约定里。

## 补充进展：renderer 层已不再直接读 legacy 协议（2026-03-20）
- `DynamicRenderer` 与 `XForgeRenderer` 已改成只消费统一 render node 结构，block 层不再显式读取 `pageData/styleData`。
- legacy 页面如果仍需渲染，会先在 `useChatStore` 内通过 `buildRenderablePageDataFromLegacy(...)` 补形成 `node.props/node.style` 结构。
- 这意味着前端 legacy 兼容层已经进一步集中到了 store，renderer 目录本身开始真正站到 `NoteDocument / render node` 主协议上。

## 补充进展：store 内部 legacy 同步路径已统一（2026-03-20）
- `useChatStore` 现在新增统一 helper：`resolveLegacyWorkspaceState(...)` 与 `syncLegacyStateFromDocument(...)`。
- `applyWorkspaceSnapshot`、`turn_end`、`rollbackTo` 已不再各自写一份 legacy `pageData/styleData` 回填逻辑，而是统一走这层 helper。
- 这样后续继续删除 legacy 兼容时，入口点更少，也更容易证明 store 正在成为唯一兼容层。

## 补充进展：发送链已优先使用 canonical merged assets（2026-03-20）
- `documentAssets` 现在会合并 `NoteDocument.assets` 与 `imageAssets` 并去重，不再因为文档里已有资产就忽略本轮暂存素材。
- `sendMessage(...)` 也已改成发送 `documentAssets.value`，这样前端发送链更贴近 `NoteDocument` 主协议，同时保留对临时上传素材的兼容。

- `NoteDocument.fact_bindings` 现在开始携带 `fact_fields`，前端后续可直接用这层字段级绑定继续增强 Inspector 与 hover 解释。

## Guardrail Added (2026-03-20)
- Added `tests/test_final_product_guards.py` to enforce that frontend components stay off direct `pageData/styleData` reads.
- This makes the current “store-only legacy compatibility” contract executable, not just documented.
