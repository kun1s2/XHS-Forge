# Interview Delivery Pack

最后更新: 2026-03-21

这是一份最终版交付总入口，供你在面试前快速准备和检查。

## 1. 从哪里开始

如果你只看一份文件，先看：

- [`README.md`](../README.md)

它负责：
- 项目一句话
- 核心亮点
- 快速启动
- 交付文档入口

## 2. 架构材料

- 架构图 / 流程图：
  - [`ARCHITECTURE_AND_FLOW.md`](./ARCHITECTURE_AND_FLOW.md)

推荐用途：
- 面试前复盘系统结构
- 面试中解释 agent/runtime/RAG/cache/benchmark 的关系
- 代码审阅时对齐整体心智模型

## 3. Demo 材料

- 演示脚本：
  - [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md)

推荐用途：
- 5 到 8 分钟线上 demo
- 控制顺序，避免一边演示一边临场想
- 确保能稳定展示：
  - 生成
  - 持续编辑
  - RAG / cache / grounding
  - Benchmark

## 4. 面试讲稿

- 最终讲稿：
  - [`INTERVIEW_TALK_TRACK.md`](./INTERVIEW_TALK_TRACK.md)

推荐用途：
- 20 秒自我介绍式项目概括
- 1 分钟项目介绍
- 3 分钟深讲
- 高频追问回答

## 5. 简历材料

- 简历项目描述：
  - [`RESUME_PROJECT_DESCRIPTION.md`](./RESUME_PROJECT_DESCRIPTION.md)

推荐用途：
- 英文 bullets
- 中文 bullets
- 一句话版本
- 不同岗位强调版本

## 6. 推荐准备顺序

### 面试前 30 分钟

1. 看 [`README.md`](../README.md)
2. 看 [`ARCHITECTURE_AND_FLOW.md`](./ARCHITECTURE_AND_FLOW.md)
3. 看 [`INTERVIEW_TALK_TRACK.md`](./INTERVIEW_TALK_TRACK.md)

### 面试前 10 分钟

1. 打开前后端
2. 按 [`DEMO_SCRIPT.md`](./DEMO_SCRIPT.md) 走一遍
3. 确认：
   - Inspector 正常
   - Benchmark 正常
   - 页面渲染正常

### 投简历时

1. 从 [`RESUME_PROJECT_DESCRIPTION.md`](./RESUME_PROJECT_DESCRIPTION.md) 里挑一版
2. 按岗位侧重点调整 bullets

## 7. 这套项目当前能讲什么

现在这套项目已经具备完整交付条件，核心可以讲成：

- Long-lived content editing workbench
- Unified `NoteDocument` protocol
- LangGraph runtime + agent decision nodes
- Structured editing + deterministic execution
- RAG with preload / ingest / grounding / anti-decay
- Cache with TTL / freshness / diagnostics
- Benchmark + Inspector + Prompt Lab

## 8. 当前封板状态

当前正式验收结果：

- 最终验收：`180 passed, 1 skipped`
- guardrails：`21 passed`
- 前端 build：通过

所以这份交付包对应的是：

**已经封板、可以直接面试使用的最终版本。**
