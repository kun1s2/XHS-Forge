import asyncio
import json
import os
from app.agents.nodes.render_node import render_node
from app.agents.nodes.intent_node import intent_agent
from app.agents.nodes.patch_node import surgical_patch_agent
from app.agents.state import UIProjectState, merge_dsl
from langchain_core.messages import HumanMessage

# --- 🛡️ Sentinel-X Mock Data ---

MOCK_DATA_DSL = {
    "page_order": ["title_1", "swiper_1", "inter_1"],
    "title_1": {"type": "TitleBlock", "title": "Sentinel-X Test Title"},
    "swiper_1": {"type": "CoverSwiper", "image_urls": ["https://picsum.photos/400/600"]},
    "inter_1": {"type": "InteractionsBar", "likes": "999+", "collects": "888", "comments": "66"}
}

MOCK_STYLE_DSL = {
    "global_vars": {
        "--primary-vibe": "#ff2442",
        "--bg-color": "#ffffff"
    },
    "title_1": {"css_classes": "px-4 pt-4"},
    "swiper_1": {"css_classes": "mt-2"},
    "inter_1": {"css_classes": "px-4 py-3"}
}

# --- 🚀 Test Cases ---

async def test_render_node():
    print("\n🔍 [Sentinel-X] Testing render_node...")
    state: UIProjectState = {
        "data_dsl": MOCK_DATA_DSL,
        "style_dsl": MOCK_STYLE_DSL
    }
    
    result = await render_node(state)
    html = result.get("final_html", "")
    
    # Assertions
    if "Sentinel-X Test Title" in html:
        print("✅ render_node: Title found in HTML")
    else:
        print("❌ render_node: Title MISSING from HTML")
        
    if "InteractionsBar" in html or "🤍" in html:
        print("✅ render_node: InteractionsBar rendered successfully")
    else:
        print("❌ render_node: InteractionsBar MISSING (Unknown Social Component?)")

async def test_intent_routing():
    print("\n🔍 [Sentinel-X] Testing intent_node (Requires API Key)...")
    if not os.getenv("LLM_API_KEY"):
        print("⚠️ Skipped: LLM_API_KEY not found in env")
        return

    state: UIProjectState = {
        "main_messages": [HumanMessage(content="帮我改一下标题，改成：哨兵来了")],
        "data_dsl": MOCK_DATA_DSL
    }
    
    try:
        result = await intent_agent(state)
        route = result.get("intent_route", "")
        print(f"📡 Intent Route: {route}")
        if "patch" in route.lower():
            print("✅ intent_node: Correctly routed to patch_node")
        else:
            print(f"❌ intent_node: Unexpected route -> {route}")
    except Exception as e:
        print(f"💥 intent_node failed: {e}")

async def test_patch_logic():
    print("\n🔍 [Sentinel-X] Testing surgical_patch_agent (Requires API Key)...")
    if not os.getenv("LLM_API_KEY"):
        print("⚠️ Skipped: LLM_API_KEY not found in env")
        return

    # Simulate targeting the title
    state: UIProjectState = {
        "main_messages": [HumanMessage(content="把标题改成：Sentinel-X 正在巡逻")],
        "data_dsl": MOCK_DATA_DSL,
        "selected_element_id": "title_1"
    }
    
    try:
        result = await surgical_patch_agent(state)
        new_data = result.get("data_dsl", {})
        print(f"🛠️ Patch Output: {json.dumps(new_data, ensure_ascii=False)}")
        
        # Verify merge_dsl logic
        merged = merge_dsl(MOCK_DATA_DSL, new_data)
        if merged["title_1"]["title"] == "Sentinel-X 正在巡逻":
            print("✅ patch_node: Title successfully updated in DSL")
        else:
            print(f"❌ patch_node: Update failed. Current title: {merged['title_1'].get('title')}")
    except Exception as e:
        print(f"💥 surgical_patch_agent failed: {e}")

async def run_all():
    await test_render_node()
    await test_intent_routing()
    await test_patch_logic()
    print("\n🏁 [Sentinel-X] Smoke test completed.")

if __name__ == "__main__":
    asyncio.run(run_all())
