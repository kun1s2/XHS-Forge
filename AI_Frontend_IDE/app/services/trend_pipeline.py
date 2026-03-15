import asyncio
from pydantic import BaseModel, Field
from zhipuai import ZhipuAI
from langchain_openai import ChatOpenAI
from app.core.config import settings
from app.core.persistence import generate_vector_store

# 1. 智谱客户端：【仅用于联网搜索工具】使用原生 SDK
zhipu_client = ZhipuAI(api_key=settings.ZHI_PU_API_KEY)

# 2. 主模型客户端：【走标准的 OpenAI 第三方接口范式】
llm = ChatOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_BASE_URL,
    model=settings.LLM_MODEL,
    temperature=0.1
)

# 3. 定义绝对严谨的结构化输出 Schema
class TrendDistillation(BaseModel):
    objective_facts: str = Field(description="客观事实，无感情色彩")
    subjective_vibes: str = Field(description="主观舆论与网友槽点")
    core_summary: str = Field(description="核心一句话摘要")

_active_tasks = set()

async def process_new_trend_background(keyword: str):
    """后台异步清洗流水线：解耦搜索与蒸馏"""
    normalized_kw = keyword.strip().lower()
    if normalized_kw in _active_tasks: return
        
    _active_tasks.add(normalized_kw)
    print(f"🕵️‍♂️ [后台主编] 嗅探到新热点: {keyword}，开始异步清洗...")
    
    try:
        # ==========================================
        # 步骤 1：利用智谱作为“外挂搜索引擎”获取生肉资料 (使用官方最新 web_search 接口)
        # ==========================================
        def fetch_search_results():
            response = zhipu_client.web_search.web_search(
                search_engine="search_pro",
                search_query=keyword,
                count=15,
                content_size="high"
            )
            # 提取搜索结果列表
            res = getattr(response, "search_result", [])
            lines = [
                (item.get("content", "") if isinstance(item, dict) else getattr(item, "content", ""))
                for item in res
            ]
            return "\n".join(lines)

        print(f"🌐 [后台主编] 正在调用智谱官方 SDK 进行全网搜索...")
        search_context = await asyncio.to_thread(fetch_search_results)

        # ==========================================
        # 步骤 2：利用主模型 (OpenAI 范式) 进行数据结构化蒸馏
        # ==========================================
        print(f"🧠 [后台主编] 搜索完毕，正交由主脑 {settings.LLM_MODEL} 进行信息蒸馏...")
        # ✨ 铁腕约束：强制要求直接输出字段，严禁包裹外层 Key
        prompt = f"""你是一个严谨的结构化数据提取器。
请根据以下搜索结果提炼【{keyword}】的热点内容。

【输出指令】：
1. 必须严格遵守 JSON 格式。
2. 必须且只能包含以下三个字段：'objective_facts', 'subjective_vibes', 'core_summary'。
3. 严禁在最外层包裹任何额外的 Key（如 'review_note' 或 'data'）。
4. 严禁包含任何 Markdown 标记。

【背景资料】：
{search_context}
"""
        structured_llm = llm.with_structured_output(TrendDistillation)
        distilled_data = await structured_llm.ainvoke(prompt)
        
        # ==========================================
        # 步骤 3：强力注入 PGVector (使用智谱 Embedding)
        # ==========================================
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
        print(f"✅ [后台主编] 热点 「{keyword}」 已成功蒸馏入库完成！")
        
    except Exception as e:
        print(f"❌ [后台主编] 处理热点 {keyword} 失败: {e}")
    finally:
        _active_tasks.discard(normalized_kw)
