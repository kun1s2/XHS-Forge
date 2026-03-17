import base64
import random
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.services.oss_client import upload_html_to_oss

# --- 🚀 物理组件库 (Physical Component Library) ---

def render_node_recursive(node: Dict[str, Any], data_dsl: Dict[str, Any]) -> str:
    """
    【递归渲染核心】：将 AST 树转化为具备 Tailwind 样式的 HTML 字符串。
    """
    if not node or not isinstance(node, dict):
        return ""
        
    comp_id = node.get("id", "unknown_id")
    comp_type = node.get("component_type", "Container")
    props = node.get("props", {})
    computed_classes = node.get("computed_classes", "")
    
    # 获取由并发工兵填充的内容数据
    comp_data = data_dsl.get(comp_id, {})
    
    # 递归渲染子节点
    children_html = ""
    for child in node.get("children", []):
        children_html += render_node_recursive(child, data_dsl)

    # --- 🧱 各组件物理 HTML 模板 ---

    if comp_type == "Container":
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="w-full flex flex-col gap-6 {computed_classes}">{children_html}</div>'

    elif comp_type == "BentoGrid":
        cols = props.get("cols", 2)
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="grid grid-cols-{cols} gap-4 w-full {computed_classes}">{children_html}</div>'

    elif comp_type == "CollageContainer":
        # 模拟散落感：为子组件注入随机旋转和层叠
        collage_children = ""
        rotations = ["-rotate-1", "rotate-1", "-rotate-2", "rotate-2"]
        for idx, child in enumerate(node.get("children", [])):
            rot = rotations[idx % len(rotations)]
            inner = render_node_recursive(child, data_dsl)
            collage_children += f'<div class="w-full transform transition-transform hover:scale-105 hover:z-30 {rot} mb-4" style="z-index: {10+idx}">{inner}</div>'
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="relative w-full py-8 px-4 flex flex-col items-center {computed_classes}">{collage_children}</div>'

    elif comp_type == "TitleBlock":
        title = comp_data.get("title") or "未命名的发现"
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-2 {computed_classes}"><h1 class="text-2xl font-bold text-gray-900 tracking-tight leading-snug">{title}</h1></div>'

    elif comp_type == "StoryText":
        paragraphs = comp_data.get("paragraphs") or ["正在构思有趣的内容..."]
        inner = "".join([f'<p class="mb-3 text-[15px] text-gray-700 leading-relaxed">{p}</p>' for p in paragraphs])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="px-2 {computed_classes}">{inner}</div>'

    elif comp_type == "PolaroidImage":
        img = comp_data.get("image_url") or "https://picsum.photos/seed/xhs/800/800"
        caption = comp_data.get("caption") or "Moment in 2026"
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="bg-white p-3 pb-10 shadow-xl border border-gray-100 flex flex-col gap-3 group {computed_classes}">
            <div class="aspect-square bg-gray-50 overflow-hidden relative">
                <img src="{img}" class="w-full h-full object-cover" />
                <div class="absolute inset-0 bg-gradient-to-tr from-transparent via-white/5 to-white/10 pointer-events-none"></div>
            </div>
            <div class="text-center font-serif italic text-stone-500 text-sm tracking-wide">{caption}</div>
        </div>
        '''

    elif comp_type == "HandwrittenText":
        text = comp_data.get("text") or comp_data.get("content") or "博主的碎碎念..."
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="p-4 transform -rotate-1 {computed_classes}">
            <div class="relative inline-block">
                <div class="absolute -bottom-1 -left-1 w-full h-3 bg-rose-100/40 -z-10 rounded-full"></div>
                <p class="text-stone-700 font-serif italic text-[16px] leading-relaxed">"{text}"</p>
            </div>
        </div>
        '''

    elif comp_type == "ProductCard":
        title = comp_data.get("title") or "宝藏单品"
        price = comp_data.get("price") or "参考价待定"
        img = comp_data.get("image_url") or "https://via.placeholder.com/300"
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="rounded-3xl overflow-hidden border border-gray-100 shadow-sm transition-all hover:shadow-md {computed_classes}">
            <img src="{img}" class="w-full h-48 object-cover" />
            <div class="p-4 bg-white">
                <div class="text-sm font-bold text-gray-800 line-clamp-1">{title}</div>
                <div class="text-[#ff2442] font-extrabold mt-1 text-lg">{price}</div>
            </div>
        </div>
        '''

    elif comp_type == "InteractionsBar":
        likes = comp_data.get("likes", "0")
        collects = comp_data.get("collects", "0")
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="flex items-center justify-between py-4 border-t border-gray-50 {computed_classes}">
            <div class="flex gap-6 text-gray-400">
                <div class="flex items-center gap-1"><span>🤍</span><span class="text-xs font-bold">{likes}</span></div>
                <div class="flex items-center gap-1"><span>⭐</span><span class="text-xs font-bold">{collects}</span></div>
            </div>
            <button class="px-6 py-2 bg-[#ff2442] text-white text-xs font-bold rounded-full shadow-lg shadow-red-500/20 active:scale-95 transition-all">关注博主</button>
        </div>
        '''

    return f'<div id="{comp_id}" class="p-4 border border-dashed border-red-200 text-red-400 text-xs rounded-xl">Unknown: {comp_type}</div>'


async def render_node(state: UIProjectState) -> dict:
    """
    【后端物理渲染器】：将 PageDSL 树静态化为最终的 HTML 源码。
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    page_theme = data_dsl.get("page_theme", {})
    page_title = data_dsl.get("page_title", "XHS-Forge AST Preview")
    
    if not ast_root:
        return {"final_html": "<h1>DSL Error: No Root Node</h1>"}

    css_vars = "; ".join([f"{k}: {v}" for k, v in page_theme.items()])
    
    body_content = render_node_recursive(ast_root, data_dsl)
    
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{page_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link href="https://fonts.googleapis.com/css2?family=Caveat:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{ {css_vars} }}
        body {{ 
            background-color: var(--bg-color, #f9fafb); 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0; padding: 0;
            display: flex; justify-content: center;
        }}
        .font-serif {{ font-family: 'Caveat', serif; }}
        [data-comp-id]:hover {{ outline: 2px dashed #ff2442; outline-offset: -2px; cursor: pointer; }}
        .mobile-viewport {{
            width: 100%; max-width: 420px;
            min-height: 100vh;
            background-color: #ffffff;
            box-shadow: 0 0 40px rgba(0,0,0,0.05);
            padding: 24px 16px 80px 16px;
        }}
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
