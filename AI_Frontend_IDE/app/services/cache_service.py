import redis.asyncio as redis
from app.core.config import settings
import logging
import asyncio
import json
import os
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 使用环境变量中的 REDIS_URL，确保从 settings 读取
REDIS_URL = settings.REDIS_URL
redis_client = redis.from_url(REDIS_URL, decode_responses=False)

async def get_trend_cache(query: str, selected_element_id: str):
    """极速嗅探：从 Redis 获取已缓存的热点生成结果"""
    if not redis_client: return None
    cache_key = f"aifrontend:trend:{query}:{selected_element_id}"
    try:
        val = await redis_client.get(cache_key)
        return json.loads(val) if val else None
    except Exception: return None

async def set_trend_cache(query: str, selected_element_id: str, data: dict, expire: int = 86400):
    """热点收录：将生成结果存入 Redis 缓存"""
    if not redis_client: return
    cache_key = f"aifrontend:trend:{query}:{selected_element_id}"
    try:
        await redis_client.setex(cache_key, expire, json.dumps(data))
    except Exception: pass

class RiskControlCache:
    @staticmethod
    async def check_veto(query: str) -> bool:
        """双栈风控：关键词精确拦截 + 语义嗅探"""
        if not redis_client: return False
        normalized = query.strip().lower()
        try:
            # 1. 关键词拦截
            raw_words = await redis_client.smembers("aifrontend:veto:exact_words")
            exact_words = {w.decode("utf-8") if isinstance(w, bytes) else w for w in raw_words}
            
            # 如果 Redis 为空，触发一次紧急同步（从本地文件）
            if not exact_words:
                await sync_risk_words_from_local()
                raw_words = await redis_client.smembers("aifrontend:veto:exact_words")
                exact_words = {w.decode("utf-8") if isinstance(w, bytes) else w for w in raw_words}
                
            for word in exact_words:
                if word in normalized:
                    print(f"🚫 [风控拦截] 命中敏感词汇: {word}")
                    return True
            return False
        except Exception as e:
            logger.error(f"风控拦截执行出错: {e}")
            return False

async def sync_risk_words_from_local():
    """从本地 mock_veto_words.txt 同步最新违禁词到 Redis"""
    if not redis_client: return
    
    # 获取本地词库路径
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    # 新路径：app/mock/veto_words.txt
    mock_file = os.path.join(base_dir, "mock", "veto_words.txt")
    
    if not os.path.exists(mock_file):
        logger.warning(f"⚠️ 找不到本地风控词库文件: {mock_file}")
        # 尝试创建一个默认的 mock 文件
        try:
            os.makedirs(os.path.dirname(mock_file), exist_ok=True)
            with open(mock_file, "w", encoding="utf-8") as f:
                f.write("# XHS-Forge 默认风控词库\n暴力破解\n代写论文\n违禁品\n")
            logger.info(f"✅ 已自动生成默认风控词库: {mock_file}")
        except Exception:
            pass
        return

    print(f"📂 [风控同步] 正在从本地 Mock 目录读取词库: {mock_file}")
    try:
        new_words = []
        with open(mock_file, "r", encoding="utf-8") as f:
            for line in f:
                word = line.strip()
                # 过滤掉空行和注释行
                if word and not word.startswith("#"):
                    new_words.append(word)
        
        if new_words:
            # 增量追加到 Redis
            await redis_client.sadd("aifrontend:veto:exact_words", *new_words)
            count = await redis_client.scard("aifrontend:veto:exact_words")
            print(f"✅ [风控同步] 本地同步成功！当前黑名单总量: {count}")
    except Exception as e:
        logger.error(f"❌ [风控同步] 本地同步失败: {e}")

# 兼容旧名称以减少 main.py 的修改
sync_risk_words_from_cloud = sync_risk_words_from_local

async def scheduled_risk_sync_task():
    """定时同步守护任务：每天凌晨 02:00 重新从本地加载一次（支持运维热更新文件）"""
    while True:
        now = datetime.now()
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if now >= target: target += timedelta(days=1)
        sleep_seconds = (target - now).total_seconds()
        
        print(f"⏰ [定时任务] 下次本地风控词库重载将在 {sleep_seconds/3600:.2f} 小时后执行。")
        await asyncio.sleep(sleep_seconds)
        await sync_risk_words_from_local()
