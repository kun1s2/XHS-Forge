import json
import asyncio
import random
from typing import Any, List
from app.core.llm_factory import create_llm
from app.agents.utils.entity_utils import normalize_entity_name
from app.agents.utils.fact_utils import build_fact_grounding_context, summarize_confirmed_attributes
from app.agents.state import ComponentTaskState
from app.core.config import settings
from app.core.schema import ComponentBuilderOutput

# 🐝 蜂群限制器
_github_limiter = asyncio.Semaphore(10)

_llm_instance = None
def get_builder_llm():
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = create_llm(
            model=settings.LLM_WORKER_MODEL, 
            api_key=settings.LLM_API_KEY, 
            base_url=settings.LLM_BASE_URL, 
            temperature=0.3
        )
    return _llm_instance

def build_component_fallback(
    comp_type: str,
    comp_id: str,
    content_brief: str,
    user_query: str,
    retrieved_knowledge: Any,
    image_assets: list[dict[str, str]],
) -> dict:
    knowledge = retrieved_knowledge if isinstance(retrieved_knowledge, dict) else {}
    entity_name = normalize_entity_name(knowledge.get("entity_name") or user_query)
    attrs = knowledge.get("core_attributes") or {}
    selling_points = knowledge.get("key_selling_points") or []
    known_issues = knowledge.get("known_issues") or []
    summary = knowledge.get("summary") or content_brief or user_query
    confirmed_summaries = summarize_confirmed_attributes(knowledge)
    image_urls = [asset.get("url") for asset in image_assets if asset.get("url")]

    if comp_type == "TitleBlock":
        return {"type": comp_type, "title": content_brief or entity_name}
    if comp_type == "StoryText":
        paragraphs = []
        if summary:
            paragraphs.append(summary)
        if confirmed_summaries:
            paragraphs.append("已确认参数：" + " / ".join(confirmed_summaries[:3]))
        if selling_points:
            paragraphs.append("亮点: " + " / ".join(selling_points[:3]))
        if not paragraphs:
            paragraphs.append(content_brief or "内容整理中")
        return {"type": comp_type, "paragraphs": paragraphs}
    if comp_type == "ProductSpecCard":
        features = confirmed_summaries[:4] + [f"{k}: {v}" for k, v in list(attrs.items())[:6] if f"{k}: {v}" not in confirmed_summaries]
        if not features:
            features = selling_points[:4] or [content_brief or "核心参数整理中"]
        return {"type": comp_type, "core_features": features}
    if comp_type == "CoverSwiper":
        return {"type": comp_type, "image_urls": image_urls[:5]}
    if comp_type == "RadarChartBlock":
        dimensions = ["性能", "影像", "续航", "设计", "体验"]
        score_seed = min(95, 60 + len(selling_points) * 5)
        scores = [score_seed, score_seed - 4, score_seed - 8, score_seed - 2, score_seed - 6]
        return {"type": comp_type, "dimensions": dimensions, "scores": scores}
    if comp_type == "PollBlock":
        return {
            "type": comp_type,
            "question": f"{entity_name} 最打动你的是哪一点？",
            "option_a": selling_points[0] if selling_points else "影像表现",
            "option_b": known_issues[0] if known_issues else "价格门槛",
        }
    if comp_type == "VersusCard":
        battle_report = knowledge.get("battle_report") or {}
        return {
            "type": comp_type,
            "title": battle_report.get("title") or "优缺点速览",
            "proText": battle_report.get("pros", {}).get("details") or (selling_points[0] if selling_points else "优势整理中"),
            "conText": battle_report.get("cons", {}).get("details") or (known_issues[0] if known_issues else "短板整理中"),
        }
    if comp_type == "LocationBlock":
        return {"type": comp_type, "poi_name": entity_name, "location": summary}
    if comp_type == "WeatherPolaroid":
        return {
            "type": comp_type,
            "image_url": image_urls[0] if image_urls else None,
            "weather": "晴",
            "temperature": "24C",
            "time": "今日",
            "desc": summary,
        }
    return {"type": comp_type, "title": content_brief or "内容整理中"}


def enforce_component_contract(comp_type: str, result_data: dict, fallback_data: dict) -> dict:
    merged = dict(result_data or {})
    required_fields_map = {
        "TitleBlock": ["title"],
        "StoryText": ["paragraphs"],
        "ProductSpecCard": ["core_features"],
        "RadarChartBlock": ["dimensions", "scores"],
        "PollBlock": ["question", "option_a", "option_b"],
        "VersusCard": ["title", "proText", "conText"],
        "CoverSwiper": ["image_urls"],
        "LocationBlock": ["poi_name", "location"],
        "WeatherPolaroid": ["desc"],
    }

    for field in required_fields_map.get(comp_type, []):
        value = merged.get(field)
        if value in (None, "", [], {}):
            fallback_value = fallback_data.get(field)
            if fallback_value not in (None, "", [], {}):
                merged[field] = fallback_value

    if "type" not in merged:
        merged["type"] = comp_type
    return merged

