import asyncio
import json
import os
from app.agents.nodes.render_node import render_node
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.outline_node import outline_agent
from app.agents.nodes.style_node import style_agent
from app.agents.nodes.component_builder import component_builder_node
from app.agents.state import UIProjectState, ComponentTaskState
from langchain_core.messages import HumanMessage

# --- 🛡️ Sentinel-X 极端火控数据构造 ---

# 1. 模拟深层嵌套 AST (用于测试递归渲染)
DEEP_NESTED_AST = {
    "id": "root_container",
    "component_type": "Container",
    "props": {"variant": "glassmorphism"},
    "children": [
        {
            "id": "bento_grid_perf",
            "component_type": "BentoGrid",
            "props": {"cols": 2},
            "children": [
                {
                    "id": "perf_text",
                    "component_type": "StoryText",
                    "props": {"col_span": 2},
                    "content_brief": "仅撰写性能参数爆料，强调跑分破300万"
                },
                {
                    "id": "spec_1",
                    "component_type": "ProductSpecCard",
                    "props": {"col_span": 1},
                    "content_brief": "提炼CPU和内存规格"
                }
            ]
        }
    ]
}

# --- 🚀 压力测试用例 ---

async def test_recursive_render_stress():
    print("\n🔍 [火控校验 1] 递归深度压力测试...")
    state: UIProjectState = {
        "data_dsl": {
            "root": DEEP_NESTED_AST,
            "perf_text": {"paragraphs": ["测试性能文案"]},
            "spec_1": {"title": "测试规格", "core_features": ["参数A"]}
        },
        "style_dsl": {} # style_node 会负责填充
    }
    
    # 模拟经过 style_node 处理
    result_styled = await style_agent(state)
    html_result = await render_node(result_styled)
    html = html_result.get("final_html", "")
    
    # 断言：检查递归渲染是否完整
    if "grid-cols-2" in html and "perf_text" in html and "spec_1" in html:
        print("✅ 递归测试通过：BentoGrid 及其深层子节点已完美渲染。")
    else:
        print("❌ 递归测试失败：部分深层节点在 HTML 中丢失。")

async def test_content_collision_check():
    print("\n🔍 [火控校验 2] 文案切片防碰撞测试 (需要大模型)...")
    if not os.getenv("LLM_API_KEY"):
        print("⚠️ 跳过：未检测到 API Key")
        return

    # 模拟主编下发的互斥任务
    tasks = [
        {"id": "text_unbox", "type": "StoryText", "brief": "【开箱】仅描述撕膜的快感和外观颜值，严禁提性能。"},
        {"id": "text_perf", "type": "StoryText", "brief": "【性能】仅描述跑分和游戏帧率，严禁提外观。"}
    ]
    
    results = []
    for t in tasks:
        task_state: ComponentTaskState = {
            "component_id": t["id"],
            "component_type": t["type"],
            "content_brief": t["brief"],
            "user_query": "写一篇小米17 Ultra测评",
            "active_archetype": "seeding",
            "retrieved_knowledge": "小米17 Ultra，外观钛金属，跑分300w",
            "creator_persona": "专业博主"
        }
        res = await component_builder_node(task_state)
        results.append(res["data_dsl"][t["id"]])
    
    # 交叉检查：开箱文案是否提了性能？
    unbox_content = str(results[0].get("paragraphs", ""))
    perf_content = str(results[1].get("paragraphs", ""))
    
    if "跑分" not in unbox_content and "外观" not in perf_content:
        print("✅ 防碰撞通过：两个组件任务简报执行精准，无内容重叠。")
    else:
        print(f"⚠️ 防碰撞瑕疵：内容可能存在重叠。开箱: {unbox_content[:30]} | 性能: {perf_content[:30]}")

async def test_semantic_mapping_vibe():
    print("\n🔍 [火控校验 3] 语义化样式压力测试...")
    styles = ["neon", "glassmorphism", "flat-dark"]
    
    for vibe in styles:
        node = {
            "id": "vibe_test",
            "component_type": "ProductCard",
            "props": {"variant": vibe, "animation": "fade-up"}
        }
        from app.agents.nodes.style_node import apply_visual_styles
        styled_node = apply_visual_styles(node, {})
        classes = styled_node.get("computed_classes", "")
        
        print(f"📡 风格 [{vibe}] 映射类名: {classes}")
        if classes:
            print(f"✅ 映射成功：{vibe} 准确转化为 Tailwind 组合。")
        else:
            print(f"❌ 映射失败：{vibe} 未命中映射表。")

async def run_full_smoke():
    print("🚀 [Sentinel-X] 开启全量火控校验模式...")
    await test_recursive_render_stress()
    await test_content_collision_check()
    await test_semantic_mapping_vibe()
    print("\n🏁 [Sentinel-X] 校验任务结束。")

if __name__ == "__main__":
    asyncio.run(run_full_smoke())
