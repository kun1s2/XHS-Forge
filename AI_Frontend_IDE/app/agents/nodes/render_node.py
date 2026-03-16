import uuid
from app.agents.state import UIProjectState
from app.services.oss_client import upload_html_to_oss

def render_component(comp_id: str, comp_data: dict, comp_style: dict) -> str:
    """
    【核心物理渲染器】：将小红书风格 DSL 映射为真实的 HTML DOM
    """
    comp_type = comp_data.get("type", "div")
    
    # 提取样式
    css_classes = comp_style.get("css_classes", "")
    inline_styles_dict = comp_style.get("inline_styles", {})
    inline_style_str = "; ".join([f"{k}: {v}" for k, v in inline_styles_dict.items()])
    style_attr = f'style="{inline_style_str}"' if inline_style_str else ""
    
    # 基础 DOM 壳子，附带 data-comp-id 供前端鼠标 Hover 锁定使用！
    dom_wrapper_start = f'<div id="{comp_id}" data-comp-id="{comp_id}" class="{css_classes} relative" {style_attr}>'
    dom_wrapper_end = '</div>'
    
    inner_html = ""
    
    # 1. 渲染 CoverSwiper (小红书顶部轮播)
    if comp_type == "CoverSwiper":
        images = comp_data.get("image_urls", [])
        if not images and comp_data.get("image_url"):
            images = [comp_data.get("image_url")]
            
        if images:
            # 简单实现：水平滚动容器
            inner_html += '<div class="flex overflow-x-auto snap-x snap-mandatory scrollbar-hide w-full h-[400px] bg-gray-100">'
            for idx, img in enumerate(images):
                inner_html += f'<div class="snap-center shrink-0 w-full h-full flex-none">'
                inner_html += f'<img src="{img}" alt="cover-{idx}" class="w-full h-full object-cover"/>'
                inner_html += '</div>'
            inner_html += '</div>'
            # 假装有一个页码指示器
            inner_html += f'<div class="absolute bottom-4 right-4 bg-black/40 backdrop-blur-sm text-white text-xs px-2.5 py-1 rounded-full">1/{len(images)}</div>'
        else:
            inner_html += '<div class="w-full h-64 bg-gray-200 flex items-center justify-center text-gray-500">📸 暂无图片</div>'
            
    # 2. 渲染 TitleBlock (带情绪的标题)
    elif comp_type == "TitleBlock":
        title = comp_data.get("title", "")
        inner_html += f'<h1 class="text-xl font-bold text-gray-900 leading-snug">{title}</h1>'
        
    # 3. 渲染 StoryText (正文故事)
    elif comp_type == "StoryText":
        for p in comp_data.get("paragraphs", []):
            inner_html += f'<p class="text-[15px] text-gray-800 leading-relaxed mb-3 whitespace-pre-wrap">{p}</p>'
            
    # 4. 渲染 ProductCard (商品种草卡片)
    elif comp_type == "ProductCard":
        img = comp_data.get("image_url", "")
        price = comp_data.get("price", "暂无标价")
        # ✨ 修复：优先取 title 作为商品名称，如果没有再取 desc
        product_name = comp_data.get("title") or comp_data.get("desc") or "宝藏好物"
        rating = comp_data.get("rating")
        
        inner_html += '<div class="flex bg-gray-50 rounded-xl p-3 items-center border border-gray-100/50">'
        if img:
            inner_html += f'<img src="{img}" class="w-16 h-16 object-cover rounded-lg mr-3 shadow-sm border border-gray-200/50"/>'
        inner_html += '<div class="flex-1 min-w-0">'
        # ✨ 插值修复
        inner_html += f'<div class="text-sm text-gray-800 line-clamp-2 mb-1.5 font-medium">{product_name}</div>'
        
        # 如果有评分，渲染星星
        if rating:
            inner_html += f'<div class="text-[10px] text-orange-400 mb-1">⭐ {rating}</div>'
            
        inner_html += f'<div class="text-[#ff2442] font-bold text-base">{price}</div>'
        inner_html += '</div>'
        inner_html += '<button class="ml-3 shrink-0 bg-[#ff2442] text-white text-xs px-4 py-2 rounded-full font-medium">去看看</button>'
        inner_html += '</div>'
        
    # ✨ 任务 1：新增 ProductSpecCard (参数规格卡片) 的渲染逻辑
    elif comp_type == "ProductSpecCard":
        features = comp_data.get("core_features", [])
        inner_html += '<div class="bg-white rounded-2xl p-4 shadow-sm border border-gray-100/50">'
        inner_html += '<div class="flex items-center gap-2 mb-3">'
        inner_html += '  <div class="w-1 h-4 rounded-full bg-[var(--primary-vibe)]"></div>'
        inner_html += '  <h3 class="text-sm font-bold text-gray-900 uppercase tracking-wider">Product Specs</h3>'
        inner_html += '</div>'
        inner_html += '<div class="grid grid-cols-1 gap-2">'
        for feature in features:
            inner_html += f'''
            <div class="flex items-start gap-2 p-2 rounded-lg bg-gray-50/50">
              <span class="text-[var(--primary-vibe)] text-xs">✓</span>
              <span class="text-xs text-gray-700 leading-tight">{feature}</span>
            </div>
            '''
        if not features:
            inner_html += '<div class="text-center py-2 text-xs text-gray-400 italic">正在通过互联网获取参数...</div>'
        inner_html += '</div></div>'
        
    # 6. 渲染 TagList (底部话题标签)
    elif comp_type == "TagList":
        inner_html += '<div class="flex flex-wrap gap-2 mt-2">'
        for tag in comp_data.get("tags", []):
            # 确保标签带 # 号
            display_tag = tag if str(tag).startswith('#') else f'#{tag}'
            inner_html += f'<span class="text-[#13386c] bg-blue-50/50 px-2 py-0.5 rounded text-[13px] font-medium cursor-pointer hover:bg-blue-100 transition-colors">{display_tag}</span>'
        inner_html += '</div>'

    # ✨ 任务 2：新增 InteractionsBar (社交互动条) 的渲染逻辑
    elif comp_type == "InteractionsBar":
        likes = comp_data.get("likes", "0")
        collects = comp_data.get("collects", "0")
        comments = comp_data.get("comments", "0")
        
        inner_html += f'''
        <div class="flex items-center justify-between w-full">
            <div class="flex gap-6 items-center text-gray-500">
                <div class="flex items-center gap-1.5"><span class="text-base">🤍</span><span class="text-[13px] font-medium">{likes}</span></div>
                <div class="flex items-center gap-1.5"><span class="text-base">⭐</span><span class="text-[13px] font-medium">{collects}</span></div>
                <div class="flex items-center gap-1.5"><span class="text-base">💬</span><span class="text-[13px] font-medium">{comments}</span></div>
            </div>
            <div class="flex gap-3">
                <button class="px-5 py-2 bg-gray-100 text-gray-800 text-[13px] font-bold rounded-full hover:bg-gray-200 transition-colors">分享</button>
                <button class="px-5 py-2 bg-[#ff2442] text-white text-[13px] font-bold rounded-full shadow-lg shadow-red-500/20 active:scale-95 transition-all">关注</button>
            </div>
        </div>
        '''
        
    # 兜底：如果是不认识的组件，直接把数据打出来
    else:
        inner_html = f'<pre class="text-xs text-red-500 p-2 bg-red-50 rounded">Unknown Social Component: {comp_type}</pre>'

    return dom_wrapper_start + inner_html + dom_wrapper_end


