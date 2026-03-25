# Resume Project Description

最后更新: 2026-03-24

## 1. 一句话版本

构建了一套面向数码购买决策的 Supervisor Agent 工作台，围绕 artifact/version、知识审查和 revision loop 实现自然语言协作式成品维护。

## 2. 两句话版本

设计并实现一套数码购买决策 Agent 工作台，用户可在同一份购买决策档案上持续进行自然语言编辑、补图、补知识、回滚和分叉。  
系统采用 free-dialogue supervisor + worker 架构，结合 artifact/version、结构化优先 RAG、会话知识审查、白盒 trace 和评估面板，形成一套可观测、可回滚、可维护的 agent 产品。

## 3. 简历项目段落版本

XHS-Forge 是一个面向数码购买决策的 Agent 工作台。项目以一份持续演化的购买决策档案为核心产物，围绕 artifact/version、revision loop 和局部重做构建长期协作体验。架构上采用 free-dialogue supervisor 统一对话入口，并将 retrieval、composition、critique 拆成固定 worker；原来的知识审查前整理与素材补齐职责收回到了 retrieval/composition 中。同时补齐结构化优先 RAG、会话知识审查、热点缓存、trace/export、Benchmark 与前端 observability，从而把项目收成一个真正可解释、可评估的 agent 应用系统。

## 4. 推荐简历 bullets

- Built a free-dialogue supervisor agent system for digital purchase decisions, where users iteratively co-edit a long-lived decision artifact instead of receiving one-shot generated content.
- Designed an artifact-centered runtime with explicit `artifact_version`, parent lineage, changed-block diffs, knowledge-version references, rollback, and branching.
- Implemented a structured revision loop with block-scoped redo contracts, asset diff validation, and a lightweight revision panel that keeps critique non-blocking by default.
- Built a knowledge-governed RAG stack with structured-first retrieval, candidate/session/persistent KB layers, evidence grounding, cache warm-up, and artifact-linked knowledge references.
- Added white-box observability and evaluation surfaces exposing worker selection, tool calls, knowledge versions, changed blocks, failure reasons, and retrieval/generation metrics.

## 5. 中文简历 bullets

- 设计并实现了一个面向数码购买决策的 Supervisor Agent 工作台，用户可以围绕同一份购买决策档案持续进行自然语言协作，而不是一次性生成内容。
- 构建了 artifact-centered runtime，显式建模 `artifact_version`、父版本链、changed-block diff、knowledge version、回滚和分支。
- 实现了结构化 revision loop 与局部重做 contract，支持块级修改、补图验证、非阻断 revision panel 和失败原因回传。
- 设计了结构化优先的 RAG 与知识治理主链，区分 `candidate_session_kb / session_kb / persistent_kb`，并把证据与成品版本挂钩。
- 补齐了前端白盒 observability 与 evaluation 面板，可直接观察 worker 选择、工具调用、knowledge version、changed blocks 与失败点。
