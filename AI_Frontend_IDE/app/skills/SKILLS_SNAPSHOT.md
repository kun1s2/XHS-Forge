# Skills Snapshot

当前正式产品只围绕 **持续笔记协作 Agent**。

## 可用 Skills

### `product-search`
- 适用任务：`create / edit / review`
- 典型输入：主题名、背景资料、关键概念、来源线索等字段
- 输出约束：返回证据片段、候选知识、检索摘要，不直接越权改正文
- 推荐角色：`retrieval_worker`

### `product-images`
- 适用任务：`asset_edit`
- 典型输入：补图、搜图、缺图检查、附件整理、封面说明
- 输出约束：要么回填图片资产或图片区块，要么显式说明失败原因
- 推荐角色：`retrieval_worker` / `composition_worker`

### `spec-sheet-ingest`
- 适用任务：`ingest`
- 典型输入：需求说明、会议纪要、研究资料、用户上传文档
- 输出约束：切块、抽候选知识、送入会话审查，不直接写成正式知识
- 推荐角色：`retrieval_worker`

### `decision-note-compose`
- 适用任务：`create / edit / critique`
- 典型输入：已审知识、当前页面状态、局部块级修改目标
- 输出约束：产出持续笔记所需结构，并验证这轮是否真的改到了页面
- 推荐角色：`composition_worker` / `critique_worker`


