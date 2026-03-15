import asyncio
import os
import sys
import selectors
from pathlib import Path

# 将项目根目录加入路径，确保能导入 app 模块
sys.path.append(str(Path(__file__).parents[2]))

from app.core.persistence import generate_vector_store
from langchain_core.documents import Document

async def seed_data():
    print("🚀 \033[1m开始执行【PGVector 终极 RAG】数据灌溉...\033[0m")
    
    # 构造 20 条包含价格、品牌、城市等丰富 metadata 的测试数据
    rich_docs = [
        # 咖啡系列
        Document(
            page_content="【极密】陨石生椰拿铁：内部定价 ¥19.9。采用宁夏冷榨生椰乳，混合 II 级黑巧风味陨石晶球。",
            metadata={"doc_type": "product_specs", "brand": "my_coffee", "price": 19.9, "city": "北京", "status": "active"}
        ),
        Document(
            page_content="【新品】丝绒拿铁：定价 ¥22.0。口感丝滑如绸缎，使用定制 0 糖丝绒乳。",
            metadata={"doc_type": "product_specs", "brand": "my_coffee", "price": 22.0, "city": "上海", "status": "active"}
        ),
        Document(
            page_content="【经典】美式咖啡：定价 ¥15.0。精选埃塞俄比亚日晒豆，柑橘香气浓郁。",
            metadata={"doc_type": "product_specs", "brand": "my_coffee", "price": 15.0, "city": "北京", "status": "active"}
        ),
        # 护肤品系列 (SK-II 模拟)
        Document(
            page_content="SK-II 神仙水 (护肤精华露)：专柜价 ¥1690。核心成分 PITERA™，提升晶莹剔透感。",
            metadata={"doc_type": "product_specs", "brand": "SK-II", "price": 1690.0, "category": "skincare"}
        ),
        Document(
            page_content="SK-II 大红瓶面霜：专柜价 ¥1310。紧致提拉，多维充盈，针对 25+ 熟龄肌。",
            metadata={"doc_type": "product_specs", "brand": "SK-II", "price": 1310.0, "category": "skincare"}
        ),
        # 数码产品 (iPhone 18 模拟)
        Document(
            page_content="iPhone 18 Pro：内部预估价 ¥9999。首创全息投影显示，搭载 A20 仿生芯片。",
            metadata={"doc_type": "gadget_news", "brand": "Apple", "price": 9999.0, "year": 2026}
        ),
        Document(
            page_content="Apple Watch Ultra 4：定价 ¥6699。支持 100 米潜水，新增卫星求救求生模式。",
            metadata={"doc_type": "product_specs", "brand": "Apple", "price": 6699.0, "year": 2026}
        ),
        # 美食探店
        Document(
            page_content="顺德细妹牛杂：人均 ¥45。老字号，酱汁浓郁，推荐萝卜和牛肺。",
            metadata={"doc_type": "gourmet_review", "brand": "细妹牛杂", "price": 45.0, "city": "顺德"}
        ),
        Document(
            page_content="上海阿姨奶茶：人均 ¥18。血糯米浓厚，口感丰富，童年回忆。",
            metadata={"doc_type": "gourmet_review", "brand": "阿姨奶茶", "price": 18.0, "city": "上海"}
        ),
        Document(
            page_content="成都陈麻婆豆腐：人均 ¥60。正宗川味，麻辣鲜香，非物质文化遗产。",
            metadata={"doc_type": "gourmet_review", "brand": "陈麻婆豆腐", "price": 60.0, "city": "成都"}
        ),
        # 更多数据填充到 20 条
        Document(page_content="瑞幸咖啡联名：猫和老鼠联名拿铁，限时 ¥9.9。", metadata={"brand": "Luckin", "price": 9.9, "status": "expired"}),
        Document(page_content="库迪咖啡：米博联名，全场 ¥8.8。", metadata={"brand": "Cotti", "price": 8.8, "status": "expired"}),
        Document(page_content="Dyson 吹风机：售价 ¥2999。负离子护发，高速马达。", metadata={"brand": "Dyson", "price": 2999.0}),
        Document(page_content="特斯拉 Model 3：落地价 ¥245900。极简内饰，辅助驾驶升级。", metadata={"brand": "Tesla", "price": 245900.0}),
        Document(page_content="大疆 Neo 2 无人机：售价 ¥1999。掌上起降，AI 自动跟随拍摄。", metadata={"brand": "DJI", "price": 1999.0}),
        Document(page_content="喜茶：多肉葡萄 ¥19.0。真果肉，芝士浓郁。", metadata={"brand": "Heytea", "price": 19.0, "city": "深圳"}),
        Document(page_content="奈雪的茶：鸭屎香柠檬茶 ¥16.0。清爽解腻。", metadata={"brand": "Nayuki", "price": 16.0, "city": "深圳"}),
        Document(page_content="全聚德：烤鸭 ¥298。皮脆肉嫩，北京特产。", metadata={"brand": "全聚德", "price": 298.0, "city": "北京"}),
        Document(page_content="小龙坎火锅：人均 ¥150。正宗麻辣，环境古色古香。", metadata={"brand": "小龙坎", "price": 150.0, "city": "成都"}),
        Document(page_content="海底捞：人均 ¥120。服务天花板，菜品丰富。", metadata={"brand": "海底捞", "price": 120.0, "city": "全球"})
    ]

    # 2. 获取向量库连接并灌入
    async with generate_vector_store() as store:
        print("📡 正在调用智谱 Embedding-3 进行向量化并存入 PGVector...")
        # 清除旧数据以便重新测试（可选，这里采用追加）
        await store.aadd_documents(rich_docs)
        print("✅ \033[92m20 条多维元数据已成功入库！\033[0m")

if __name__ == "__main__":
    selector = selectors.SelectSelector()
    loop = asyncio.SelectorEventLoop(selector)
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(seed_data())
    finally:
        loop.close()
