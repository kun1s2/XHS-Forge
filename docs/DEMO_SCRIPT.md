# Demo Script

最后更新: 2026-03-24

这份脚本用于 5 到 8 分钟的稳定演示。目标是让面试官快速看到：

- 这不是一次性问答
- 系统围绕 artifact/version 工作
- revision loop 和局部重做是正式能力
- 知识审查、RAG、缓存和 observability 都是白盒的

## 0. 开场一句话

> 我做的是一个数码购买决策 Agent 工作台。用户只和一个 supervisor 对话，系统会围绕同一份购买决策档案持续补知识、补图、改结论、做版本修订。

## 1. 启动

后端：

```bash
cd /root/XHS-Forge
uvicorn AI_Frontend_IDE.app.main:app --reload --port 8000
```

前端：

```bash
cd /root/XHS-Forge/ai-frontend-ide
npm run dev
```

## 2. 第一段：新建一份决策档案

用户输入：

```text
帮我判断华为 Mate 60 现在值不值得买，预算 5000 左右，先给我一个克制但结论明确的版本。
```

演示重点：

- 会话工作台生成一份完整决策档案
- Inspector 里能看到：
  - 当前 worker
  - selected skills
  - retrieval / knowledge 轨迹
- 会话知识面板里能看到待审知识和当前 artifact version

## 3. 第二段：连续编辑成品

用户输入：

```text
保留当前结论，把对比那块改得更直接一点，再补几张真机图。
```

演示重点：

- 不是整页重写，而是局部重做
- `changed_blocks` 有明确变化
- 如果补图成功，能看到 `assets_delta` 或图片区块变化
- 当前 artifact version 会增加

## 4. 第三段：revision loop

不直接继续聊天，点击输入框旁 `听取意见`。

演示重点：

- revision panel 默认非阻断
- 用户显式触发后才进入 revision loop
- 这轮会生成 `revision_plan`
- 修订成功后出现新的 artifact version

## 5. 第四段：白盒观测

打开 `AgentInspector`，说明：

- 当前 phase
- 当前 worker
- 当前 skill
- 当前 artifact version
- 当前 knowledge version
- changed blocks
- failure point

补一句：

> 这里不是“看起来像改了”，而是系统会把版本、知识和改动都挂到同一条成品链上。

## 6. 第五段：会话 / 全局分离

切到：

- `会话工作台`
- `全局资产中心`

演示重点：

- 会话只看当前 artifact、当前版本、当前会话知识
- 全局资产中心只管理长期资料、正式知识、demo packs、evaluation
- 全局资产不会直接污染当前会话状态

## 7. 收尾话术

> 这个项目真正的核心不是“做了几个 agent”，而是把成品、知识、修订和版本统一进了一套可持续协作的系统。  
> 所以它更像一个可维护的 agent 产品，而不是 prompt demo。
