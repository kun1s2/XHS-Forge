# ⚡️ XHS-Forge — 小红书风格生成式 UI 锻造炉 (Social-Engine 1.0)

本项目名为 **XHS-Forge**，旨在通过多 Agent 编排技术，为用户提供工业级的小红书风格前端页面生成能力。

---

## 🏗️ 项目概述 (Project Vision)

- **目标**：根据用户输入的**文字与图片**，生成高保真、小红书风格的前端页面（笔记页）。
- **核心理念**：DSL 驱动 (Data/Style JSON)、场景原型约束 (Archetype)、以及可观测的交互体验 (Observable UX)。
- **架构哲学**：主脑与感知分离。使用 OpenAI 范式进行思考，使用智谱全家桶进行感知。

---

## 📂 目录结构与职责

| 路径 | 职责 |
| :--- | :--- |
| `AI_Frontend_IDE/` | **后端**：FastAPI + LangGraph。处理状态机、RAG、工具调用及 WebSocket 流式推送。 |
| `ai-frontend-ide/` | **前端**：Vue 3 + TS + Pinia + Tailwind。负责实时渲染、时间胶囊回滚及用户交互。 |
| `.cursor/rules/` | **治理**：严格的开发规则，涵盖状态优先逻辑、中间件使用及结构化输出规范。 |
| `docker-compose.yml` | **编排**：一键启动全栈服务 (Backend, Frontend, Redis, Postgres)。 |

---

## 🚀 最新进度 (战役 G/H - 架构重构)

### 1. 硬核 Agent 架构 (LangGraph + OpenAI)
- **主脑范式**：所有 Intent/Content/Style 节点强制使用 `ChatOpenAI` 接口，兼容阿里云 Qwen/DeepSeek。
- **结构化输出**：全面启用 Pydantic `with_structured_output`，杜绝正则解析幻觉。
- **解耦设计**：主模型只负责“蒸馏”与“决策”，不直接调用底层感知 API。

### 2. 感知与记忆矩阵 (ZhipuAI 全家桶)
- **原生 SDK**：彻底移除 httpx/zai 库，全线接入智谱官方 `zhipuai` SDK。
- **搜网能力**：使用 `client.web_search` 接口进行全网即时检索。
- **多模态能力**：
    - **识图**：`glm-4.6v-flashx`
    - **绘图**：`cogview-3-plus`
- **向量记忆**：`ZhipuAIEmbeddings` (`embedding-3`) 驱动 PGVector。

### 3. 风控与安全 (Defense-in-Depth)
- **网关拦截**：在 WebSocket 入口处进行第一层短路拦截。
- **云端同步**：通过 Redis 实时同步云端变种违禁词库 (500+ 实战词汇)。
- **双栈审计**：结合关键词匹配与 PGVector 语义向量审计。

---

## 🛠️ 外部服务与凭证矩阵 (Service Matrix)

| 服务领域 | 供应商 | 核心模型/接口 | 环境变量 Key | 必填 |
| :--- | :--- | :--- | :--- | :--- |
| **中央主脑** | 兼容 OpenAI 协议 (如阿里云/DeepSeek) | `qwen-max`, `qwen-plus` 等 | `LLM_API_KEY`, `LLM_BASE_URL` | ✅ |
| **感知与搜索** | 智谱 AI (ZhipuAI) | `glm-4-flash` (搜索), `cogview-3-plus` (绘图), `glm-4v` (识图) | `ZHI_PU_API_KEY` | ✅ |
| **向量记忆** | 智谱 AI (ZhipuAI) | `embedding-3` | `ZHI_PU_API_KEY` (复用) | ✅ |
| **物理世界 (LBS)** | 高德开放平台 (AMap) | Web 服务 API (地理编码/POI) | `AMAP_WEB_SERVICE_KEY` | ❌ (可选) |
| **对象存储 (OSS)** | AWS S3 / 阿里云 OSS | S3 协议兼容接口 | `S3_ENDPOINT_URL`, `S3_ACCESS_KEY_ID`, ... | ✅ |
| **搜索引擎 (备用)** | SerpAPI (Google) | Google Search API | `SERPAPI_API_KEY` | ❌ (可选) |

---

## 📜 开发准则

- **始终** 视 `UIProjectState` 为单一事实来源。
- **优先** 使用结构化输出而非字符串解析。
- **绝不** 阻塞主线程；同步 SDK 调用必须使用 `asyncio.to_thread`。
- **遵循** 黄金比例间距系统添加任何新 UI 组件。
