import os
import time
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_community.chat_models import ChatTongyi
from langchain_core.prompts import ChatPromptTemplate

# 这是一个手动性能对比脚本，不应作为 pytest 用例执行。
__test__ = False

_env_path = Path(__file__).resolve().parent / "AI_Frontend_IDE" / ".env"
load_dotenv(dotenv_path=_env_path)

LLM_API_KEY = os.environ.get("LLM_API_KEY", "")
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "")
LLM_MODEL = os.environ.get("LLM_MODEL", "")


class MockDSL(BaseModel):
    thought_process: str = Field(description="思考过程（必须极简，绝不能超过20个字！）")
    page_title: str = Field(description="页面标题（10字以内）")
    summary: str = Field(description="核心摘要（50字以内）")


SYSTEM_PROMPT = """你是一个极其资深的数码架构师。
【强制要求】：
1. 必须从技术参数、二手残值、竞争对手等多个维度进行分析。
2. 必须包含对未来换代机型的市场预测。
3. ⚠️ 【字数红线】：请将你的回答总字数严格控制在 100 字以内！绝不废话！
(如果你在生成 JSON，请严格遵守 Schema 中的字数限制)"""

USER_PROMPT = "请分析并总结关于『索尼 A7M4 相机在 2026 年的市场地位』（考虑佳能 R6II、尼康 Z6III 的夹击）。"

prompt_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", USER_PROMPT)
])


def build_test_clients():
    return [
        (
            "ChatOpenAI 兼容",
            ChatOpenAI(
                api_key=LLM_API_KEY,
                base_url=LLM_BASE_URL,
                model=LLM_MODEL,
                temperature=0.1,
            ),
        ),
        (
            "ChatTongyi 原生",
            ChatTongyi(
                dashscope_api_key=LLM_API_KEY,
                model=LLM_MODEL,
                temperature=0.1,
            ),
        ),
    ]


async def run_test(name, llm):
    print(f"\n🚀 [测试开始]: {name}")
    results = {}
    base_chain = prompt_template | llm

    start = time.perf_counter()
    try:
        structured_llm = llm.with_structured_output(MockDSL)
        structured_chain = prompt_template | structured_llm
        resp = await structured_chain.ainvoke({})
        results['structured_time'] = time.perf_counter() - start
        print(f"  ✅ Structured 完成: {results['structured_time']:.2f}s")
        print(f"  📦 resp 预览: {resp}...")
        print(f"  📦 JSON 预览: {resp.model_dump_json()}...")
    except Exception as e:
        print(f"  ❌ Structured 失败: {e}")

    start = time.perf_counter()
    try:
        resp = await base_chain.ainvoke({})
        results['invoke_time'] = time.perf_counter() - start
        print(f"  ✅ Invoke 完成: {results['invoke_time']:.2f}s")
        print(f"  📦 resp 预览: {resp.content}...")
    except Exception as e:
        print(f"  ❌ Invoke 失败: {e}")

    start = time.perf_counter()
    ttft = None
    try:
        async for _chunk in base_chain.astream({}):
            if ttft is None:
                ttft = time.perf_counter() - start
        results['ttft'] = ttft
        results['stream_total'] = time.perf_counter() - start
        print(f"  ✅ Stream 完成: TTFT={ttft:.2f}s, Total={results['stream_total']:.2f}s")
    except Exception as e:
        print(f"  ❌ Stream 失败: {e}")

    return results


async def main():
    all_res = {}
    for name, llm in build_test_clients():
        all_res[name] = await run_test(name, llm)
        print("⏳ 冷却等待 3 秒...")
        await asyncio.sleep(3)

    print("\n" + "=" * 55)
    print("📊 [最终性能对比看板]")
    print(f"{'模型名称':<38} | {'Invoke':<7} | {'TTFT':<7} | {'Struct':<7}")
    print("-" * 75)
    for name, res in all_res.items():
        print(f"{name:<38} | {res.get('invoke_time', 0):>6.2f}s | {res.get('ttft', 0):>6.2f}s | {res.get('structured_time', 0):>6.2f}s")
    print("=" * 55)


if __name__ == "__main__":
    asyncio.run(main())
