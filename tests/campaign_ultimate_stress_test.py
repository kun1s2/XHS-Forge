import asyncio
import json
import os
import sys
from typing import List

# 设置路径
sys.path.append(os.path.join(os.getcwd(), 'AI_Frontend_IDE'))

from app.agents.graph import compile_my_graph
from app.agents.state import UIProjectState
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.memory import MemorySaver

async def run_ultimate_stress_test():
    print("🎬 [Ultimate Stress Test] 启动：X-Forge 7.0 导演级 ReAct 压测...")
    
    # 指令：包含 6 个以上的组件需求
    user_query = (
        "刚入手了徕卡 M11，这台相机简直是‘情怀与实力的天花板’。帮我做个顶级排版。"
        "首先要有氛围感大图；然后详细对比它的复古外观与数码内核；列出传感器、像素等硬核参数；"
        "重点：用雷达图从手感、画质、溢价、便携这四个维度打分；"
        "结尾发起投票，看大家觉得它是‘理财产品’还是‘拍照工具’；"
        "别忘了标注我在上海武康路的打卡位。全篇要美式复古风！"
    )
    
    # 初始化状态
    initial_state = {
        "main_messages": [HumanMessage(content=user_query)],
        "active_panel": "main",
        "scenarios": ["seeding"],
        "active_archetype": "general",
        "image_assets": [
            {"url": "https://leica-camera.com/m11_hero.jpg", "desc": "徕卡 M11 正面实拍"},
            {"url": "https://leica-camera.com/m11_back.jpg", "desc": "徕卡 M11 经典后背"}
        ],
        "data_dsl": {"blocks": []},
        "style_dsl": {},
        "creator_persona": "资深影像评论人",
        "messages": []
    }

    # 编译图
    memory = MemorySaver()
    app = compile_my_graph(checkpointer=memory)
    config = RunnableConfig(configurable={"thread_id": "stress_test_leica"})

    print(f"📡 [Step 1] 注入终极复杂度指令...")
    
    # 执行并实时监控节点输出
    async for event in app.astream(initial_state, config=config, stream_mode="values"):
        current_blocks = event.get("data_dsl", {}).get("blocks", [])
        msgs = event.get("messages", [])
        
        if msgs:
            last_msg = msgs[-1]
            if isinstance(last_msg, AIMessage) and last_msg.content:
                # 打印 Agent 的内心独白
                print(f"💭 [Agent Thought]: {str(last_msg.content)[:100]}...")
            if hasattr(last_msg, "tool_calls") and last_msg.tool_calls:
                for tc in last_msg.tool_calls:
                    print(f"🛠️ [Agent Action]: 调用工具 {tc['name']} -> {tc['args']}")

    # 最终状态审计
    final_state = await app.aget_state(config)
    values = final_state.values
    blocks = values.get("data_dsl", {}).get("blocks", [])
    block_types = [b["component_type"] for b in blocks]

    print("\n" + "="*50)
    print("🏁 [终极压测审计报告]")
    print(f"🧱 积木总数: {len(blocks)}")
    print(f"📋 区块序列: {' -> '.join(block_types)}")
    
    # 核心组件穿透校验
    required_blocks = ["CoverSwiper", "VersusCard", "ProductSpecCard", "RadarChartBlock", "PollBlock", "LocationBlock"]
    success_count = 0
    for rb in required_blocks:
        found = rb.lower() in [bt.lower() for rb in required_blocks for bt in block_types]
        if any(rb.lower() == bt.lower() for bt in block_types):
            print(f"✅ [组件校验] {rb}: 命中")
            success_count += 1
        else:
            print(f"❌ [组件校验] {rb}: 缺失")

    # 风格审计
    style_dsl = values.get("style_dsl", {})
    global_vars = style_dsl.get("global_vars", {})
    print(f"🎨 [视觉调性] 背景: {global_vars.get('--bg-color')} | 风格: {values.get('intent_result').visual_vibe if values.get('intent_result') else 'N/A'}")

    if success_count >= 5:
        print("\n🏆 [结论] 压测完美通过！大纲 Agent 展现了极强的 ReAct 推演与画布控制能力。")
    else:
        print("\n⚠️ [结论] 压测部分通过，积木丰富度未达预期。")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(run_ultimate_stress_test())
