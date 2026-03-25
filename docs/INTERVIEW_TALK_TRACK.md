# Interview Talk Track

最后更新: 2026-03-24

## 1. 20 秒版本

> 我做了一个数码购买决策 Agent 工作台。用户只和一个 supervisor 对话，系统会基于知识审查、artifact version 和 revision loop，持续维护一份购买决策档案，而不是一次性吐一段测评文案。

## 2. 1 分钟版本

> 这个项目不是普通聊天生成器，而是一个围绕成品持续协作的 agent 系统。  
> 用户可以先让它生成一份手机购买决策档案，之后继续说“补几张真机图”“加一个竞品”“把结论保守一点”“只改第二个对比块”。  
> 系统顶层是 free-dialogue supervisor，下面固定只有 retrieval、composition、critique 三个 worker。  
> 我把原来的 review 和 asset 职责收回到了 retrieval/composition 里，减少了不必要的状态切换。  
> 每次成功修改都会产出新的 artifact version，外部知识也必须先进入待审知识，再进入会话知识，最后才用于成品生成。前端还能直接看到 worker、tool、knowledge version、changed blocks 和 failure point。

## 3. 3 分钟版本

### 3.1 项目定位

> 我把项目收成了“数码购买决策 Agent”，而不是通用内容生成器。  
> 它服务的是一个明确任务：和用户长期协作，持续维护一份购买决策档案。

### 3.2 架构核心

> 顶层是一个自由对话式 supervisor，用户只和它说话。  
> supervisor 每轮动态选择 retrieval、composition 或 critique worker，不再依赖一条写死的 graph 流程。  
> review 和 asset 现在作为 retrieval/composition 的内聚职责存在，而不是额外 worker。

### 3.3 成品与版本

> 系统不是把文档塞在 session 里完事，而是把成品正式建模成 artifact。  
> 每次成功 turn 都会生成一个 artifact version，记录 parent version、changed blocks、assets delta 和 knowledge version，所以回滚、分支和局部高亮都能围绕同一个产物对象工作。

### 3.4 知识治理

> 我的 RAG 不是直接拿搜索结果写答案。  
> 外部命中会先进入 candidate session KB，用户审过后才进入 session KB，正式知识库也是慢入口。  
> 所以这个项目更像“知识驱动的决策工作台”，而不是“接个向量库做问答”。

### 3.5 修订系统

> critique 不再每轮打断用户。  
> 我把它改成输入框旁的 revision panel，只给一个主建议，用户点击 `听取意见` 才进入 revision loop。  
> 这样系统既有反思能力，又不会破坏连续编辑体验。

## 4. 高频追问

### Q1: 为什么要做 artifact/version？

> 因为我的产品不是一次性回复，而是持续维护一个成品。  
> 如果没有 artifact/version，回滚、局部重做、版本对比、修订理由就都只能挂在 session 细节上，成品本身不会成立。

### Q2: 为什么不是单一大 agent？

> 因为这个任务同时包含检索、知识判断、补图、成品修改和复盘几类不同决策。  
> 用 supervisor + 固定 worker 后，职责边界更清楚，工具权限更稳定，也更容易做 observability 和 evaluation。

### Q3: 你这个项目的后端亮点是什么？

> 我会讲 5 个：
> - supervisor runtime
> - artifact/version
> - 知识审查主链
> - 结构化优先 RAG + 缓存
> - 白盒 trace / evaluation

### Q4: 这个项目为什么有 agent 味，而不是工作流拼装？

> 因为顶层下一步做什么不是写死的，而是 supervisor 按当前状态动态决定。  
> 但我又保留了强状态、知识审查和结果校验，所以它不是黑盒 agent，而是可控的 agent 系统。
