from app.agents.nodes.component_builder import build_component_fallback, enforce_component_contract
from app.agents.state import UIProjectState


SUPPORTED_COMPONENTS = {
    "TitleBlock",
    "StoryText",
    "ProductSpecCard",
    "RadarChartBlock",
    "VersusCard",
    "PollBlock",
    "CoverSwiper",
    "LocationBlock",
    "WeatherPolaroid",
}


async def verify_note_node(state: UIProjectState) -> dict:
    """
    Deterministic verifier for Note Editor V2.
    在渲染前补齐关键字段、移除不支持的组件，尽量保证页面可渲染。
    """
    data_dsl = dict(state.get("data_dsl", {}))
    blocks = list(data_dsl.get("blocks", []))
    user_query = str(state.get("main_messages", [])[-1].content) if state.get("main_messages") else ""
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    image_assets = state.get("image_assets", [])

    verified_blocks = []
    changed = False

    for block in blocks:
        comp_type = block.get("component_type")
        comp_id = block.get("id")
        if not comp_type or not comp_id:
            changed = True
            continue
        if comp_type not in SUPPORTED_COMPONENTS:
            print(f"⚠️ [Note Verifier] 移除暂不支持的组件: {comp_type} ({comp_id})")
            changed = True
            continue

        current_payload = data_dsl.get(comp_id, {})
        fallback_payload = build_component_fallback(
            comp_type=comp_type,
            comp_id=comp_id,
            content_brief=block.get("content_brief", ""),
            user_query=user_query,
            retrieved_knowledge=retrieved_knowledge,
            image_assets=image_assets,
        )
        verified_payload = enforce_component_contract(comp_type, current_payload, fallback_payload)
        if verified_payload != current_payload:
            data_dsl[comp_id] = verified_payload
            changed = True
        verified_blocks.append(block)

    if len(verified_blocks) != len(blocks):
        data_dsl["blocks"] = verified_blocks

    if not data_dsl.get("page_title"):
        data_dsl["page_title"] = "XHS-Forge Note"
        changed = True

    if changed:
        print(f"✅ [Note Verifier] 已完成结构补强，共校验 {len(verified_blocks)} 个区块。")
        return {"data_dsl": data_dsl}
    return {}
