import asyncio
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
from zhipuai import ZhipuAI
from app.core.llm_factory import create_llm
from app.core.config import settings
from app.core.persistence import generate_vector_store
from fastapi import WebSocket

# 1. 智谱客户端：使用原生 SDK
zhipu_client = ZhipuAI(api_key=settings.ZHI_PU_API_KEY)

# 2. 主模型客户端
llm = create_llm(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    model=settings.LLM_MODEL,
    temperature=0.1
)

class TrendDistillation(BaseModel):
    objective_facts: str = Field(description="客观事实，无感情色彩")
    subjective_vibes: str = Field(description="主观舆论与网友槽点")
    core_summary: str = Field(description="核心一句话摘要")

    @field_validator('objective_facts', 'subjective_vibes', mode='before')
    @classmethod
    def ensure_string(cls, v: Any) -> str:
        if isinstance(v, list):
            return "；".join([str(item) for item in v])
        return str(v)

_active_tasks = set()

async def process_new_trend_background(keyword: str, websocket: Optional[WebSocket] = None):
    """后台异步清洗流水线：解耦搜索与蒸馏，并实时上报"""
    normalized_kw = keyword.strip().lower()
    if normalized_kw in _active_tasks: return
        
    _active_tasks.add(normalized_kw)
    print(f"🕵️‍♂️ [后台主编] 嗅探到新热点: {keyword}，开始异步清洗...")
    
    try:
        # 1. 发送“正在搜索”状态给前端
        if websocket:
            await websocket.send_json({
                "event": "thought",
                "node": "trend_harvester",
                "data": f"🔍 后端正在异步搜集「{keyword}」的最新全网资料..."
            })

        # 2. 调用智谱搜网
        def fetch_search_results():
            response = zhipu_client.web_search.web_search(
                search_engine="search_pro",
                search_query=keyword,
                count=8, # ✨ 减少搜索数量，降低 Token 压力
                content_size="high"
            )
            res = getattr(response, "search_result", [])
            lines = [
                (item.get("content", "") if isinstance(item, dict) else getattr(item, "content", ""))
                for item in res
            ]
            # ✨ 物理截断：强制限制在 20000 字符以内，留出 10000 字符给 System Prompt 和 思考空间
            full_text = "\n".join(lines)
            return full_text[:20000]

        search_context = await asyncio.to_thread(fetch_search_results)
        
        # ✨ 物理打印到控制台
        print(f"\n--- 📄 [后台主编] 搜集到关于「{keyword}」的原始资料 ---\n{search_context[:1000]}...\n------------------------------------------------\n")

        # ✨ 实时推送到前端显示（截取前 500 字，避免 WS 拥塞）
        if websocket:
            await websocket.send_json({
                "event": "thought_process",
                "data": {
                    "node": "trend_harvester",
                    "content": f"【全网实时资料搜集完毕】\n\n{search_context[:500]}..."
                }
            })

        # 3. 信息蒸馏
        print(f"🧠 [后台主编] 正在交由主脑进行信息蒸馏...")
        prompt = f"""你是一个严谨的结构化数据提取器。提炼【{keyword}】的热点内容。
【输出指令】：
1. 必须严格遵守 JSON 格式。
2. 包含字段：'objective_facts', 'subjective_vibes', 'core_summary'。
3. 严禁包裹外层 Key。

【背景资料】：
{search_context}
"""
        structured_llm = llm.with_structured_output(TrendDistillation, method="function_calling")
        distilled_data = await structured_llm.ainvoke(prompt)
        
        # 4. 入库 PGVector
        async with generate_vector_store() as store:
            await store.aadd_texts(
                texts=[distilled_data.core_summary],
                metadatas=[{
                    "doc_type": "trending_topic",
                    "keyword": keyword,
                    "facts": distilled_data.objective_facts,
                    "vibes": distilled_data.subjective_vibes,
                }]
            )
        print(f"✅ [后台主编] 热点 「{keyword}」 蒸馏入库完成！")
        
        if websocket:
            await websocket.send_json({
                "event": "thought",
                "node": "trend_harvester",
                "data": f"✅ 热点「{keyword}」已完成深度清洗，并归档至 XHS-Forge 全局知识库。"
            })
            
    except Exception as e:
        print(f"❌ [后台主编] 失败: {e}")
    finally:
        _active_tasks.discard(normalized_kw)
