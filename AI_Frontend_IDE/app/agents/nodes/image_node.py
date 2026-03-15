from app.agents.state import UIProjectState
from app.tools.image_recognition import describe_image


async def image_agent(state: UIProjectState) -> dict:
    """
    多模态节点。读取 image_assets 或 image_urls，通过图片识别工具生成场景描述并写入 visual_perception。
    """
    # 优先使用全局图库（url+desc），否则回退到 image_urls
    image_assets = state.get("image_assets") or []
    image_urls = state.get("image_urls") or []
    urls_with_desc = []
    if image_assets:
        for item in image_assets:
            if isinstance(item, dict) and item.get("url"):
                urls_with_desc.append((item["url"], item.get("desc") or "用户上传图片"))
    if not urls_with_desc and image_urls:
        for u in image_urls:
            if isinstance(u, str) and u.strip():
                urls_with_desc.append((u.strip(), "用户上传图片"))

    if not urls_with_desc:
        return {}

    current_perception = list(state.get("visual_perception") or [])
    for url, user_desc in urls_with_desc:
        scene_description = describe_image(url)
        current_perception.append({
            "url": url,
            "desc": user_desc,
            "scene_description": scene_description,
            "main_colors": [],
        })

    return {"visual_perception": current_perception}