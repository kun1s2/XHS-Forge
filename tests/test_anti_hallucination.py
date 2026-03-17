import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from langchain_core.messages import HumanMessage, SystemMessage

# 引入核心节点
from app.agents.nodes.research_agent import research_agent
from app.agents.nodes.content_node import content_agent
from app.agents.state import UIProjectState

# --- 🧪 核心测试：小米手机防幻觉回归测试 ---

@pytest.mark.asyncio
@patch("app.agents.nodes.research_agent.retrieve_from_mock_db")
async def test_xiaomi_latest_phone_regression(mock_retrieve):
    """
    【防幻觉回归战役】：验证系统在面对“新事实”时是否能压制“旧权重”
    """
    
    # 1. 网络隔离打桩：强制注入一个大模型本地权重绝对不存在的“未来机型”
    # 我们假设小米 17 Ultra 具备 1.5英寸超大底，这是 2026 年的事实
    FUTURE_FACT = """
    【绝密爆料】：小米 17 Ultra 正式发布！
    - 核心：搭载 1.5 英寸超大底主摄，行业首创。
    - 屏幕：4K 四等深微曲屏。
    - 电池：6500mAh 金沙江电池。
    - 警告：严禁提及过时的小米 13 Pro 或 14 Pro，那些机型的传感器只有 1 英寸。
    """
    mock_retrieve.return_value = FUTURE_FACT

    # 2. 初始化状态机：模拟用户输入
    state: UIProjectState = {
        "main_messages": [HumanMessage(content="写一篇最新的小米手机测评，重点说说相机")],
        "active_panel": "main",
        "retrieved_knowledge": {}, # 初始知识库为空
        "active_archetype": "general",
        "creator_persona": "硬核数码博主"
    }

    print("\n[Step 1]: 启动阻塞式调研节点 (research_node)...")
    
    # 3. 执行阶段一：阻塞式调研与结构化
    # 注意：此处会调用真实的 LLM 进行蒸馏，以验证 Prompt 的服从性
    research_result = await research_agent(state)
    
    # 4. 阶段一断言：检查知识库是否被同步硬化
    knowledge = research_result.get("retrieved_knowledge")
    assert knowledge is not None, "错误：调研节点未返回任何知识！"
    assert "17 Ultra" in knowledge.get("entity_name", ""), f"错误：调研节点未能识别出 17 Ultra，识别结果为: {knowledge.get('entity_name')}"
    assert "1.5" in str(knowledge), "错误：调研节点丢失了关键参数 1.5 英寸底！"
    
    print("✅ [阶段一通过]: 调研节点成功阻塞并完成了结构化蒸馏。")

    # 5. 准备进入文案节点：将调研结果注入状态
    state["retrieved_knowledge"] = knowledge
    state["active_archetype"] = research_result.get("active_archetype", "seeding")

    print("[Step 2]: 启动创作大脑 (content_node)，验证防幻觉表现...")
    
    # 6. 执行阶段二：创作生成
    # 此处调用真实的 gemini-3.0-flash，看它是否敢违背注入的 17 Ultra 事实
    content_result = await content_agent(state)
    
    # 获取生成的最终文案
    content_messages = content_result.get("content_messages", [])
    assert len(content_messages) > 0, "错误：文案大脑未生成任何内容！"
    
    final_content = content_messages[-1].content
    print(f"\n--- 生成文案预览 ---\n{final_content[:200]}...\n------------------")

    # 7. 致命断言：查服从性与防幻觉
    
    # 断言 A：必须包含新事实 (服从性)
    assert "17 Ultra" in final_content, "❌ [服从性失败]: 文案中未提及 17 Ultra！"
    assert "1.5" in final_content, "❌ [服从性失败]: 文案中未提及 1.5 英寸超大底！"
    
    # 断言 B：绝对禁止包含旧记忆 (防幻觉)
    # 大模型记忆中可能觉得小米 13 Pro 才是最新的大底，我们要确保它被压制
    hallucination_models = ["12 Pro", "13 Pro", "14 Pro"]
    for old_model in hallucination_models:
        assert old_model not in final_content, f"❌ [幻觉检测]: 文案中混入了过时型号 {old_model}，系统防幻觉失效！"

    print("\n🏆 [防幻觉回归测试通过]: 阻塞式 RAG 成功压制了大模型的本地旧记忆！")

if __name__ == "__main__":
    # 方便直接运行测试
    asyncio.run(test_xiaomi_latest_phone_regression())
