import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from pydantic import ValidationError
from fastapi.testclient import TestClient

# 引入核心业务组件
from app.core.schema import FocusedKnowledge
from app.services.mock_rag_service import retrieve_from_mock_db
from app.agents.nodes.research_agent import research_agent
from app.agents.state import UIProjectState
from app.main import app # 引入 FastAPI 实例

# --- 🧪 Test Suite 1: 测试 Mock 库与 Schema 强校验 ---

@pytest.mark.asyncio
async def test_mock_db_retrieval():
    """验证本地热缓存能否正确命中"""
    # 命中测试
    content = await retrieve_from_mock_db("帮我看看小米17 Ultra")
    assert content is not None
    assert "骁龙 8 Gen 5" in content
    
    # 错过测试
    missing = await retrieve_from_mock_db("不存在的神秘产品")
    assert missing is None

def test_focused_knowledge_schema():
    """验证 Pydantic 契约的严谨性"""
    valid_data = {
        "domain_category": "3C数码测评",
        "entity_name": "小米 17 Ultra",
        "core_attributes": {"处理器": "骁龙8 Gen 5"},
        "key_selling_points": ["卫星通话"],
        "known_issues": ["重"],
        "summary": "测试总结"
    }
    
    # 1. 实例化测试
    knowledge = FocusedKnowledge(**valid_data)
    assert knowledge.domain_category == "3C数码测评"
    
    # 2. 越界测试：传入非法领域
    invalid_data = valid_data.copy()
    invalid_data["domain_category"] = "非法领域 (如金融)"
    with pytest.raises(ValidationError):
        FocusedKnowledge(**invalid_data)

# --- 🧪 Test Suite 2: 测试主线阻塞与时序流转 ---

@pytest.mark.asyncio
@patch.dict(
    "app.agents.nodes.research_agent.TOOL_POOL",
    {
        "network_search": MagicMock(
            ainvoke=AsyncMock(side_effect=[
                "小米 17 Ultra 参数: CPU=Snapdragon 8 Gen 5, 价格=6999",
                "用户评价: 影像强，但价格偏高"
            ])
        )
    },
)
@patch("app.agents.nodes.research_agent.search_google_images", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.get_hot_knowledge", new_callable=AsyncMock)
@patch("app.services.cache_service.cache_service.match_trends_in_text", new_callable=AsyncMock)
async def test_research_node_blocking_flow(mock_match_trends, mock_get_hot_knowledge, mock_search_google_images):
    """【核心战役】：验证 research_node 必须阻塞并正确填充 State"""

    mock_match_trends.return_value = []
    mock_get_hot_knowledge.return_value = None
    mock_search_google_images.return_value = []
    
    # 2. 构造初始状态
    from langchain_core.messages import HumanMessage
    state: UIProjectState = {
        "main_messages": [HumanMessage(content="我想写小米17 Ultra")],
        "active_panel": "main",
        "retrieved_knowledge": None,
        "intent_result": {"asset_request": "NONE"},
    }
    
    # 3. 触发节点（执行必须是阻塞的）
    result = await research_agent(state)
    
    # 4. 生死断言：检查状态机是否被同步更新
    assert result["retrieved_knowledge"] is not None
    assert result["retrieved_knowledge"]["entity_name"] == "小米17 Ultra"
    assert result["retrieved_knowledge"]["is_fact_ready"] is True
    assert "Snapdragon 8 Gen 5" in result["retrieved_knowledge"]["text_facts"]
    assert result["image_assets"] == []
    print("\n✅ [时序校验通过]: research_node 已阻塞完成并成功回填 State。")

# --- 🧪 Test Suite 3: 测试白盒探针 API ---

def test_glassbox_inspect_api():
    """验证前端能否顺利偷窥 Agent 脑电图"""
    # ✨ 哨兵修复：手动初始化 app.state，防止 AttributeError
    if not hasattr(app.state, 'agent'):
        app.state.agent = MagicMock()
        
    client = TestClient(app)
    
    # 1. 模拟一个 thread_id
    test_thread_id = "test_case_001"
    
    # 2. Mock 掉 app.state.agent 的 aget_state 方法
    # 创建一个模拟的 StateSnapshot
    mock_values = {
        "intent_route": "research_agent",
        "creator_persona": "硬核数码博主",
        "retrieved_knowledge": {"entity_name": "小米 17 Ultra", "summary": "热缓存命中"}
    }
    mock_snapshot = MagicMock()
    mock_snapshot.values = mock_values
    
    # 使用 patch 修改 mock 对象的 aget_state 行为
    app.state.agent.aget_state = AsyncMock(return_value=mock_snapshot)
    
    # 3. 发起请求
    response = client.get(f"/workspace/{test_thread_id}/inspect")
    
    # 4. 断言
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["data"]["intent_route"] == "research_agent"
    assert data["data"]["creator_persona"] == "硬核数码博主"
    assert data["data"]["retrieved_knowledge"]["entity_name"] == "小米 17 Ultra"
    print("\n✅ [白盒探针通过]: FastAPI 成功透传 Agent 决策元数据。")

if __name__ == "__main__":
    # 方便直接运行
    asyncio.run(test_mock_db_retrieval())
    test_focused_knowledge_schema()
    print("Suite 1: OK")
