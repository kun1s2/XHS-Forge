# Resume Project Description

最后更新: 2026-03-21

这份文档给你不同长度的简历项目描述版本，方便直接复制使用。

## 1. 一句话版本

构建了一套面向类小红书内容创作的 Agent 工作台，围绕统一的 `NoteDocument` 协议实现自然语言生成与持续编辑，并补齐 RAG、热点缓存、Benchmark 与前端可观察性。

## 2. 两句话版本

设计并实现一套类小红书内容创作 Agent 工作台，用户可在同一篇笔记上持续进行自然语言编辑、回滚、分叉和主题调整。  
项目以 `NoteDocument` 为唯一主协议，结合 LangGraph runtime、structured editing、RAG grounding、TTL 缓存、Benchmark 和 Inspector，形成一套完整的 agent 应用系统。

## 3. 简历项目段落版本

XHS-Forge 是一个面向类小红书内容创作的 Agent 工作台。项目围绕统一的 `NoteDocument` 协议组织前后端、编辑链和渲染链，支持自然语言生成、结构化编辑、checkpoint / rollback / fork、RAG 搜证与 grounding、热点缓存与 Benchmark 评估。架构上采用 LangGraph 作为 workflow/runtime，保留少量高价值 agent 节点负责决策，并将 resolver、builder、verifier、renderer 等能力收回确定性执行层，从而兼顾灵活性、稳定性和可维护性。

## 4. 推荐简历 bullets

- Designed and shipped a long-lived content creation workbench for Xiaohongshu-style notes, enabling natural-language generation, incremental editing, rollback, and branching on a unified `NoteDocument` state model.
- Unified the runtime around a single protocol by removing legacy DSL/state paths and restructuring the system into LangGraph orchestration, agent decision nodes, and deterministic execution layers.
- Built structured editing and component generation pipelines with manifest-driven contracts, block-level fact bindings, and frontend-observable trace/diagnostic views.
- Implemented an engineering-grade RAG stack with `system_preload`, `task_triggered_ingest`, retrieval policy/rerank, grounding/citation, anti-decay freshness control, and cache diagnostics.
- Added a benchmark dashboard and runtime observability surface to evaluate grounding score, citation coverage, cache hit rate, builder fallback rate, and scenario/theme/component distributions.

## 5. 中文简历 bullets

- 设计并实现了一套类小红书内容创作 Agent 工作台，支持自然语言生成、增量编辑、回滚和分叉创作，核心围绕统一的 `NoteDocument` 长期状态工作。
- 将系统从旧双轨状态收敛为单一协议，基于 LangGraph 搭建 workflow/runtime，并把 agent 决策层与 resolver / builder / verifier / renderer 等确定性执行层明确分层。
- 实现了结构化编辑与 manifest 驱动的组件生成链，支持 block 级事实绑定、前端可观察 trace、Inspector 与 Benchmark 评估面板。
- 构建了工程化 RAG 能力，包括 `system_preload`、`task_triggered_ingest`、retrieval policy / rerank、grounding / citation、anti-decay 与缓存诊断。
- 设计并实现了系统级 Benchmark 面板，可视化 grounding score、citation coverage、cache hit rate、builder fallback rate 与多场景分布指标。

## 6. 面向岗位的强调版本

### Agent / AI Application Engineer

- 强调：
  - LangGraph workflow
  - NoteDocument state protocol
  - structured editing
  - prompt/context engineering
  - RAG + grounding + benchmark

### AI Backend Engineer

- 强调：
  - workflow runtime
  - unified state model
  - WebSocket/workspace API
  - cache/RAG backend
  - observability + guardrails + benchmark

### Full-stack GenAI Engineer

- 强调：
  - 前后端统一协议
  - workbench UI
  - Inspector + Benchmark
  - block rendering system
  - backend workflow + RAG

## 7. 推荐项目标题

- XHS-Forge: Long-lived Agent Workbench for Social Content Creation
- XHS-Forge: NoteDocument-based Agent Editing System with RAG and Benchmarking
- XHS-Forge: LangGraph-powered Content Creation IDE with Grounded RAG
