# XHS-Forge Agent Rebuild Handoff

最后更新: 2026-03-19

配套文档：

1. [`JOB_SHOWCASE_BLUEPRINT.md`](/root/XHS-Forge/docs/JOB_SHOWCASE_BLUEPRINT.md)
2. [`INTERVIEW_DELIVERY_PACK.md`](/root/XHS-Forge/docs/INTERVIEW_DELIVERY_PACK.md)

这份文档用于把本轮大改造的背景、已经完成的工作、当前真实状态、验证结果、风险点和下一步方向一次性交代清楚。

目标不是写 PR 摘要，而是让另一个 agent 或新接手的人能在最短时间内进入战斗状态。

## 1. 核心结论

项目的问题不是“LangGraph 过时”或者“做 agent 这件事不对”，而是：

1. 原来的主链过于流水线化。
2. 节点之间的数据契约不够硬。
3. 渲染白名单和生成白名单不一致。
4. 自然语言编辑笔记的产品目标，和“多段式内容装配线”的实现方式不匹配。

这轮改造的主方向已经明确并部分落地：

- 保留 LangGraph 作为运行时。
- 收敛创意节点。
- 引入 `Note Editor V2` 作为主脑。
- 用 deterministic verifier 和 renderer 做兜底。
- 前端旧页面协议继续向内收缩，逐步只剩 store 内部兼容缓存。
- WebSocket `turn_end` 回包里的 `noteData` 历史别名已删除；旧页面协议进一步缩减为 `pageData/styleData` 兼容层。
- `test_note_editor_v2.py`、`test_chat_ws_integration.py` 与前端 `WSEvent` 类型也已同步移除 `noteData` 口径，避免仓库继续示范过时字段。
- 已新增 `BLOCK_SEMANTIC_ROLES.md` 与 `COMPONENT_MANIFEST_SEMANTIC_MAPPING.md`，把积木从 UI 名称正式收成跨场景语义角色，并给出落回 manifest 的字段映射。
- 已新增 `CORE_BLOCK_SET.md` 与 `CORE_BLOCK_SET_INTENT_MAPPING.md`，把核心积木集合与 planner/resolver/builder 的工程映射补齐。

当前项目已经从“流水线生成器”明显转向“自然语言编辑 Note DSL 的 editor runtime”。

## 2. 原始主问题

在本轮改造前，实际观测到的问题有：

1. `research_agent` 已拿到事实，但 `distill_node` 只认 `ToolMessage`，导致事实链断裂。
2. `component_builder` 的结构化输出与当前模型接口兼容性差，失败后大量回落为占位文案。
3. `style_node` 和组件生成并发，样式依赖状态未稳定落库。
4. `outline_node` 推荐的组件和 `render_node` 实现的组件不一致，常导致最后只渲出一半。
5. 后端 HTML renderer 与前端 Vue renderer 存在协议偏差。
6. 整体交互仍然是 `intent -> research -> distill -> outline -> component_builder -> style -> render` 的旧式流水线，不适合“自然语言直接编辑笔记”。

## 3. 架构判断

### 3.1 版本判断

库版本本身不算老：

- `langgraph==1.0.9`
- `langchain-core==1.2.15`
- `langchain-openai==1.1.10`

后来为了后续迁移基线，也在 [`requirements.txt`](/root/XHS-Forge/AI_Frontend_IDE/requirements.txt) 里补入了 `langchain==1.2.12`。

真正“显得旧”的不是版本号，而是使用方式：

- 项目大量依赖 `langgraph.prebuilt.create_react_agent`
- 主流程依赖多节点内容装配
- 与官方更推荐的 `langchain.agents.create_agent` + 统一 agent 入口相比，心智模型偏旧

### 3.2 新方向

### 3.3 待执行的架构收缩判断

### 3.4 新共识：场景权重与 Planner 层

### 3.5 组件系统能力判断

### 3.6 最终形态目标与后续总路线

当前已确认，项目后续应持续收敛到如下最终形态：

> 一个可长期编辑、可回滚分支、可追踪事实来源的社交笔记创作工作台。

围绕这个最终形态，当前还存在 10 个比普通 bug 更深层的问题：

1. 还没有真正独立的 `planner`，高层决策分散在 `intent / outline / note_editor`。
2. 当前状态模型还不够文档化，旧页面状态曾混合文档、工作区和 patch 职责。
3. 组件系统还不是单一真相源，组件知识散落在 prompt、registry、renderer、alias 等多处。
4. prompt 中写死的业务知识过多，许多内容其实应该沉到 `scenario policy / tone policy / component policy / asset policy`。
5. `note_editor` 仍偏启发式修补器，存在较多 alias 猜测、关键词纠偏和特例 patch。
6. 事实可信链目前更像段落级可信，还没有完全达到字段级 fact binding。
7. 资产系统还不够可编排，图片与 block 之间的绑定、锁定、复用与替图理由还不够强。
8. 前后端双渲染仍然是长期隐患，Vue preview 与 HTML export 仍是两套实现。
9. 评估体系还不够强，缺少结构化评估样本、事实正确性样本、编辑稳定性样本和混合场景样本。
10. 项目讲述层还需要持续收束，所有节点、策略和系统设计最终都应服务于上面的产品级总故事。

当前确认的最高优先级四刀：

1. 增加 `planner`
2. 建立 `component_manifest`
3. 将场景收敛成 `scenario_scores + policy`
4. 将 `NoteDocument` 状态模型独立出来

如果这四刀落地，项目将从“已经很强的 demo”继续进化为“真正有架构说服力的系统”。


当前组件系统的判断也已明确：

1. 对求职 demo 来说，现有核心组件已经足够做出亮点版本。
2. 对“广泛自然语言输入 + 长期编辑”的目标来说，当前组件能力还不够。
3. 当前问题不在数量，而在于组件更像“UI 展示形态”，还不够像“语义内容容器”。
4. 后续应把组件系统收成两层：
   - 核心语义组件：`hero_media / heading / rich_text / fact_list / comparison / opinion_poll / location_info / quote / timeline / cta_footer`
   - 风格化特化组件：`WeatherPolaroid / GiftBox / FlipCard` 等增强型展示块
5. 继续加组件时，不应优先追求更花的卡片，而应优先补：
   - `QuoteBlock`
   - `ChecklistBlock`
   - `EvidenceSummaryBlock`
   - `UseCaseBlock`
   - `DecisionCard`

这条判断意味着：后续组件演进的重点是“语义覆盖面”和“长期可编辑性”，不是继续堆展示形态。


当前已明确采纳以下后续重构方向：

1. 场景不再作为“切换整套 prompt / 工具”的总开关，而改为策略输入。
2. `intent` 后续应输出 `scenario_scores`，而不是只给单一主场景。
3. 新增 `planner` 层，负责把：
   - `scenario_scores`
   - 用户目标
   - 事实状态
   - 资产状态
   转换为统一的：
   - `tone_policy`
   - `layout_policy`
   - `interaction_policy`
   - `asset_policy`
   - `theme_policy`
4. `outline` 不再直接承担上层策划，而只负责把 planner 的 block intent 翻译成区块结构。
5. 组件系统后续改为 manifest 驱动：固定语义组件、固定 props schema、统一 registry，避免“现场发明组件协议”。
6. 样式系统继续收敛为 `theme compiler`，不走自由生成任意 CSS 的路线。

这组共识已被确认，应视为后续大改默认方向。


当前又新增两条关键架构判断，后续重构应以此为准：

1. `intent_agent` 与 `outline_agent` 存在职责重叠。
   - `intent_agent` 当前同时承担路由、场景判定、叙事模式、视觉风格、受众画像、CTA、搜图策略。
   - `outline_agent` 又在做页面级策划、积木选择、互动结构与叙事节奏决策。
   - 后续建议收缩为：
     - `intent`: 只负责网关信号（create/edit/inspect、编辑范围、是否 research、是否需要资产、场景、风险）
     - `planner`: 单独负责内容策略与页面叙事
     - `outline`: 只负责把策略翻译成区块结构

2. 组件系统当前是“字符串驱动的积木流水线”，不是统一的 manifest 系统。
   - 当前组件白名单、工具层、前端 registry、后端 renderer 是多处并存的。
   - `ComponentData` 过宽，类型边界不清。
   - 后续建议重构为：
     - 单一 `component_manifest`
     - 每个组件独立 props schema
     - `planner` 先产出语义 block intent，再由 resolver 映射到具体组件
     - 前后端共用同一份组件注册中心

这两条是后续大改的优先级很高的“方向性决定”，不建议再回到“让 intent 和 outline 同时做策划”或“继续扩大全量字符串组件类型”的旧路线。


目标架构已经单独写在 [`NOTE_EDITOR_V2.md`](/root/XHS-Forge/docs/NOTE_EDITOR_V2.md)。

简化后应是：

理想目标仍然是：

`intent -> note_editor -> verify -> render`

但当前仓库里的实际稳定运行策略已经调整为：

- 整页新建生成：优先走 `research -> distill -> controversy -> battle -> outline -> component_builder -> style -> render`
- 选中组件后的自然语言修改：优先走 `note_editor -> verify -> style -> render`

也就是说，`editor runtime` 目前已经主导“修改”场景，但“整页新建”暂时仍然由旧的稳定生成链负责。

如果需要 research，可作为 note editor 的辅助输入，而不是继续做成整条主流水线。

## 4. 已完成的代码改造

这一节按“已经落地到代码里”的维度写。

### 4.1 事实链修复

文件：

- [`distill_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/distill_node.py)
- [`research_agent.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/research_agent.py)
- [`entity_utils.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/utils/entity_utils.py)

已完成：

1. `distill_node` 不再只依赖 `ToolMessage`，也会承接 `retrieved_knowledge.text_facts`。
2. 统一了实体名清洗逻辑，新增 `normalize_entity_name`。
3. 避免把整句用户请求当作 `entity_name`。
4. `distill_node` 会优先保留已经规范化过的主体名。

效果：

- `帮我针对华为 Mate 60 做一个深度种草笔记` 不再被当成主体名。
- 实际请求中主体已能稳定落为 `华为 Mate 60`。

### 4.2 组件工兵与渲染兜底

文件：

- [`component_builder.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/component_builder.py)
- [`render_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/render_node.py)
- [`schema.py`](/root/XHS-Forge/AI_Frontend_IDE/app/core/schema.py)

已完成：

1. `component_builder` 结构化输出改成 `function_calling` 模式。
2. 增加 `build_component_fallback`。
3. 增加 `enforce_component_contract`。
4. 避免失败后整页都是“内容填充中...”。
5. `render_node` 修复旧样式状态读取方式。
6. 补上对 `RadarChartBlock`、`PollBlock`、`LocationBlock`、`WeatherPolaroid` 的渲染支持。

效果：

- 原先大量空卡和占位卡的问题已明显下降。
- 组件字段不完整时会由 verifier 或 fallback 补齐。

### 4.3 样式链收敛

文件：

- [`style_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/style_node.py)

已完成：

1. 取消不稳定的 ReAct 样式子图依赖。
2. 收敛为更 deterministic 的样式涂装。
3. 输出更稳定的样式编译结果。

效果：

- 样式不再过度依赖中途 agent 自发探索。
- 能稳定给最终 renderer 提供 `global_vars` 和区块样式补丁。

### 4.4 前后端渲染协议对齐

文件：

- [`DynamicRenderer.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/DynamicRenderer.vue)
- [`XForgeRenderer.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/XForgeRenderer.vue)
- [`RadarChartBlock.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/blocks/RadarChartBlock.vue)
- [`PollBlock.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/blocks/PollBlock.vue)

已完成：

1. `styleData` 已真正接入前端渲染层。
2. 前端兼容后端产出的 `RadarChartBlock` 数据格式。
3. 前端兼容后端产出的 `PollBlock` 数据格式。
4. 区块样式数据能传到具体 block 组件。

效果：

- 后端生成的 `RadarChartBlock`、`PollBlock` 不再因为 props 形状不一致而在前端半失效。

### 4.5 新主线：Note Editor V2

文件：

