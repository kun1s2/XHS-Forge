# decision-note-compose

## 目标
把已审知识组织成一份数码购买决策档案。

## 正式区块职责
- `decision_summary`
- `fact_list`
- `comparison`
- `risk_boundary`
- `hero_media`
- `narrative_text`

## 什么时候用
- 首次生成购买决策档案
- 用户要求改结论、改对比、改参数表达、改吸引力
- 用户要求把图片和文字一起整理成更完整的成品

## 执行约束
- 只能使用已审知识或用户直接提供的事实
- 缺关键知识时要降级表达
- 文本改写必须有 `changed_blocks`
- 补图必须有 `assets` 或图片区块变化

## 失败回退
- 如果这轮没有实际改动，显式告诉总控失败点：未命中块、缺知识、缺素材或无有效差异
