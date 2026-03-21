# XHS-Forge Final Execution Roadmap

## Mission
把项目收敛成最终展示版：
- `NoteDocument` 成为主协议
- `note_editor` 成为结构化编辑主脑
- 正式 agent runtime 统一到 `create_agent`
- 事实链、资产链、恢复链、调试链全部站稳

## Phase Tracker

### Phase 1: Control Plane
- Status: completed
- Entry: 已确定最终路线，允许连续执行
- Exit: 已建立任务包与路线图文档
- Validation:
  - 文档落地
  - 后续每轮执行都能回写当前状态

### Phase 2: Note Editor Finalization
- Status: completed
- Entry: 结构化动作矩阵已覆盖创建、局部编辑、局部新增、整页编辑、整页新增
- Progress: `note_editor` 正式执行路径已移除开放式 fallback，非空画布统一走结构化整页编辑
- Goals:
  - 移除 `note_editor` 正式链路中的开放式 fallback
  - 让非空画布统一走结构化整页编辑
  - 让目标识别优先依赖 `NoteDocument + manifest + planner_policy`
- Exit:
  - 高频编辑场景均走结构化动作
  - `note_editor` 正式 runtime 只上报 `structured_function_calling`

### Phase 3: Agent Backend Unification
- Status: completed
- Entry: `patch`、`enrichment` 已具备 `create_agent` 形态
- Goals:
  - 正式链路不再出现 `langgraph_create_react_agent`
  - `agent_backends` 在 Inspector 中只展示 `create_agent` 或确定性后端
- Exit:
  - 主链 agent runtime 统一

### Phase 4: NoteDocument Frontend Final
- Status: completed
- Entry: store 已成为主要兼容层
- Progress: legacy `pageData/styleData` 已不再往 block 组件层层透传
- Goals:
  - 前端 UI、渲染、恢复、Inspector 全部优先消费 `NoteDocument`
  - `pageData/styleData` 只在 store 内集中兜底
- Exit:
  - 组件内部不再散落 legacy 协议推导

### Phase 5: Fact + Asset Final Binding
- Status: completed
- Entry: 参数卡与正文已有来源/冲突/确认机制
- Goals:
  - 参数卡关键字段和正文关键数字绑定来源
  - 资产与 block 的绑定关系完全进入 `NoteDocument.assets`
- Exit:
  - 可解释、可恢复、可演示

### Phase 6: Cleanup + Packaging
- Status: completed
- Entry: 主链功能收完
- Goals:
  - 删除迁移期死分支
  - 完成最终交接和展示文档
  - 跑全量回归
- Exit:
  - 只剩可选增强项

## Current Stop Conditions
- `note_editor` 正式链路不再触发 `create_react_agent`
- 前端 build 通过
- 核心测试通过
- 文档已同步

- Phase 1 协议冻结继续推进：`NoteDocumentBlock` 的正式 schema 已追平当前真实 block 元数据，主协议现在正式承认 `label/semantic_role/editable_targets/asset_support/fact_binding_support`。

- Phase 3 运行时分类继续澄清：`intent` 已显式标记为 `structured_function_calling`，`planner` 已显式标记为 `deterministic_policy_builder`，后续 `create_agent` 统一将只针对真正的 agent 入口推进。

- Phase 4 前端主链继续收口：renderer 目录已不再直接读取 legacy `pageData/styleData`，legacy 补形状逻辑进一步集中到 store。

- Phase 3 已完成正式 runtime 入口统一：代码与测试中已不再存在 `create_react_agent/langgraph_create_react_agent`，正式 agent 入口只剩 `create_agent`。

- Phase 4 前端兼容层继续集中：`useChatStore` 新增统一 `resolveLegacyWorkspaceState/syncLegacyStateFromDocument`，workspace 恢复、turn_end 收尾、rollback 恢复现在共用同一条 legacy 同步路径，减少 store 内部散落的旧协议赋值逻辑。

- Phase 5 资产链继续收口：store 的 `documentAssets` 已改成合并文档资产与暂存素材，`sendMessage` 发送 canonical merged assets，避免新上传素材在文档已有资产时被遗漏。

- Phase 2 继续收口：整页 `append_block` 现在已支持抽象锚点解析，新增区块不再强依赖 structured plan 里显式带 `block_id/block_index`，可直接利用 `NoteDocument + planner_policy` 命中“互动那块/证据那块”等语义锚点。

