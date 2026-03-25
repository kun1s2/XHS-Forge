# Full System Audit

这份文档把当前项目的前后端大检查固定成一套可重复执行的体检流程，目标是避免再次陷入“靠人工一条条找 bug”的循环。

当前正式产品已经统一到：

- 自由对话式 `supervisor`
- 三个正式 worker：`retrieval_worker / composition_worker / critique_worker`
- `artifact / artifact_version / revision`
- 数码购买决策主线

## 一键体检

在仓库根目录运行：

```bash
bash scripts/full_system_audit.sh
```

这条命令会按顺序完成：

1. 最终验收
2. runtime / workspace / websocket 体检
3. artifact / revision / supervisor 主链体检
4. RAG / 热点 / 缓存体检
5. 前端视觉回归体检

## 体检覆盖面

### A. Supervisor 主链

- `supervisor -> retrieval_worker / composition_worker / critique_worker`
- `artifact / artifact_version / revision_plan / revision_result`
- `workspace` / `chat` / `upload` API
- websocket 创建、编辑、回退、checkpoint、revision

对应测试：

- `tests/test_chat_ws_integration.py`
- `tests/test_agent_runtime.py`
- `tests/test_artifact_revision_services.py`
- `tests/test_digital_purchase_runtime.py`
- `tests/test_ws_probe.py`

### B. 局部修改与资产链

- 选中组件后的局部编辑
- 资产区块和图片落地
- 高亮与 `changed_blocks`
- revision loop 和局部重做 contract
- 资源不应提前污染页面结构

对应测试：

- `tests/test_workspace_assets_api.py`
- `tests/test_workspace_api.py`
- `tests/test_final_product_guards.py`
- `tests/test_artifact_revision_services.py`

### C. RAG / 热点 / 缓存

- `system_preload`
- `task_triggered_ingest`
- retrieval / grounding / citation
- hot trends
- cache hit / freshness / TTL

对应测试：

- `tests/test_rag_pipeline.py`
- `tests/test_trend_pipeline.py`
- `tests/test_enrichment_agent.py`
- `tests/test_enrichment_integration.py`
- `tests/test_workspace_api.py`

### D. 前端工作台

- 聊天区
- 输入框旁 Revision Panel
- 右侧 Inspector / Benchmark / Evaluation
- Showcase
- Block Gallery
- 素材库
- 主预览组件选中态与 artifact 视角

对应测试：

- `tests/test_final_product_guards.py`
- `tests/test_workspace_showcase_api.py`
- `tests/test_workspace_api.py`
- `tests/test_chat_ws_integration.py`

### E. 视觉回归

- 固定 fixture
- 固定 viewport
- 整页截图
- 全积木总览

执行：

```bash
cd ai-frontend-ide
npm run visual:test
```

参考：

- `docs/VISUAL_REGRESSION_WORKFLOW.md`
- `ai-frontend-ide/src/visualFixtures.ts`
- `ai-frontend-ide/src/components/visual/VisualRegressionLab.vue`

## 当前建议巡检节奏

### 每次较大改动后

运行：

```bash
bash scripts/full_system_audit.sh
```

### 每次前端视觉调整后

运行：

```bash
cd ai-frontend-ide
npm run visual:test
```

### 每次改资源/补图/热点链后

至少补跑：

```bash
pytest -q tests/test_workspace_assets_api.py tests/test_trend_pipeline.py tests/test_final_product_guards.py tests/test_artifact_revision_services.py
```

## 仍建议保留的人工抽检

自动化已经覆盖主链，但真人演示视角仍建议抽查 5 条：

1. 新建数码对比，无图
2. 给已有页面补图
3. 点击 `听取意见` 跑一轮 revision
4. 对已有页面做局部编辑
5. 查看 Inspector / Benchmark / Evaluation / Block Gallery 是否符合预期

这些不是为了替代自动化，而是为了从“最终观感和真实操作”角度补最后一层保险。
