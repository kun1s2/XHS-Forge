import asyncio
import json
from app.agents.state import UIProjectState
from app.tools.image_recognition import describe_image

async def asset_processor_node(state: UIProjectState) -> dict:
    """
    拿到新图片 -> 【并发】调用 describe_image 打标 -> 仅返回新资产供系统追加，清空 pending_images。
    """
    pending_images = state.get("pending_images") or []
    current_assets = state.get("image_assets") or []

    if not pending_images:
        return {}

    # ====== ✨ 魔法 1：去重过滤，配合 operator.add ======
    # 提取已存在的 URL 集合，防止用户重复发同一张图导致图库冗余
    existing_urls = {a.get("url") for a in current_assets if isinstance(a, dict) and a.get("url")}
    
    # 只挑出真正“新鲜”的图片
    new_images = [url for url in pending_images if url not in existing_urls]

    if not new_images:
        print("🖼️ [资产打标大脑] 所有待处理图片已存在，跳过打标。")
        return {"pending_images": []} # 记得清空队列

    print(f"🖼️ [资产打标大脑] 发现 {len(new_images)} 张新图片，正在【并发】进行视觉识别...")

    # 定义处理单张图片的闭包函数
    async def process_single_image(img_url: str) -> dict:
        try:
            # ✨ 升级：多模态真实取色 (Vision-to-Hex)
            # 要求提取主色调（Primary）和点缀色（Accent）
            vibe_prompt = """请精准分析这张图片：
1. 用一两句话描述内容和构图氛围。
2. 提取一个最能代表该图片灵魂的主色调（Primary Hex Color）。
3. 提取一个能与之形成高级感搭配的点缀色（Accent Hex Color）。
请严格按照以下 JSON 格式输出：
{"desc": "...", "primary": "#......", "accent": "#......"}"""
            
            raw_result = await asyncio.to_thread(describe_image, img_url, prompt=vibe_prompt)
            
            try:
                # 兼容 Markdown 格式清洗
                clean_json = raw_result.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0].strip()
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0].strip()
                
                data = json.loads(clean_json)
                desc = data.get("desc", "用户上传的图片")
                primary = data.get("primary", "#ff2442") 
                accent = data.get("accent", "#333333")
            except:
                desc = raw_result
                primary = "#ff2442"
                accent = "#333333"

            print(f"👁️ [视觉调性引擎] 打标成功: {desc} | 主色: {primary} | 点缀: {accent}")
            return {
                "url": img_url, 
                "desc": desc, 
                "vibe_color": primary, # 兼容老代码字段
                "primary_color": primary,
                "accent_color": accent
            }
        except Exception as e:
            print(f"❌ 视觉引擎异常 ({img_url}): {e}")
            return {"url": img_url, "desc": "用户上传的图片", "vibe_color": "#ff2442", "primary_color": "#ff2442", "accent_color": "#333333"}

    # ====== ✨ 魔法 2：并发之王 asyncio.gather ======
    # 如果有 3 张图，它们会同时向大模型发起请求！耗时从 12 秒瞬间压缩到 4 秒！
    new_assets_tuple = await asyncio.gather(*(process_single_image(url) for url in new_images))

    # ====== ✨ 魔法 3：纯净的增量输出 ======
    # 绝不再把 current_assets 混合进来了！
    # 直接把纯净的 new_assets 发给状态机，底层的 operator.add 会自动把它们挂载到老图库后面！
    return {
        "image_assets": list(new_assets_tuple),
        "pending_images": [], # 必须清空队列，防止无限循环
    }