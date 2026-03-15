# LangChainProject — 项目上下文与进化历程 (Social-Engine 1.0)

本文档为 Gemini 提供项目根目录的工作上下文，定义了系统架构、工程标准以及最新的开发进度。

---

## 🏗️ 项目概述 (Social-Engine)

- **目标**：根据用户输入的**文字与图片**，生成高保真、小红书风格的前端页面（笔记页）。
- **形态**：基于 **LangGraph** 的多 Agent 编排平台。
- **核心理念**：DSL 驱动 (Data/Style JSON)、场景原型约束 (Archetype)、以及可观测的交互体验 (Observable UX)。

---

## 📂 目录结构与职责

| 路径 | 职责 |
| :--- | :--- |
| `AI_Frontend_IDE/` | **后端**：FastAPI + LangGraph。处理状态机、RAG、工具调用及 WebSocket 流式推送。 |
| `ai-frontend-ide/` | **前端**：Vue 3 + TS + Pinia + Tailwind。负责实时渲染、时间胶囊回滚及用户交互。 |
| `.cursor/rules/` | **治理**：严格的开发规则，涵盖状态优先逻辑、中间件使用及结构化输出规范。 |
| `src/` / `frontend/` | **遗留**：旧项目文件，保留作历史参考，不作为新功能的依赖。 |

---

## 🚀 最新进度 (重大里程碑)

### 1. 硬核 Agent 架构 (2026 版 LangGraph 实装)
- **结构化输出 4.0**：`intent_node` 和 `style_node` 已全面从正则解析进化为原生 `with_structured_output(PydanticModel)`。
- **自主工具调用**：废弃了死板的串行节点，引入 ReAct 模式的 **`research_agent`**，能够根据意图动态调用 RAG、网搜和识图工具。
- **官方记忆截断器**：集成 LangChain 官方 `trim_messages` 中间件，彻底解决长对话导致的 Token 爆池问题。

### 2. 多层防御体系 (安全与优化)
- **双层缓存拦截**：
    - **L1 (Redis MD5)**：瞬间秒杀完全重复的请求。
    - **L2 (PGVector 语义)**：高精度 (0.95 阈值) 拦截相似语义意图，实现 0.1s 极速旁路返回。
- **自适应 HITL (人类在环)**：
    - **立场裁决**：针对争议话题，自动暂停并请求用户选择“红黑榜”立场。
    - **实体消歧**：当搜索置信度 < 0.6 时，自动挂起并请求用户手动校准歧义项。
- **风控网关**：前置过滤敏感词及高危语义话题。

### 3. 数据与 RAG 引擎 (PGVector 深度集成)
- **混合召回 (Hybrid Search)**：实装了 Postgres 原生 RRF 算法，结合向量距离与全文检索 (`to_tsvector`)。
- **Self-Querying**：利用 LLM 提取 Metadata 过滤条件（如 `price < 50`），实现精准的 JSONB 索引查询。
- **异步知识飞轮**：利用后台任务进行热点蒸馏与向量入库，不阻塞主生成流程。

### 4. 视觉与交互 (Vibe Engine)
- **视觉感知引擎**：通过 GLM-4V 自动从图片提取色彩 Token，并动态注入全站 CSS 变量。
- **黄金比例间距系统**：基于 8px 栅格的设计宪法，强制推行标准间距 Token (SM, MD, LG)。
- **可观测 UX**：通过 WebSocket 实时推送 Agent 的“思考流”状态描述，消除用户的等待焦虑。

---

## 🛠️ 技术栈速查表

- **Conda 环境**：`LangChainProject`
- **后端入口**：`AI_Frontend_IDE/run.py` (端口 8000)
- **前端入口**：`ai-frontend-ide/npm run dev` (端口 5173)
- **数据库**：PostgreSQL + PGVector + Redis
- **核心模型**：`qwen-max` (主控), `glm-4-flash` (调研), `CogView-3-Plus` (生图), `GLM-4V` (识图)。

---

## 🎯 当前关注重点与战略

1.  **交互体感优化**：完善实时思考动画与思考流映射。
2.  **创作者人设注入**：支持用户随时切换身份（如硬核数码博主、毒舌美妆专家）以变换文风。
3.  **云端总攻**：向阿里云 Docker 环境迁移，验证内网环境下的极致响应速度。

---

## 📜 开发准则

- **始终** 视 `UIProjectState` 为单一事实来源。
- **优先** 使用结构化输出而非字符串解析。
- **绝不** 阻塞主线程；同步 SDK 调用必须使用 `asyncio.to_thread`。
- **遵循** 黄金比例间距系统添加任何新 UI 组件。