async def render_node(state: UIProjectState) -> dict:
    """
    负责将 data_dsl 和 style_dsl 拼装为真实的 HTML 文件，并部署到云端。
    """
    data_dsl = state.get("data_dsl", {})
    style_dsl = state.get("style_dsl", {})
    
    # 1. 提取全局 CSS 变量
    global_vars = style_dsl.get("global_vars", {})
    css_vars_str = "; ".join([f"{k}: {v}" for k, v in global_vars.items()])
    
    # 2. 按照 data_dsl 的 page_order 顺序组装 DOM
    page_order = data_dsl.get("page_order", [])
    components_html = ""
    
    for comp_id in page_order:
        comp_data = data_dsl.get(comp_id)
        if not comp_data:
             continue # 忽略被删除 (null) 或不存在的组件
             
        comp_style = style_dsl.get(comp_id, {})
        components_html += render_component(comp_id, comp_data, comp_style) + "\n"
    
    # 3. 组装完整的 HTML5 骨架 (注入 Tailwind CDN 和全局变量)
    page_title = data_dsl.get("page_title", "小红书笔记")
    html_template = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{page_title}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        :root {{ {css_vars_str} }}
        body {{ 
            background-color: var(--bg-color, #f5f5f5); 
            color: var(--text-color, #333333); 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            margin: 0;
            padding: 0;
            display: flex;
            justify-content: center;
        }}
        /* 为前端鼠标悬停锁定提供高亮特效 */
        [data-comp-id]:hover {{
            outline: 2px dashed #ff2442;
            outline-offset: -2px;
            cursor: pointer;
        }}
        /* 模拟手机容器 */
        .mobile-container {{
            width: 100%;
            max-width: 420px;
            background-color: #ffffff;
            min-height: 100vh;
            box-shadow: 0 0 20px rgba(0,0,0,0.05);
            position: relative;
            overflow-x: hidden;
        }}
        /* 隐藏滚动条 */
        .scrollbar-hide::-webkit-scrollbar {{
            display: none;
        }}
        .scrollbar-hide {{
            -ms-overflow-style: none;
            scrollbar-width: none;
        }}
    </style>
</head>
<body>
    <div class="mobile-container pb-20">
        <!-- 顶部导航栏模拟 -->
        <div class="sticky top-0 z-50 bg-white/95 backdrop-blur-md px-4 py-3 flex justify-between items-center border-b border-gray-100">
            <div class="text-xl font-bold cursor-pointer hover:bg-gray-100 w-8 h-8 flex items-center justify-center rounded-full transition-colors">←</div>
            <div class="flex gap-5 text-[15px]">
                <span class="text-gray-500 font-medium">发现</span>
                <span class="text-gray-500 font-medium">附近</span>
                <span class="text-gray-900 border-b-2 border-[#ff2442] pb-1 font-semibold">北京</span>
            </div>
            <div class="text-xl cursor-pointer hover:bg-gray-100 w-8 h-8 flex items-center justify-center rounded-full transition-colors">🔍</div>
        </div>

        <!-- 动态生成的笔记内容 -->
        <div class="w-full">
            {components_html}
        </div>
        
        <!-- 底部互动栏模拟 -->
        <div class="fixed bottom-0 w-full max-w-[420px] bg-white border-t border-gray-100 px-4 py-2.5 flex justify-between items-center z-50">
            <div class="bg-gray-100 rounded-full px-4 py-2 text-[13px] text-gray-500 flex-1 mr-4 cursor-text">说点什么...</div>
            <div class="flex gap-5 text-xl">
                <span class="cursor-pointer hover:scale-110 transition-transform">🤍</span>
                <span class="cursor-pointer hover:scale-110 transition-transform">⭐</span>
                <span class="cursor-pointer hover:scale-110 transition-transform">💬</span>
            </div>
        </div>
    </div>
    
    <!-- 注入前端通信脚手架 -->
    <script>
        document.addEventListener('click', function(e) {{
            const comp = e.target.closest('[data-comp-id]');
            if (comp) {{
                const compId = comp.getAttribute('data-comp-id');
                window.parent.postMessage({{ type: 'SELECT_REGION', id: compId }}, '*');
            }}
        }});
        document.addEventListener('mouseover', function(e) {{
            const comp = e.target.closest('[data-comp-id]');
            if (comp) {{
                window.parent.postMessage({{ type: 'HOVER_REGION', id: comp.getAttribute('data-comp-id') }}, '*');
            }}
        }});
        document.addEventListener('mouseout', function(e) {{
            const comp = e.target.closest('[data-comp-id]');
            if (comp) {{
                window.parent.postMessage({{ type: 'UNHOVER_REGION' }}, '*');
            }}
        }});
    </script>
</body>
</html>
"""
    
    try:
        # 上传到 OSS
        oss_url = upload_html_to_oss(html_template)
    except Exception as e:
        print(f"❌ 上传 OSS 失败: {e}")
        # 如果没有配置 OSS，直接用 Data URI 兜底
        import base64
        b64_html = base64.b64encode(html_template.encode('utf-8')).decode('utf-8')
        oss_url = f"data:text/html;base64,{b64_html}"
        
    return {
        "final_html": html_template,
        "final_oss_url": oss_url
    }