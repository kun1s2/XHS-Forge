import hashlib
import json
import logging
import asyncio
from app.core.config import settings
import redis.asyncio as redis

# 引入 PGVector 基础设施
from app.core.persistence import generate_vector_store
from langchain_core.documents import Document

logger = logging.getLogger(__name__)

# 初始化异步 Redis 连接池
try:
    redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning(f"Redis 连接初始化失败: {e}")
    redis_client = None

# 语义相似度阈值（0.95 表示极度相似）
SEMANTIC_THRESHOLD = 0.95

def _generate_exact_key(query: str, selected_element: str) -> str:
    """生成精确匹配的短缓存 Key（用于兜底或精准命中）"""
    normalized = query.strip().lower()
    raw = f"{normalized}_{selected_element}"
    return f"social_engine:cache:exact:{hashlib.md5(raw.encode()).hexdigest()}"

async def get_trend_cache(query: str, selected_element: str):
    """
    【真·语义缓存嗅探】：结合 PGVector 与 Redis。
    """
    if not redis_client:
        return None

    # 1. 第一道防线：极速精准匹配 (MD5)
    exact_key = _generate_exact_key(query, selected_element)
    try:
        cached_data = await redis_client.get(exact_key)
        if cached_data:
            print(f"⚡ [精准缓存命中] MD5 拦截: {query[:15]}...")
            return json.loads(cached_data)
    except Exception as e:
        logger.warning(f"读取 Redis 精准缓存失败: {e}")

    # 2. 第二道防线：高阶语义嗅探 (PGVector)
    # 只有全局生成（未选中局部元素）且指令较长时，才建议走语义缓存
    if selected_element in ["无 (全局修改)", "none", None] and len(query) > 5:
        print(f"🧠 [语义嗅探] 正在为「{query[:15]}...」计算向量距离...")
        
        # ✨ 代码净化：简单的实体抽取，防止“泛指令”导致缓存误杀
        import re
        # 如果指令太短或只是“好物分享”、“探店”这种泛词，直接跳过语义匹配
        if re.match(r"^(写|帮我写).*(测评|笔记|探店|推荐|分享)的?$", query.strip()):
            print(f"⚠️ [语义嗅探] 识别为高危泛查询，跳过语义拦截以防误杀。")
            return None
            
        try:
            async with generate_vector_store() as store:
                # 执行相似度检索（带分数），只取最相似的 1 条
                results = await store.asimilarity_search_with_relevance_scores(
                    query, 
                    k=1, 
                    # 可以通过 filter 限制只搜 cache 类型
                    # filter={"doc_type": "semantic_cache"} 
                )
                
                if results:
                    doc, score = results[0]
                    # score 越接近 1 越相似 (具体取决于距离度量，这里假设是余弦相似度转化)
                    print(f"📊 [语义比对] 找到最近邻: 「{doc.page_content[:15]}...」 (得分: {score:.4f})")
                    
                    if score >= SEMANTIC_THRESHOLD and doc.metadata.get("redis_key"):
                        target_redis_key = doc.metadata["redis_key"]
                        semantic_data = await redis_client.get(target_redis_key)
                        if semantic_data:
                            print(f"\033[92m🚀 [语义缓存] 命中高相似度热点，大模型已旁路！(相似度: {score:.2f})\033[0m")
                            return json.loads(semantic_data)
        except Exception as e:
            logger.error(f"PGVector 语义检索失败: {e}")

    return None

async def set_trend_cache(query: str, selected_element: str, dsl_result: dict, ttl_seconds: int = 3600):
    """将结果存入 Redis，并将 Query 向量化存入 PGVector 构建语义防线"""
    if not redis_client:
        return
        
    exact_key = _generate_exact_key(query, selected_element)
    
    try:
        # 1. 存入 Redis (物理数据)
        await redis_client.setex(exact_key, ttl_seconds, json.dumps(dsl_result))
        print(f"💾 [缓存写入] 物理数据已入 Redis (TTL: {ttl_seconds}s)")
        
        # 2. 存入 PGVector (语义指针)
        # 同样，只有全局生成才建立语义索引
        if selected_element in ["无 (全局修改)", "none", None]:
            async with generate_vector_store() as store:
                doc = Document(
                    page_content=query.strip(),
                    metadata={
                        "doc_type": "semantic_cache", 
                        "redis_key": exact_key,
                        "element": selected_element
                    }
                )
                await store.aadd_documents([doc])
                print(f"🕸️ [语义布网] Query 向量已入库，指向 {exact_key}")
                
    except Exception as e:
        logger.warning(f"写入语义缓存体系失败: {e}")

class RiskControlCache:
    """【双栈风控系统】结合 Redis 和 PGVector 的动态否决缓存"""
    
    @staticmethod
    async def check_veto(query: str) -> bool:
        if not redis_client:
            return False
            
        normalized = query.strip().lower()
        
        # 1. 检查精确词拦截 (Redis Set)
        try:
            # 获取精确否决词列表 (确保 Redis 客户端已配置 decode_responses=True)
            # 如果没配置，我们这里手动解码
            raw_words = await redis_client.smembers("aifrontend:veto:exact_words")
            exact_words = {w.decode("utf-8") if isinstance(w, bytes) else w for w in raw_words}
            
            if not exact_words:
                # 初始设定几个敏感词用于演示（实际生产环境建议对接专业风控 API）
                default_veto = [
                    "代写论文", "违禁品", "敏感话题", 
                    "暴力破解", "脱库", "黑客教程", "破解补丁", 
                    "病毒源码", "攻击脚本", "入侵教程"
                ]
                await redis_client.sadd("aifrontend:veto:exact_words", *default_veto)
                exact_words = set(default_veto)
                
            for word in exact_words:
                if word in normalized:
                    print(f"🚫 [风控拦截] 命中敏感词汇: {word}")
                    return True
                    print(f"🚫 [风控拦截] 命中敏感词汇: {word}")
                    return True
        except Exception as e:
            logger.warning(f"读取 Redis 风控词失败: {e}")

        # 2. 检查语义向量拦截 (PGVector)
        # 假设我们在库里存了 doc_type = "veto_topic" 的风控知识
        print(f"🛡️ [风控嗅探] 正在进行语义级安全检查...")
        try:
            async with generate_vector_store() as store:
                results = await store.asimilarity_search_with_relevance_scores(
                    query, 
                    k=1
                )
                if results:
                    doc, score = results[0]
                    # 如果高度相似且标记为 veto_topic
                    if score >= 0.95 and doc.metadata.get("doc_type") == "veto_topic":
                        print(f"🚫 [风控拦截] 命中违规语义: {doc.page_content[:15]}... (相似度: {score:.2f})")
                        return True
        except Exception as e:
            logger.warning(f"PGVector 风控语义检查失败: {e}")

        return False
