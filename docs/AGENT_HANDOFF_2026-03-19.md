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
5. `render_node` 修复 `style_dsl` 读取方式。
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
3. 输出更稳定的 `style_dsl`。

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
6. `note_editor_node` 已补 state schema，保证内部工具修改过的 `data_dsl/style_dsl` 能回传外层图。
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
- 已有整页的主题修改现在也能稳定写回 `data_dsl.page_theme`，不再只是“看起来像变了”。

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
   - 通过扩展后的四回合压测，已经确认第四回合“把整体页面改成更克制的灰蓝风格”会真实写回 `data_dsl.page_theme`
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
