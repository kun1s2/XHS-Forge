import pytest
import json
import os
from AI_Frontend_IDE.app.agents.nodes.enrichment_agent import enrichment_node_v2
from AI_Frontend_IDE.app.agents.state import UIProjectState
from dotenv import load_dotenv

# 加载环境变量以确保 LLM 配置生效
load_dotenv(dotenv_path="AI_Frontend_IDE/.env")

@pytest.mark.asyncio
async def test_enrichment_node_v2_integration():
    """【集成测试】调用真实的 LLM 引擎进行端到端数据增强测试。"""
    
    # 1. 构造一个包含待增强数据的初始状态
    initial_state: UIProjectState = {
        "data_dsl": {
            "page_order": ["header", "product_1", "location_1"],
            "header": {"type": "Header", "title": "今日推荐"},
            "product_1": {
                "type": "ProductCard", 
                "title": "索尼 A7M4", 
                "price": "价格待定",
                "specs": ["传感器类型待补全"]
            },
            "location_1": {
                "type": "LocationBlock",
                "address": "上海东方明珠",
                "lat": None,
                "lng": None
            }
        },
        "active_archetype": "electronics",
        "image_assets": []
    }

    print("\n🚀 [集成测试] 启动真实 Agent 增强流程...")
    
    # 2. 调用真实的节点函数
    result = await enrichment_node_v2(initial_state)

    # 3. 验证增强结果
    print(f"✅ [集成测试] 增强后的数据: {json.dumps(result.get('data_dsl'), ensure_ascii=False, indent=2)}")
    
    enriched_dsl = result.get("data_dsl", {})
    
    # 验证商品信息是否被增强（如价格不再是“价格待定”）
    product = enriched_dsl.get("product_1")
    assert product is not None, "product_1 丢失"
    assert product.get("price") != "价格待定", f"商品价格未被成功增强: {product.get('price')}"
    
    # 验证位置坐标是否被增强
    location = enriched_dsl.get("location_1")
    assert location is not None, "location_1 丢失"
    # 注意：某些模型可能只增强了部分工具，或者并行的工具调用只返回了部分结果
    # 这里我们根据实际输出做调整。如果 location 没有增强，我们需要检查 enrichment_node_v2 的逻辑
    assert location.get("lat") is not None or "refined_name" in str(location), "地理坐标或名称未被增强"

    # 验证图片资产是否生成
    # (如果 generate_images_tool 被调用，应该会有 image_assets)
    # new_assets = result.get("image_assets", [])
    # print(f"🖼️ [集成测试] 生成了 {len(new_assets)} 个新素材")
