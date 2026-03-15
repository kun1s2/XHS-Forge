# AI Frontend IDE — 后端架构说明（以 LangChain / LangGraph 为主）

本文档描述 **AI_Frontend_IDE** 后端的整体架构、状态机、图与节点、提示词与约束规范，以及与本项目约定的「禁止在提示词构建中使用 f-string、一律采用外部文件 + 模板」的实践。

---

## 1. 项目概览

后端是一个基于 **LangGraph** 的多节点工作流引擎：用户通过 WebSocket 发送指令与资产，经意图路由后进入对应管线（文案 / 结构 / 样式 / RAG / 图片等），最终产出可部署的 HTML 页面与 OSS 链接。

- **入口**：FastAPI WebSocket ` /ws/chat/{thread_id}`
- **状态持久化**：LangGraph Checkpointer（如 Postgres），支持基于 `parent_checkpoint_id` 的时光机回滚与分叉
- **前端契约**：`ChatWSPayload`（文本、面板、父 checkpoint、锁定组件、图库资产、待打标图片 URL）

---

## 2. 技术栈与 LangChain/LangGraph 用法

### 2.1 框架角色

- **LangGraph**：定义 `StateGraph(UIProjectState)`，编排节点与条件边，`compile(checkpointer=...)` 得到可流式执行的图。
- **LangChain**：`ChatOpenAI`、`with_structured_output(Pydantic)`、`ChatPromptTemplate`（Jinja2）、LCEL 管道 `prompt | structured_llm`。
- **状态**：`TypedDict` + `Annotated[..., reducer]`，节点只返回「增量更新」，由 reducer 合并，不直接写死整份 state。

### 2.2 与本项目相关的实践

- **State 为单一事实来源**：业务数据（如 `data_dsl`、`style_dsl`、`image_assets`）一律存在 state 中，由节点读/写，不依赖从 messages 里反推。
- **结构化输出**：排版与样式节点使用 `with_structured_output(StructurePatchOutput)` / `StylePatchOutput`，保证 JSON 形状与 Pydantic 一致，便于下游渲染与合并。
- **流式**：通过 `agent.astream_events(inputs, config=config, version="v2")` 向客户端推送 `token`、`middleware`、`turn_end` 等事件；状态从流中产生的 updates 获取，end 仅传 checkpoint_id 等无法在流中自然产出的字段。

---

## 3. 状态定义（State）与 Reducer

### 3.1 UIProjectState（`app/agents/state.py`）

| 字段 | 类型 | 说明 |
|------|------|------|
| `main_messages` / `content_messages` / `image_messages` / `structure_messages` / `style_messages` | `Annotated[list[BaseMessage], add_messages]` | 五路独立消息通道，由 `add_messages` 追加，不覆盖 |
| `messages` | `Annotated[list[BaseMessage], add_messages]` | 兼容用消息列表 |
| `intent_route` | `str` | 意图节点写下的路由目标（如 `structure_node`） |
| `active_panel` | `str` | 当前面板（如 `main`） |
| `selected_element_id` | `Optional[str]` | 前端锁定的组件 ID，用于局部修改 |
| `image_urls` | `List[str]` | 原始图片 URL 列表（兼容） |
| `image_assets` | `Annotated[List[Dict[str, str]], operator.add]` | 全局图库资产池 `[{"url","desc"}]`，节点只返回「新增」列表，由 `operator.add` 追加 |
| `pending_images` | `List[str]` | 本轮新上传的 URL，由 asset 节点打标后清空 |
| `entity_knowledge` / `visual_perception` | dict / list | RAG 与视觉感知缓存 |
| `content_template_id` / `style_template_id` | `str` | 文案/样式主题 ID |
| `data_dsl` | `Annotated[dict, merge_dsl]` | 页面结构 DSL，由 `merge_dsl` 深度合并 |
| `style_dsl` | `Annotated[dict, merge_dsl]` | 样式 DSL，同上 |
| `final_oss_url` / `final_html` | `Optional[str]` | 渲染结果 URL 与 HTML 源码 |

### 3.2 自定义 Reducer

- **merge_dsl(left, right)**：深度合并字典；若 `right` 非 dict 则丢弃并保留 `left`，避免大模型返回异常类型导致崩溃。
- **add_messages**：LangGraph 内置，消息列表追加。
- **operator.add**：列表拼接，用于 `image_assets`，asset 节点只返回新打标列表，不再次传入整份图库。

---

## 4. 图与节点（Graph + Nodes）

