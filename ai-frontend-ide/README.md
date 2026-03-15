# AI Frontend IDE

Vue 3 + TypeScript + Vite + Tailwind + Pinia，左侧对话、右侧画布预览。

## 如何启动前端

**方式一：双击或命令行运行启动脚本**

- Windows 双击：`start.bat`
- PowerShell：`.\start.ps1`

脚本会自动进入项目目录，若无 `node_modules` 会先安装依赖，再执行 `pnpm run dev`（无 pnpm 则用 `npm run dev`）。

**方式二：手动命令**

```bash
cd ai-frontend-ide
pnpm install   # 或 npm install（首次）
pnpm run dev   # 或 npm run dev
```

开发服务器默认：<http://localhost:5173>。

---

基于 Vue 3 + TypeScript + Vite 模板。 The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about the recommended Project Setup and IDE Support in the [Vue Docs TypeScript Guide](https://vuejs.org/guide/typescript/overview.html#project-setup).
