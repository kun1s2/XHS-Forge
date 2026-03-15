# app/tools/amap.py — 高德地图 Web 服务工具，对应 .env 的 AMAP_WEB_SERVICE_KEY
"""
地理编码（地址→坐标）、逆地理（坐标→地址）、输入提示、POI 关键字搜索。
未配置 AMAP_WEB_SERVICE_KEY 时返回说明文案。
文档：https://lbs.amap.com/api/webservice/guide/create-project/get-key
"""

import logging
from typing import Any, List, Optional

import httpx

logger = logging.getLogger(__name__)

AMAP_BASE = "https://restapi.amap.com"
_TIMEOUT = 10.0


def _get_key() -> str:
    """从 settings 读取高德 Web 服务 Key，未配置返回空字符串。"""
    from app.core.config import settings
    return (getattr(settings, "AMAP_WEB_SERVICE_KEY", None) or "").strip()


async def _get(url: str, params: dict) -> Optional[dict]:
    """发起 GET 请求，解析 JSON；失败返回 None 并打日志。"""
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as e:
        logger.warning("Amap HTTP error %s: %s", e.response.status_code, url)
        return None
    except Exception as e:
        logger.warning("Amap request error: %s", e)
        return None
    if data.get("status") != "1":
        logger.debug("Amap API status not 1: info=%s", data.get("info"))
        return data  # 仍返回，便于调用方根据 status/info 处理
    return data


# ---------- 地理编码：地址 → 坐标 ----------


