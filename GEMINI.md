# XHS-Forge Project Guide

XHS-Forge 当前正式产品是一套 **数码购买决策 Agent 工作台**。

它的核心不是传统页面生成器，而是：

- 一个自由对话式 `supervisor`
- 三个正式 worker：`retrieval_worker`、`composition_worker`、`critique_worker`
- 一份持续演化的 `purchase_decision_note` artifact
- 一条围绕 `artifact_version`、知识审查、revision loop、局部重做和白盒观测的主链

## Product Positioning

- 用户始终只和一个 supervisor 对话
- 系统围绕一份长期维护的购买决策档案工作
- 所有外部知识先进入待审会话知识，再进入正式生成
- revision 默认不打断主聊天流，只通过输入框旁的轻量面板触发

## Formal Runtime

正式后端主控已经统一到：

- `AI_Frontend_IDE/app/agents/runtime/supervisor_runtime.py`
- `AI_Frontend_IDE/app/agents/runtime/session_state.py`

正式状态真相为：

- `SupervisorSessionState`

正式产物协议为：

- `artifact`
- `artifact_version`
- `revision_plan`
- `revision_result`

## Repo Responsibilities

| 路径 | 职责 |
| :--- | :--- |
| `AI_Frontend_IDE/` | 后端运行时、RAG、知识治理、artifact/version、WebSocket 与诊断 API |
| `ai-frontend-ide/` | 前端会话工作台、全局资产中心、RevisionAssistPanel、Inspector 与预览 |
| `docs/` | 当前产品架构、交付材料、视觉回归、运行维护说明 |
| `scripts/` | 最终验收、全量体检、运行时重置、WebSocket 探测 |

## Backend Design Principles

- **单一正式主控**：只有 supervisor runtime 是正式运行入口
- **结构化优先**：所有关键产物都必须是结构化对象，而不是自由文本拼接
- **artifact-centered**：每次成功 turn 必须生成 `artifact_version`
- **revision-safe**：局部重做、补图、润色必须走统一 contract
- **knowledge-governed**：`candidate_session_kb -> session_kb -> persistent_kb`
- **observable by default**：phase、worker、skill、tool、knowledge version、failure point 必须可追踪

## Frontend Principles

- 会话工作台只展示 session runtime 数据
- 全局资产中心不污染 session artifact/state
- 高亮、最近变更块、revision 状态从 artifact diff 派生
- revision 默认走输入框旁小面板，不走强打断卡片

## Operational Guidance

- 正式验收：
  - `bash scripts/final_acceptance.sh`
- 全量体检：
  - `bash scripts/full_system_audit.sh`
- 运行时清空重置：
  - `bash scripts/reset_project_state.sh --yes`

## Guardrails

- 不再把旧运行时状态模型和旧 checkpoint 语义作为正式路径
- 不再扩回 travel/general 主线
- 不要重新引入任何旧时代运行时命名或多版本兼容语义
- Prompt 继续统一文件化管理，不在 Python 中重新散落内嵌系统提示
