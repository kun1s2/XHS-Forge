from typing import Dict, Any, List
from app.agents.state import UIProjectState
from app.core.note_document import build_note_document_layout_from_state

def generate_observation_dashboard(state: UIProjectState) -> str:
    """
    【面试亮点】：ReAct 核心组件 —— 动态环境观测仪表盘。
    将复杂的状态机数据脱水为 Agent 易于理解的战术概览。
    """
    # 1. 观测：已建成的页面
    execution_view = build_note_document_layout_from_state(state)
    current_blocks = execution_view.get("blocks", [])
    
    canvas_summary = []
    used_images_count = 0
    for idx, b in enumerate(current_blocks):
        b_type = b.get("component_type")
        canvas_summary.append(f"{idx+1}. [{b_type}] (ID: {b.get('id')})")
        # 估算已用图片（简单的启发式算法）
        if b_type in ["CoverSwiper", "CollageContainer", "PolaroidImage"]:
            used_images_count += 3 # 假设平均用3张
        elif b_type in ["ProductCard", "WeatherPolaroid"]:
            used_images_count += 1

    # 2. 观测：事实情报储备
    know = state.get("retrieved_knowledge", {})
    pros_count = len(know.get("key_selling_points", [])) if isinstance(know, dict) else 0
    cons_count = len(know.get("known_issues", [])) if isinstance(know, dict) else 0
    
    # 3. 观测：资产余量
    image_assets = state.get("image_assets", [])
    remaining_images = max(0, len(image_assets) - used_images_count)

    # 4. 组装仪表盘文本
    dashboard = f"""
【👁️ 上帝视角：实时环境观测仪表盘】

📦 当前页面进度 (Canvas):
{chr(10).join(canvas_summary) if canvas_summary else "（暂无积木，请开始你的第一步）"}
(提示：目标积木数为 4-6 个，目前已完成 {len(canvas_summary)} 个)

📚 事实库存 (RAG Knowledge):
- 待转化的【优势点】: {pros_count} 个
- 待转化的【槽点/局限】: {cons_count} 个
- 核心实体: {know.get('entity_name', '未知') if isinstance(know, dict) else '未知'}

🖼️ 资产余量 (Assets):
- 还可以使用的图片数: {remaining_images} 张
(⚠️ 注意：若图片数为 0，严禁调用 CoverSwiper, PolaroidImage 等组件！)

---------------------------------------------------------
"""
    return dashboard
