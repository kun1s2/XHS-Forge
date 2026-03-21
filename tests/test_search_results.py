import os

import pytest
from dotenv import load_dotenv
from zhipuai import ZhipuAI
from zhipuai.core._errors import APIConnectionError

load_dotenv(dotenv_path="AI_Frontend_IDE/.env")


@pytest.mark.integration
def test_fetch_search_results():
    api_key = os.getenv("ZHI_PU_API_KEY")
    if not api_key:
        pytest.skip("未配置 ZHI_PU_API_KEY，跳过真实搜网测试")

    keyword = "索尼 A7M4 相机测评"
    client = ZhipuAI(api_key=api_key)
    try:
        response = client.web_search.web_search(
            search_engine="search_pro",
            search_query=keyword,
            count=5,
            content_size="high",
        )
    except APIConnectionError:
        pytest.skip("当前环境无法访问外部搜索服务，跳过真实搜网测试")

    results = getattr(response, "search_result", [])
    assert isinstance(results, list)