- Phase 2 补强：整页语义锚点新增已进入节点级测试覆盖，`note_editor` 现在不只在 `_apply_global_edit_plan(...)` 纯函数层支持抽象锚点插入，正式节点执行也已被钉住。

- Phase 2 继续收口：结构化 `move_block` 现在已支持语义锚点和前后关系解析，不再强依赖模型显式输出 `move_to_index`。
- Phase 2 继续收口：局部结构化 `move_block` 现在也已支持语义锚点，并且局部作用域保护会保留新的 block 顺序，不再把结构化移动结果回退掉。
- Phase 5 开始做字段级可信收口：参数卡与正文元数据现在会显式携带事实字段键，`NoteDocument.fact_bindings` 已经从“有来源”推进到“知道绑定的是哪个事实字段”。
- Phase 5 继续收口：字段级 `fact_bindings` 已经进入参数卡 hover、正文 hover 和 Inspector，可解释性不再只停留在后端元数据。

## Final Status
- 最终展示版已完成。
- 正式 agent runtime 已统一到 `create_agent` 与确定性后端；正式链路不再存在 `create_react_agent`。
- 前端主链已站到 `NoteDocument`，legacy `pageData/styleData` 仅保留在 store 兼容层。
- `note_editor` 高频编辑场景已结构化覆盖。
- 字段级事实绑定已进入参数卡 hover、正文 hover 与 Inspector。
- 全量回归 `124 passed`，前端 `npm run build` 通过。

- 收尾护栏已补齐：新增 `tests/test_final_product_guards.py`，持续防止正式代码路径重新引入 `create_react_agent` 或前端组件层重新直连 `pageData/styleData`。

- 一键最终验收脚本已补齐：`scripts/final_acceptance.sh`

- `scripts/final_acceptance.sh` 已实跑通过：全量 `pytest`、guardrails、legacy react-agent 检查、前端 build 均通过。

- CI 收尾已补齐：`.github/workflows/final-acceptance.yml` 会在 push / pull_request 上自动跑最终验收脚本，持续守住成品状态。

- Agent 决策层继续定型：正式 `route_intent(...)` 现在优先消费 `intent_result_v2` 的 `task_type/edit_scope/needs_research`，旧 `intent_route` 已退居兼容兜底。
- 大纲层进一步去历史化：`outline_node.py` 已改成现代 resolver 的兼容壳，仓库内不再保留大纲工具循环实现；正式 graph 与节点文件都已站到 resolver 口径。
- Builder 继续 contract-first：`component_builder` 现在会注入 manifest contract snapshot 和 planner policy 摘要，输出统一走 contract layer。

- 继续收掉旧六维意图信号对主题链的主导：`style_node` 现在优先消费 `planner_policy.theme_policy`（`preset + interaction_bias`），旧 `intent_result.visual_vibe/intensity_level` 降级为兼容输入。
- `note_editor` 的 `update_page_theme` fallback 现在也优先读 `planner_policy.theme_policy.preset`，不再只靠 legacy `visual_vibe` 推主题补丁。
- `intent_agent` 的运行时摘要和 prompt snapshot 已改成 Gateway V2 视角，弱化历史 6D 叙事字段在正式主链中的存在感。

- 正式主题链进一步收口：`style_node` 已移除对 `intent_result.visual_vibe/intensity_level` 的主链依赖，主题完全优先来自 `planner_policy.theme_policy`。
- `research_agent` 现在优先使用 `intent_result_v2.needs_assets` 判定是否需要搜图，旧 `intent_result.asset_request` 仅保留兼容回退。
- `workspace` 的 inspector/document 摘要已不再回落到 `note_document.theme.visual_vibe`，正式主题展示统一为 `preset`。

- `theme_compiler` 已纳入正式 runtime trace 和 `agent_backends`，Inspector/trace 现在可以明确看到主题编译来自确定性 compiler，而不是旧意图信号。
- 新增 guardrails，禁止 `style_node / note_editor_node / research_agent` 回流到旧 `visual_vibe / intensity_level / asset_request` 主链依赖。

