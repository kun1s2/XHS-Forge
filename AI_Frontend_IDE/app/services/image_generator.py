import logging
import json
import asyncio
import re
from copy import deepcopy
from app.tools.image_generation import generate_image
from app.tools.image_recognition import describe_image
from app.core.llm_factory import create_llm
from app.core.config import settings

logger = logging.getLogger(__name__)

async def auto_generate_images(note_document: dict, archetype: str) -> tuple[dict, list[dict]]:
    """Generate missing media directly onto NoteDocument blocks."""
    document = deepcopy(note_document or {})
    blocks = list(document.get("blocks") or [])
    new_assets = []
    
    # 场景判断：加入 seeding (种草)，允许自动生图
    if archetype not in ["travel", "gourmet", "seeding"]:
        return document, []

    # ✨ 提取页面全局主体，用于构思生图 Prompt
    page_title = ((document.get("document_meta") or {}).get("title") or "").strip()
    title_block = next(
        (
            str((block.get("props") or {}).get("title") or "").strip()
            for block in blocks
            if isinstance(block, dict) and block.get("type") == "TitleBlock"
        ),
        "",
    )
    subject = title_block or page_title or "宝藏好物"
    # 清理掉特殊字符
    subject = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9 ]", " ", subject).strip()

    # 初始化一个轻量级模型来生成生图 Prompt
    llm = create_llm(model=settings.LLM_MODEL, api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

    # ✨ 审美多元化：根据场景分配最合适的摄影风格
    AESTHETIC_MAP = {
        "seeding": "Product photography, studio lighting, clean background, 8k resolution, minimalist, premium texture",
        "gourmet": "Food photography, close-up, warm light, steam, high-end restaurant vibe, appetizing",
        "travel": "Landscape photography, wide angle, natural lighting, cinematic colors, travel magazine style",
        "general": "High quality photography, soft lighting, balanced composition"
    }
    aesthetic_style = AESTHETIC_MAP.get(archetype, AESTHETIC_MAP["general"])

    for block in blocks:
        if not isinstance(block, dict):
            continue

        comp_id = str(block.get("id") or "")
        props = deepcopy(block.get("props") or {})
        comp_type = str(block.get("type") or "")

        # 逻辑：如果是轮播图且没有图片，或者商品卡片没有图片
        needs_image = False
        target_field = ""

        if comp_type == "CoverSwiper" and not props.get("image_urls"):
            needs_image = True
            target_field = "image_urls"
        elif comp_type == "ProductCard" and not props.get("image_url"):
            needs_image = True
            target_field = "image_url"

        if needs_image:
            print(f"🎨 [智能配图] 正在为「{subject}」构思指令 (场景: {archetype})...")

            # 1. 构思生图 Prompt
            context = f"主题: {subject}, 组件类型: {comp_type}, 描述: {props.get('desc', '')}"
            prompt_gen_msg = f"请为以下内容生成一段极简的 CogView 生图提示词（英文）。风格要求：{aesthetic_style}。内容主体：{context}"

            try:
                image_prompt_resp = await llm.ainvoke(prompt_gen_msg)
                image_prompt = image_prompt_resp.content
                # 2. 调用生图工具
                generated_url = await asyncio.to_thread(generate_image, image_prompt)
                
                if generated_url:
                    # 3. 填充 DSL
                    if target_field == "image_urls":
                        props["image_urls"] = [generated_url]
                    else:
                        props["image_url"] = generated_url
                    
                    # 4. ✨ 闭环关键：立即进行视觉取色，确保 Vibe 统一
                    print(f"👁️ [智能配图] 图片已生成，正在提取视觉调性...")
                    vibe_prompt = '{"desc": "...", "primary": "#......", "accent": "#......"}'
                    vibe_result_raw = await asyncio.to_thread(describe_image, generated_url, prompt=f"分析这张图的配色并输出JSON: {vibe_prompt}")
                    
                    # 简单解析并加入待同步资产列表
                    try:
                        # 兼容 Markdown
                        clean_vibe = re.sub(r"```json\n?|```", "", vibe_result_raw).strip()
                        vibe_data = json.loads(clean_vibe)
                        new_assets.append({
                            "url": generated_url,
                            "desc": vibe_data.get("desc", f"AI生成的{subject}"),
                            "primary_color": vibe_data.get("primary", "#ff2442"),
                            "accent_color": vibe_data.get("accent", "#333333"),
                            "vibe_color": vibe_data.get("primary", "#ff2442")
                        })
                    except:
                        new_assets.append({"url": generated_url, "desc": f"AI生成的{subject}", "vibe_color": "#ff2442"})
                    block["props"] = props
                    print(f"✅ [智能配图] 组件 {comp_id} 配图成功")
            except Exception as e:
                logger.error(f"智能配图失败: {e}")

    document["blocks"] = blocks
    return document, new_assets
