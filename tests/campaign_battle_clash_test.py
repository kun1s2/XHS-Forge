import asyncio
import json
import os
from app.agents.graph import compile_my_graph
from app.agents.state import UIProjectState
from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from app.core.config import settings
from langgraph.checkpoint.memory import MemorySaver

async def run_battle_clash_test():
    print("🎬 [Battle Clash Test] 启动舆情对冲全链路测试...")
    
    # 模拟一个极具争议的话题
    user_query = "华为 Mate 60 和 iPhone 15 到底谁才是年度机皇？别说废话，直接对比它们的优缺点，告诉我哪个更值得入！"
    
    # 初始化状态
    initial_state = {
        "main_messages": [HumanMessage(content=user_query)],
        "active_panel": "main",
        "scenarios": ["seeding"],
        "active_archetype": "general",
        "image_assets": [],
        "pending_images": [],
        "document_view": {},
        "block_style_map": {},
        "creator_persona": "硬核数码博主",
        "retrieved_knowledge": {}
    }

    # 编译图
    memory = MemorySaver()
    app = compile_my_graph(checkpointer=memory)

    print(f"📡 [Step 1] 发送指令: {user_query}")
    
    # 执行图
    config = RunnableConfig(configurable={"thread_id": "test_battle_clash"})
    
    final_state = await app.ainvoke(initial_state, config=config)
    
    print("\n--- 🏁 对冲引擎审计报告 ---")
    
    # 1. 审计争议识别
    know = final_state.get("retrieved_knowledge", {})
    clash_report = know.get("clash_report")
    print(f"🧐 [争议识别] 是否争议: {final_state.get('has_controversy')} | 标题: {clash_report.get('clash_title') if clash_report else 'N/A'}")
    
    # 2. 审计并发生成结果
    battle_report = know.get("battle_report")
    if battle_report:
        print(f"⚔️ [对冲合成] 成功！")
        print(f"🔴 红榜摘要: {battle_report['pros']['summary']}")
        print(f"⚫ 黑榜摘要: {battle_report['cons']['summary']}")
    else:
        print(f"❌ [对冲合成] 失败：未找到 battle_report")

    # 3. 审计区块与数据填充
    document_view = final_state.get("document_view", {})
    blocks = document_view.get("blocks", [])
    block_types = [b["component_type"] for b in blocks]
    print(f"🧱 [区块序列] { ' -> '.join(block_types) }")
    
    # 查找 VersusCard 数据
    vs_card_id = next((b["id"] for b in blocks if b["component_type"] == "VersusCard"), None)
    if vs_card_id and vs_card_id in document_view:
        vs_data = document_view[vs_card_id]
        print(f"📦 [VersusCard 数据校验] 标题存在: {bool(vs_data.get('title'))} | Pros存在: {bool(vs_data.get('proText'))}")
    else:
        print(f"⚠️ [VersusCard 数据校验] 未在 document_view 中找到 VersusCard 数据")

    # 4. 结论
    if battle_report and "VersusCard" in block_types and vs_card_id in document_view:
        print("\n🏆 [结论] 舆情对冲测试完美通过！多线程并发生成与物理合成逻辑闭环。")
    else:
        print("\n⚠️ [结论] 测试未完全达标，请检查 Graph 链路或节点输出。")

if __name__ == "__main__":
    asyncio.run(run_battle_clash_test())
