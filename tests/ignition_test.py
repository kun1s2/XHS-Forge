import asyncio
import json
import os
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.outline_node import outline_agent
from app.agents.nodes.render_node import render_node
from app.agents.state import UIProjectState
from langchain_core.messages import HumanMessage

async def run_xiaomi_ignition_test():
    print("\n🔥 [X-Forge 4.0 点火演习]: 小米 17 Ultra 争议测评")
    
    # 1. 构造初始状态
    state: UIProjectState = {
        "main_messages": [HumanMessage(content="客观测评一下小米 17 Ultra，说说大家都在吵什么？")],
        "active_panel": "main",
        "scenarios": ["seeding"],
        "active_archetype": "seeding",
        "retrieved_knowledge": {
            "entity_name": "小米 17 Ultra",
            "core_attributes": {"处理器": "骁龙 8 Gen 5", "主摄": "1.5英寸超大底"},
            "known_issues": ["机身太沉 (240g)", "溢价严重 (起售价 6999)", "镜头模组巨大"],
            "key_selling_points": ["地表最强影像", "首发定制骁龙芯片"],
            "summary": "一款极致性能与极致重量并存的影像旗舰。"
        }
    }

    # 2. 执行意图路由 (验证协议打标)
    print("Step 1: 启动意图大脑...")
    intent_res = await intent_agent(state)
    mode = intent_res.get("intent_result").narrative_mode
    intensity = intent_res.get("intent_result").intensity_level
    print(f"📡 [协议拦截] Mode: {mode} | Intensity: {intensity}")
    
    assert mode == "contrast", f"❌ 意图识别错误，预期 contrast，实际 {mode}"
    assert intensity >= 0.7, f"❌ 情绪烈度不足，预期 >= 0.7，实际 {intensity}"
    print("✅ [意图校验通过]")

    # 3. 执行大纲编排 (验证 AST 变异)
    print("\nStep 2: 启动大纲策划...")
    state.update(intent_res)
    outline_res = await outline_agent(state)
    
    ast_json = json.dumps(outline_res["page_outline"], ensure_ascii=False)
    print(f"🌲 [AST 变异预览]: {ast_json[:200]}...")
    
    assert "VersusCard" in ast_json, "❌ [AST 错误]: 未能在冲突场景下自动挂载 VersusCard！"
    print("✅ [AST 编排通过]: VersusCard 已成功注入树结构。")

    # 4. 物理渲染验证
    print("\nStep 3: 启动物理渲染...")
    state["data_dsl"] = outline_res["data_dsl"]
    state["page_outline"] = outline_res["page_outline"]
    
    # 填充 Mock 的数据（模拟工兵已完成任务）
    state["data_dsl"].update({
        "versus_specs": {
            "proText": "地表最强 1.5 英寸超大底，夜景之王！",
            "conText": "半斤重的机身，真的在考验我的腕力..."
        }
    })
    
    render_res = await render_node(state)
    html = render_res.get("final_html", "")
    
    assert "VersusCard" in html or "VS" in html, "❌ [渲染错误]: HTML 中缺失红蓝对峙组件！"
    print("✅ [渲染校验通过]: 物理源码已包含 VersusCard。")

    print("\n🏆 [演习大捷]: 全链路叙事协议闭环验证成功！")

if __name__ == "__main__":
    # 需要设置环境变量才能运行（由于脚本中包含了 intent_agent 调用）
    if os.getenv("LLM_API_KEY"):
        asyncio.run(run_xiaomi_ignition_test())
    else:
        print("⚠️ 演习取消：未检测到弹药 (LLM_API_KEY)")
