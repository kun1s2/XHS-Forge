import asyncio
import os
import sys

# 设置路径以导入项目模块
import os
import sys
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'AI_Frontend_IDE'))

from app.agents.tools_registry import google_images

async def test_image_search():
    print("🧪 [Test] 启动图片搜索工具测试...")
    query = "Sony A7C2 silver black product photo"
    print(f"📡 搜索关键词: {query}")
    
    try:
        # 调用工具
        result = await google_images.ainvoke({"query": query})
        print("\n--- 🔍 搜索结果 ---")
        print(result)
        
        if "http" in result:
            print("\n✅ [成功] 工具返回了图片链接！")
            # 检查链接有效性（简单正则）
            import re
            urls = re.findall(r'https?://[^\s<>"]+?\.(?:jpg|jpeg|png|webp)', result)
            if urls:
                print(f"📦 捕获到 {len(urls)} 条有效图片直链：")
                for i, url in enumerate(urls, 1):
                    print(f"  [{i}] {url}")
            else:
                print("⚠️  警告：虽然有 http 字符串，但未匹配到标准图片直链后缀。可能是网页链接。")
        else:
            print("\n❌ [失败] 工具未返回任何有效链接。请检查 API Key 或 网络连接。")
            
    except Exception as e:
        print(f"\n💥 [异常] 测试过程中发生错误: {e}")

if __name__ == "__main__":
    asyncio.run(test_image_search())