- `intent_agent` 已新增 deterministic fast-path：非主面板且已选中区块的局部编辑请求不再进入 LLM，直接落 Gateway V2（`deterministic_fast_path`）。
- 这一步让正式网关更符合现代 agent 形态：局部编辑优先走协议与状态判断，而不是任何请求都先做一次意图推理。

- `research_agent` 的最后一个 legacy 资产信号词根已从正式代码中拿掉，guardrails 现在不会再因为 `asset_request` 回流而失效。
- `component_builder` 的 contract-first trace 已进入 `inspector_summary`：后端现在会汇总本轮 builder 的组件数、fallback 次数和组件类型，前端 `Agent 状态` 总览与 `本轮追踪` 也能直接看到“积木是怎么落下来的”。
- 当 builder 发生 fallback 时，Inspector 总览现在会直接给出建议，不再需要人工先从原始 trace 里猜“是不是组件工兵兜底了”。

- `intent_agent` 的 deterministic fast-path 已从“选中块局部编辑”扩展到 `content / style / structure` 三个编辑子面板的全局编辑请求；这些明确编辑上下文现在会直接返回 Gateway V2，不再无谓调用意图 LLM。
- `image` 面板仍刻意保留在更灵活路径上，避免把素材检索语义误收成纯编辑；正式网关现在更接近“编辑上下文走协议，开放语义才走 LLM”的现代形态。

- `intent_agent` 现在还会在 `main` 面板的“已有画布显式编辑请求”上命中 deterministic fast-path：像“文本简短一点”“整体改成灰蓝风格”这类请求不再先走意图 LLM，而是直接落 Gateway V2 edit/global。
- 同时保留了轻量路由区分：主面板已有画布编辑会按 query 语义优先映射到 `content_node / style_node / structure_node`，再由正式 graph 稳定收束到 `note_editor`。

- `intent_agent` 的 LLM 慢路也已切到瘦身的 `IntentGatewayOutput` 协议，正式网关不再让模型产出旧六维 `IntentOutput` 才映射到 V2。
- 旧 `IntentOutput` 现在只保留在兼容 helper 和历史测试上下文里；正式 `intent_agent` 已经做到“快路 V2、慢路也 V2”。

- `research_agent` 也进一步脱离了 legacy `intent_result`：现在正式只消费 `intent_result_v2.needs_assets` 或显式 query 信号来判定搜图，不再依赖旧资产请求对象。
- 搜图回填的资产描述已改成实体级标签，不再把整句用户指令原样塞进 `image_assets[*].desc`；执行层开始更像产品能力，而不是 prompt 残留拼接。

- 仓库里的历史示范脚本和 campaign 测试也开始统一现代口径：`campaign_1_intent_tests / campaign_6d_radar_test / campaign_ultimate_stress_test / ignition_test` 已切到 `IntentGatewayOutput / planner_policy / resolver` 叙事，不再继续用 `visual_vibe / narrative_mode / asset_request` 当作正式主线示范。
- 部分 `style_agent / note_editor` 测试样例也已改成优先喂 `planner_policy.theme_policy`，减少测试层面对 legacy `intent_result.visual_vibe` 的示范依赖。

- 已正式删除旧意图兼容链：`IntentOutput`、`intent_result`、`intent_system.xml` 已从正式 runtime 退场；对应 refusal/persistence/chat thought 提取也同步改掉，正式网关唯一输出现在是 `intent_result_v2`。
- `test_final_product_guards.py` 已新增护栏，防止仓库把旧意图 schema、旧 prompt 文件或 `intent_result` 兼容逻辑重新带回正式主链。

- 前端消息时间胶囊也继续去旧页面协议化：`ChatMessage` 已不再保存 `pageData/styleData` 副本，回滚与消息恢复优先只依赖 `noteDocument`；`pageData/styleData` 目前已进一步收缩为 store 内部派生缓存，而不是对话消息的一等数据。
- `useChatStore` 现在已把旧页面状态显式改名为 `legacyPageCache/legacyStyleCache`，并从 public store API 中移除；旧页面协议正式降级为 store 内部兼容缓存。
- `test_final_product_guards.py` 已新增护栏，防止 store 再次把 legacy page/style cache 暴露给组件层或外部调用方。
- `turn_end` payload 中的 `noteData` 历史别名已删除；当前旧页面协议只剩 `page_data/pageData + style_data/styleData` 两组兼容字段。
- 相关前端类型与测试口径也已同步删掉 `noteData`，仓库关于旧页面协议的正式残留现在集中在 `pageData/styleData` 这一层。
- 已补齐积木语义职责与 manifest 映射文档：`BLOCK_SEMANTIC_ROLES.md` 与 `COMPONENT_MANIFEST_SEMANTIC_MAPPING.md`，后续积木升级将围绕跨场景语义角色，而不是围绕数码测评特供组件。
- 已补齐 `CORE_BLOCK_SET.md` 与 `CORE_BLOCK_SET_INTENT_MAPPING.md`，把“最值得长期保留的核心积木”直接映射到 planner block intents 与 manifest contract。
## 2026-03-21 Update

