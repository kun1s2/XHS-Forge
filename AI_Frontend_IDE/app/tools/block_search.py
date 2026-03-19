import json
from langchain_core.tools import tool
from app.core.block_registry import block_registry

@tool
def search_block_manual(keywords: str) -> str:
    """
    【架构级组件检索引擎】：
    作为 Outline Agent 的眼睛。当需要排版但不知道用什么积木时，输入关键词（如：'对比', '参数', '气氛'），
    返回匹配的积木使用说明书。
    """
    # 简单的分词检索（这里简化处理，实际可扩展为 embedding 检索）
    kws = [k.strip().lower() for k in keywords.split(",")]
    
    results = []
    for b in block_registry._blocks.values():
        desc_lower = b.description.lower()
        if any(kw in desc_lower for kw in kws) or any(kw in b.component_type.lower() for kw in kws):
            results.append(f"📦 [{b.component_type}] ({b.name}): {b.description}")
            
    if results:
        return "【为您检索到以下可用积木】：\n" + "\n".join(results)
    else:
        return "⚠️ 未找到完全匹配的特殊积木。建议退回使用 StoryText 或自行变通。"