### 4.1 图结构（`app/agents/graph.py`）

- **起点**：`START → asset_processor → intent_agent`
- **条件分支**：`intent_agent` 后由 `route_intent(state)` 决定走向：`rag_node` / `image_node` / `content_node` / `structure_node` / `style_node` 或 `END`。
- **瀑布流级联**：进入某一管线后顺序执行，例如：  
  `rag_node → content_node → structure_node → style_node → render → END`  
  `image_node → content_node → …`  
  `content_node → structure_node → style_node → render → END`  
  等，直到 `render` 写回 `final_oss_url` / `final_html`。

路由使用模糊匹配（如 `"structure" in route`、`"样式" in route`），避免模型少写后缀导致路由失败。

### 4.2 节点职责简述

| 节点 | 作用 | 输出 |
|------|------|------|
| **asset_processor** | 对 `pending_images` 并发调用 `describe_image` 打标，去重后仅返回新资产 | `image_assets`（增量）、`pending_images=[]` |
| **intent_agent** | 根据用户指令与当前页面/锁定组件，输出路由键（Literal） | `intent_route` |
| **rag_node** | 从 config 注入的 PGVector 做异步检索，结果写入 `entity_knowledge`，并追加 ToolMessage | `entity_knowledge`、对应 panel 的 messages |
| **image_node** | 使用图库或 image_urls 调用图片识别，写入 `visual_perception` | `visual_perception` |
| **content_node** | 根据是否「已有页面」与锁定组件，生成/扩写文案纯文本 | `content_messages` |
| **structure_node** | 根据 content 与图库资产，生成/局部修改页面结构（JSON） | `data_dsl`（补丁，由 merge_dsl 合并） |
| **style_node** | 根据 data_dsl 与当前 style_dsl，生成/局部修改样式（JSON） | `style_dsl`（补丁） |
| **render** | 将 data_dsl + style_dsl 渲染为 HTML，上传 OSS，注入 `data-comp-id` 与 postMessage 脚本 | `final_oss_url`、`final_html` |

---

## 5. 提示词规范：外部文件 + 模板（禁止 f-string）

项目约定：**不在代码中用 f-string 拼接系统提示词**，而是使用「外部 XML + Jinja2 模板」与 LangChain 的 `ChatPromptTemplate`。

### 5.1 已采用该方式的节点

- **structure_node**：从 `app/prompts/structure_system.xml` 读取系统提示模板，占位符包括 `is_update`、`current_data_dsl`、`selected_element`、`content_context`、`assets_text`、`user_query`。使用 `ChatPromptTemplate.from_messages(..., template_format="jinja2")`，再 `chain = prompt | structured_llm`，最后 `chain.ainvoke({...})` 传入变量。
- **style_node**：从 `app/prompts/style_system.xml` 读取，占位符包括 `is_update`、`theme_id`、`data_dsl`、`current_style_dsl`、`selected_element`、`user_query`，同样 Jinja2 + LCEL 管道。