- `turn_end` 正式协议已进一步收口，只保留 `note_document / planner_output / planner_policy / turn_trace / agent_backends / source_code / image_assets` 等现代字段，不再公开 `pageData/styleData`。
- 前端 `WSEvent` 已同步移除 `pageData/styleData`，`turn_end` 收尾改为直接从 `noteDocument` 派生内部 legacy cache。
- `component_builder` 继续现代化：新增 contract/filter/precheck 摘要，Inspector 汇总现在能显示：
  - `contract_filter_count`
  - `precheck_warning_count`
  - fallback 次数
- 相关 guard 已补齐，防 `turn_end` 旧页面协议回流。
- `useChatStore` 的 workspace 恢复链也不再读取 `pageData/styleData` 别名，只围绕旧运行时页面载体与 `NoteDocument` 工作。
- 高频跨场景块继续抛光：
  - `PollBlock` 更明确转向“互动语义块”，不再带平台真票数错觉
  - `RadarChartBlock` 新增综合判断和维度解读，更像证据摘要块而不是静态图
- `CoverSwiper` 增加当前帧说明区和整组媒体摘要，更像稳定的 `hero_media` 积木
- `VersusCard` 增加对比阅读说明和最佳使用语境，更像跨场景 `comparison` 积木
- `componentManifest.json` 已补一轮 `quick_actions`，让核心块的语义动作与文档口径更一致
- `outline_resolver` 现在开始更明确地围绕 manifest 语义字段选块：
  - `semantic_role`
  - `supported_scenarios`
  - `asset_support`
  - `fact_binding_support`
- `turn_trace.outline` 已新增 `resolution_source=manifest_semantic_role`
- `component_builder` prompt 已进一步收成 compact contract-first 形态：
  - 不再注入大段全局背景和全量事实库
  - 改为只消费：
    - block contract snapshot
    - 全局导引摘要
    - 事实摘要
    - 资产摘要
    - planner policy 摘要
- `turn_trace.component_builder[*]` 已新增：
  - `prompt_mode=compact_contract_first`
  - `fact_summary_count`
  - `asset_count`
- `inspector_summary.builder` 已新增：
  - `fact_summary_count`
  - `asset_count`
  - `prompt_modes`
- 当前 builder 主线更接近“轻 prompt + 强 contract + 强观察性”的现代执行层，而不是全局大 prompt 工兵
- `useChatStore` 的 legacy cache 派生顺序也继续现代化了：
  - 现在只要存在 `noteDocument`，`legacyPageCache/legacyStyleCache` 就优先完全由文档派生
  - 旧运行时页面载体只在 `noteDocument` 缺失时才退回兜底
- 已新增 guard，防止 store workspace 恢复链重新读取 `data.pageData/data.styleData`
- `component_manifest.py` 已继续补强正式 helper：
  - `get_component_aliases`
  - `get_theme_slots`
  - `get_quick_actions`
- 这让“核心积木集合 -> block_intents -> manifest contract”的工程链更完整：
  - 不只是文档定义语义
  - resolver / builder / editor 现在有正式 helper 可以消费这些字段
- `component_builder.build_component_contract_snapshot(...)` 现在也开始正式依赖 manifest helper，而不是自己拆 entry 字典：
  - `label`
  - `semantic_role`
  - `asset_support`
  - `fact_binding_support`
  - `theme_slots`
  - `quick_actions`
- `note_editor` 的组件契约文本已补入：
  - 组件 label
  - `semantic_role`
  - `quick_actions`
