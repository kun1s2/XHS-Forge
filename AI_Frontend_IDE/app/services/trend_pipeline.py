import json
from zhipuai import ZhipuAI
import asyncio
from app.core.config import settings
from app.core.persistence import generate_vector_store

# 智谱官方 SDK 暂时不支持原生 AsyncZhipuAI
client = ZhipuAI(api_key=settings.LLM_API_KEY)

# ✨ 代码净化：引入内存锁，防止高并发下的“后台任务踩踏” (Task Stampede)
_active_tasks = set()

async def process_new_trend_background(keyword: str):
    """后台异步清洗流水线：抓取 -> 蒸馏 -> 存入 PGVector"""
    # 提取核心词作为锁的 Key
    normalized_kw = keyword.strip().lower()
    if normalized_kw in _active_tasks:
        print(f"🛡️ [后台主编] 任务去重：热点「{normalized_kw}」正在被其他线程清洗，跳过本次触发。")
        return
        
    _active_tasks.add(normalized_kw)
    print(f"🕵️‍♂️ [后台主编] 嗅探到新热点: {keyword}，开始异步清洗...")
    
    try:
        # 1. 大模型直连网搜 + 数据蒸馏 (合并为一次 API 调用以提升极速)
        # 将同步调用放到线程池中执行以防止阻塞事件循环
        def fetch_trend_data():
            return client.chat.completions.create(
                model="glm-4-flash", 
                messages=[
                    {"role": "system", "content": "你是一个无情的新闻主编。请结合联网搜索，提炼该热点事件。严格拆分为客观事实和主观舆论。必须输出纯合法的JSON，不要任何Markdown标记。格式：{\"objective_facts\": \"...\", \"subjective_vibes\": \"...\", \"core_summary\": \"...\"}"},
                    {"role": "user", "content": f"请搜索最新关于【{keyword}】的网络热点。"}
                ],
                tools=[{"type": "web_search", "web_search": {"enable": True}}],
                temperature=0.1
            )
        
        response = await asyncio.to_thread(fetch_trend_data)
        
        raw_text = response.choices[0].message.content.strip()
        # 极简清洗 JSON
        clean_text = raw_text.replace("```json", "").replace("```", "").strip()
        distilled_data = json.loads(clean_text)
        
        core_summary = distilled_data.get("core_summary", keyword)
        facts = distilled_data.get("objective_facts", "")
        vibes = distilled_data.get("subjective_vibes", "")
        
        # 2. ⚡ 强力注入 PGVector
        async with generate_vector_store() as store:
            await store.aadd_texts(
                texts=[core_summary],
                metadatas=[{
                    "doc_type": "trending_topic",
                    "keyword": keyword,
                    "facts": facts,
                    "vibes": vibes,
                    "source": "background_distillation"
                }]
            )
        print(f"✅ [后台主编] 热点 「{keyword}」 已成功清洗并注入 PGVector 武器库！")
        
    except Exception as e:
        print(f"❌ [后台主编] 处理热点 {keyword} 失败: {e}")
    finally:
        # 确保无论成功失败，锁都会被释放
        _active_tasks.discard(normalized_kw)