提示词文件应放在 **app/prompts/** 下。节点内通过统一根路径解析到该目录（例如基于 `Path(__file__).resolve().parent.parent.parent / "prompts"` 定位到 `app/prompts/`），避免把 f-string 写在 Python 里。

### 5.2 外部模板的约束与格式警告

在 XML 中通过标签表达「约束」与「格式警告」，例如：

- **structure_system.xml**：`<constraints>` 下区分增量/全新规则，并包含「必须严格输出 JSON」「必须 100% 遵守底层提供的数据结构字段名，绝不允许自创或缩写 Key」等说明。
- **style_system.xml**：`<css_rules>`、`<output_format>` 中规定 Tailwind、global_vars/components 结构、禁止破坏排版类名等。

在模板末尾可统一追加一句格式警告（与代码中曾使用的文案一致）：  
**【⚠️ 格式警告】：必须严格输出 JSON 格式！且必须 100% 遵守底层提供的数据结构字段名，绝不允许自创或缩写 Key！**

### 5.3 尚未外置的节点

- **intent_agent**、**content_node** 当前仍在节点内使用多行字符串 + `ChatPromptTemplate.from_messages([("system", "..."), ("human", "...")])`，其中 system 使用 `{data_context}`、`{query}` 等占位符。建议后续将 system 部分抽到 `app/prompts/intent_system.xml`、`app/prompts/content_system.xml`，用 Jinja2 传入变量，彻底去掉 prompt 构建中的 f-string。

---

## 6. 约束与标注（Pydantic、Literal、Field）

### 6.1 结构化输出与字段约束

- **StructurePatchOutput**：`page_title`、`page_order`、`components: Dict[str, ComponentData]`。`ComponentData` 的 `type` 为 `Literal["HeroBanner", "TextSection", "ImageCard", "FeatureGrid"]`，其余字段为可选，`Field(..., description="...")` 中写明「绝对不允许发明其他类型」「必须从全局图库资产提取 URL」等。
- **StylePatchOutput**：`global_vars`、`components: Dict[str, ComponentStyle]`，`ComponentStyle` 含 `css_classes`、`inline_styles`，description 中约束 Tailwind 与保留排版类名。
- **IntentOutput**：`reason`（思维链）+ `intent_route: Literal["content_node", "structure_node", "style_node", "rag_node"]`，强制单选且可解析。

这些 Pydantic 模型与 XML 中的「必须遵守底层数据结构字段名」一致，共同保证大模型输出可被下游安全解析与合并。

### 6.2 组件白名单（component_dict.py）

`COMPONENT_DICTIONARY` 以字符串形式列出允许的组件类型及字段说明（HeroBanner、TextSection、ImageCard、FeatureGrid），可在提示词或模板中引用，避免模型自创 type 或字段。

---

## 7. API 与 WebSocket 入口

### 7.1 ChatWSPayload（app/schemas/requests.py）

- `content`：用户输入文本。
- `panel`：当前面板，默认 `main`。
- `parent_checkpoint_id`：可选，回滚/分叉时的父 checkpoint。
- `selected_element_id`：可选，画布锁定的组件 ID。
- `current_assets`：全局图库 `[{"url","desc"}]`，覆盖 state 中的 `image_assets`（与 state 的「单一事实来源」一致，由前端同步）。
- `image_urls`：本轮新上传的图片 URL，写入 `pending_images`，由 asset 节点打标后并入 `image_assets`。

### 7.2 WebSocket 流（app/api/chat.py）

- 将 `content` 与 `current_assets` 中的图片组装为多模态 `HumanMessage(content=[{"type":"text", "text": ...}, {"type":"image_url", ...}])`。
- `inputs` 写入 `msg_key`、`active_panel`、`selected_element_id`、`image_assets`、`pending_images`；若存在 `parent_checkpoint_id` 则写入 `config.configurable.checkpoint_id`。
- `agent.astream_events(..., version="v2")` 中：  
  - `on_chat_model_stream`：仅对指定节点（如 content_node）转发 `token`。  
  - `on_chain_start`：转发 `middleware`（节点名）。  
  - `on_chain_end`（LangGraph 整图结束）：`aget_state` 后发送 `turn_end`，包含 `checkpoint_id`、`oss_url`、`image_assets`、`page_data`（data_dsl）、`source_code`（final_html）等。

---

## 8. 配置与扩展点

- **app/core/config.py**：Pydantic Settings，从 `.env` 读取 LLM、PGVector、S3/OSS、Embedding 等；图编译时注入 `vector_store` 到 `config["configurable"]`，供 rag_node 使用。
- **Checkpointer**：在 `main.py` 的 lifespan 中创建并传入 `compile_my_graph(checkpointer=..., store=...)`，实现线程级持久化与时光机。
- **渲染与 OSS**：`render_node` 调用 `app/services/oss_client.upload_html_to_oss`，失败时回退到本地预览 URL；生成的 HTML 中为组件根元素设置 `data-comp-id`，并注入 click / mouseover / mouseout 的 postMessage，供前端「选中」与「悬浮检视」使用。

---

## 9. 小结

- **状态**：`UIProjectState` + 自定义 reducer（merge_dsl、operator.add、add_messages），业务数据以 state 为准。
- **图**：LangGraph `StateGraph`，条件路由 + 瀑布流级联，节点只返回增量。
- **提示词**：禁止在节点内用 f-string 拼系统提示；structure/style 已改为「外部 XML + Jinja2 + ChatPromptTemplate」；建议 intent/content 同样外置模板。
- **约束**：Pydantic 结构化输出 + Literal/Field description + XML 内约束/格式警告 + 组件白名单，保证 JSON 与字段名 100% 符合底层约定。
- **前后端契约**：WebSocket payload 与 `turn_end` 字段已涵盖 checkpoint、资产、页面数据、源码，前端从流与 end 中取数，不重复从 messages 反推业务状态。

以上即为当前后端（以 LangChain/LangGraph 为主）的架构与规范总结。