- `workspace` 的会话标题提取现在优先读取 `note_document.document_meta.title`，旧页面标题字段已降为兼容兜底。
- `workspace` 的会话标题提取现在已彻底不再读取 legacy 页面标题字段，正式标题语义只来自：
  - 首条用户消息
  - `note_document.document_meta.title`
- `NoteDocument.blocks[*].asset_support` 已从布尔值升级为 manifest 正式语义值：
  - `none`
  - `optional`
  - `required`
  这让 block 协议不再丢失组件资产能力的精度，后续 resolver / editor / Inspector 可以直接消费正式能力描述。
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
  这让 `planner / trace / inspector` 也开始脱离泛 JSON，正式进入前端类型层。
- `useChatStore` 的主状态链也开始直接使用 `NoteDocument` 类型：
  - `noteDocument` ref
  - `pickNoteDocument(...)`
  - `documentBlocks/documentAssets`
  - workspace 恢复与回滚时的目标文档读取
  这让前端 store 不再只是“运行时优先信文档”，而是在类型层也开始围绕正式文档协议组织。
- `useChatStore` 的以下主状态 ref 现在也已切到正式类型：
  - `plannerOutput`
  - `plannerPolicy`
  - `turnTrace`
  - `agentBackends`
  - `inspectorSummary`
  这意味着前端主工作台正在从“NoteDocument first”继续推进到“整个诊断/规划协议 first”。
- `AgentInspector` 现已优先直接消费正式类型化的：
  - `InspectorSummary`
  - `PlannerOutput`
  - `PlannerPolicy`
  - `TurnTrace`
  继续压缩 `as any / Record<string, unknown>` 漂移。
- `chat.ts` 现已继续补齐：
  - `RetrievedKnowledge`
  - `AgentMeta`
  并同步接入：
  - `useChatStore.agentMeta`
  - `AgentInspector`
  这让前端“观察性协议”开始从 store 到 UI 全链路摆脱 `as any`。
- 这让 manifest 已不只是 resolver 的数据源，也开始成为 builder / editor 共享的语义解释层
- `note_editor` 的 block 打分也开始直接消费 manifest:
  - 组件 `label`
  - `quick_actions`
- 这意味着像“更毒舌一点”“结论更鲜明”这类表达，正在从纯手写 heuristics 继续转向 manifest 驱动的语义命中
- `AgentInspector` 的“积木构建摘要”也已接上 builder 新信号：
  - `prompt_modes`
  - `fact_summary_count`
  - `asset_count`
  - `contract_filter_count`
  - `precheck_warning_count`
- 这让 compact contract-first builder 不只是 trace 里可见，也已经进入前端诊断面板
- `workspace` 首屏正式回包也已进一步去旧：
  - `WorkspaceDataResponse` 不再暴露旧页面载体
  - 前端 `applyWorkspaceSnapshot(...)` 现在完全按 `noteDocument` 恢复正式状态
- 这意味着正式对外协议层目前已经做到：
  - `turn_end` 不回 legacy 页面字段
  - `workspace` 首屏回包也不回 legacy 页面字段
- 前端 `useChatStore` 里的 `legacyPageCache / legacyStyleCache` 已彻底删除。
- store 的页面派生、选中块、hover payload、工作台恢复、回滚和 AI 回执摘要，现在都只围绕：
  - `NoteDocument`
  - `renderPageData`
  - `renderStyleData`
  工作，不再保留内部 legacy 页面缓存状态。
- 对应 guard 也已补齐：
  - store 文件中不允许再出现 `legacyPageCache / legacyStyleCache`
  - 最终验收重新通过：后端 `170 passed`、guardrails `16 passed`、前端 build 通过
- 后端主执行链也继续去旧：
  - `planner_node`
  - `style_node`
  - `render_node`
  现在都不再直接读取旧页面状态字段，而是统一先折叠为 `NoteDocument` 执行视图再工作。
- 对应 guard 已补：
  - `tests/test_final_product_guards.py::test_primary_execution_nodes_do_not_directly_read_legacy_dsl_state`
- 最新最终验收：
  - 后端 `171 passed`
  - guardrails `17 passed`
  - 前端 build 通过
- 为可读性，前端 `useChatStore.ts` 顶部的大块纯派生/摘要/协议 helper 已抽离到：
  - [`chatStoreDerivations.ts`](/root/XHS-Forge/ai-frontend-ide/src/stores/chatStoreDerivations.ts)