async def component_builder_node(state: ComponentTaskState) -> dict:
    """
    【单体工兵节点 5.8】：纯文本注入版 (杜绝 jinja2 错误)。
    """
    comp_id = state["component_id"]
    comp_type = state["component_type"]
    content_brief = state.get("content_brief", "填充内容")
    user_query = state.get("user_query", "")
    
    # 1. 提取 RAG 知识
    retrieved_knowledge = state.get("retrieved_knowledge", {})
    battle_report = None
    
    fact_str = "无外部参考资料"
    if isinstance(retrieved_knowledge, dict):
        battle_report = retrieved_knowledge.get("battle_report")
        if retrieved_knowledge.get("entity_name"):
            fact_context = {
                "entity": retrieved_knowledge.get('entity_name'),
                "attributes": retrieved_knowledge.get('core_attributes', {}),
                "images": state.get("image_assets", []) 
            }
            fact_str = json.dumps(fact_context, ensure_ascii=False, indent=2)
        fact_grounding = build_fact_grounding_context(retrieved_knowledge)
    else:
        fact_grounding = ""

    # 2. 提取导引文案
    content_msgs = state.get("content_messages", [])
    global_guide = "未提供全局定调"
    if content_msgs:
        for msg in reversed(content_msgs):
            if hasattr(msg, "content") and msg.content:
                global_guide = str(msg.content)
                break

    async with _github_limiter:
        await asyncio.sleep(random.uniform(0.1, 0.2))
        print(f"👷 [并发工兵] 构建中: {comp_id} ({comp_type})")
        
        llm = get_builder_llm()
        structured_llm = llm.with_structured_output(ComponentBuilderOutput, method="function_calling")
        
        # 3. 构造指令 (纯 f-string 拼接，最安全)
        system_prompt = f"""你是一个顶级组件设计师。当前构建 ID: [{comp_id}], 类型: "{comp_type}"。

【⚠️ 本组件专项简报】: >> {content_brief} <<

【📖 全局定调背景】:
{global_guide}

【📊 结构化事实库】:
{fact_str}

【🧭 事实可信度约束】:
{fact_grounding or "暂无已确认事实；若存在冲突，不要编造绝对参数。"}

【通用铁律】：
1. 职责锁定：仅针对简报指派的细节创作。
2. 严禁复读：严禁照抄全局背景原句。
3. 📸 零幻觉图像：若事实库无图，image_url 设为 null。
4. 若“已确认事实”存在，优先使用这些值，不要输出与其冲突的参数。
5. 若某个参数仍存在冲突且未确认，不要把它写成确定数字结论。
"""

        if comp_type == "VersusCard" and battle_report:
            system_prompt += f"\n【🚨 强制对冲数据】:\n{json.dumps(battle_report, ensure_ascii=False)}"

        try:
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
            )
            result: ComponentBuilderOutput = await structured_llm.ainvoke([
                ("system", system_prompt),
                ("human", f"请根据指令完成组件数据构建。用户指令：{user_query}")
            ])
            
            res_data = {}
            if result.data:
                res_data = result.data.model_dump(exclude_none=True)
            res_data["type"] = comp_type
            res_data = enforce_component_contract(comp_type, res_data, fallback_data)
            
            # VersusCard 深度纠偏
            if comp_type == "VersusCard" and battle_report:
                res_data["title"] = battle_report.get('title')
                res_data["proText"] = battle_report.get('pros', {}).get('details')
                res_data["conText"] = battle_report.get('cons', {}).get('details')
            
            style_data = {"css_classes": "", "inline_styles": {}}
            if result.style:
                style_data = result.style.model_dump(exclude_none=True)

            return {
                "data_dsl": {comp_id: res_data},
                "style_dsl": {comp_id: style_data}
            }
        except Exception as e:
            print(f"🩹 [工兵自愈] {comp_id} 失败: {e}")
            fallback_data = build_component_fallback(
                comp_type=comp_type,
                comp_id=comp_id,
                content_brief=content_brief,
                user_query=user_query,
                retrieved_knowledge=retrieved_knowledge,
                image_assets=state.get("image_assets", []),
            )
            
            # 最后的挣扎：如果是 VersusCard 且有报告，直接硬填
            if comp_type == "VersusCard" and battle_report:
                 return {
                    "data_dsl": {comp_id: {
                        "type": "VersusCard",
                        "title": battle_report.get('title'),
                        "proText": battle_report.get('pros', {}).get('details'),
                        "conText": battle_report.get('cons', {}).get('details')
                    }},
                    "style_dsl": {comp_id: {"css_classes": "opacity-90", "inline_styles": {}}}
                }
            
            return {
                "data_dsl": {comp_id: fallback_data},
                "style_dsl": {comp_id: {"css_classes": "", "inline_styles": {}}}
            }
