import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './assets/tailwind.css'
import { setupFrontendObserver } from './utils/frontendObserver'
import App from './App.vue'

// ✨ 哨兵核心修复：全局注册递归渲染引擎
// 这样可以彻底打破子积木（如 CollageContainer）与渲染器之间的循环引用死锁
import XForgeRenderer from './components/renderers/XForgeRenderer.vue'

const app = createApp(App)
const pinia = createPinia()

app.component('XForgeRenderer', XForgeRenderer)

app.use(pinia)
setupFrontendObserver(pinia)
app.mount('#app')
