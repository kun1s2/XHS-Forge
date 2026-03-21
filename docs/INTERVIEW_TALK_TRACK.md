# Interview Talk Track

最后更新: 2026-03-21

这份讲稿是最终版。你可以按 20 秒、1 分钟、3 分钟、追问问答四个层级来讲。

## 1. 20 秒版本

> 我做了一个面向类小红书内容创作的 Agent 工作台。  
> 用户可以生成并持续编辑一篇笔记，系统围绕统一的 `NoteDocument` 状态工作，支持 RAG 搜证、热点缓存、版本回滚/分叉、Benchmark 评估和前端可观察性。

## 2. 1 分钟版本

> 这个项目不是一次性生成页面的聊天机器人，而是一个长期可编辑的内容创作系统。  
> 用户可以先生成一篇笔记，后面继续说“保留标题，重写第二段”“把互动卡换成雷达图”“整体改成灰蓝风格”，系统会在同一份 `NoteDocument` 上继续编辑，而不是每轮从零生成。  
> 我把系统收成了统一协议 + LangGraph runtime + 少量 agent 决策层 + 大量确定性执行层的结构。同时补齐了 RAG、grounding、热点缓存、Benchmark 面板和 Inspector，所以它既是一个产品化工作台，也是一套完整的 agent 应用工程项目。

## 3. 3 分钟版本

### 3.1 项目定位

> 我把这个项目定位成内容创作工作台，而不是 prompt demo。  
> 关键差别是系统真正维护一份长期状态对象，而不是每轮只返回一段文本。

### 3.2 核心协议

> 整个系统围绕 `NoteDocument` 工作。  
> 这是唯一主协议，前后端、编辑链、渲染链、RAG grounding 和 Inspector 都围绕它组织。  
> 我还彻底移除了旧 DSL 和兼容方案，让代码、运行时和展示层只讲一种语言。

### 3.3 Agent 架构

> 我没有把所有东西都做成 agent。  
> 外层用 LangGraph 负责编排和状态流转，真正保留成 agent 的只有：
> - `intent_agent`
> - `planner_agent`
> - `note_editor_agent`
>
> 大纲、主题、校验、渲染这些收回到了确定性系统里。  
> 这是我后来很重要的一个工程判断：agent 应该做高价值决策，而不是吞掉整个系统。

### 3.4 RAG 与缓存

> 这个项目里的 RAG 不是“接个向量库问答”，而是和工作流打通的。  
> 我做了两条 ingestion 主线：
> - `system_preload`
> - `task_triggered_ingest`
>
> 再加上 retrieval policy、grounding、anti-decay、cache TTL 和 cache diagnostics。  
> 所以面试时我不只是能说“我们有 RAG”，还能展示这轮到底怎么搜、是否命中缓存、用了哪些来源、grounding 分是多少。

### 3.5 可观察性

> 我把 Inspector 和 Benchmark 都做进了前端。  
> Inspector 看单轮过程，Benchmark 看多轮整体表现。  
> 这对 agent 应用特别重要，因为面试官可以直接看到系统怎么决策、怎么落地、怎么评估，而不是只听我口头描述。

## 4. 高频追问回答

### Q1: 你为什么不是做成“全都用 agent”？

> 因为真正稳定的系统不应该把所有能力都交给 agent。  
> 我后来的收敛方向是：agent 只负责高价值决策，像 resolver、theme compiler、verifier、renderer 这类稳定能力要收回确定性系统，这样系统才可解释、可测试、可维护。

### Q2: 你为什么要统一成 `NoteDocument`？

> 因为长期编辑系统最怕双协议。  
> 如果前端一套、后端一套、RAG 又一套，后面所有逻辑都会变成桥接代码。  
> 统一成 `NoteDocument` 后，编辑、渲染、grounding、trace 和 benchmark 都能围绕同一个对象组织，可读性和稳定性都会明显更高。

### Q3: 你这个项目里后端含金量在哪？

> 后端部分主要有 8 块：
> - LangGraph runtime/workflow
> - 统一状态协议
> - prompt/context engineering
> - structured output + contract enforcement
> - RAG backend
> - cache system
> - WebSocket/workspace API
> - observability + benchmark + guardrails

### Q4: 你为什么做 Benchmark？

> 因为 Inspector 只能说明这一轮发生了什么，Benchmark 才能说明这套系统很多轮下来表现得怎么样。  
> 我希望这个项目在面试里不是“看起来很炫”，而是“我还能证明它有效”。

## 5. 讲项目时不要这样说

### 不要说

> 我做了很多 agent，每个 agent 都很智能。

### 更好的说法

> 我把系统收成了少量高价值 agent + 大量确定性执行层，这样兼顾了灵活性和稳定性。

### 不要说

> 这个项目能做任意场景、任意页面。

### 更好的说法

> 我刻意围绕 `seeding / travel / daily_share` 三类高价值场景收束能力，确保系统闭环、展示稳定、叙事清晰。

## 6. 最后 15 秒收尾

> 这个项目让我最大的收获不是“做了多少 agent”，而是学会了如何把 agent、RAG、缓存、状态协议和可观察性收成一套真正能长期维护的系统。  
> 最终我做出来的不是一个 prompt demo，而是一个更像内容创作 IDE 的 agent 应用。
