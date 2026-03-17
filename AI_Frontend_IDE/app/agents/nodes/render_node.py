import base64
from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.services.oss_client import upload_html_to_oss

# --- 🚀 递归组件模板引擎 (Recursive Template Engine) ---

def render_node_recursive(node: Dict[str, Any], data_dsl: Dict[str, Any]) -> str:
    """
    【递归渲染核心】：遍历 AST，根据组件类型调用模板并递归渲染子节点。
    """
    comp_id = node.get("id")
    comp_type = node.get("component_type")
    props = node.get("props", {})
    computed_classes = node.get("computed_classes", "")
    
    # 尝试从 data_dsl 中获取工兵填充的真实数据（叶子节点）
    comp_data = data_dsl.get(comp_id, {})
    
    # 递归渲染所有子节点
    children_html = ""
    children = node.get("children") or []
    for child in children:
        if isinstance(child, dict):
            children_html += render_node_recursive(child, data_dsl)

    # 组件分发逻辑
    if comp_type == "Container":
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="w-full {computed_classes}">{children_html}</div>'
    
    elif comp_type == "BentoGrid":
        cols = props.get("cols", 2)
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="grid grid-cols-{cols} gap-4 w-full {computed_classes}">{children_html}</div>'
    
    elif comp_type == "TitleBlock":
        title = comp_data.get("title", "未命名标题")
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="{computed_classes}"><h1 class="text-2xl font-bold">{title}</h1></div>'
    
    elif comp_type == "StoryText":
        paragraphs = comp_data.get("paragraphs", [])
        inner = "".join([f'<p class="mb-2">{p}</p>' for p in paragraphs])
        return f'<div id="{comp_id}" data-comp-id="{comp_id}" class="{computed_classes}">{inner}</div>'
    
    elif comp_type == "ProductCard":
        title = comp_data.get("title", "好物分享")
        price = comp_data.get("price", "价格待定")
        img = comp_data.get("image_url", "https://via.placeholder.com/150")
        return f'''
        <div id="{comp_id}" data-comp-id="{comp_id}" class="rounded-2xl overflow-hidden border border-gray-100 shadow-sm {computed_classes}">
            <img src="{img}" class="w-full h-32 object-cover" />
            <div class="p-3">
                <div class="text-sm font-bold truncate">{title}</div>
                <div class="text-red-500 font-bold mt-1">{price}</div>
            </div>
        </div>
        '''
    
    # 兜底渲染
    return f'<div id="{comp_id}" class="p-4 border border-dashed border-gray-300">{comp_type}: {comp_id} {children_html}</div>'


async def render_node(state: UIProjectState) -> dict:
    """
    【AST 渲染器】：将 PageDSL 树物理化为最终的 HTML
    """
    data_dsl = state.get("data_dsl", {})
    ast_root = data_dsl.get("root")
    page_theme = data_dsl.get("page_theme", {})
    page_title = data_dsl.get("page_title", "XHS-Forge AST Page")
    
    if not ast_root:
        return {"final_html": "<h1>DSL Error: No Root Found</h1>"}

    # 1. 注入全局 CSS 变量
    css_vars_str = "; ".join([f"{k}: {v}" for k, v in page_theme.items()])
    
    # 2. 执行递归渲染
    body_content = render_node_recursive(ast_root, data_dsl)
    
    # 3. 组装完整 HTML (注入 Tailwind Play CDN)
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{page_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {{ {css_vars_str} }}
        body {{ background-color: var(--bg-color, #f9fafb); font-family: sans-serif; }}
        [data-comp-id]:hover {{ outline: 2px dashed #ff2442; outline-offset: -2px; cursor: pointer; }}
    </style>
</head>
<body class="p-4 flex justify-center">
    <div class="w-full max-w-[420px] min-h-screen bg-white shadow-xl overflow-x-hidden">
        {body_content}
    </div>
    <script>
        // 前端交互脚手架 (Hover/Select)
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
