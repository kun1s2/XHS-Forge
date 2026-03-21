"""Location enrichment on top of the canonical NoteDocument."""

import logging
from copy import deepcopy

from app.tools.amap import place_search_structured_async

logger = logging.getLogger(__name__)

async def enrich_location_blocks(note_document: dict) -> dict:
    """Fill LocationBlock props with POI metadata directly on NoteDocument."""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])

    for block in blocks:
        if not isinstance(block, dict) or str(block.get("type") or "") != "LocationBlock":
            continue

        props = deepcopy(block.get("props") or {})
        poi_name = props.get("poi_name") or props.get("location")
        if not poi_name:
            continue

        try:
            print(f"📍 [位置增强] 发现待补全地点: {poi_name}，正在请求高德地图...")
            pois = await place_search_structured_async(keywords=poi_name, offset=1)
            if not pois:
                print(f"⚠️ [位置增强] 未找到地点「{poi_name}」的真实坐标")
                continue

            best_match = pois[0]
            location_str = best_match.get("location", "")
            real_address = best_match.get("address", "")
            real_name = best_match.get("name", "")
            if location_str and "," in location_str:
                lng_str, lat_str = location_str.split(",")
                props["lng"] = float(lng_str)
                props["lat"] = float(lat_str)

            props["location"] = real_address or props.get("location")
            props["poi_name"] = real_name or poi_name
            block["props"] = props
            print(f"✅ [位置增强] 补全成功: {real_name}")
        except Exception as e:
            logger.error(f"位置增强失败: {e}")
            print(f"❌ [位置增强] 异常: {e}")

    document["blocks"] = blocks
    return document
