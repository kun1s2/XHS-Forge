# Demo Script

最后更新: 2026-03-21

这份脚本用于 5 到 8 分钟的稳定演示。目标是让面试官在最短时间内感受到：

- 这不是单次生成工具
- 系统有长期状态
- RAG、缓存、grounding 是真的可见
- 页面和后端工程是连在一起的

## 0. Demo Goal

一句话开场：

> 我做的是一个类小红书内容创作 Agent 工作台，不只是生成文案，而是围绕同一份 `NoteDocument` 持续编辑、搜证、回滚、分叉和评估。

## 1. 演示前准备

启动后端：

```bash
cd /root/XHS-Forge
uvicorn AI_Frontend_IDE.app.main:app --reload --port 8000
```

启动前端：

```bash
cd /root/XHS-Forge/ai-frontend-ide
npm run dev
```

可选：先打开右侧 `Agent 状态` 面板，确保能看到：

- `总览`
- `策略规划`
- `事实与检索`
- `Benchmark`

## 2. Demo Route

推荐按下面顺序演示：

1. `seeding`
2. `travel`
3. `daily_share`
4. 用 `Benchmark` 收尾

这样既能展示跨场景，又能证明同一套语义积木和 RAG/Cache 工程是复用的。

## 3. Scene A: Seeding

### 用户输入

```text
帮我生成一篇关于华为 Mate 60 的对比种草笔记，语气克制一点，但结论要鲜明。
```

### 你要说的话

> 这里不是返回一段文案，而是会生成一整份可继续编辑的 `NoteDocument`。  
> 左侧是交互，右侧是画布和诊断面板，系统会先判断意图、规划 block intents，再落地到具体积木。

### 演示重点

- 页面不是一次性字符串
- `Agent 状态 -> 策略规划`
  - 展示场景权重
  - 展示 block intents
- `Agent 状态 -> 事实与检索`
  - 展示 query、strategy、citation、grounding
- 页面里的对比块、证据块、互动块

## 4. Scene B: Structured Edit

### 用户输入

```text
保留标题，把第二段改得更尖锐一点，再把互动卡换成雷达图。
```

### 你要说的话

> 这一步最重要的是证明系统不是整页重写。  
> 它会基于已有页面进入结构化编辑链，只修改目标区块或目标段落。

### 演示重点

- `Agent 状态 -> 本轮追踪`
  - 查看 action
  - 查看 target
  - 查看 changed blocks
- 页面里确实只改了对应区块
- `note_editor` 是长期编辑器，而不是每轮重生

## 5. Scene C: Travel

### 用户输入

```text
帮我做一篇阿那亚一日游攻略，想要更像生活方式博主的表达，但信息要靠谱。
```

### 你要说的话

> 这一步用来证明系统不是只适合数码种草。  
> 同一套协议和积木，在 travel 场景下会走不同的 planner policy、地点信息、主视觉和证据组织方式。

### 演示重点

- `LocationBlock`
- `CoverSwiper`
- 页面主题风格切换
- `事实与检索` 里地点/引用来源

## 6. Scene D: Daily Share

### 用户输入

```text
写一篇周末咖啡店小分享，整体更轻一点，正文像真实记录，不要像广告。
```

### 你要说的话

> 这一步强调语气控制和长期编辑体验。  
> 同样的系统并不会因为场景变化就切换成另一套产品，它还是围绕 `NoteDocument`、planner policy 和语义积木工作。

### 演示重点

- 叙事正文
- 轻互动
- 主题与气质变化
- 非数码场景也能复用同一套系统

## 7. Cache / RAG 演示

### 你要说的话

> RAG 不是藏在后端的，我把它直接做进了页面。  
> 现在能看到这轮是缓存命中还是在线搜证，引用有多少，grounding 分是多少。

### 要点

在 `事实与检索` 里指出：

- strategy
- policy name
- cache hit / live search
- citation count
- grounding score
- knowledge records

如果有 cache hit，再展示：

- cache key
- age
- TTL
- remaining TTL

## 8. Benchmark 收尾

### 你要说的话

> Inspector 看的是单轮过程，Benchmark 看的是整套系统很多轮下来表现得怎么样。  
> 这对面试最重要，因为它说明我不是只做了功能，还做了系统评估。

### 要点

切到 `Benchmark` tab，点这几项：

- cache hit rate
- grounding score
- citation coverage
- builder fallback rate
- scenario / theme / component distribution

## 9. 收尾话术

> 这个项目对我最重要的不是“我做了很多 agent”，而是我把它收成了一套真正可维护的系统：  
> 统一协议、长期编辑、RAG grounding、热点缓存、Benchmark 评估和前端可观察性都打通了。

## 10. 演示顺序备忘

1. 先生成一篇 `seeding`
2. 再改已有页面
3. 再切一个 `travel`
4. 最后用 `Benchmark` 收尾

这个顺序最稳，也最容易让面试官记住项目亮点。
