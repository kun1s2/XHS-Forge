import base64
import random
import json
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.services.oss_client import upload_html_to_oss

# --- 🚀 全量物理组件库 (AST Compatible) ---

def render_node_recursive(node: Dict[str, Any], data_dsl: Dict[str, Any]) -> str:
    """
    【递归渲染核心】：将 AST 树物理化。
    """
    if not node or not isinstance(node, dict):
        return ""
        
    comp_id = node.get("id", "unknown_id")
    comp_type = node.get("component_type", "Container")
    props = node.get("props", {})
    computed_classes = node.get("computed_classes", "")
    
    # 数据提取
    comp_data = data_dsl.get(comp_id, {})
    
    # 递归渲染子节点
    children_html = ""
    for child in node.get("children", []):
        children_html += render_node_recursive(child, data_dsl)

    # --- 🧱 物理组件模板矩阵 ---

    if comp_type in ["Container", "CollageContainer"]:
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="w-full relative flex flex-col gap-4 {computed_classes}">{children_html}</div>'

    elif comp_type == "BentoGrid":
        cols = props.get("cols", 2)
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="grid grid-cols-{cols} gap-4 w-full {computed_classes}">{children_html}</div>'

    elif comp_type == "CoverSwiper":
        images = comp_data.get("image_urls") or [comp_data.get("image_url")] or ["https://picsum.photos/seed/cover/800/800"]
        img_tags = "".join([f'<img src="{url}" class="w-full h-full object-cover shrink-0" />' for url in images if url])
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="w-full h-[450px] overflow-hidden rounded-b-[40px] relative shadow-2xl {computed_classes}">
            <div class="flex w-full h-full overflow-x-auto snap-x snap-mandatory scrollbar-hide">{img_tags}</div>
            <div class="absolute bottom-6 right-6 bg-black/30 backdrop-blur-md text-white text-[10px] px-3 py-1 rounded-full border border-white/10 font-bold tracking-widest">1/{len(images)}</div>
        </div>
        '''

    elif comp_type == "TitleBlock":
        title = comp_data.get("title") or "发现新的灵感"
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-4 py-2 {computed_classes}"><h1 class="text-[22px] font-black text-gray-900 leading-tight tracking-tight">{title}</h1></div>'

    elif comp_type == "StoryText":
        paragraphs = comp_data.get("paragraphs") or ["正在构思..."]
        inner = "".join([f'<p class="mb-4 text-[15.5px] text-gray-800 leading-[1.8] font-normal">{p}</p>' for p in paragraphs])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-4 {computed_classes}">{inner}</div>'

    elif comp_type == "ProductCard":
        title = comp_data.get("title") or "宝藏单品"
        price = comp_data.get("price") or "参考价待定"
        img = comp_data.get("image_url") or "https://via.placeholder.com/400"
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="mx-4 bg-white rounded-3xl overflow-hidden border border-gray-100/50 shadow-xl transition-all {computed_classes}">
            <div class="aspect-[4/3] bg-gray-50 overflow-hidden"><img src="{img}" class="w-full h-full object-cover" /></div>
            <div class="p-5"><div class="text-sm font-bold text-gray-900 mb-1">{title}</div><div class="text-[#ff2442] font-black text-xl italic">{price}</div></div>
        </div>
        '''

    elif comp_type == "TagList":
        tags = comp_data.get("tags") or ["话题", "记录生活"]
        tags_html = "".join([f'<span class="text-blue-800 bg-blue-50/50 px-3 py-1 rounded-full text-xs font-medium border border-blue-100/30"># {t}</span>' for t in tags])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="flex flex-wrap gap-2 px-4 {computed_classes}">{tags_html}</div>'

    elif comp_type == "InteractionsBar":
        likes = comp_data.get("likes", "0")
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="flex items-center justify-between px-4 py-6 border-t border-gray-100 {computed_classes}">
            <div class="flex gap-8 text-gray-400">
                <div class="flex flex-col items-center gap-1"><span class="text-xl">🤍</span><span class="text-[10px] font-bold">{likes}</span></div>
                <div class="flex flex-col items-center gap-1"><span class="text-xl">⭐</span><span class="text-[10px] font-bold">收藏</span></div>
            </div>
            <button class="px-8 py-3 bg-[#ff2442] text-white text-sm font-bold rounded-full shadow-lg shadow-red-500/20 active:scale-95 transition-all">关注作者</button>
        </div>
        '''

    return f'<div id="{comp_id}" class="p-4 border border-dashed border-red-200 text-red-400 text-xs rounded-xl">Unknown Component: {comp_type}</div>'


async def render_node(state: UIProjectState) -> dict:
    """
    【后端物理渲染器 3.0】：全量视觉对齐与通透化版。
    """
    data_dsl = state.get("data_dsl", {})
    style_dsl = state.get("style_dsl", {})
    ast_root = data_dsl.get("root")
    
    # 聚合全量 CSS 变量
    page_theme = data_dsl.get("page_theme") or {}
    style_vars = style_dsl.get("global_vars") or {}
    all_vars = {**page_theme, **style_vars}
    
    # 强制注入通透底色 (如果缺失)
    if "--bg-color" not in all_vars:
        all_vars["--bg-color"] = "#f9fafb"
    
    css_vars_str = "; ".join([f"{k}: {v}" for k, v in all_vars.items()])
    
    if not ast_root:
        return {"final_html": "<h1>DSL Error: No Root Node</h1>"}

    body_content = render_node_recursive(ast_root, data_dsl)
    
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{data_dsl.get('page_title', 'XHS-Forge Preview')}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{ {css_vars_str} }}
        body {{ 
            background-color: var(--bg-color); 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0; padding: 0; display: flex; justify-content: center;
        }}
        [data-comp-id]:hover {{ outline: 2px dashed #ff2442; outline-offset: -2px; cursor: pointer; }}
        .mobile-viewport {{
            width: 100%; max-width: 420px; min-height: 100vh;
            background-color: var(--bg-color);
            box-shadow: 0 40px 100px rgba(0,0,0,0.03);
            padding-bottom: 100px;
            display: flex; flex-direction: column; gap: 20px;
        }}
        .scrollbar-hide::-webkit-scrollbar {{ display: none; }}
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
</html>
"""
    
    try:
        oss_url = upload_html_to_oss(html_template)
    except:
        b64 = base64.b64encode(html_template.encode()).decode()
        oss_url = f"data:text/html;base64,{b64}"
        
    return {
        "final_html": html_template,
        "final_oss_url": oss_url
    }
