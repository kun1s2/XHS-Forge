# app/services/image_generator.py
import logging
import json
import asyncio
import re
from typing import List, Dict, Any
from app.tools.image_generation import generate_image
from app.tools.image_recognition import describe_image
from langchain_openai import ChatOpenAI
from app.core.config import settings

logger = logging.getLogger(__name__)

async def auto_generate_images(data_dsl: dict, archetype: str) -> dict:
    """
    【AI 智能配图服务】：如果页面缺少图片，自动调用 CogView 生成契合氛围的图片。
    """
    enriched_dsl = data_dsl.copy()
    new_assets = []
    
    # 场景判断：加入 seeding (种草)，允许自动生图
    if archetype not in ["travel", "gourmet", "seeding"]:
        return enriched_dsl, []

    # ✨ 提取页面全局主体，用于构思生图 Prompt
    page_title = data_dsl.get("page_title", "")
    title_block = next((v.get("title") for v in data_dsl.values() if isinstance(v, dict) and v.get("type") == "TitleBlock"), "")
    subject = title_block or page_title or "宝藏好物"
    # 清理掉特殊字符
    subject = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9 ]", " ", subject).strip()

    # 初始化一个轻量级模型来生成生图 Prompt
    llm = ChatOpenAI(model=settings.LLM_SMALL_MODEL, api_key=settings.LLM_API_KEY, base_url=settings.LLM_BASE_URL)

    # ✨ 审美多元化：根据场景分配最合适的摄影风格
    AESTHETIC_MAP = {
        "seeding": "Product photography, studio lighting, clean background, 8k resolution, minimalist, premium texture",
        "gourmet": "Food photography, close-up, warm light, steam, high-end restaurant vibe, appetizing",
        "travel": "Landscape photography, wide angle, natural lighting, cinematic colors, travel magazine style",
        "general": "High quality photography, soft lighting, balanced composition"
    }
    aesthetic_style = AESTHETIC_MAP.get(archetype, AESTHETIC_MAP["general"])

    for comp_id, comp_data in enriched_dsl.items():
        if not isinstance(comp_data, dict):
            continue

        comp_type = comp_data.get("type")

        # 逻辑：如果是轮播图且没有图片，或者商品卡片没有图片
        needs_image = False
        target_field = ""

        if comp_type == "CoverSwiper" and not comp_data.get("image_urls"):
            needs_image = True
            target_field = "image_urls"
        elif comp_type == "ProductCard" and not comp_data.get("image_url"):
            needs_image = True
            target_field = "image_url"

        if needs_image:
            print(f"🎨 [智能配图] 正在为「{subject}」构思指令 (场景: {archetype})...")

            # 1. 构思生图 Prompt
            context = f"主题: {subject}, 组件类型: {comp_type}, 描述: {comp_data.get('desc', '')}"
            prompt_gen_msg = f"请为以下内容生成一段极简的 CogView 生图提示词（英文）。风格要求：{aesthetic_style}。内容主体：{context}"

            try:
                image_prompt_resp = await llm.ainvoke(prompt_gen_msg)
                image_prompt = image_prompt_resp.content
                # 2. 调用生图工具
                generated_url = await asyncio.to_thread(generate_image, image_prompt)
                
                if generated_url:
                    # 3. 填充 DSL
                    if target_field == "image_urls":
                        enriched_dsl[comp_id]["image_urls"] = [generated_url]
                    else:
                        enriched_dsl[comp_id]["image_url"] = generated_url
                    
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
                        
                    print(f"✅ [智能配图] 组件 {comp_id} 配图成功")
            except Exception as e:
                logger.error(f"智能配图失败: {e}")

    return enriched_dsl, new_assets
