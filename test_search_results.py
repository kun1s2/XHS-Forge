import asyncio
from zhipuai import ZhipuAI
import os
from dotenv import load_dotenv

# 加载环境变量
load_dotenv(dotenv_path="AI_Frontend_IDE/.env")

def test_fetch_search_results(keyword: str):
    api_key = os.getenv("ZHI_PU_API_KEY")
    if not api_key:
        print("❌ 错误: 未在 .env 中找到 ZHI_PU_API_KEY")
        return

    client = ZhipuAI(api_key=api_key)
    
    print(f"🌐 [测试] 正在调用智谱搜网，关键词: 「{keyword}」...")
    try:
        response = client.web_search.web_search(
            search_engine="search_pro",
            search_query=keyword,
            count=15,
            content_size="high"
        )
        
        # 提取搜索结果列表
        res = getattr(response, "search_result", [])
        print(f"✅ 搜集到 {len(res)} 条原始结果")
        
        full_context_list = []
        for i, item in enumerate(res):
            # 兼容处理：智谱返回的是对象列表，而非字典列表
            title = getattr(item, "title", "无标题")
            link = getattr(item, "link", "无链接")
            content = getattr(item, "content", "")
            
            print(f"\n--- 结果 [{i+1}] ---")
            print(f"标题: {title}")
            print(f"链接: {link}")
            print(f"内容预览 (前150字): {content[:150]}...")
            print(f"内容总长度: {len(content)} 字符")
            full_context_list.append(content)

        full_context = "\n".join(full_context_list)
        print(f"\n==================================================")
        print(f"📊 [数据统计]")
        print(f"合并后的总文本长度: {len(full_context)} 字符")
        print(f"是否超过阿里兼容模式限制 (30000字符): {'⚠️ 是' if len(full_context) > 30000 else '✅ 否'}")
        print(f"==================================================")

    except Exception as e:
        print(f"❌ 搜索失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    kw = "索尼 A7M4 相机测评"
    test_fetch_search_results(kw)
