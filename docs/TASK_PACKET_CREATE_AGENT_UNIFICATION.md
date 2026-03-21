# Task Packet: Create Agent Unification

## Goal
把正式 agent 入口统一到 `create_agent`，不再在正式链路中保留 `create_react_agent`。

## Included
- `patch`
- `enrichment`
- `note_editor`
- 其他仍然保留 agent 性质的节点

## Excluded
- `theme_compiler`
- `document_verifier`
- `document_renderer`
- `fact_confirm`
- `asset_bind`
- checkpoint / rollback / fork

## Migration Rule
- 能通过静态 system prompt + 动态 user context 建模的，统一走 `create_agent`
- 能拆成结构化动作的，优先拆结构化，不保留 stateful open-ended agent
- 不允许为了“统一入口”把确定性节点错误 agent 化

## Acceptance
- Inspector 的 `Agent Runtime` 不再出现正式链路的 `langgraph_create_react_agent`
- 回归测试覆盖：
  - `patch`
  - `enrichment`
  - `note_editor`
- `agent_runtime` 只作为兼容门面存在，不再被正式主链用来回退到 react backend

## 补充进展：运行时类型进一步澄清（2026-03-20）
- `intent` 当前被明确标记为 `structured_function_calling` 路线，而不是开放式 agent。
- `planner` 当前被明确标记为 `deterministic_policy_builder`，不是待迁移的 `create_agent` 入口。
- 这意味着后续统一 `create_agent` 的实际迁移目标应继续聚焦在真正的 agent 节点：`patch / enrichment / note_editor / 未来仍保留为 agent 的 research`，而不是机械地把 `intent/planner` 也算进迁移数量。

## 补充进展：research 运行时分类已明确（2026-03-20）
- `research_agent` 当前显式上报为 `deterministic_tool_orchestrator`。
- 这意味着正式迁移到 `create_agent` 的范围可以进一步收窄：主攻仍是 `patch / enrichment / note_editor`，而 research 主链应继续优先保持为受控工具编排层，除非未来真的引入开放式研究 agent。

## 里程碑完成：正式 runtime 已统一（2026-03-20）
- `create_controlled_agent(...)` 已不再内置 react fallback，正式产品路径只接受 `create_agent` 兼容形态。
- `grep -RIn "create_react_agent|langgraph_create_react_agent" AI_Frontend_IDE/app tests` 已无结果。
- 当前正式 runtime 分类为：
  - `langchain_create_agent`
  - `structured_function_calling`
  - 确定性后端
- 这意味着“统一 agent 入口”这条主线已经基本完成，后续只剩继续清理文档叙事和少量兼容痕迹。

## Guardrail Added (2026-03-20)
- Added `tests/test_final_product_guards.py` to enforce that formal code paths do not reintroduce `create_react_agent` or `langgraph_create_react_agent`.
- This turns agent unification into a regression-checked contract.
