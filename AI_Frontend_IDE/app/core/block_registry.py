from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field

class BlockInterface(BaseModel):
    """【积木语义契约】：定义积木如何被 Agent 理解与调用"""
    component_type: str = Field(..., description="积木的物理类型，对应 Vue 文件名")
    name: str = Field(..., description="积木的业务名称")
    description: str = Field(..., description="积木的用途描述（ReAct 推理的核心依据）")
    applicable_modes: List[str] = Field(default_factory=list)
    vibe_match: List[str] = Field(default_factory=list)
    action_type: Literal["display", "interactive", "conversion"] = Field("display")

class BlockRegistry:
    def __init__(self):
        self._blocks: Dict[str, BlockInterface] = {}

    def register(self, block: BlockInterface):
        self._blocks[block.component_type] = block

# 单例
block_registry = BlockRegistry()

# --- 🧱 正式主线：基础与高频承载容器 ---
block_registry.register(BlockInterface(component_type="TitleBlock", name="主标题卡", description="页面顶部的核心标题，抓取用户第一注意力。"))
block_registry.register(BlockInterface(component_type="StoryText", name="叙事文本", description="最自由的语义容器，适合承接任何暂时不需要特殊 UI 的正文、总结或解释。"))
block_registry.register(BlockInterface(component_type="CoverSwiper", name="封面轮播", description="用首屏图片和短文案建立页面第一印象；如果图片不足，也允许退回更轻的开场方式。"))
block_registry.register(BlockInterface(component_type="VersusCard", name="对比判断卡", description="把两种路线、两个品牌或两组观点放到一起，帮助用户快速看出取舍。", applicable_modes=["contrast"]))
block_registry.register(BlockInterface(component_type="ProductSpecCard", name="关键信息卡", description="当页面确实需要把参数、价格或事实整理成判断点时再使用；如果只是普通说明，不必强上参数卡。"))
block_registry.register(BlockInterface(component_type="RadarChartBlock", name="判断雷达图", description="当内容真的需要多维判断时再使用；如果依据还不够，宁可退回正文总结，也不要硬做成精确评分卡。"))
block_registry.register(BlockInterface(component_type="QuoteBlock", name="一句话摘要卡", description="用于强调一句核心观点摘要；如果没有明确来源或用户原话，就把它当摘要容器，而不是强做引用。"))
block_registry.register(BlockInterface(component_type="TimelineBlock", name="顺序时间轴", description="适合承接推荐顺序、阶段节点或已确认时间线；如果顺序感不强，允许退回正文说明，而不是硬写成日志。"))
block_registry.register(BlockInterface(component_type="PollBlock", name="互动投票卡", description="提供选项供用户站队，提升互动率。", action_type="interactive"))
block_registry.register(BlockInterface(component_type="WeatherPolaroid", name="氛围拍立得", description="当页面确实需要一块氛围画面时再使用；如果没有足够画面或场景感，也可以退回正文表达，不必假装现场快照。"))
block_registry.register(BlockInterface(component_type="LocationBlock", name="地点信息卡", description="展示地点建议或已确认位置信息；如果地点只是顺手一提，不必强做成独立地点卡或导航卡。"))
