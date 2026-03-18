import asyncio
import json
import os
from app.agents.graph import compile_my_graph
from app.agents.state import UIProjectState
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings

async def run_6d_radar_test():
    print("🎬 [6D Radar Test] 启动全链路集成测试...")
    
    # 模拟用户输入
    user_query = "刚入手的索尼 A7C2，银黑色真的帅炸！在这个阴雨连绵的下午，我想给数码圈的朋友们做个深度测评。它真的是目前最强的全画幅微单吗？大家怎么看？帮我搜几张索尼 A7C2 的实拍图。"
    
    # 初始化状态
    initial_state = {
        "main_messages": [HumanMessage(content=user_query)],
        "active_panel": "main",
        "scenarios": ["seeding"],
        "active_archetype": "general",
        "image_assets": [],
        "pending_images": [],
        "data_dsl": {},
        "style_dsl": {},
        "creator_persona": "硬核数码博主",
        "retrieved_knowledge": {}
    }

    # 编译图
    from langgraph.checkpoint.memory import MemorySaver
    memory = MemorySaver()
    app = compile_my_graph(checkpointer=memory)

    print(f"📡 [Step 1] 发送指令: {user_query}")
    
    # 执行图
    # 由于我们是测试环境，不使用持久化存储
    config = RunnableConfig(configurable={"thread_id": "test_6d_radar"})
    
    final_state = await app.ainvoke(initial_state, config=config)
    
    print("\n--- 🏁 测试结果审计报告 ---")
    
    # 1. 审计意图信号
    intent = final_state.get("intent_result")
    print(f"🎭 [意图探测] 风格:{getattr(intent, 'visual_vibe', 'N/A')} | CTA:{getattr(intent, 'call_to_action', 'N/A')} | 环境:{getattr(intent, 'temporal_context', 'N/A')}")
    
    # 2. 审计积木流 (Blocks)
    data_dsl = final_state.get("data_dsl", {})
    blocks = data_dsl.get("blocks", [])
    block_types = [b["component_type"] for b in blocks]
    print(f"🧱 [区块序列] { ' -> '.join(block_types) }")
    
    # 检查特定积木是否注入成功
    has_weather = "WeatherPolaroid" in block_types
    has_vs = "VersusCard" in block_types
    has_poll = "PollBlock" in block_types
    
    print(f"✅ [物理注入校验] 氛围拍立得:{has_weather} | 对冲卡片:{has_vs} | 互动投票:{has_poll}")
    
    # 3. 审计视觉风格
    style_dsl = final_state.get("style_dsl", {})
    global_vars = style_dsl.get("global_vars", {})
    print(f"🎨 [视觉调性] 背景:{global_vars.get('--bg-color')} | 主色:{global_vars.get('--primary-vibe')}")

    # 4. 审计最终 HTML
    html = final_state.get("final_html", "")
    print(f"📄 [HTML 字节数] {len(html)} 字节")
    
    if has_weather and has_vs and has_poll and global_vars.get("--bg-color") == "#050505":
        print("\n🏆 [结论] 测试完美通过！六维信号已成功穿透至最终物理产物。")
    else:
        print("\n⚠️ [结论] 测试部分通过，请检查信号衰减点。")

if __name__ == "__main__":
    asyncio.run(run_6d_radar_test())
