# Visual Regression Workflow

前端视觉观测现在采用一套固定流程：

1. 固定样例输入  
   - 使用 [`VisualRegressionLab.vue`](../ai-frontend-ide/src/components/visual/VisualRegressionLab.vue)
   - 所有样例都来自 [`visualFixtures.ts`](../ai-frontend-ide/src/visualFixtures.ts)

2. 固定视口截图  
   - `mobile`
   - `desktop`

3. 基线图 / 当前图 / 差异图  
   - 基线：[`ai-frontend-ide/visual-regression/baseline`](../ai-frontend-ide/visual-regression/baseline)
   - 当前：[`ai-frontend-ide/visual-regression/current`](../ai-frontend-ide/visual-regression/current)
   - 差异：[`ai-frontend-ide/visual-regression/diff`](../ai-frontend-ide/visual-regression/diff)
   - 人工 review：[`ai-frontend-ide/visual-regression/review`](../ai-frontend-ide/visual-regression/review)
   - 按块 review：[`ai-frontend-ide/visual-regression/review/blocks`](../ai-frontend-ide/visual-regression/review/blocks)

4. 自动比较  
   - 脚本：[`visual-regression.mjs`](../ai-frontend-ide/scripts/visual-regression.mjs)
   - 使用 `pixelmatch` 比较截图差异

## 常用命令

生成或更新基线图：

```bash
cd /root/XHS-Forge/ai-frontend-ide
npm run visual:baseline
```

执行视觉回归对比：

```bash
cd /root/XHS-Forge/ai-frontend-ide
npm run visual:test
```

## 当前固定样例

- `seeding_compare`
- `seeding_camera_focus`
- `seeding_decision_file`

## 这套观测主要防什么

- 高频积木被挤压拉长
- 无图时混入随机跑题图
- 主题、内容和积木语义不一致
- 预览和导出 HTML 观感分叉
- 回归图一旦异常，能直接定位到具体是哪个积木出了比例或主题问题
