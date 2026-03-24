# Skills Snapshot

当前正式产品只围绕 **数码购买决策 Agent**。

## 可用 Skills

### `product-search`
- 适用任务：`create / edit / review`
- 典型输入：产品名、竞品、价格/芯片/续航等关键字段
- 输出约束：返回证据片段、候选知识、检索摘要，不直接下最终购买结论
- 推荐角色：`retrieval_worker`

### `product-images`
- 适用任务：`asset_edit`
- 典型输入：补图、搜图、缺图检查、产品主图/真机图
- 输出约束：要么回填图片资产或图片区块，要么显式说明失败原因
- 推荐角色：`retrieval_worker` / `composition_worker`

### `spec-sheet-ingest`
- 适用任务：`ingest`
- 典型输入：参数表、价格表、品牌资料、用户上传文档
- 输出约束：切块、抽候选知识、送入会话审查，不直接写成正式知识
- 推荐角色：`retrieval_worker`

### `decision-note-compose`
- 适用任务：`create / edit / critique`
- 典型输入：已审知识、当前页面状态、局部块级修改目标
- 输出约束：产出购买决策档案所需结构，并验证这轮是否真的改到了页面
- 推荐角色：`composition_worker` / `critique_worker`