async def geocode_async(
    address: str,
    city: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    将结构化地址转为经纬度。address 必填；city 可选，限定城市。
    返回可读字符串；未配置 Key 或无结果时返回说明/错误文案。
    """
    key = (api_key or "").strip() or _get_key()
    if not key:
        return "[高德] 未配置 AMAP_WEB_SERVICE_KEY，请在 .env 中设置。"
    address = (address or "").strip()
    if not address:
        return "[高德] 地理编码：地址不能为空。"
    params: dict[str, Any] = {"key": key, "address": address, "output": "json"}
    if city:
        params["city"] = city.strip()
    data = await _get(f"{AMAP_BASE}/v3/geocode/geo", params)
    if not data:
        return "[高德] 地理编码请求失败。"
    if data.get("status") != "1":
        return f"[高德] 地理编码失败: {data.get('info', '未知')}。"
    geocodes = data.get("geocodes") or []
    if not geocodes:
        return f"[高德] 未找到与「{address}」相关的坐标。"
    lines = []
    for i, g in enumerate(geocodes[:5], 1):
        loc = g.get("location") or ""
        addr = g.get("formatted_address") or g.get("address") or address
        level = g.get("level", "")
        lines.append(f"[{i}] {addr}\n坐标: {loc}\n匹配级别: {level}")
    return "\n\n".join(lines)


async def geocode_structured_async(
    address: str,
    city: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[dict]:
    """地理编码，返回结构化列表，每项含 location, formatted_address, level 等。"""
    key = (api_key or "").strip() or _get_key()
    if not key or not (address or "").strip():
        return []
    params: dict[str, Any] = {"key": key, "address": address.strip(), "output": "json"}
    if city:
        params["city"] = city.strip()
    data = await _get(f"{AMAP_BASE}/v3/geocode/geo", params)
    if not data or data.get("status") != "1":
        return []
    geocodes = data.get("geocodes") or []
    return [
        {
            "location": g.get("location"),
            "formatted_address": g.get("formatted_address") or g.get("address"),
            "province": g.get("province"),
            "city": g.get("city"),
            "district": g.get("district"),
            "level": g.get("level"),
        }
        for g in geocodes
    ]


# ---------- 逆地理：坐标 → 地址 ----------


async def regeo_async(
    location: str,
    extensions: str = "base",
    radius: int = 1000,
    api_key: Optional[str] = None,
) -> str:
    """
    将经纬度转为地址描述。location 格式为 "经度,纬度"。
    extensions: base 仅基本地址，all 含周边 POI/道路等；radius 为搜索半径（米）。
    """
    key = (api_key or "").strip() or _get_key()
    if not key:
        return "[高德] 未配置 AMAP_WEB_SERVICE_KEY，请在 .env 中设置。"
    location = (location or "").strip()
    if not location:
        return "[高德] 逆地理：坐标不能为空，格式为「经度,纬度」。"
    params: dict[str, Any] = {
        "key": key,
        "location": location,
        "output": "json",
        "extensions": extensions if extensions in ("base", "all") else "base",
        "radius": min(max(0, radius), 3000),
    }
    data = await _get(f"{AMAP_BASE}/v3/geocode/regeo", params)
    if not data:
        return "[高德] 逆地理请求失败。"
    if data.get("status") != "1":
        return f"[高德] 逆地理失败: {data.get('info', '未知')}。"
    regeo = data.get("regeocode") or {}
    addr = regeo.get("formatted_address") or regeo.get("addressComponent", {})
    if isinstance(addr, dict):
        comp = addr
        parts = [
            comp.get("province"),
            comp.get("city"),
            comp.get("district"),
            comp.get("township"),
            comp.get("streetNumber", {}).get("street"),
            comp.get("streetNumber", {}).get("number"),
        ]
        addr = "".join(p for p in parts if p) or "（无详细地址）"
    pois = (extensions == "all" and (regeo.get("pois") or [])) or []
    out = f"地址: {addr}"
    if pois:
        out += "\n附近 POI:\n" + "\n".join(
            f"  - {p.get('name', '')} ({p.get('type', '')}) {p.get('address', '')}" for p in pois[:8]
        )
    return out


async def regeo_structured_async(
    location: str,
    extensions: str = "base",
    radius: int = 1000,
    api_key: Optional[str] = None,
) -> Optional[dict]:
    """逆地理，返回结构化对象：formatted_address, addressComponent, pois 等。"""
    key = (api_key or "").strip() or _get_key()
    if not key or not (location or "").strip():
        return None
    params = {
        "key": key,
        "location": location.strip(),
        "output": "json",
        "extensions": extensions if extensions in ("base", "all") else "base",
        "radius": min(max(0, radius), 3000),
    }
    data = await _get(f"{AMAP_BASE}/v3/geocode/regeo", params)
    if not data or data.get("status") != "1":
        return None
    return data.get("regeocode")


# ---------- 输入提示 ----------


async def input_tips_async(
    keywords: str,
    city: Optional[str] = None,
    location: Optional[str] = None,
    api_key: Optional[str] = None,
) -> str:
    """
    输入提示：根据关键词返回联想地点列表，适合搜索框补全。
    location 为 "经度,纬度" 时可在该点附近优先排序。
    """
    key = (api_key or "").strip() or _get_key()
    if not key:
        return "[高德] 未配置 AMAP_WEB_SERVICE_KEY，请在 .env 中设置。"
    keywords = (keywords or "").strip()
    if not keywords:
        return "[高德] 输入提示：关键词不能为空。"
    params: dict[str, Any] = {"key": key, "keywords": keywords, "output": "json"}
    if city:
        params["city"] = city.strip()
    if location:
        params["location"] = location.strip()
    data = await _get(f"{AMAP_BASE}/v3/assistant/inputtips", params)
    if not data:
        return "[高德] 输入提示请求失败。"
    if data.get("status") != "1":
        return f"[高德] 输入提示失败: {data.get('info', '未知')}。"
    tips = data.get("tips") or []
    if not tips:
        return f"[高德] 未找到与「{keywords}」相关的提示。"
    lines = [f"[{i}] {t.get('name', '')} | {t.get('district', '')} | {t.get('address', '')}" for i, t in enumerate(tips[:10], 1)]
    return "\n".join(lines)


async def input_tips_structured_async(
    keywords: str,
    city: Optional[str] = None,
    location: Optional[str] = None,
    api_key: Optional[str] = None,
) -> List[dict]:
    """输入提示，返回结构化列表，每项含 id, name, district, address, location 等。"""
    key = (api_key or "").strip() or _get_key()
    if not key or not (keywords or "").strip():
        return []
    params = {"key": key, "keywords": keywords.strip(), "output": "json"}
    if city:
        params["city"] = city.strip()
    if location:
        params["location"] = location.strip()
    data = await _get(f"{AMAP_BASE}/v3/assistant/inputtips", params)
    if not data or data.get("status") != "1":
        return []
    return data.get("tips") or []


# ---------- POI 关键字搜索 ----------


async def place_search_async(
    keywords: str,
    city: Optional[str] = None,
    page: int = 1,
    offset: int = 10,
    api_key: Optional[str] = None,
) -> str:
    """
    POI 关键字搜索。keywords 为关键词；city 可选；page/offset 分页。
    返回可读字符串，适合展示给用户或 Agent。
    """
    key = (api_key or "").strip() or _get_key()
    if not key:
        return "[高德] 未配置 AMAP_WEB_SERVICE_KEY，请在 .env 中设置。"
    keywords = (keywords or "").strip()
    if not keywords:
        return "[高德] POI 搜索：关键词不能为空。"
    params: dict[str, Any] = {
        "key": key,
        "keywords": keywords,
        "output": "json",
        "page": max(1, page),
        "offset": min(max(1, offset), 25),
    }
    if city:
        params["city"] = city.strip()
    data = await _get(f"{AMAP_BASE}/v3/place/text", params)
    if not data:
        return "[高德] POI 搜索请求失败。"
    if data.get("status") != "1":
        return f"[高德] POI 搜索失败: {data.get('info', '未知')}。"
    pois = data.get("pois") or []
    total = int(data.get("count", 0))
    if not pois:
        return f"[高德] 未找到与「{keywords}」相关的 POI。"
    lines = [f"共 {total} 条结果（当前页 {len(pois)} 条）："]
    for i, p in enumerate(pois, 1):
        name = p.get("name", "")
        addr = p.get("address", "")
        loc = p.get("location", "")
        typ = p.get("type", "")
        tel = p.get("tel", "")
        line = f"[{i}] {name}"
        if typ:
            line += f" | {typ}"
        if addr:
            line += f"\n    地址: {addr}"
        if loc:
            line += f" 坐标: {loc}"
        if tel:
            line += f" 电话: {tel}"
        lines.append(line)
    return "\n".join(lines)


async def place_search_structured_async(
    keywords: str,
    city: Optional[str] = None,
    page: int = 1,
    offset: int = 10,
    api_key: Optional[str] = None,
) -> List[dict]:
    """POI 关键字搜索，返回结构化列表，每项含 id, name, location, address, type, tel 等。"""
    key = (api_key or "").strip() or _get_key()
    if not key or not (keywords or "").strip():
        return []
    params = {
        "key": key,
        "keywords": keywords.strip(),
        "output": "json",
        "page": max(1, page),
        "offset": min(max(1, offset), 25),
    }
    if city:
        params["city"] = city.strip()
    data = await _get(f"{AMAP_BASE}/v3/place/text", params)
    if not data or data.get("status") != "1":
        return []
    return data.get("pois") or []