- 现在 `useChatStore.ts` 更明确地只承担：
  - 状态定义
  - WebSocket / workspace 同步
  - 用户动作
  - 主流程编排
  而不是继续混合协议解析、页面摘要、渲染派生和会话动作。
- 后端 `note_editor_node.py` 也已完成第一轮可读性拆分：
  - 语义命中、token map、block scoring、theme fallback、组件契约文本等 helper 已抽离到
    [`note_editor_support.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_support.py)
  - `note_editor_node.py` 现在更聚焦于：
    - 取当前文档状态
    - 选择结构化编辑动作
    - 应用动作并产出 trace
- 关键主链文件也已补充结构型说明注释，打开文件即可快速理解：
  - graph runtime
  - NoteDocument bridge
  - component manifest
  - component builder
  - note editor orchestration
- 后端剩余几个旧执行层节点也已继续去旧：
  - [`verify_note_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/verify_note_node.py)
  - [`patch_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/patch_node.py)
  - [`enrichment_agent.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/enrichment_agent.py)
- 现在这三处不再直接读取旧页面状态字段，而是统一经由
  [`build_legacy_execution_state_from_state(...)`](/root/XHS-Forge/AI_Frontend_IDE/app/core/note_document.py)
  从 `NoteDocument` 桥接出执行 payload。
- 对应 guard 也已扩展，防止 `planner/style/render/verify/patch/enrichment`
  再回退到直接读取旧 DSL 状态。
- [`note_editor_node.py`](/root/XHS-Forge/AI_Frontend_IDE/app/agents/nodes/note_editor_node.py)
  现在也已不再直接读取旧页面状态字段：
  - prompt 组装
  - 主编辑流程
  都统一经由 `build_legacy_execution_state_from_state(...)` 拿执行视图。
- 这意味着后端主编辑/渲染/验证/补丁/增强链已经统一到：
  - 正式主协议：`NoteDocument`
  - 单点桥接层：`note_document.py`
  不再允许各节点各自维护旧执行 shape 的读取逻辑。
- 主编排层和网关层也已进一步去旧：
  - `graph.py`
  - `intent_node.py`
  - `structure_node.py`
- 它们现在关于“是否已有画布”“当前块清单”“当前页面标题”的判断，也统一改成通过
  `NoteDocument` / execution view 获取，不再直接读旧 DSL 状态。
- 工具层与观测 helper 也已继续跟进：
  - `note_tools.py`
  - `patch_tools.py`
  - `canvas_tools.py`
  - `observation_dashboard.py`
- 这些模块读取运行时页面状态时，也统一改成通过
  `build_legacy_execution_state_from_state(...)` 或 execution view，
  不再各自直接从 state 读取旧 DSL 状态。
- 为继续压缩旧方案的可见面，旧的页面/样式 patch 结构也已开始收口到
  `note_document.py` 的统一 helper：
  - `build_component_patch_update(...)`
  - `build_block_append_update(...)`
  - `build_block_insert_update(...)`
  - `build_block_remove_update(...)`
  - `build_block_metadata_update(...)`
  - `build_blocks_override_update(...)`
  - `build_page_title_update(...)`
  - `build_page_theme_update(...)`
- `component_builder.py`、`note_tools.py`、`patch_tools.py`、`canvas_tools.py`、
  `state.py` 已开始消费这些 helper，不再到处手写旧 patch 结构。

## 2026-03-21 Final NoteDocument Unification

- 正式应用代码已不再包含：
  - 旧页面 patch 状态
  - 旧样式 patch 状态
  - 旧文档 patch 载体
  - 旧样式 patch 载体
  - 旧画布快照载体
- 运行时正式状态与正式接口统一围绕：
  - `note_document`
  - `planner_output`
  - `planner_policy`
  - `turn_trace`
  - `agent_backends`
- 主执行链和工具层全部改成：
  - 从 `NoteDocument` 读取
  - 必要时仅通过 `note_document.py` 生成只读 `document_view`
  - 最终只回写 `note_document`
- 前端 store、类型、Inspector、Prompt/Trace 面板都已对齐到正式协议。
- 最终验收结果：
  - backend `170 passed, 2 skipped`
  - guardrails `18 passed`
  - frontend production build `passed`
