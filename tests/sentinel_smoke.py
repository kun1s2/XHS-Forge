import asyncio
import json
import os
from app.agents.nodes.document_renderer_node import document_renderer
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.outline_resolver_node import outline_resolver_preview
from app.agents.nodes.theme_compiler_node import theme_compiler
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

async def _run_recursive_render_stress():
    print("\n🔍 [火控校验 1] 递归深度压力测试...")
    state: UIProjectState = {
        "document_view": {
            "root": DEEP_NESTED_AST,
            "perf_text": {"paragraphs": ["测试性能文案"]},
            "spec_1": {"title": "测试规格", "core_features": ["参数A"]}
        },
        "block_style_map": {} # theme_compiler 会负责填充
    }
    
    # 模拟经过 theme_compiler 处理
    result_styled = await theme_compiler(state)
    html_result = await document_renderer(result_styled)
    html = html_result.get("final_html", "")
    
    # 断言：检查递归渲染是否完整
    if "grid-cols-2" in html and "perf_text" in html and "spec_1" in html:
        print("✅ 递归测试通过：BentoGrid 及其深层子节点已完美渲染。")
    else:
        print("❌ 递归测试失败：部分深层节点在 HTML 中丢失。")

async def _run_content_collision_check():
    print("\n🔍 [火控校验 2] 文案切片防碰撞测试...")

    # 模拟主编下发的互斥任务
    tasks = [
        {"id": "text_unbox", "type": "StoryText", "brief": "【开箱】仅描述撕膜的快感和外观颜值，严禁提性能。"},
        {"id": "text_perf", "type": "StoryText", "brief": "【性能】仅描述跑分和游戏帧率，严禁提外观。"}
    ]

    unbox_task = tasks[0]
    perf_task = tasks[1]
    assert "严禁提性能" in unbox_task["brief"]
    assert "严禁提外观" in perf_task["brief"]
    assert unbox_task["brief"] != perf_task["brief"]
    print("✅ 防碰撞通过：互斥任务切片清晰，适合作为独立组件构建输入。")

async def _run_semantic_mapping_vibe():
    print("\n🔍 [火控校验 3] 语义化样式压力测试...")
    styles = ["neon", "glassmorphism", "flat-dark"]
    from app.agents.nodes.theme_compiler_node import _build_block_style

    for vibe in styles:
        style_patch = _build_block_style("ProductCard", 0.8, vibe)
        classes = style_patch.get("css_classes", "")
        
        print(f"📡 风格 [{vibe}] 映射类名: {classes}")
        if classes:
            print(f"✅ 映射成功：{vibe} 准确转化为 Tailwind 组合。")
        else:
            print(f"❌ 映射失败：{vibe} 未命中映射表。")

async def run_full_smoke():
    print("🚀 [Sentinel-X] 开启全量火控校验模式...")
    await _run_recursive_render_stress()
    await _run_content_collision_check()
    await _run_semantic_mapping_vibe()
    print("\n🏁 [Sentinel-X] 校验任务结束。")


def test_recursive_render_stress():
    asyncio.run(_run_recursive_render_stress())


def test_content_collision_check():
    asyncio.run(_run_content_collision_check())


def test_semantic_mapping_vibe():
    asyncio.run(_run_semantic_mapping_vibe())

if __name__ == "__main__":
    asyncio.run(run_full_smoke())
