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

# --- 🧱 1. 基础排版系列 ---
block_registry.register(BlockInterface(component_type="TitleBlock", name="主标题卡", description="页面顶部的核心标题，抓取用户第一注意力。"))
block_registry.register(BlockInterface(component_type="StoryText", name="叙事文本", description="基础段落文本，用于逻辑连接。"))
block_registry.register(BlockInterface(component_type="CoverSwiper", name="大图轮播", description="展示多张高清图片的核心视觉件。"))
block_registry.register(BlockInterface(component_type="TagList", name="话题标签组", description="置于页尾，汇总 SEO 词汇和社交话题。"))
block_registry.register(BlockInterface(component_type="Divider", name="呼吸分割线", description="用于在密集信息间创造留白，控制节奏。"))

# --- 💻 2. 硬核测评系列 ---
block_registry.register(BlockInterface(component_type="VersusCard", name="红蓝对冲卡", description="展示两个品牌或正反观点的极性对决。", applicable_modes=["contrast"]))
block_registry.register(BlockInterface(component_type="ProductSpecCard", name="参数网格卡", description="将参数转化为整齐的网格展示。"))
block_registry.register(BlockInterface(component_type="RadarChartBlock", name="五维雷达图", description="数据可视化展示产品的综合素质。"))
block_registry.register(BlockInterface(component_type="ProgressBarSpec", name="性能 PK 条", description="直观对比单项数值（如续航、功率）。"))

# --- 🛍️ 3. 电商种草系列 ---
block_registry.register(BlockInterface(component_type="PriceTagBlock", name="爆款价格卡", description="高亮展示价格、促销和限时优惠。"))
block_registry.register(BlockInterface(component_type="QuoteBlock", name="金句放大卡", description="用于强调博主的锐评或核心痛点。"))
block_registry.register(BlockInterface(component_type="TimelineBlock", name="时空演进轴", description="梳理产品迭代或旅行打卡路线。"))

# --- 🎭 4. 高频互动系列 ---
block_registry.register(BlockInterface(component_type="PollBlock", name="互动投票卡", description="提供选项供用户站队，提升互动率。", action_type="interactive"))
block_registry.register(BlockInterface(component_type="GiftBox", name="惊喜礼盒", description="带动画的点击展开组件，用于揭晓惊喜。", action_type="interactive"))
block_registry.register(BlockInterface(component_type="FlipCard", name="翻转真相卡", description="点击翻转显示背面内容，制造悬念。", action_type="interactive"))

# --- ☕ 5. 生活方式系列 ---
block_registry.register(BlockInterface(component_type="WeatherPolaroid", name="氛围拍立得", description="带时间天气水印的图片，增强现场感。"))
block_registry.register(BlockInterface(component_type="LocationBlock", name="地图打卡卡", description="展示 POI 位置和距离，用于探店分享。"))
block_registry.register(BlockInterface(component_type="HandwrittenText", name="手写体感言", description="模拟私人手写笔记，传递情绪价值。"))
