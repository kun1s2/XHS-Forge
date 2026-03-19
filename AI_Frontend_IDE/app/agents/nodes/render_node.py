import base64
import random
import json
from typing import Dict, Any
from app.agents.state import UIProjectState
from app.services.oss_client import upload_html_to_oss

# --- 🚀 全量物理组件库 5.6 (Precision Edition) ---

def render_block(block: Dict[str, Any], data_dsl: Dict[str, Any], style_dsl: Dict[str, Any], global_vars: Dict[str, Any]) -> str:
    """
    【物理组件锻造炉】：严禁脑补，数据驱动。
    """
    if not block: return ""
    comp_id = block.get("id")
    comp_type = block.get("component_type", "").lower()
    comp_data = data_dsl.get(comp_id, {})
    
    # 获取组件专属样式
    style_info = style_dsl.get(comp_id, {})
    css_classes = style_info.get("css_classes", "")

    # --- 1. TitleBlock (大标题) ---
    if comp_type == "titleblock":
        title = comp_data.get("title")
        if not title: return ""
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-6 mt-4 {css_classes}"><h1 class="text-2xl font-black text-gray-900 leading-tight tracking-tight">{title}</h1></div>'

    # --- 2. StoryText (叙事文本) ---
    elif comp_type == "storytext":
        paras = comp_data.get("paragraphs") or [comp_data.get("title")]
        if not paras or paras[0] in ["正在构思...", None]: return ""
        html = "".join([f'<p class="mb-4 text-[15px] text-gray-700 leading-relaxed tracking-wide">{p}</p>' for p in paras if p])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-6 {css_classes}">{html}</div>'

    # --- 3. CoverSwiper (大图轮播) ---
    elif comp_type == "coverswiper":
        raw_urls = comp_data.get("image_urls") or ([comp_data.get("image_url")] if comp_data.get("image_url") else [])
        
        # ✨ 物理黑名单拦截：过滤掉所有占位符幽灵
        urls = [u for u in raw_urls if u and "example.com" not in str(u) and "picsum.photos" not in str(u)]
        
        if not urls: return "" # 物理熔断：无真图不渲染
        
        img_tags = "".join([f'<img src="{u}" class="w-full h-full object-cover shrink-0 snap-center" />' for u in urls if u])
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="w-full aspect-[4/5] relative overflow-hidden bg-gray-100 {css_classes}">
            <div class="flex w-full h-full overflow-x-auto snap-x snap-mandatory scrollbar-hide">
                {img_tags}
            </div>
            <div class="absolute bottom-4 right-4 bg-black/30 backdrop-blur-md text-white text-[10px] px-2 py-0.5 rounded-full font-bold">1/{len(urls)}</div>
        </div>
        '''

    # --- 4. VersusCard (红蓝对冲卡) ---
    elif comp_type == "versuscard":
        title = comp_data.get("title", "极性博弈")
        pros = comp_data.get("pros", {}).get("summary") or comp_data.get("proText")
        cons = comp_data.get("cons", {}).get("summary") or comp_data.get("conText")
        if not pros or not cons: return ""
        
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 mt-2 {css_classes}">
            <div class="flex items-center gap-2 mb-3 px-1">
                <span class="w-1 h-3 bg-rose-500 rounded-full"></span>
                <span class="text-[10px] font-black text-gray-400 uppercase tracking-widest">{title}</span>
            </div>
            <div class="relative h-44 rounded-[28px] overflow-hidden flex shadow-xl border border-white/20">
                <div class="w-1/2 bg-rose-500 p-5 flex flex-col justify-center text-white">
                    <div class="text-[8px] font-bold opacity-60 mb-1">PROS</div>
                    <div class="text-[13px] font-black leading-snug line-clamp-4">{pros}</div>
                </div>
                <div class="w-1/2 bg-zinc-900 p-5 flex flex-col justify-center text-right text-zinc-400 border-l border-white/5">
                    <div class="text-[8px] font-bold opacity-40 mb-1">CONS</div>
                    <div class="text-[13px] font-black leading-snug line-clamp-4">{cons}</div>
                </div>
                <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-9 h-9 bg-white rounded-full flex items-center justify-center shadow-2xl z-10 border-4 border-zinc-100 font-black italic text-[10px] text-zinc-900">VS</div>
            </div>
        </div>
        '''

    # --- 5. TagList (话题标签) ---
    elif comp_type == "taglist":
        tags = comp_data.get("tags") or comp_data.get("killer_tags")
        if not tags: return ""
        tag_html = "".join([f'<span class="text-blue-600 bg-blue-50/50 px-3 py-1 rounded-full text-[11px] font-bold border border-blue-100/50"># {t}</span>' for t in tags])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-6 flex flex-wrap gap-2 {css_classes}">{tag_html}</div>'

    # --- 6. ProductSpecCard (参数矩阵) ---
    elif comp_type == "productspeccard":
        features = comp_data.get("features") or comp_data.get("core_features", [])
        if not features: return ""
        items = "".join([f'<div class="bg-white/50 p-3 rounded-2xl border border-gray-100/50"><div class="text-[10px] text-gray-400 mb-1">Key Feature</div><div class="text-xs font-black text-gray-800">{f}</div></div>' for f in features])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-6 grid grid-cols-2 gap-3 {css_classes}">{items}</div>'

    # --- 7. RadarChartBlock (雷达图) ---
    elif comp_type == "radarchartblock":
        dimensions = comp_data.get("dimensions") or []
        scores = comp_data.get("scores") or []
        if not dimensions or not scores: return ""
        rows = []
        for dim, score in zip(dimensions[:6], scores[:6]):
            safe_score = max(0, min(100, int(score)))
            rows.append(
                f'''
                <div class="space-y-1">
                    <div class="flex items-center justify-between text-[12px] font-semibold text-slate-700">
                        <span>{dim}</span>
                        <span>{safe_score}</span>
                    </div>
                    <div class="h-2 rounded-full bg-slate-200 overflow-hidden">
                        <div class="h-full rounded-full bg-[var(--primary-vibe)]" style="width:{safe_score}%"></div>
                    </div>
                </div>
                '''
            )
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 p-5 {css_classes}"><div class="text-sm font-black text-slate-800 mb-4">五维表现雷达</div>{"".join(rows)}</div>'

    # --- 8. PollBlock (投票卡) ---
    elif comp_type == "pollblock":
        question = comp_data.get("question")
        option_a = comp_data.get("option_a")
        option_b = comp_data.get("option_b")
        if not question or not option_a or not option_b: return ""
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 p-5 {css_classes}">
            <div class="text-sm font-black text-slate-900 mb-4">{question}</div>
            <div class="space-y-3">
                <button class="w-full text-left rounded-2xl bg-rose-50 border border-rose-100 px-4 py-3 text-sm font-bold text-rose-700">{option_a}</button>
                <button class="w-full text-left rounded-2xl bg-slate-100 border border-slate-200 px-4 py-3 text-sm font-bold text-slate-700">{option_b}</button>
            </div>
        </div>
        '''

    # --- 9. LocationBlock (地点卡) ---
    elif comp_type == "locationblock":
        poi_name = comp_data.get("poi_name") or comp_data.get("title")
        location = comp_data.get("location") or comp_data.get("desc")
        if not poi_name and not location: return ""
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 p-5 {css_classes}">
            <div class="text-[11px] font-black uppercase tracking-[0.18em] text-[var(--primary-vibe)] mb-2">Location</div>
            <div class="text-base font-black text-slate-900">{poi_name or "目的地"}</div>
            <div class="mt-2 text-sm leading-relaxed text-slate-600">{location or ""}</div>
        </div>
        '''

    # --- 10. WeatherPolaroid (天气拍立得) ---
    elif comp_type == "weatherpolaroid":
        image_url = comp_data.get("image_url")
        desc = comp_data.get("desc") or ""
        weather = comp_data.get("weather") or ""
        temperature = comp_data.get("temperature") or ""
        time = comp_data.get("time") or ""
        if not image_url and not desc: return ""
        image_html = f'<img src="{image_url}" class="w-full aspect-[4/5] object-cover" />' if image_url else ""
        meta = " ".join(part for part in [weather, temperature, time] if part)
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 overflow-hidden {css_classes}">
            {image_html}
            <div class="p-4">
                <div class="text-[11px] font-bold text-slate-500 mb-2">{meta}</div>
                <div class="text-sm leading-relaxed text-slate-700">{desc}</div>
            </div>
        </div>
        '''

    return ""

async def render_node(state: UIProjectState) -> dict:
    """
    【后端物理渲染器 5.6】：物理级数据校验，严禁占位符。
    """
    data_dsl = state.get("data_dsl", {})
    style_dsl = state.get("style_dsl", {})
    blocks = data_dsl.get("blocks", [])
    
    # 聚合变量
    page_theme = data_dsl.get("page_theme") or {}
    style_vars = style_dsl.get("global_vars") or {}
    all_vars = {**style_vars, **page_theme}
    
    # 强制修正背景色饱和度
    if all_vars.get("--bg-color") == "#ffffff":
        all_vars["--bg-color"] = "#f8fafc"
    
    css_vars_str = "; ".join([f"{k}: {v}" for k, v in all_vars.items()])
    
    if not blocks:
        return {"final_html": "<div style='padding:40px; text-align:center;'>Waiting for content...</div>"}

    # 执行物理区块渲染
    body_content = "".join([render_block(b, data_dsl, style_dsl, all_vars) for b in blocks])
    
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{data_dsl.get('page_title', 'XHS-Forge Note')}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {{ {css_vars_str} }}
        body {{ background-color: var(--bg-color); margin: 0; padding: 0; display: flex; justify-content: center; }}
        .mobile-viewport {{
            width: 100%; max-width: 420px; min-height: 100vh;
            background-color: var(--bg-color);
            box-shadow: 0 40px 120px rgba(0,0,0,0.08);
            display: flex; flex-direction: column; gap: 28px;
            padding-bottom: 100px; position: relative;
        }}
        .scrollbar-hide::-webkit-scrollbar {{ display: none; }}
        [data-comp-id]:hover {{ outline: 2px dashed #ff2442; outline-offset: -2px; cursor: pointer; }}
    </style>
</head>
<body>
    <div class="mobile-viewport">
        {body_content}
    </div>
    <script>
        document.addEventListener('click', e => {{
            const comp = e.target.closest('[data-comp-id]');
            if (comp) window.parent.postMessage({{ type: 'SELECT_REGION', id: comp.dataset.compId }}, '*');
        }});
    </script>
</body>
</html>"""

    # 上传并返回
    try:
        oss_url = await upload_html_to_oss(html_template)
    except:
        b64 = base64.b64encode(html_template.encode()).decode()
        oss_url = f"data:text/html;base64,{b64}"
        
    return {
        "final_html": html_template,
        "final_oss_url": oss_url
    }
