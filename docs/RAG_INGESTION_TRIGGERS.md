# RAG Ingestion Triggers

XHS-Forge 当前只优先建设两条入库主线：

- `system_preload`
- `task_triggered_ingest`

不把“用户手动上传知识库”作为主入口。

## 1. system_preload

### 目标
- 提前准备高概率会被使用的热点知识
- 降低首响延迟
- 为常见展示场景准备 grounded evidence

### 典型对象
- 热门产品
- 热门地点
- 热门争议点
- 高频趋势话题

### 当前落点
- `app/services/trend_pipeline.py`
- `app/services/cache_service.py`

### 入库要求
- 必须带来源
- 必须带更新时间
- 必须有 TTL
- 只存蒸馏后高价值知识，不囤原始噪声

## 2. task_triggered_ingest

### 目标
- 用户提需求后在线搜证
- 将“值得复用”的知识沉淀回 KB
- 让系统越用越强

### 流程
1. 用户请求触发 research
2. research agent 搜证
3. 结构化蒸馏事实与来源
4. 仅将高价值知识写入 KB
5. 当前会话继续消费同一份知识

### 当前落点
- `app/agents/nodes/research_agent.py`
- `app/services/rag_ingestion.py`
- `app/services/rag_knowledge.py`

### 入库要求
- 不是什么都沉淀
- 不确定或冲突信息不能直接固化为硬事实
- 必须保留 citation

## 3. 不作为主线的触发方式

### user_uploaded_kb
- 可后续补，但不是当前主能力
- 当前项目重点是系统预热与任务驱动沉淀，不是企业文档问答

## 设计原则

- 先服务当前任务，再决定是否沉淀
- 沉淀的是可复用依据，不是一次性结果
- preload 与 task-ingest 共同组成 KB 增长飞轮