- [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
- [`verify_note_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/verify_note_node.py)
- [`note_tools.py`](/root/XHS-Forge/AI_Frontend_IDE/app/tools/note_tools.py)
- [`tools_registry.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/tools_registry.py)
- [`graph.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/graph.py)

已完成：

1. 新增 `Note Editor V2` 主脑节点。
2. 新增 Note 级工具：
   - `inspect_note_state`
   - `create_note_block`
   - `update_note_block`
   - `set_note_title`
   - `set_note_theme`
3. 新增 `verify_note_node` 做 deterministic 结构校验和字段补全。
4. `intent` 对 `structure/style` 已优先路由到 `note_editor`。
5. 当用户已选中某个组件时，`patch/content/style/structure` 类意图会优先路由到 `note_editor`。
6. `note_editor_node` 已补 state schema，保证内部工具修改过的页面与样式 patch 能回传外层图。
7. 修复了嵌套 agent 里 `messages` reducer 缺失导致的工具消息序列错误。
8. `note_editor` prompt 已改为基于实时 state 的动态 prompt，而不是节点开始时写死的静态 prompt。
9. 新增更像编辑器的操作工具：
   - `move_note_block`
   - `replace_note_block`
10. 为避免全局生成链被实验中的 editor loop 拖垮，`battle_node` 已暂时切回稳定的 `outline_node` 主线；`note_editor` 当前主要负责局部编辑。
11. `note_editor` 局部模式新增了代码级限域护栏：即使模型输出试图误改其他区块，节点出口也只允许目标区块的数据与样式变更通过。
12. `note_editor` 局部模式已进一步收敛为结构化补丁路径：
   - 带 `selected_element_id` 时，优先走 `with_structured_output(..., method="function_calling")`
   - 输出单区块编辑计划，再由代码层确定性执行
   - 当前支持 `update_block / replace_block / move_block / remove_block / noop`
13. 对于“已有整页但未选中具体区块”的修改请求，`note_editor` 现在也有结构化整页编辑路径：
   - 可处理 `update_page_title / update_block / rewrite_paragraph / replace_block / move_block / remove_block / noop`
   - 像“保留标题，重写第二段”这类请求，不再强依赖旧链路或 ReAct 自由发挥
14. 整页主题修改已纳入结构化编辑路径：
   - 新增 `update_page_theme`
   - 当模型返回空主题补丁时，会根据用户请求和 `visual_vibe` 做确定性主题回填
   - 常见别名变量如 `--primary-color / --secondary-color` 会自动归一化到 `--primary-vibe / --muted-color`

效果：

- 后端现在已经具备 editor runtime，但在生产策略上对“新建”和“修改”做了更务实的拆分。
- 新主脑对“编辑已有页面”的感知能力更强，不再只适合空白页生成。
- 局部编辑与全局编辑开始收敛到同一套 editor runtime。
- 选中区块后的自然语言修改现在比之前更少空转，也更适合继续补自动化测试。
- 已有整页的全局文案修改开始具备更可预测的结构化落地能力。
- 已有整页的主题修改现在也能稳定写回页面主题字段，不再只是“看起来像变了”。

### 4.6 WebSocket 回包兼容层

文件：

- [`chat.py`](/root/XHS-Forge/AI_Frontend_IDE/app/api/chat.py)

已完成：

1. 新增 `_build_turn_end_payload`。
2. `turn_end` 同时返回：
   - `checkpoint_id` / `checkpointId`
   - `oss_url` / `ossUrl`
   - `page_data` / `pageData` / `noteData`
   - `style_data` / `styleData`
   - `source_code` / `sourceCode` / `htmlPreview`
3. `veto`、`cache hit`、正常生成结束三条路径都统一使用该 payload 构造器。

效果：

- 新旧前端消费者都更容易兼容。
- 降低“后端明明生成成功，但某个客户端读不到字段”的风险。
- 前端 `useChatStore` 现在也会同时兼容 snake_case / camelCase 两套 `turn_end` 字段。

### 4.7 Workspace 恢复链补全

文件：

- [`workspace.py`](/root/XHS-Forge/AI_Frontend_IDE/app/api/workspace.py)
- [`responses.py`](/root/XHS-Forge/AI_Frontend_IDE/app/schemas/responses.py)

已完成：

1. `WorkspaceDataResponse` 现已显式包含：
   - `node_prompts`
   - `source_code`
2. `WorkspaceDataResponse` 已从旧的字符串协议放宽到实际使用的结构化消息 / 结构化 prompt 协议。
3. `GET /workspace/{thread_id}` 的 checkpoint 时间戳格式化现已兼容 `datetime` 和字符串两种来源。
4. `GET /workspace/{thread_id}` 返回会话时，现已把：
   - `node_prompts`
   - `final_html`
   一并返回给前端

效果：

- 切换会话或刷新页面后，前端能更完整地恢复：
   - 调试提示词
   - HTML 源码
   - 页面状态
- `/workspace/{thread_id}` 不再因为历史 checkpoint 元数据形状或结构化消息 schema 不匹配而 500。

### 4.8 Checkpoint 序列化告警处理

文件：

- [`persistence.py`](/root/XHS-Forge/AI_Frontend_IDE/app/core/persistence.py)

已完成：

1. 为 `AsyncPostgresSaver` 显式配置 `JsonPlusSerializer`。
2. 将 `app.core.schema.IntentOutput` 加入 `allowed_msgpack_modules`。

效果：

- 之前日志里的 `IntentOutput` 反序列化 warning 已被消除。

### 4.9 小型稳定性修复

文件：

- [`graph.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/graph.py)
- [`intent_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/intent_node.py)

已完成：

1. `Send` 导入改为 `langgraph.types.Send`。
2. `intent_node.py` 补了 `asyncio` 导入。

### 4.10 求职展示面收敛

文件：

- [`showcase_manager.py`](/root/XHS-Forge/AI_Frontend_IDE/app/services/showcase_manager.py)
- [`workspace.py`](/root/XHS-Forge/AI_Frontend_IDE/app/api/workspace.py)
- [`ShowcaseRail.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/ShowcaseRail.vue)
- [`ChatPanel.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/ChatPanel.vue)
- [`useChatStore.ts`](/root/XHS-Forge/ai-frontend-ide/src/stores/useChatStore.ts)
- [`JOB_SHOWCASE_BLUEPRINT.md`](/root/XHS-Forge/docs/JOB_SHOWCASE_BLUEPRINT.md)

已完成：

1. 新增 `daily_share` 业务场景，和既有 `seeding`、`travel` 组成 3 条求职展示主线。
2. 新增 `showcase_manager`，统一维护策展后的 demo profiles。
3. `GET /workspace/showcase/profiles` 已可直接返回：
   - 标题
   - 推荐人设
   - starter/edit/theme/branch prompts
4. 前端 `ChatPanel` 已接入 `ShowcaseRail`：
   - 可直接看到 3 条业务线卡片
   - 可一键开新会话并发送 starter prompt
   - 可将 edit/theme/branch prompt 直接带入输入框
   - 可展开面试手卡，直接查看 demo script 与 talking points
5. 一键演示会同步切换推荐创作者人设，并清空上一条业务线遗留的选中态 / 素材态。
6. 前端支持 `VITE_ENABLE_SHOWCASE` 编译期开关，默认可保持隐藏；关闭时不会渲染 showcase 入口，也不会请求对应 profiles 接口。

效果：

- 项目从“需要自己临场想 prompt”提升到“打开即能演示”。
- 更适合求职场景下快速讲清三条业务线和后续编辑闭环。

## 5. 测试与验证

### 5.1 已补/已更新测试

文件：

- [`tests/conftest.py`](/root/XHS-Forge/tests/conftest.py)
- [`test_rag_pipeline.py`](/root/XHS-Forge/tests/test_rag_pipeline.py)
- [`test_generation_smoke.py`](/root/XHS-Forge/tests/test_generation_smoke.py)
- [`test_note_editor_v2.py`](/root/XHS-Forge/tests/test_note_editor_v2.py)
- [`test_chat_ws_integration.py`](/root/XHS-Forge/tests/test_chat_ws_integration.py)
- [`test_workspace_api.py`](/root/XHS-Forge/tests/test_workspace_api.py)
- [`test_showcase_manager.py`](/root/XHS-Forge/tests/test_showcase_manager.py)
- [`test_workspace_showcase_api.py`](/root/XHS-Forge/tests/test_workspace_showcase_api.py)
- [`ws_probe.py`](/root/XHS-Forge/scripts/ws_probe.py)

覆盖点：

1. RAG 主链当前结构兼容性。
2. 生成链 smoke test。
3. `route_intent` 对 `note_editor` 的优先路由。
4. verifier 会补齐 `PollBlock` 必填字段。
5. `turn_end` payload 同时保留 snake_case 和 camelCase 字段。
6. `note_editor` 的动态 prompt 和新增编辑器工具已有单测覆盖。
7. 已验证“选中组件后的 patch/content/style 意图”会优先路由到 `note_editor`。
8. 已为局部编辑补上代码级 scope guard 测试，确保非目标区块不会被误改。
9. 已为局部编辑补上结构化补丁测试，覆盖单区块更新、类型替换和 `note_editor_node` 的局部模式直达路径。
10. 已新增 WebSocket handler 集成测试，直接验证 `turn_end` 兼容字段和 `selected_element_id` 透传。
11. 已新增真实 WebSocket 探针脚本 `scripts/ws_probe.py`，可一键验证“新建 -> 局部编辑”双回合链路。
12. 已为“已有页面的全局修改”补上单测，覆盖 `route_intent` 优先进入 `note_editor`、结构化整页编辑 prompt，以及“保留标题，重写第二段”的段落级修改落地。
13. `scripts/ws_probe.py` 现已扩展为三回合探针：
   - 第 1 回合新建页面
   - 第 2 回合局部选中编辑
   - 第 3 回合全局修改已有页面
14. `scripts/ws_probe.py` 现已扩展为四回合探针：
   - 第 4 回合整页主题修改
15. 已为主题编辑补上单测，覆盖：
   - 空主题补丁的确定性回填
   - 主题别名变量归一化
   - `style_node` 对 `page_theme` 的优先级处理
16. 已为 `/workspace` 响应协议补上单测，覆盖：
   - checkpoint 时间戳兼容
   - 结构化 messages / node_prompts 的 schema 兼容
17. 已为全局编辑补上更强的目标区块解析测试，覆盖：
   - “把投票换成雷达图”这类无 `block_id` 的组件替换
   - “删掉参数卡”这类无 `block_id` 的组件删除
   - 组件别名到正式组件类型的归一化
18. `scripts/ws_probe.py` 现已扩展为六回合探针：
   - 第 5 回合全局替换组件
   - 第 6 回合全局删除区块
19. 已为求职展示入口补上后端单测，覆盖：
   - `showcase_manager` 返回的 3 条业务线与推荐人设
   - `/workspace/showcase/profiles` 的接口协议

### 5.2 最近确认通过的命令

```bash
PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_showcase_manager.py tests/test_workspace_showcase_api.py tests/test_note_editor_v2.py tests/test_generation_smoke.py tests/test_rag_pipeline.py tests/test_chat_ws_integration.py tests/test_ws_probe.py tests/test_workspace_api.py -q
```

结果：

- `58` 项通过

### 5.3 真实链路验证结果

做过多轮真实请求验证，方式是：

1. 启动后端 `uvicorn app.main:app --host 127.0.0.1 --port 8000`
2. 通过 WebSocket 发送真实自然语言请求
3. 观察节点日志与最终渲染日志

已确认的事实：

1. 早期试验里主线曾实际走通 `intent -> research -> distill -> controversy -> battle -> note_editor -> verify_note -> style -> render`
2. 在后续真实压测中发现，`note_editor` 作为“整页新建主脑”仍可能因为过度追求局部润色而打满递归上限。
3. 为了保证产品先稳定可用，当前已经把“整页新建”切回旧的稳定生成链。
4. 真实日志确认：
   - 整页新建链可稳定生成 `VersusCard / ProductSpecCard / PollBlock`
   - `render` 节点可稳定产出完整 HTML
   - 第二条带 `selected_element_id` 的修改消息已成功进入局部编辑入口
   - 局部编辑入口内部现在已进一步收敛为结构化补丁路径，减少 ReAct 工具循环空转
   - 通过 `scripts/ws_probe.py` 的真实双回合压测，已经确认第二回合能把 `PollBlock.question/option_a/option_b` 真正改写为更毒舌的可见文案，而不是只改 `content_brief`
   - 通过扩展后的 `scripts/ws_probe.py` 三回合压测，已经确认第三回合“保留标题，重写第二段，让语气更尖锐一点”会进入 `note_editor` 的整页结构化编辑分支，并真实改写现有 `StoryText` 的第二段
   - 通过扩展后的四回合压测，已经确认第四回合“把整体页面改成更克制的灰蓝风格”会真实写回页面主题字段
   - 真机里模型若返回 `--primary-color / --secondary-color` 这类别名变量，后端会自动补出 `--primary-vibe / --muted-color`，确保渲染器真正吃到主题主色
   - 通过扩展后的六回合压测，已经确认第五回合“把投票换成雷达图”会把 `PollBlock` 真替换成 `RadarChartBlock`
   - 同一轮六回合压测里，也已经确认第六回合“删掉参数卡”会把 `ProductSpecCard` 真从页面里移除
5. 自动化层面，已有整页的全局修改现在也已被回归测试覆盖，尤其是“保留标题，重写第二段”这类真实编辑诉求
6. checkpoint 的 `IntentOutput` warning 已不再出现
7. `/workspace/{thread_id}` 真实接口现已恢复可用，能返回结构化消息、node prompts 和持久化后的 `page_theme`

需要如实说明的一点：

- 现在已经有一条真正跑 WebSocket handler 的自动化测试，能稳定验证 `turn_end` 兼容字段和 `selected_element_id` 透传。
- 换句话说：
  - WebSocket handler 的接口协议已经有自动化保障
  - 后端链路已在真实日志中确认可生成页面
  - “真实模型在线时连续完成新建 -> 选中块编辑 -> 前端消费回包”已经有一轮可复现探针验证
  - 后续更值得做的是把这条真机压测接进更接近前端操作的端到端流程

## 6. 当前项目状态判断

可以认为现在处于：

### 已完成

1. 把项目从“纯流水线心智”推进到了“editor runtime”主线。
2. 事实链、组件兜底、渲染白名单、前后端协议都做了系统性收口。
3. 整页新建已经回到稳定生成主链，局部选中编辑已经开始由 `Note Editor V2` 真实承接。
4. 局部选中编辑已经具备“结构化补丁 + 代码级限域”的双保险。
5. WebSocket handler 的回包兼容和局部编辑透传现在已有接口层自动化测试。
6. 真实双回合 WebSocket 探针已经确认“更毒舌一点”这类局部语气改写会落到可见 payload，而不只是修改描述字段。
7. 现有画布的全局文案修改已经开始通过 `note_editor` 的结构化整页编辑分支处理。
8. 真机三回合探针已经确认“新建 -> 局部编辑 -> 全局编辑已有页面”这条链可以连续执行。
9. 真机四回合探针已经确认“新建 -> 局部编辑 -> 全局改文案 -> 全局改主题”可以连续执行。
10. 真机六回合探针已经确认“新建 -> 局部编辑 -> 全局改文案 -> 全局改主题 -> 全局替换组件 -> 全局删除区块”可以连续执行。

### 尚未彻底完成

1. 还没有把所有旧节点彻底退休。
2. 还没有把所有 `create_react_agent` 迁到 `langchain.agents.create_agent`。
3. `intent` 对所有“新建/全局编辑”场景还没有彻底统一成直接走 editor runtime。
4. 还没有做完贴近前端真实点击和预览反馈的端到端压测闭环。
5. 现有整页编辑已经覆盖文案、结构和主题，但多区块联动编辑还可以继续扩。

## 7. 下一位接手时最应该先做什么

优先级按顺序排列。

### P0

1. 做一次干净的 WebSocket 真机回包验证。
   目标：
   - 进一步把现有 `scripts/ws_probe.py` 扩成更接近前端操作的冒烟脚本
   - 覆盖更多组件类型的局部编辑，而不只是一种 `PollBlock`
   - 覆盖更多全局编辑意图，而不只是一种“重写第二段”
   - 继续扩成更贴近真实前端操作链的 replace/remove/insert 压测

2. 在前端真实页面里手测一轮：
   - 新建笔记
   - 全局改写
   - 全局改主题
   - 带投票
   - 带对比卡
   - 观察是否真的在 preview 里出图

### P1

3. 把 `intent -> research -> distill -> controversy -> battle -> note_editor` 再往前收敛。
   目标不是马上删掉 research，而是让 “是否 research” 成为 note editor 的辅助能力，而不是固定流水线。

4. 为 `note_editor` 增加更多“修改现有页面”的回归测试。
   当前已经覆盖单区块局部编辑和一部分整页文案修改，但还缺更复杂的已有页面编辑场景。
   还需要覆盖：
   - 保留标题，重写第二段
   - 删除一个区块
   - 把投票换成雷达图
   - 改主题但不改内容
   - 同时改两个已有区块
   - 插入新区块但不破坏原顺序

### P2

5. 逐步迁移 `create_react_agent -> create_agent`
   这是技术债，但不是当前 blocker。

## 8. 明确的未决风险

1. `Note Editor V2` 的 prompt 动态 state 感知问题已修复。
   现在每次模型调用都会看到最新画布状态、区块清单和选中区块数据。

2. `note_editor` 作为“整页新建主脑”仍不够稳定。
   在真实运行中仍可能出现重复 `update_note_block` 导致递归打满的问题。

3. 旧节点仍在仓库中保留。
   这对稳定回滚有帮助，但也意味着项目里存在双轨心智。

4. `intent_agent` 仍会把很多请求先判到 `content_node` 语义，再进入 research/battle。
   这和最终想要的“editor first”还有距离。

5. 真实内容质量仍然受 research 文本质量影响。
   现在工程稳定性提升明显，但内容判断质量不是这轮的全部重点。

6. 局部结构化补丁路径目前只针对单个选中区块。
   如果后续要支持“一次点名改两个区块”或“同时改标题和选中块”，还需要扩展输出协议。
7. 整页结构化编辑虽然已经覆盖主题，但目前仍更偏单动作执行。
   如果后续要支持“一句话同时重排多个区块并改主题”，还需要扩展输出协议与落地逻辑。

## 9. 推荐的交接口令

如果要让另一个 agent 接手，建议直接给它下面这段任务说明：

```text
请先阅读 /root/XHS-Forge/docs/AGENT_HANDOFF_2026-03-19.md 和 /root/XHS-Forge/docs/NOTE_EDITOR_V2.md。
当前主线已经改成 Note Editor V2，重点文件是：
- AI_Frontend_IDE/app/agents/nodes/note_editor_node.py
- AI_Frontend_IDE/app/agents/nodes/verify_note_node.py
- AI_Frontend_IDE/app/tools/note_tools.py
- AI_Frontend_IDE/app/agents/graph.py
- AI_Frontend_IDE/app/api/chat.py

先不要推翻当前方案。先做三件事：
1. 在 `scripts/ws_probe.py` 基础上继续扩大真机压测覆盖面
2. 补“全局修改已有笔记”的回归测试
3. 继续把 editor runtime 变成真正的主线，而不是 research/battle 后面的尾节点
```

## 10. 一句话交接总结

本轮工作已经把项目从“不稳定的多段装配线”推进到了“整页生成稳定、局部自然语言编辑可控”的阶段；接下来不是推翻重来，而是继续把 editor runtime 扩到更多场景，逐步接管主线。


## 11. 2026-03-20 增量进展

1. `NoteDocument` 继续向前端主协议迁移。
   - `DynamicRenderer.vue` 已优先按 `noteDocument.blocks/theme` 组织渲染。
   - `PreviewIframe.vue` 的封面读取、hover payload、素材库资产源已优先读 `noteDocument`。
   - `ChatPanel.vue` 的选中块与 payload 也开始优先读 `noteDocument.blocks`。

2. 工作台直接修改接口现在会同步维护 `note_document`。
   - `assets/import`
   - `assets/cover`
   - `facts/confirm`
   - `rollback/component`
   - `select-region`
   - `fork`
   这些接口不再只改旧页面/资产/检索状态，也会同步写回新文档协议。

3. `NoteDocument` 现已携带 `patch_tracks`。
   - `app/core/note_document.py` 现在会把 patch 历史带进 `ui_state.patch_tracks`。
   - `AgentInspector.vue` 的“视觉补丁”页优先从 `noteDocument.ui_state.patch_tracks` 读，不再只依赖旧 `pageData.patch_tracks`。

4. `AgentInspector` 已开始以新协议为主。
   - 活跃标签优先读 `noteDocument.document_meta.scenarios`
   - DSL 面板优先展示 `NoteDocument`，旧 `pageData/styleData` 降为兼容视图

5. 前端 store 已开始在本地直接维护 `NoteDocument.assets` 与封面块。
   - `importAssetToLibrary` 在接口成功后，会先把素材同步进 `noteDocument.assets`。
   - `setAssetAsCover` 的本地预览不再只改旧 `pageData`，也会同步更新 `noteDocument.blocks/assets`，减少素材操作对旧协议的依赖。

6. 前端结果回执与 turn_end 收尾已开始优先比较 `NoteDocument`。
   - `useChatStore.ts` 新增了从 `NoteDocument` 构造可比较页面快照的逻辑。
   - 生成完成、workspace 恢复、兜底补 AI 回执时，都会优先根据 `note_document` 判断区块新增/替换/主题变化，而不是只盯旧 `pageData`。
   - 回滚历史消息、workspace 恢复和 turn_end 现在也能从 `note_document` 反推兼容的 `pageData/styleData`，旧页面协议开始退居兼容层。

7. `note_editor` 继续去启发式化。
   - 组件契约文本已包含 manifest 的 `editable_targets`
   - 目标组件推断优先走 manifest alias 映射
   - 对“重写第二段”这类段落级指令，会更稳定命中 `StoryText`
   - alias map 现在直接复用 `component_manifest`，减少节点内重复维护
   - 全局编辑触发词已改成“通用编辑意图 + manifest 组件别名 + 段落引用”三层判断，不再在节点里硬写一串组件中文名。

8. 最新验证结果。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_architecture_v2.py` -> 5 passed
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 48 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

9. `create_react_agent -> create_agent` 的迁移前置已经落下。
   - 新增 `app/core/agent_runtime.py`，统一 agent 入口。
   - `patch_node.py`、`enrichment_agent.py`、`note_editor_node.py` 都已改成通过兼容层创建 agent。
   - 当前环境里顶层 `langchain` 仍缺失，所以运行时会继续安全回退到 `langgraph.prebuilt.create_react_agent`。
   - 一旦环境补齐，静态 prompt / 无 state_schema 的节点可以先自然切到 `create_agent`。

10. 当前下一优先级。
   - 继续砍前端残余的旧 `pageData` 直耦合，尤其是 Inspector 和调试视图
   - 继续让 `note_editor` 读 manifest / NoteDocument / planner_policy，而不是依赖散落 heuristics
   - 在环境允许后，逐步让兼容层真正切到 `create_agent` 后端

11. 本轮补充进展（渲染与选择链继续去 legacy 化）。
   - `ChatPanel.vue` 的选中块与选中 payload 现在直接复用 store 暴露的 `getDocumentBlockById/getDocumentPayloadById`，进一步减少组件内手写 `noteDocument.blocks` 遍历与旧 `pageData` fallback。
   - `PreviewIframe.vue` 的可渲染判断和封面读取已进一步向 `NoteDocument`/文档资产收口：若文档资产里存在 `role=cover` 的素材，也会直接作为当前封面来源。
   - `PolaroidImage.vue`、`HandwrittenText.vue` 已改成优先吃 `data/node.props`，不再只从 `pageData[node.id]` 取内容。
   - `CollageContainer.vue` 嵌套渲染时现在会继续透传 `styleData`，避免组合块把新样式链截断。
   - `XForgeRenderer.vue` 已把 `styleData` 一并透传给子块，当前核心遗留 `pageData` 读取点只剩统一 fallback，而不再散落在多个 block 里。

12. 最新验证结果（本轮）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_architecture_v2.py tests/test_note_editor_v2.py` -> 49 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

13. 目标块推断继续去启发式化。
   - `note_editor_node.py` 的全局编辑目标选择不再只靠组件别名和固定关键词。
   - 新增了按 `content_brief + 可改写 payload 文案 + manifest alias` 综合打分的轻量逻辑，像“把结论那块简短一点”这类不直接说组件名的请求，也能更自然命中正确区块。
   - 对应回归已补到 `tests/test_note_editor_v2.py`，覆盖了“无组件别名时根据块上下文命中目标”的样本。

14. 最新验证结果（补充）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py` -> 46 passed

15. 渲染器与 Inspector 再次向新协议收口。
   - `XForgeRenderer.vue` 现在会优先使用 `node.style` 作为区块样式来源，`styleData` 更明确退为兼容 fallback。
   - `XForgeRenderer.vue` 的 payload 合并顺序也继续偏向 `node.props`，避免旧 `pageData` 意外覆盖新文档块。
   - `AgentInspector.vue` 的活跃场景标签现在优先来自 `noteDocument.document_meta.scenarios`，其次才看 `planner_output/planner_policy` 的 `scenario_scores`，最后才回退旧 `pageData.archetype_tags`。
   - `note_editor_node.py` 的全局编辑触发识别也增强了一层：当用户没有直接说组件名，但 query 能和当前块上下文形成明显命中时，也会更稳定进入整页编辑路径。

16. 最新验证结果（补充）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 51 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

17. NoteDocument 开始携带组件语义元数据。
   - `app/core/note_document.py` 现在会把每个 block 的 `label / semantic_role / editable_targets / asset_support / fact_binding_support` 一并写进文档。
   - `DynamicRenderer.vue` 会继续把这些字段透传到前端 block 节点，渲染链和编辑链开始共享同一份组件能力信息，而不只是共享 props。
   - 对应契约回归已补到 `tests/test_architecture_v2.py`，确认 `StoryText` 之类的核心块会在 `NoteDocument` 中带上可编辑目标和语义角色。

18. 最新验证结果（补充）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_architecture_v2.py tests/test_note_editor_v2.py` -> 51 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

19. note_editor 开始显式消费 NoteDocument 的组件能力元数据。
   - `note_editor_node.py` 新增了 `NoteDocument` 区块能力摘要与选中区块元数据展示，prompt 不再只注入旧 DSL 和 payload，而会明确看到每个 block 的 `semantic_role / editable_targets`。
   - 局部编辑、整页编辑、基础 note editor prompt 都已接入这层摘要，后续继续削减 heuristics 时可以更多依赖文档协议，而不是散落规则。
   - `tests/test_note_editor_v2.py` 已补对应断言，确认 prompt 中会出现 `interactive_opinion`、`editable_targets` 这类来自 manifest/document 的能力信息。

20. 最新验证结果（补充）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 51 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

21. note_editor 目标识别开始使用块级语义元数据。
   - `note_editor_node.py` 新增了从 legacy 页面状态构造轻量 `NoteDocument` block meta map 的逻辑。
   - `_has_global_edit_request` 与 `_resolve_global_target_id` 现在除了组件别名和 payload/context 文案外，还会利用 block 的 `semantic_role / editable_targets` 做目标识别。
   - 新增回归覆盖了“把互动那块改得更毒舌一点”这类不直接说组件名、但能靠块语义角色命中 `PollBlock` 的样本。

22. 最新验证结果（补充）。
   - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 52 passed
   - `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 23. 前端 legacy 兼容层继续下沉到 store selector。
- 时间：2026-03-20
- 目标：继续减少 `ChatPanel / PreviewIframe / AgentInspector` 自己手写旧 `pageData/styleData` fallback，让 UI 通过 store selector 读取“优先新协议、兼容旧协议”的结果。
- 关键改动：
  - [`useChatStore.ts`](/root/XHS-Forge/ai-frontend-ide/src/stores/useChatStore.ts)
    - 新增：
      - `getPreferredBlockById(doc, page, blockId)`
      - `getPreferredPayloadById(doc, page, blockId)`
      - `getPreferredScenarioTags(doc, plannerOutput, plannerPolicy, page)`
      - `getPreferredPatchTracks(doc, page)`
      - `getPreferredCoverUrl(doc, page, assets)`
    - 这批 selector 统一封装了“优先 `NoteDocument`，再回退 legacy `pageData/styleData`”的兼容逻辑。
  - [`ChatPanel.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/ChatPanel.vue)
    - 选中块与选中 payload 不再自己遍历 `noteDocument.blocks/pageData.blocks`，统一改走 store selector。
  - [`PreviewIframe.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/canvas/PreviewIframe.vue)
    - hover payload 和当前封面读取改走 store selector，减少组件内 legacy fallback。
  - [`AgentInspector.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/AgentInspector.vue)
    - 活跃场景标签和 patch track 读取改走 store selector，不再自己拼 `noteDocument/planner/pageData` 三套逻辑。
- 结果：
  - 前端“新协议优先、旧协议兼容”的判断开始集中到 store，UI 层更轻，后续继续淡出 `pageData/styleData` 会容易很多。

## 24. 最新验证结果（补充）。
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 25. planner policy 开始进入 note_editor 的真实目标识别。
- 时间：2026-03-20
- 目标：不再让 `planner_policy` 只停留在 prompt 展示层，而是让它开始参与整页编辑的目标识别与编辑请求判断。
- 关键改动：
  - [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
    - 新增：
      - `_extract_planner_intent_hints(user_query, planner_policy)`
      - `_score_block_planner_match(block_meta, user_query, planner_policy)`
    - `_score_block_for_query(...)` 现在除了组件别名、payload/context、块语义元数据外，还会吸收 `planner_policy.layout_policy.preferred_block_intents` 的轻量意图提示。
    - `_has_global_edit_request(...)` 与 `_resolve_global_target_id(...)` 新增可选参数 `planner_policy`，整页编辑入口现在会把 `state.planner_policy` 透传进去。
    - 这意味着用户说“证据那块”“互动那块”“收敛一点”这种更抽象的表达时，编辑器会更倾向于命中符合当前 planner 策略和块语义角色的目标，而不只是依赖显式组件别名。
    - 顺手补强了编辑触发词，新增 `收敛 / 克制 / 柔和 / 锐利` 等自然编辑表达，减少“明明像修改请求却没进入整页编辑”的情况。
- 对应回归：
  - [`tests/test_note_editor_v2.py`](/root/XHS-Forge/tests/test_note_editor_v2.py)
    - 新增 `test_resolve_global_target_id_uses_planner_policy_intent_hint`，验证当 planner policy 偏好 `evidence_summary` 时，`把证据那块收敛一点` 会稳定命中 `ProductSpecCard`。

## 26. 最新验证结果（补充）。
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` -> passed
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 53 passed
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 27. 渲染链继续去 legacy 主源化。
- 时间：2026-03-20
- 目标：继续让前端渲染链明确以 `NoteDocument.blocks[*].props/style` 为主，legacy `pageData/styleData` 只在新协议缺席时回退。
- 关键改动：
  - [`PolaroidImage.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/blocks/PolaroidImage.vue)
    - 去掉了对 `pageData` 的直接依赖，当前只吃 `data` 或 `node.props`。
  - [`HandwrittenText.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/blocks/HandwrittenText.vue)
    - 同样去掉了对 `pageData` 的直接依赖，只保留 `data / node.props`。
  - [`XForgeRenderer.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/XForgeRenderer.vue)
    - `pageData/styleData` 改为可选 props。
    - `nodeData` 现在优先使用 `node.props`；只有当 `node.props` 为空时，才会回退到 legacy `pageData[node.id]`。
    - 这让 `NoteDocument` 继续坐稳主渲染协议，legacy payload 退为兼容兜底，而不是默认参与合并。
- 结果：
  - 渲染壳与遗留 block 又少了一批对旧协议的直接读取，前端“新协议优先、旧协议兜底”的边界进一步清晰。

## 28. 最新验证结果（补充）。
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 29. planner policy 继续前移到更早的组件类型推断。
- 时间：2026-03-20
- 目标：不只在 `_score_block_for_query(...)` 阶段消费 `planner_policy`，而是让编辑器更早在“推断目标组件类型”时就参考 planner 的 block intent 偏好。
- 关键改动：
  - [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
    - 新增 `_infer_component_type_from_planner_policy(user_query, planner_policy)`。
    - `_infer_target_component_type(...)` 现在支持可选 `planner_policy`，会在显式组件 alias 未命中时，依据 `layout_policy.preferred_block_intents` 和抽象语义词（如 `证据/互动/正文/封面`）先推断一个目标组件类型。
    - `_resolve_global_target_id(...)` 现在把 `planner_policy` 继续向内透传到 `_infer_target_component_type(...)`，让组件类型推断和块目标打分共享同一份 planner 偏好。
  - 效果：
    - 当 planner 偏好 `evidence_summary` 且用户说“把证据那块收敛一点”时，编辑器会更早推断目标组件应落在 `RadarChartBlock/ProductSpecCard` 这类证据块，而不只是依赖最后的上下文打分。
- 对应回归：
  - [`tests/test_note_editor_v2.py`](/root/XHS-Forge/tests/test_note_editor_v2.py)
    - 新增 `test_infer_target_component_type_can_use_planner_policy_hints`，验证 seeding 场景下 planner policy 偏好 `evidence_summary` 时，抽象表达 `把证据那块收敛一点` 会推断到 `RadarChartBlock`。

## 30. 最新验证结果（补充）。
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` -> passed
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 54 passed
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 31. note_editor 的全局编辑识别开始优先消费传入的 NoteDocument 元数据。
- 时间：2026-03-20
- 目标：继续减少 `note_editor` 在目标识别时对 legacy 页面状态反推 `NoteDocument` 的依赖，让它在 state 已带 `note_document` 时优先直接使用这份新协议元数据。
- 关键改动：
  - [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
    - 旧的 legacy block meta map helper 被统一升级为同时支持 `note_document` 和 legacy 页面状态。
    - `_has_global_edit_request(...)` 和 `_resolve_global_target_id(...)` 新增可选参数 `note_document`，在传入 `NoteDocument` 且其 `blocks` 已存在时，会优先直接使用块级元数据，而不是重新从旧页面状态推导。
    - `_apply_global_edit_plan(...)` 也开始接收 `note_document`，整页编辑主链会把 `build_note_document_from_state(state)` 的结果一路透传给目标识别逻辑。
  - 效果：
    - 现在当 state 里已经有 richer `NoteDocument` 元数据时，整页编辑判断和目标命中会优先相信这份文档协议，而不是继续依赖 legacy block 信息。
- 对应回归：
  - [`tests/test_note_editor_v2.py`](/root/XHS-Forge/tests/test_note_editor_v2.py)
    - 新增 `test_resolve_global_target_id_prefers_passed_note_document_metadata`，验证当传入的 `note_document` 明确把某个 `StoryText` 标记成 `interactive_opinion` 时，`把互动那块改得更毒舌一点` 会优先命中这份文档元数据，而不是单纯依赖 legacy 组件类型。

## 32. 最新验证结果（补充）。
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` -> passed
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 55 passed
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 33. DynamicRenderer 的协议组装继续下沉回 store。
- 时间：2026-03-20
- 目标：继续减少渲染组件自己拼 `NoteDocument -> legacy render page/style` 的逻辑，让“新协议优先、旧协议兜底”的渲染兼容层集中在 store。
- 关键改动：
  - [`useChatStore.ts`](/root/XHS-Forge/ai-frontend-ide/src/stores/useChatStore.ts)
    - 新增：
      - `buildRenderablePageDataFromDocument(doc)`
      - `getPreferredRenderPageData(doc, page)`
      - `getPreferredRenderStyleData(doc, style)`
    - 这些 helper 统一负责：
      - 把 `NoteDocument.blocks[*]` 映射成前端渲染所需的 block 节点结构
      - 在文档可用时优先输出新协议渲染数据
      - 否则才回退 legacy `pageData/styleData`
  - [`DynamicRenderer.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/renderers/DynamicRenderer.vue)
    - 不再自己手写 `renderPageData/renderStyleData` 的 `NoteDocument -> legacy` 映射逻辑，统一改用 store helper。
- 结果：
  - 渲染入口层继续变轻，前端“协议转换逻辑”开始更多集中在 store，而不是散落在多个 renderer 组件里。

## 34. 最新验证结果（补充）。
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 35. note_editor 的更早期组件类型推断开始直接消费 NoteDocument 语义提示。
- 时间：2026-03-20
- 目标：不只在 `_resolve_global_target_id(...)` 的块打分阶段消费 `NoteDocument` 元数据，而是让 `_infer_target_component_type(...)` 这层更早的组件类型推断也能直接参考文档中的 `semantic_role`。
- 关键改动：
  - [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
    - 抽出统一的 `ROLE_TOKEN_MAP`，把 `互动/正文/标题/封面/证据/对比/地点/氛围` 这类语义词映射集中到一处。
    - 新增 `_infer_component_type_from_note_document(user_query, note_document)`。
    - `_infer_target_component_type(...)` 新增可选参数 `note_document`，现在在显式组件 alias 和 planner policy 都未命中时，会直接扫描 `NoteDocument.blocks[*].semantic_role` 来推断目标组件类型。
    - `_resolve_global_target_id(...)` 已把 `note_document` 往 `_infer_target_component_type(...)` 透传，组件类型推断和后续块命中共享同一份文档语义提示。
  - 效果：
    - 现在像“把互动那块改得更毒舌一点”这种表达，不只在最终块打分阶段依赖 `NoteDocument`，在更早的“目标组件类型推断”阶段也已经开始消费文档语义。
- 对应回归：
  - [`tests/test_note_editor_v2.py`](/root/XHS-Forge/tests/test_note_editor_v2.py)
    - 新增 `test_infer_target_component_type_can_use_note_document_semantic_hints`，验证当 `note_document` 里某个 `StoryText` 被标成 `interactive_opinion` 时，抽象表达会在组件类型推断阶段就拿到 `StoryText`。

## 36. 最新验证结果（补充）。
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` -> passed
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> 56 passed
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 37. Frontend Store-Derived State Reuse + Action-Aware Target Scoring (2026-03-20)
- `PreviewIframe.vue` 现在直接通过 store 的 `documentAssets/currentCoverUrl` 读取素材与封面，不再在组件内重复做 `noteDocument -> legacy` 资产/封面兼容计算。
- `AgentInspector.vue` 改成通过 `storeToRefs` 直接消费 `scenarioTags/patchTracks/plannerOutput/plannerPolicy/noteDocument`，把策略与补丁兼容逻辑继续收回 store。
- `note_editor_node.py` 新增 `EDITABLE_TARGET_TOKEN_MAP` 与 `ACTION_EDITABLE_TARGET_MAP`，并引入 `_score_block_action_match(...)`。
- `_score_block_for_query(...)` 现在支持 `action`，`_resolve_global_target_id(...)` 在全局编辑命中阶段会把 `plan.action` 透传进去，让 `editable_targets` 真正参与动作级匹配，而不是只做静态说明。
- 同时修掉了旧 `_score_block_capability_match(...)` 里 `context` 重复 key 覆盖的问题，统一复用 `ROLE_TOKEN_MAP/EDITABLE_TARGET_TOKEN_MAP`。
- 新增回归 `test_score_block_for_query_uses_action_aware_editable_targets`，验证当 query 词面很弱时，`rewrite_paragraph` 仍会优先命中具备 `paragraphs` 编辑能力的块。

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `57 passed`
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 38. Store-Level Selected State + Edit-Intent Helper Consolidation (2026-03-20)
- `useChatStore.ts` 新增 store 派生状态：
  - `selectedBlock`
  - `selectedPayload`
  - `hasRenderableDocument`
- `ChatPanel.vue` 不再自己拼 `noteDocument/pageData` 去找选中块和 payload，改为直接消费 store 的 `selectedBlock/selectedPayload`。
- `PreviewIframe.vue` 改为直接消费 store 的 `hasRenderableDocument`，继续减少组件内本地兼容逻辑。
- `note_editor_node.py` 新增 `_has_edit_intent_language(...)`，把全局编辑入口对“编辑意图语言”的判断收成统一 helper；`GLOBAL_EDIT_INTENT_TOKENS` 与 `EDIT_STYLE_HINT_TOKENS` 也正式分层。
- 这样 `_has_global_edit_request(...)` 不再内联维护多套散乱词表，后面继续削 heuristics 时会更容易往统一策略层收。

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `57 passed`
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 39. `create_agent` Runtime Unblocked + Enrichment Node Migration (2026-03-20)
- 当前 Conda 环境原先缺失顶层 `langchain` 包，导致 `app/core/agent_runtime.py` 里的 `create_agent` 分支虽然有兼容代码，但实际永远回退到 `create_react_agent`。
- 本轮已在 `LangChainProject` 环境中补齐：
  - `langchain==1.2.12`
  - `langgraph==1.1.3`
- 同步将 [`AI_Frontend_IDE/requirements.txt`](/root/XHS-Forge/AI_Frontend_IDE/requirements.txt) 中的 `langgraph` 版本对齐为 `1.1.3`，避免后续复现环境再次出现版本漂移。
- [`enrichment_agent.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/enrichment_agent.py) 已从“全量动态 prompt”收成“静态 system prompt + 动态 user context”结构：
  - `create_controlled_agent(..., prompt=system_prompt)` 现在满足 `create_agent` 使用条件。
  - 当前环境下，这个节点已具备真正走 `langchain_create_agent` 后端的条件。
- [`tests/test_enrichment_agent.py`](/root/XHS-Forge/tests/test_enrichment_agent.py) 也按当前架构修正为 patch `create_controlled_agent`，不再依赖早已不存在的全局 `enrichment_react_agent` 变量。

### Validation
- `python - <<'PY' ... from langchain.agents import create_agent ... PY` -> ok
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/enrichment_agent.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_agent_runtime.py tests/test_enrichment_agent.py tests/campaign_3_enrichment_tests.py tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `63 passed`
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 40. Patch Node Migrated Toward `create_agent` Shape (2026-03-20)
- [`patch_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/patch_node.py) 已从“动态整段 prompt”重构为“静态 system prompt + 动态 user context”：
  - system prompt 只描述微创 patch 流程与约束。
  - user message 只携带 `selected_element_id + user_instruction`。
- 这样 `patch_doctor = create_controlled_agent(..., prompt=system_prompt)` 现在满足 `create_agent` 的静态 prompt 入口条件。
- 这意味着当前环境下，除强 stateful 的 `note_editor` 外，`patch_node` 与 `enrichment_agent` 都已经具备实际走 `langchain_create_agent` 后端的条件。
- 新增测试 [`tests/test_patch_node.py`](/root/XHS-Forge/tests/test_patch_node.py)，验证：
  - `patch_node` 使用静态 system prompt 构建 agent。
  - 动态用户上下文仍正确进入 user message。
  - 返回结果仍正常回写到旧页面 patch 状态。

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/patch_node.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_patch_node.py tests/test_agent_runtime.py tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `60 passed`
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed

## 41. Preview/Inspector Further De-Legacy + Enrichment Migration Regression (2026-03-20)
- [`PreviewIframe.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/canvas/PreviewIframe.vue) 现在直接消费 store 的 `renderPageData`，hover payload fallback 不再显式依赖 `pageData`。
- [`AgentInspector.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/AgentInspector.vue) 的 DSL compat 面板改为展示 `renderPageData/renderStyleData`，不再直接读取 `pageData/styleData`。
- 这意味着前端两个高频调试/预览入口已经进一步统一到 store 派生出来的“新协议优先兼容态”，减少显式 legacy 读取。
- [`tests/test_enrichment_agent.py`](/root/XHS-Forge/tests/test_enrichment_agent.py) 继续补强：
  - 现在不仅验证 user prompt 含动态上下文，还验证 `create_controlled_agent` 收到的是静态 system prompt，确保 `enrichment_agent` 的 `create_agent` 迁移形态可回归。

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/enrichment_agent.py AI_Frontend_IDE/app/agents/nodes/patch_node.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_enrichment_agent.py tests/test_patch_node.py tests/test_agent_runtime.py tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `62 passed`
- `cd /root/XHS-Forge/ai-frontend-ide && npm run build` -> passed


## 42. Structured Canvas Creation Path for `note_editor`

This round removed another major dependency on the open-ended `create_react_agent` fallback inside [`note_editor_node.py`](../AI_Frontend_IDE/app/agents/nodes/note_editor_node.py).

### What changed
- Added `CanvasCreationOutput` and `CanvasCreationBlockOutput` as structured creation-plan schemas.
- Added `_build_canvas_creation_prompt(...)` so empty-canvas requests now go through a structured creation pass first.
- Added `_build_canvas_creation_fallback(...)` and `_apply_canvas_creation_plan(...)` so even if the structured call fails, `note_editor` can deterministically materialize a first-pass canvas from `planner_output.block_intents` plus manifest/component fallbacks.
- Empty-canvas creation now happens before local/global edit routing, so brand-new note generation no longer needs to fall into the open-ended stateful agent loop by default.
- The creation path reuses `component_manifest` + `build_component_fallback(...)` + `enforce_component_contract(...)`, which keeps it aligned with the verifier/component system instead of inventing a separate protocol.

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py tests/test_note_editor_v2.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `60 passed`
- `cd ai-frontend-ide && npm run build` -> passed

### New tests
- `test_build_canvas_creation_fallback_guarantees_title_and_story_blocks`
- `test_apply_canvas_creation_plan_materializes_structured_blocks`
- `test_note_editor_node_uses_structured_canvas_creation_path`

### Why it matters
This is the first step toward migrating `note_editor` itself off the remaining stateful `create_react_agent` fallback. The empty-canvas branch is now structured and deterministic enough that the remaining open-ended agent loop is increasingly just a true fallback path for edge cases, not the default creation mechanism.


## 43. Structured Global `append_block` Path for `note_editor`

This round expanded the structured global-edit protocol so `note_editor` can add a new block without falling back to the open-ended agent loop.

### What changed
- Extended `GlobalCanvasEditOutput.action` with `append_block`.
- Added `_append_structured_block_from_plan(...)` so global edit plans can deterministically materialize a new block using:
  - inferred/new component type
  - `component_manifest`
  - `build_component_fallback(...)`
  - `enforce_component_contract(...)`
- Updated the global edit prompt so “新增/增加/添加/补一个” style requests are first-class structured actions.
- Expanded `GLOBAL_EDIT_INTENT_TOKENS` so additive edit requests are more likely to stay on the structured global-edit path.
- Added regression coverage for appending a `PollBlock` through `_apply_global_edit_plan(...)`.

### Validation
- `python -m py_compile AI_Frontend_IDE/app/agents/nodes/note_editor_node.py tests/test_note_editor_v2.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `61 passed`
- `cd ai-frontend-ide && npm run build` -> passed

### Why it matters
Now two high-frequency `note_editor` paths are structured and deterministic by default:
- empty-canvas first-pass creation
- existing-canvas block append

This further shrinks the surface area where the stateful `create_react_agent` fallback is needed.


## 44. Node-Level Structured Global Append Coverage

This round added node-level regression coverage to ensure global additive edits stay on the structured path instead of silently dropping back to the open-ended `note_editor` fallback.

### What changed
- Added `test_note_editor_node_uses_structured_global_append_path` in [`tests/test_note_editor_v2.py`](../tests/test_note_editor_v2.py).
- The test explicitly patches `create_controlled_agent(...)` to raise if called, then verifies that a request like `再加一个投票区块` is handled by the structured `GlobalCanvasEditOutput(action="append_block")` path.
- This gives us coverage that the structured append logic is not only available at helper level, but actually used by `note_editor_node(...)` before the fallback agent loop.

### Validation
- `python -m py_compile tests/test_note_editor_v2.py`
- `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `62 passed`
- `cd ai-frontend-ide && npm run build` -> passed

### Why it matters
The structured global-edit matrix now has explicit node-level coverage for:
- rewrite paragraph
- replace block
- remove block
- update page theme
- append block

That makes the remaining stateful `create_react_agent` fallback much closer to a true edge-case safety net instead of a default path.


## 45. Agent Runtime Transparency End-to-End
- Added `agent_backends` to `UIProjectState` in `/root/XHS-Forge/AI_Frontend_IDE/app/agents/state.py`.
- Extended `/chat` turn-end payloads in `/root/XHS-Forge/AI_Frontend_IDE/app/api/chat.py` to include:
  - `note_document`
  - `planner_output`
  - `planner_policy`
  - `agent_backends`
  in both snake_case and camelCase forms.
- Extended workspace/inspect responses in `/root/XHS-Forge/AI_Frontend_IDE/app/api/workspace.py` and `/root/XHS-Forge/AI_Frontend_IDE/app/schemas/responses.py` with `agent_backends`.
- Instrumented node outputs so current runtimes are visible:
  - `/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/enrichment_agent.py` -> `{"enrichment_agent": enrichment_react_agent.backend}`
  - `/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/patch_node.py` -> `{"patch_doctor": patch_doctor.backend}` or `skipped_no_selection`
  - `/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` -> `{"note_editor": "structured_function_calling"}` for structured branches, `editor.backend` for fallback branch
- Frontend now stores and displays runtime backend info:
  - `/root/XHS-Forge/ai-frontend-ide/src/types/chat.ts`
  - `/root/XHS-Forge/ai-frontend-ide/src/stores/useChatStore.ts`
  - `/root/XHS-Forge/ai-frontend-ide/src/components/chat/AgentInspector.vue`
- Result: Inspector can now show whether a node currently ran via `langchain_create_agent`, `langgraph_create_react_agent`, or a deterministic `structured_function_calling` path.
- Validation:
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_workspace_api.py tests/test_agent_runtime.py tests/test_patch_node.py tests/test_enrichment_agent.py tests/campaign_3_enrichment_tests.py tests/test_note_editor_v2.py tests/test_architecture_v2.py`
  - `77 passed`
  - `cd /root/XHS-Forge/ai-frontend-ide && npm run build`


## 46. Structured Local `append_block` Path for `note_editor`
- Extended `/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py` so local structured edit plans can now use `action="append_block"`.
- `LocalNoteEditOutput.action` now supports:
  - `update_block`
  - `replace_block`
  - `move_block`
  - `remove_block`
  - `append_block`
  - `noop`
- Added `_append_local_block_from_plan(...)` to deterministically insert a new block immediately after the currently selected block.
- `_apply_local_edit_plan(...)` now accepts `user_query / retrieved_knowledge / image_assets` so local append can reuse:
  - `component_manifest`
  - `build_component_fallback(...)`
  - `enforce_component_contract(...)`
- Updated local edit prompt to explicitly allow `append_block` only when the user clearly asks to add a block before/after the selected one.
- Upgraded `_restrict_local_edit_scope(...)` so local scope protection still blocks unintended edits to other existing blocks, but preserves newly appended local blocks when `action="append_block"`.
- Added regression coverage in `/root/XHS-Forge/tests/test_note_editor_v2.py`:
  - `test_apply_local_edit_plan_appends_structured_block_after_selected`
  - `test_note_editor_node_uses_structured_local_append_path`
- Validation:
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py`
  - `64 passed`
  - `cd /root/XHS-Forge/ai-frontend-ide && npm run build`

## 47. Relative Insert Position for Structured Append Actions
- Added `_infer_append_insert_index(user_query, target_index, block_count)` in `/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py`.
- Structured append actions now support relative placement based on natural language:
  - `前面 / 前边 / 上面 / 之前 / 前插` -> insert before target
  - default -> insert after target
- Local structured append now respects relative placement against the currently selected block.
- Global structured append now respects `block_id` / `block_index` as an insertion anchor, instead of always appending to the end.
- Updated global edit prompt so `append_block` can carry `block_id` or `block_index` when the user specifies “在某块前面/后面新增”.
- Added regression coverage in `/root/XHS-Forge/tests/test_note_editor_v2.py`:
  - `test_apply_local_edit_plan_appends_structured_block_before_selected_when_requested`
  - `test_apply_global_edit_plan_appends_structured_block_after_anchor`
- Validation:
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py`
  - `66 passed`
  - `cd /root/XHS-Forge/ai-frontend-ide && npm run build`


## 48. Note Editor Formal Path No Longer Uses Open-Ended Agent Fallback
- `note_editor_node.py` 已移除正式执行路径上的 `create_controlled_agent(...)` fallback。
- 非空画布现在统一走结构化 `GlobalCanvasEditOutput`，即使用户请求更模糊，也不会再掉进 `create_react_agent`。
- 这意味着 `note_editor` 的正式 runtime 现在固定上报 `structured_function_calling`，`langgraph_create_react_agent` 不再出现在主脑链路里。
- 新增回归：
  - `test_note_editor_node_uses_structured_global_path_for_generic_edit_copy`
  - 用更泛化的“整体再打磨一下”请求验证不会回到开放式 fallback。

## 49. Frontend Legacy Props No Longer Flow Into Block Components
- `/root/XHS-Forge/ai-frontend-ide/src/components/renderers/XForgeRenderer.vue` 不再把 legacy `pageData/styleData` 继续传给具体 block 组件。
- `/root/XHS-Forge/ai-frontend-ide/src/components/renderers/blocks/CollageContainer.vue` 也不再把 `pageData/styleData` 透传给嵌套 `XForgeRenderer`。
- 现在 legacy 协议只保留在最外层 renderer 兜底，block 组件本身更明确地围绕 `node.props/node.style` 工作。
- 结果：前端的 `NoteDocument` 主协议更干净，legacy fallback 的作用域进一步收缩到 renderer/store 边界。

## 50. NoteDocument Schema Now Matches Richer Block Metadata
- `app/core/schema.py` 的 `NoteDocumentBlock` 已补齐当前文档真实携带的字段：`label`、`semantic_role`、`editable_targets`、`asset_support`、`fact_binding_support`。
- 这次不是只改字典生成逻辑，而是把主协议的 Pydantic 契约追平到了当前 `build_note_document(...)` 实际产物，减少后续继续清理 legacy 协议时的“代码里有、schema 里没有”分叉。
- 新增回归 `tests/test_architecture_v2.py::test_note_document_schema_accepts_richer_block_metadata`，直接用 `NoteDocument(**note_document)` 验证 richer block metadata 已被正式承认。
- 验证：`PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_architecture_v2.py tests/test_note_editor_v2.py` 与前端 `npm run build` 均通过。

## 51. Intent / Planner Runtime Types Are Now Explicit
- `intent_node.py` 现在会显式上报 `agent_backends.intent_agent`：
  - `structured_function_calling`
  - `skipped_no_messages`
  - `fallback_route`
- `planner_node.py` 现在会显式上报 `agent_backends.planner = deterministic_policy_builder`。
- 这一步的作用不是“把它们 agent 化”，而是反过来把运行时类型说清楚：`intent` 目前是一次性结构化 LLM，`planner` 目前是确定性策略节点。后续做 `create_agent` 统一时，只应迁移真正的 agent 入口，不应误迁这些本来就不该 agent 化的节点。
- 回归已补到 `tests/test_architecture_v2.py`，验证 `planner` backend 和 `intent` 无消息时的 backend 标记。

## 52. Research Runtime Is Now Explicitly Classified As Deterministic
- `research_agent.py` 现在会显式上报 `agent_backends.research_agent = deterministic_tool_orchestrator`。
- 这和 `intent/planner` 一样，作用不是把 research agent 化，而是反向确认：当前 research 主链本质上是受控工具编排，不是待统一到 `create_agent` 的开放式 agent。
- `tests/test_rag_pipeline.py` 已补断言，确保 research 节点回传 runtime 分类。

## 53. Frontend Renderer Layer No Longer Reads Legacy pageData/styleData
- `useChatStore.ts` 新增 `buildRenderablePageDataFromLegacy(...)`，把旧 `pageData/styleData` 统一在 store 内补形成 `node.props/node.style` 结构。
- `getPreferredRenderPageData(...)` 现在无论来自 `NoteDocument` 还是 legacy 页面，都会产出同一种 render node 结构。
- `DynamicRenderer.vue` 不再向 `XForgeRenderer` 传 `pageData/styleData`；`XForgeRenderer.vue` 也已删除对 `pageData/styleData` 的显式依赖，只消费 `node.props/node.style`。
- 结果：前端 renderer 目录里的 block/renderer 组件已经不再直接读取 legacy `pageData/styleData`，legacy 协议被进一步压回 store 兼容层。
- 验证：`grep -RIn "pageData|styleData" ai-frontend-ide/src/components/renderers` 已无结果，前端 `npm run build` 通过。

## 54. Formal Runtime No Longer Contains create_react_agent
- `app/core/agent_runtime.py` 已移除对 `langgraph.prebuilt.create_react_agent` 的正式回退，`create_controlled_agent(...)` 现在只支持静态 string system prompt + 无 `state_schema` 的 `create_agent` 路线。
- 这意味着正式产品路径里，agent 入口已经统一成：
  - `langchain_create_agent`
  - `structured_function_calling`
  - 确定性后端（如 `deterministic_policy_builder` / `deterministic_tool_orchestrator`）
- `tests/test_agent_runtime.py` 已改成验证：
  - legacy stateful prompt 会被明确拒绝
  - 缺少 `create_agent` 环境会报错
  - 静态 prompt 正常走 `langchain_create_agent`
- 同时 `enrichment_agent.py` 现在也会显式返回 `agent_backends.enrichment_agent`，便于 Inspector 观察。
- 验证：`grep -RIn "create_react_agent|langgraph_create_react_agent" AI_Frontend_IDE/app tests` 已无结果；相关后端回归 `85 passed`，前端 build 通过。

## 55. Store Legacy Compatibility Is Now Centralized In One Helper
- `ai-frontend-ide/src/stores/useChatStore.ts` 新增 `resolveLegacyWorkspaceState(...)` 与 `syncLegacyStateFromDocument(...)`。
- `applyWorkspaceSnapshot(...)`、`turn_end` 收尾、`rollbackTo(...)` 不再各自手写 `resolveLegacyPageData/resolveLegacyStyleData` + `pageData/styleData` 赋值，而是统一走 store 兼容 helper。
- 这一步的意义不是新增功能，而是继续把 legacy `pageData/styleData` 收缩进 store 内部的单一兼容层，方便后续继续清理旧协议。
- 验证：前端 `npm run build` 通过。

## 56. Canonical Asset Sending Now Merges Document Assets And Staged Assets
- `ai-frontend-ide/src/stores/useChatStore.ts` 的 `documentAssets` 现在不再是“有 `NoteDocument.assets` 就忽略 `imageAssets`”，而是合并两者并去重。
- `sendMessage(...)` 也改成发送 `documentAssets.value`，这样当前文档资产和本轮暂存上传素材会一起进入后端，不会因为文档里已有资产而把新上传图丢掉。
- 这一步继续加强了“`NoteDocument` 为主协议，但允许 store 兼容层补齐临时素材”的路线。
- 验证：前端 `npm run build` 通过。

## 57. Global Structured Append Now Resolves Semantic Anchors
- `note_editor_node.py` 新增 `_resolve_global_append_anchor_id(...)`，当 `append_block` 没有明确 `block_id/block_index` 时，会把请求降格成“定位要插在哪个旧块附近”的目标识别，再复用 `NoteDocument + manifest + planner_policy` 去解析抽象锚点。
- 这意味着像“在互动那块后面加一个参数卡”这类请求，即使 structured plan 只给了 `new_component_type`，也能稳定把新区块插到 `interactive_opinion` 对应区块后面，而不是默认加到末尾。
- `_append_structured_block_from_plan(...)` 现在已经接收 `planner_policy` 和 `note_document`，新增动作开始更早依赖新协议，而不是只靠显式组件名。
- 新增回归 `tests/test_note_editor_v2.py::test_apply_global_edit_plan_appends_structured_block_after_semantic_anchor`。
- 验证：`PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `70 passed`；前端 `npm run build` 通过。

## 58. Semantic Anchor Append Is Now Covered At Node Level
- 在上一轮纯函数级语义锚点新增基础上，已补节点级回归 `tests/test_note_editor_v2.py::test_note_editor_node_uses_structured_global_append_path_with_semantic_anchor`。
- 该测试直接验证 `note_editor_node(...)` 在收到“在互动那块后面补一个参数卡”时，会沿正式结构化整页编辑主链产出 `TitleBlock -> PollBlock -> ProductSpecCard -> StoryText` 顺序，而不是退回末尾追加或开放式 fallback。
- 这意味着“抽象锚点新增”已经不是 helper 级能力，而是正式主脑能力。
- 验证：`PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `71 passed`；前端 `npm run build` 通过。

## 59. Structured Move Now Resolves Semantic Anchors
- `note_editor_node.py` 新增 `_extract_move_subject_query(...)` 与 `_resolve_global_move_target_index(...)`，把“谁要被移动”和“移到哪个锚点附近”拆开解析。
- 现在像“把互动那块放到标题后面”这种请求，不需要模型显式提供 `move_to_index`，也能依赖 `NoteDocument + planner_policy` 解析：
  - 目标块 = `interactive_opinion`
  - 位置锚点 = `heading`
  - 相对关系 = `后面`
- 这让 `move_block` 和 `append_block` 一样，开始具备真正的相对位置语义，而不是继续依赖模型硬算索引。
- 新增回归：
  - `test_apply_global_edit_plan_moves_block_after_semantic_anchor`
  - `test_note_editor_node_uses_structured_global_move_path_with_semantic_anchor`
- 验证：`PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `73 passed`；前端 `npm run build` 通过。


## 60. Local Structured Move Now Preserves Semantic Reordering
- `note_editor_node.py` 的 `_restrict_local_edit_scope(...)` 现在在 `action == "move_block"` 时会保留 `updated_blocks` 的新顺序，但仍锁住其他旧区块的数据和样式不被误改。
- 这修掉了局部结构化移动里“目标块内容更新成功，但 block 顺序被作用域保护回退”的问题。
- 现在像“把这个放到标题后面”这类局部编辑请求，正式节点主链会稳定产出新的顺序，而不会再被局部保护逻辑吃掉。
- 新增回归：
  - `test_apply_local_edit_plan_moves_selected_block_after_semantic_anchor`
  - `test_note_editor_node_uses_structured_local_move_path_with_semantic_anchor`
- 验证：`PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py` -> `75 passed`；前端 `npm run build` 通过。


## 61. Fact Bindings Now Carry Explicit Fact Field Keys
- `component_builder.py` 现在会在可信元数据里尽量补出事实字段：
  - `ProductSpecCard.feature_meta[*].field`
  - `StoryText.paragraph_meta[*].fields`
- `note_document.py` 会把这些信息继续折叠进 `blocks[*].fact_bindings[*].fact_fields`，让绑定关系从“有来源”进一步提升到“知道绑定的是哪个事实字段”。
- 这样参数卡和正文的来源 hover/Inspector 不再只是泛泛显示来源，而是开始具备字段级可追溯能力。
- 对应回归已补到：
  - `tests/test_generation_smoke.py`
  - `tests/test_architecture_v2.py`
- 验证：
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_generation_smoke.py tests/test_architecture_v2.py` -> `20 passed`
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_note_editor_v2.py tests/test_architecture_v2.py tests/test_generation_smoke.py tests/test_workspace_api.py tests/test_workspace_assets_api.py` -> `100 passed`
  - 前端 `npm run build` 通过。


## 62. Field-Level Fact Bindings Are Now Visible In The UI
- `ProductSpecCard.vue` 的 hover 现在会直接显示“绑定字段”，不再只显示来源；如果参数卡条目绑定到 `battery_capacity / price` 这类事实字段，用户可以在卡片级看到这层解释。
- `StoryText.vue` 的段落 hover 也会显示“绑定字段”，所以正文里基于已确认事实或保守表达写出的段落，开始具备字段级可解释性。
- `AgentInspector.vue` 的策略规划面板新增了 `NoteDocument.fact_bindings` 的字段级展示，会列出每个 block 的绑定项、事实字段和来源。
- 这让“字段级可信”不再只停留在后端元数据，而是真正进入用户可见界面。
- 验证：前端 `npm run build` 通过，`tests/test_generation_smoke.py + tests/test_architecture_v2.py` 通过。

## 63. Final Showcase Build Is Complete
- 本轮已完成最终展示版收官：`note_editor` 结构化主脑、`NoteDocument` 主协议、`create_agent` 统一入口、字段级可信链和前端解释层都已站稳。
- 前端组件层已不再直接读取 legacy `pageData/styleData`，兼容逻辑集中在 store 内部。
- 真实全量回归已通过：`124 passed in 32.04s`，无 warning。
- 前端生产构建已通过。
- 从当前状态开始，项目已不再有“核心主链未完成”项，只剩可选增强项。

## 64. Final Guardrails Added
- Added [`test_final_product_guards.py`](/root/XHS-Forge/tests/test_final_product_guards.py) to prevent regression in two areas:
  - formal runtime reintroducing `create_react_agent` / `langgraph_create_react_agent`
  - frontend component layer directly depending on legacy `pageData/styleData` again
- Validation:
  - `PYTHONPATH=/root/XHS-Forge/AI_Frontend_IDE pytest -q tests/test_final_product_guards.py`
  - `cd /root/XHS-Forge/ai-frontend-ide && npm run build`

## 65. Final Acceptance Script Added
- Added [`final_acceptance.sh`](/root/XHS-Forge/scripts/final_acceptance.sh) as the single-command acceptance path for the finished showcase build.
- The script runs:
  - full backend `pytest`
  - `tests/test_final_product_guards.py`
  - a grep-based runtime sanity check to ensure no formal `create_react_agent` path remains
  - frontend `npm run build`
- This makes the final handoff state reproducible instead of relying on scattered command history.

- Validation:
  - `bash /root/XHS-Forge/scripts/final_acceptance.sh` -> passed

## 66. Final Acceptance CI Added
- Added [`final-acceptance.yml`](/root/XHS-Forge/.github/workflows/final-acceptance.yml) to run the same final acceptance path automatically on `push` and `pull_request`.
- The workflow:
  - sets up Python 3.12 and Node 20
  - installs backend/frontend dependencies
  - runs `bash scripts/final_acceptance.sh`
- This turns the final showcase state into a continuously enforced repository contract, not just a one-time local result.

- 现代 agent 主链继续收口：正式 graph 已改为 `planner -> outline_resolver -> component_builder`，`route_intent(...)` 也已开始优先消费 `intent_result_v2`。
- `outline_node.py` 现仅保留兼容壳，不再承载历史工具循环实现；防回退 guard 已覆盖 graph 与节点模块两层。
- `component_builder` 已升级为 contract-first：builder prompt 会明确收到 manifest contract snapshot 与 planner policy 摘要，最终输出统一走 `apply_component_contract_layer(...)`。

- 样式与主题链继续现代化：`style_node` 已切到 `planner_policy.theme_policy` 优先，`visual_vibe/intensity_level` 仅作兼容回退；对应回归已补到 `tests/test_generation_smoke.py`。
- `note_editor` 的整页主题 fallback 已优先消费 `planner_policy.theme_policy.preset`，测试覆盖在 `tests/test_note_editor_v2.py`。
- `intent_agent` 的控制台输出与 `node_prompts` 已从历史 6D Signal 改为 `Gateway V2` 摘要，正式主链继续向“瘦 intent、强 planner”收束。

- 旧六维主题钩子继续退出主链：`style_node` 已完全改成 `planner_policy.theme_policy` 驱动；`visual_vibe/intensity_level` 不再参与正式主题信号。
- `note_editor` 的页面主题 fallback 现在只吃 `planner_policy.theme_policy` 和用户 query，不再依赖 `intent_result.visual_vibe`。
- `research_agent` 已切到 `intent_result_v2.needs_assets` 优先，正式 gateway->research 关系更符合现代 agent 网关协议。

- `theme_compiler` 现已显式写入 `turn_trace.theme_compiler` 与 `agent_backends.theme_compiler=deterministic_compiler`，现代主链的主题执行层已可观察。
- `tests/test_final_product_guards.py` 新增了现代 runtime 护栏，防关键节点重新依赖 legacy 主题/资产信号。

- `intent_agent` 新增局部编辑 fast-path，选中区块后的非主面板修改请求会直接返回 `intent_result_v2`，backend 标记为 `deterministic_fast_path`。
- 对应回归已补到 `tests/test_architecture_v2.py`，确保局部编辑网关不再无谓触发 LLM。

- `research_agent.py` 里最后一个 legacy 资产信号词根已经收进 helper，不再在正式节点源码里直接出现，`test_final_product_guards.py` 重新通过。
- `workspace._build_inspector_summary(...)` 现已汇总 `component_builder` 的 contract-first trace，会输出：
  - `builder.component_count`
  - `builder.fallback_count`
  - `builder.contract_first`
  - `builder.component_types`
- 前端 [`AgentInspector.vue`](/root/XHS-Forge/ai-frontend-ide/src/components/chat/AgentInspector.vue) 总览新增了“积木构建”卡片，`本轮追踪` 里也能直接看到 builder 摘要；当 builder 发生 fallback，Inspector 建议会主动提示优先检查组件 contract、事实摘要和局部业务简报。

- `intent_agent` 的 deterministic fast-path 又向前推进了一层：`content / style / structure` 三个编辑子面板的全局请求现在也会直接返回 Gateway V2，不再为明确编辑上下文额外调用意图 LLM。
- 对应回归已补到 [`tests/test_architecture_v2.py`](/root/XHS-Forge/tests/test_architecture_v2.py)，确保这类子面板快路仍会被正式 graph 稳定路由到 `note_editor`。

- `intent_agent` 现在还会在 `main` 面板的“已有画布显式编辑请求”上命中 deterministic fast-path：像“文本简短一点”“整体改成灰蓝风格”这类请求，不再先走意图 LLM。
- 这条快路会基于 query 做轻量语义分流（`content_node / style_node / structure_node`），但正式 graph 仍会稳定把它们收束到 `note_editor`；对应回归也已补进 [`tests/test_architecture_v2.py`](/root/XHS-Forge/tests/test_architecture_v2.py)。

- `intent_agent` 的 LLM 慢路已切到新的 [`IntentGatewayOutput`](/root/XHS-Forge/AI_Frontend_IDE/app/core/schema.py) 瘦身协议，并改用 [`intent_gateway_v2.xml`](/root/XHS-Forge/AI_Frontend_IDE/app/prompts/intent_gateway_v2.xml)。
- 现在正式网关已经是“快路 V2、慢路也 V2”；旧六维 [`IntentOutput`](/root/XHS-Forge/AI_Frontend_IDE/app/core/schema.py) 只保留在兼容 helper 和历史测试上下文里，不再是正式意图 LLM 的主输出协议。

- `research_agent` 现已不再读取 legacy `intent_result` 作为正式资产信号来源；它只使用 `intent_result_v2.needs_assets`，或在缺失时根据 query 中的搜图/实拍等显式语义做轻量推断。
- 素材回填的 `image_assets[*].desc` 也已改成实体级标签（如 `Mate 60 实拍图`），不再把整句用户指令直接拼进素材描述。

- 历史示范脚本和 campaign 测试也在同步去旧范式：`campaign_1_intent_tests / campaign_6d_radar_test / campaign_ultimate_stress_test / ignition_test` 已切到 `IntentGatewayOutput / planner_policy / resolver` 口径，避免仓库继续用 `visual_vibe / narrative_mode / asset_request` 误导后续维护方向。
- 一部分 `style_agent / note_editor` 测试状态样例也已经优先改喂 `planner_policy.theme_policy`，减少测试层面对旧意图对象的主线依赖。

- 旧意图兼容链已正式删除：`IntentOutput`、`intent_result`、`intent_system.xml` 已从正式 runtime 退场；对应 refusal 节点、checkpointer 兼容和 chat thought 提取也已同步收干净。
- `tests/test_final_product_guards.py` 现已新增护栏，防止仓库重新引入旧意图 schema、旧 prompt 文件或 `intent_result` 兼容逻辑。

- 前端消息时间胶囊也继续去 legacy 页面协议：`ChatMessage` 已不再保存 `pageData/styleData` 副本，回滚恢复优先依赖 `noteDocument`；当前旧页面协议已进一步收缩成 store 内部派生缓存。
## 2026-03-21 增量交接

- `turn_end` 现在不再回 `pageData/styleData`，前端正式改为：
  - 用 `noteDocument` 作为主恢复来源
  - store 内部再派生 `legacyPageCache/legacyStyleCache`
- `WSEvent` 已移除 `pageData/styleData`
- `component_builder` trace 新增：
  - `contract_filter_count`
  - `dropped_payload_fields`
  - `precheck_warnings`
  - `precheck_warning_count`
- `workspace inspector_summary.builder` 新增：
  - `contract_filter_count`
  - `precheck_warning_count`
- `useChatStore.applyWorkspaceSnapshot(...)` 已停止读取 `pageData/styleData` 别名，只吃旧运行时页面载体
- 高频块增量：
  - `PollBlock`：增加互动信号摘要和当前分布卡，继续去伪真实感
  - `RadarChartBlock`：增加平均表现、综合判断和维度解读
  - `CoverSwiper`：增加当前帧说明和媒体摘要，强化 `hero_media` 角色
  - `VersusCard`：增加对比阅读说明和最佳使用语境，强化 `comparison` 角色
- `componentManifest.json` 已补：
  - `RadarChartBlock.quick_actions`
  - `VersusCard.quick_actions`
  - `LocationBlock.quick_actions`
- `component_manifest.py` 新增语义 helper：
  - `get_component_semantic_role`
  - `get_supported_scenarios`
  - `get_asset_support`
  - `supports_fact_binding`
  - `list_components_for_semantic_role`
- `resolve_component_for_block_intent(...)` 现在不再只是固定 intent->component 映射，会先按 manifest 语义字段做候选解析
- `outline_resolver` trace 新增 `resolution_source=manifest_semantic_role`
- `component_builder` 已进一步压缩 prompt：
  - `global_guide` 改成摘要而不是整段注入
  - `retrieved_knowledge` 改成 compact fact summary
  - `image_assets` 改成 compact asset summary
  - `planner_policy` 只注入精简摘要
- `component_builder` trace 继续增强：
  - `prompt_mode=compact_contract_first`
  - `fact_summary_count`
  - `asset_count`
- `workspace inspector_summary.builder` 现已同步展示：
  - `fact_summary_count`
  - `asset_count`
  - `prompt_modes`
- 这意味着 builder 现在已经更像“contract-first worker + 结构化摘要输入”，不再依赖大而全背景 prompt
- `useChatStore` 内部的 `legacyPageCache/legacyStyleCache` 也继续边缘化：
  - 有 `noteDocument` 时，legacy cache 现在优先直接从文档派生
  - 只有文档缺失时才回退到旧运行时页面载体
- 已新增 guard，防止 workspace 恢复链重新读取 `data.pageData/data.styleData`
- `component_manifest.py` 现在还补了三类正式 helper：
  - `get_component_aliases`
  - `get_theme_slots`
  - `get_quick_actions`
- 这意味着 manifest 已不只是 resolver 选块依据，也开始更像正式的组件能力解释层；后续要继续把 editor/builder 上下游更多对齐到这些 helper 上
- `component_builder` 的 contract snapshot 现在也改成正式依赖 manifest helper，builder 不再自己拆 entry 取语义字段
- `note_editor` 的组件契约文本已开始显式展示：
  - 组件 label
  - `semantic_role`
  - `quick_actions`
- 这让 manifest 从“有字段”继续推进到“字段真的被主脑和工兵消费”
- `note_editor` 的 block 目标打分现在也开始读 manifest 的：
  - `label`
  - `quick_actions`
- 当前 `note_editor` 对“更毒舌一点 / 结论更鲜明”这类表达的命中逻辑，正在继续从手写 token map 转向 manifest 语义提示
- 前端 `AgentInspector` 的“积木构建摘要”现在也会直接展示：
  - `prompt_modes`
  - `fact_summary_count`
  - `asset_count`
  - `contract_filter_count`
  - `precheck_warning_count`
- 这意味着 builder 的现代化执行层信号已经真正从后端 trace 打通到了前端诊断面板
- `workspace` 正式响应协议也继续去旧：
  - `WorkspaceDataResponse` 已移除旧页面载体
  - 前端 `applyWorkspaceSnapshot(...)` 现已只围绕 `noteDocument` 恢复正式状态
- 现在正式对外链路里，legacy 页面协议已经从：
  - `turn_end`
  - `workspace`
  这两条关键接口上退场，只剩 store 内部兼容缓存和后端内部运行态
- `workspace` 的会话标题提取现在已彻底不再读取 legacy 页面标题字段，正式标题语义只来自：
  - 首条用户消息
  - `note_document.document_meta.title`
- `NoteDocument.blocks[*].asset_support` 已升级成 manifest 的正式语义值：
  - `none`
  - `optional`
  - `required`
  不再把组件资产能力压扁成布尔信号，后续 resolver / editor / Inspector 可直接消费这层精确信息。
- `AgentInspector` 的 NoteDocument 概览也已对齐新主线：
  - 主题显示优先读 `inspector_summary.theme_preset / planner_policy.theme_policy.preset`
  - 不再回落到 `visual_vibe`
  - 新增“积木能力”卡，直接展示 block 的 `semantic_role / asset_support / editable_targets / fact_binding_support`
- 前端 `chat.ts` 已补齐正式 `NoteDocument / NoteDocumentBlock / NoteDocumentAsset` 类型，`ChatMessage`、`WSEvent`、前端观察器与 Inspector 开始直接消费文档协议，而不是继续停留在 `Record<string, unknown>/any`。
- 前端 `chat.ts` 现在还补齐了正式的：
  - `PlannerOutput`
  - `PlannerPolicy`
  - `TurnTrace`
  - `InspectorSummary`
  这让 `planner / trace / inspector` 也开始从泛 JSON 进入正式前端协议层。
- `useChatStore` 的主状态链也开始直接使用 `NoteDocument` 类型：
  - `noteDocument` ref
  - `pickNoteDocument(...)`
  - `documentBlocks/documentAssets`
  - workspace 恢复与回滚时的目标文档读取
  这让前端 store 不再只是“运行时优先信文档”，而是在类型层也开始围绕正式文档协议组织。
- `useChatStore` 里的以下主状态 ref 也已经切到正式类型：
  - `plannerOutput`
  - `plannerPolicy`
  - `turnTrace`
  - `agentBackends`
  - `inspectorSummary`
- `AgentInspector` 已开始直接消费类型化的：
  - `InspectorSummary`
  - `PlannerOutput`
  - `PlannerPolicy`
  - `TurnTrace`
  继续压缩 `as any / Record<string, unknown>` 漂移。
- 前端 `chat.ts` 现已继续补齐：
  - `RetrievedKnowledge`
  - `AgentMeta`
  并同步接入：
  - `useChatStore.agentMeta`
  - `AgentInspector`
  这让前端“观察性协议”开始从 store 到 UI 全链路摆脱 `as any`。
- 前端 `useChatStore` 里的 `legacyPageCache / legacyStyleCache` 已完全删除。
- 这意味着前端页面状态现在正式只围绕：
  - `NoteDocument`
  - `renderPageData`
  - `renderStyleData`
  运转，旧页面协议不再以任何缓存状态的形式留在 store 内部。
- 对应护栏已补：
  - `tests/test_final_product_guards.py::test_store_contains_no_legacy_page_or_style_cache_state`
- 最新最终验收：
  - 后端 `170 passed`
  - guardrails `16 passed`
  - 前端 build 通过
- 后端主执行节点也已继续去旧：
  - `planner_node`
  - `style_node`
  - `render_node`
  不再直接读取旧页面状态字段，而是统一经由 `NoteDocument` 执行视图工作。
- 对应护栏已补：
  - `tests/test_final_product_guards.py::test_primary_execution_nodes_do_not_directly_read_legacy_dsl_state`
- 最新最终验收更新为：
  - 后端 `171 passed`
  - guardrails `17 passed`
  - 前端 build 通过
- 为提升可读性，前端 `useChatStore.ts` 顶部的大块纯 helper 现已抽离到：
  - [`chatStoreDerivations.ts`](/root/XHS-Forge/ai-frontend-ide/src/stores/chatStoreDerivations.ts)
- 这让 store 主文件更像状态机和动作编排层，不再混着大量：
  - 协议 pick helper
  - NoteDocument 派生 helper
  - AI 回执摘要逻辑
  - render/cover/scenario 派生逻辑
- 为提升后端可读性，`note_editor` 的语义命中与评分 helper 已抽离到：
  - [`note_editor_support.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_support.py)
- 现在 [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py) 更像正式执行管线：
  - 收集当前文档状态
  - 决定结构化 action
  - 应用 action
  - 回写 state 与 trace
- 关键核心文件已补充结构型说明，帮助后续维护者快速建立心智模型：
  - `graph.py`
  - `note_document.py`
  - `component_manifest.py`
  - `component_builder.py`
  - `note_editor_node.py`
- 后端继续去旧的下一层也已经落下：
  - `verify_note_node.py`
  - `patch_node.py`
  - `enrichment_agent.py`
- 这三处现在不再直接使用旧页面状态字段，
  而是统一通过 `note_document.py` 中的
  `build_legacy_execution_state_from_state(...)` 桥接出执行 payload。
- 当前旧方案已进一步被压回单一桥接层，提升了可读性，也减少了执行节点各自维护旧 shape 的负担。
- `note_editor_node.py` 也已完成这一步：
  - 不再直接读取旧页面状态字段
  - prompt 组装与主编辑流程统一经由 `build_legacy_execution_state_from_state(...)`
- 当前后端主执行链已经基本形成统一模式：
  - 节点消费 `NoteDocument`
  - 必要时通过 `note_document.py` 单点桥接旧执行 payload
  - 不再允许节点自己分散读取旧 DSL 状态
- `graph.py`、`intent_node.py`、`structure_node.py` 也已完成同样收口：
  - 是否已有页面
  - 页面标题
  - 当前块清单
  都改为围绕 `NoteDocument` / execution view，而不是继续直接读旧页面载体
- 工具层和环境观测也已同步：
  - `note_tools.py`
  - `patch_tools.py`
  - `canvas_tools.py`
  - `observation_dashboard.py`
- 现在旧方案已经进一步压缩到：
  - `note_document.py` 中的单点桥接 helper
  - 以及少量节点仍用旧页面/样式 patch 作为返回载体
- patch 载体本身也已开始统一 helper 化，相关 helper 现集中在：
  - `note_document.py`
- 当前已消费这层 helper 的模块包括：
  - `component_builder.py`
  - `note_tools.py`
  - `patch_tools.py`
  - `canvas_tools.py`
  - `state.py`
- 这让仓库里“手写旧 patch 结构”的可见面继续缩小，即使内部 patch 机制尚未完全迁成纯 `NoteDocument patch`，主代码阅读体验也已经明显统一。

## 2026-03-21 Final Handoff Update

- 旧 DSL 方案已从正式应用代码中移除：
  - 旧页面 patch 状态
  - 旧样式 patch 状态
  - 旧文档 patch 载体
  - 旧样式 patch 载体
  - 旧画布快照载体
- 当前正式主线只保留：
  - `NoteDocument`
  - `planner_output / planner_policy`
  - `turn_trace / agent_backends`
- `note_document.py` 现在只承担：
  - 构建正式 `NoteDocument`
  - 生成只读 `document_view`
  - 提供文档级 patch helper
- 前端已完全围绕正式协议工作，不再保留旧页面缓存方案。
- 最终验收状态：
  - backend `170 passed, 2 skipped`
  - guardrails `18 passed`
  - frontend build `passed`
