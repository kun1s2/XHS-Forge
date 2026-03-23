# Runtime Data Reset

这个项目现在已经不兼容旧 checkpoint / 旧 DSL 数据。  
如果你看到历史反序列化告警，或者想把数据库、缓存和向量库全部清空后重新开始，请直接使用下面的脚本。

## 一键全量重置

```bash
bash scripts/reset_project_state.sh --yes
```

它会做这些事：

1. 清空 Redis 当前库
2. 清空 PostgreSQL `public` schema
3. 重新创建：
   - LangGraph checkpointer
   - LangGraph store
   - PGVector 表
4. 重新灌入一份基础知识样本
5. 清理本地运行日志

## 只重建空表，不灌入知识样本

```bash
bash scripts/reset_project_state.sh --yes --skip-seed
```

## 保留日志

```bash
bash scripts/reset_project_state.sh --yes --skip-logs
```

## 说明

- 脚本会优先检测 Docker：
  - `xhs-postgres`
  - `xhs-redis`
  - `xhs-backend`
- 如果这些容器正在运行，就优先在容器里执行
- 如果没有检测到容器，就回退到本地 `psql / redis-cli / Python`

## 什么时候应该用

- 你想彻底删掉旧 checkpoint
- 你想清空历史热点缓存和 RAG 缓存
- 你想把当前项目重置成“只保留当前架构”的干净状态
- 你看到类似 `IntentOutput` 的历史 checkpoint 反序列化告警

## 风险

这是破坏性操作：

- 会删掉所有历史线程
- 会删掉所有 checkpoint
- 会删掉所有热点榜和缓存
- 会删掉向量库中的历史知识

所以脚本必须显式加 `--yes` 才能执行。
