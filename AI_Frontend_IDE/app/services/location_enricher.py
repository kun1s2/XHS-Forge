# app/services/location_enricher.py
import logging
from app.tools.amap import place_search_structured_async

logger = logging.getLogger(__name__)

async def enrich_page_dsl(data_dsl: dict) -> dict:
    """
    【数据拦截增强服务】：扫描 DSL，为 LocationBlock 补充真实的经纬度和详细地址。
    """
    # 避免修改原引用，虽然在 LangGraph 中通常是返回新字典
    enriched_dsl = data_dsl.copy()
    
    # 遍历组件
    for comp_id, comp_data in enriched_dsl.items():
        # 如果是字典且类型是 LocationBlock
        if isinstance(comp_data, dict) and comp_data.get("type") == "LocationBlock":
            # 优先使用 poi_name，如果没有则退而求其次使用 location
            poi_name = comp_data.get("poi_name") or comp_data.get("location")
            
            if not poi_name:
                continue
                
            try:
                print(f"📍 [位置增强] 发现待补全地点: {poi_name}，正在请求高德地图...")
                # 调用高德 POI 搜索，只取第 1 条
                pois = await place_search_structured_async(keywords=poi_name, offset=1)
                
                if pois:
                    best_match = pois[0]
                    location_str = best_match.get("location", "") # "lng,lat"
                    real_address = best_match.get("address", "")
                    real_name = best_match.get("name", "")
                    
                    # 解析经纬度
                    if location_str and "," in location_str:
                        lng_str, lat_str = location_str.split(",")
                        enriched_dsl[comp_id]["lng"] = float(lng_str)
                        enriched_dsl[comp_id]["lat"] = float(lat_str)
                    
                    # 回填真实数据
                    enriched_dsl[comp_id]["location"] = real_address or enriched_dsl[comp_id].get("location")
                    enriched_dsl[comp_id]["poi_name"] = real_name or poi_name
                    
                    print(f"✅ [位置增强] 补全成功: {real_name} -> ({enriched_dsl[comp_id]['lng']}, {enriched_dsl[comp_id]['lat']})")
                else:
                    print(f"⚠️ [位置增强] 未找到地点「{poi_name}」的真实坐标")
                    
            except Exception as e:
                logger.error(f"位置增强失败: {e}")
                print(f"❌ [位置增强] 异常: {e}")
                
    return enriched_dsl
