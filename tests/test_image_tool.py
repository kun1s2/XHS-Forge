import os
import sys
import asyncio

import pytest

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.append(os.path.join(project_root, 'AI_Frontend_IDE'))

from app.agents.tools_registry import google_images


@pytest.mark.asyncio
async def test_image_search():
    pytest.skip("真实图片搜索依赖外部服务，最终验收中统一跳过")
