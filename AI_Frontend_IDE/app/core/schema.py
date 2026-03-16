from enum import Enum
from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, field_validator
import re

# --- ✨ 维度一：业务建模 —— Archetype 宪法 ---

class ArchetypeEnum(str, Enum):
    """业务场景原型枚举"""
    GENERAL = "general"      # 通用/未分类
    GOURMET = "gourmet"      # 探店美食
    TRAVEL = "travel"        # 旅游游记
    SEEDING = "seeding"      # 好物种草/带货
    NEWS = "news"            # 资讯攻略
    OOTD = "ootd"            # 每日穿搭/美妆

class ArchetypeContract(BaseModel):
    """场景契约：规定了该场景下【必须】包含的组件类型"""
    archetype: ArchetypeEnum
    required_components: List[str]
    suggested_order: List[str]
    description: str

# 契约映射表：确保生成式 UI 的确定性
ARCHETYPE_CONTRACTS: Dict[ArchetypeEnum, ArchetypeContract] = {
    ArchetypeEnum.GOURMET: ArchetypeContract(
        archetype=ArchetypeEnum.GOURMET,
        required_components=["CoverSwiper", "TitleBlock", "ProductCard", "LocationBlock", "TagList", "InteractionsBar"],
        suggested_order=["CoverSwiper", "TitleBlock", "ProductCard", "LocationBlock", "StoryText", "TagList", "InteractionsBar"],
        description="探店美食契约：必须包含商品/店铺卡片、评分以及地理位置打卡。"
    ),
    ArchetypeEnum.TRAVEL: ArchetypeContract(
        archetype=ArchetypeEnum.TRAVEL,
        required_components=["CoverSwiper", "TitleBlock", "StoryText", "TagList", "InteractionsBar"],
        suggested_order=["CoverSwiper", "TitleBlock", "StoryText", "TagList", "InteractionsBar"],
        description="旅游游记契约：强调多图轮播与大段文字叙事。"
    ),
    ArchetypeEnum.SEEDING: ArchetypeContract(
        archetype=ArchetypeEnum.SEEDING,
        required_components=["CoverSwiper", "ProductCard", "ProductSpecCard", "StoryText", "TagList", "InteractionsBar"],
        suggested_order=["CoverSwiper", "ProductCard", "ProductSpecCard", "TitleBlock", "StoryText", "TagList", "InteractionsBar"],
        description="种草带货契约：必须将商品卡片和参数规格置于显眼位置。"
    ),
    ArchetypeEnum.NEWS: ArchetypeContract(
        archetype=ArchetypeEnum.NEWS,
        required_components=["TitleBlock", "StoryText", "TagList", "InteractionsBar"],
        suggested_order=["TitleBlock", "StoryText", "TagList", "InteractionsBar"],
        description="资讯攻略契约：强调标题的即时性与内容的条理性。"
    )
}

# --- ✨ 维度三：工程契约 —— DSL 规范 ---

class ComponentOutline(BaseModel):
    id: str = Field(..., description="组件的唯一ID，如 'title_1', 'product_1'")
    type: Literal["CoverSwiper", "TitleBlock", "StoryText", "ProductCard", "TagList", "LocationBlock", "ProductSpecCard", "InteractionsBar"] = Field(..., description="组件类型")

class OutlineOutput(BaseModel):
    """大纲大脑输出的页面结构"""
    page_title: str = Field(..., description="网页标签标题")
    page_order: List[ComponentOutline] = Field(..., description="页面的组件大纲序列")
    detected_archetype: ArchetypeEnum = Field(default=ArchetypeEnum.GENERAL, description="本次排版最终确定的业务原型")

    @field_validator('page_order', mode='before')
    @classmethod
    def handle_string_ids(cls, v: Any) -> Any:
        """【极限容错】：如果模型只吐了 ID 列表，尝试自动恢复类型"""
        if isinstance(v, list) and len(v) > 0 and isinstance(v[0], str):
            new_order = []
            for item_id in v:
                # 根据 ID 前缀尝试推断类型，推断失败默认用 StoryText
                lower_id = item_id.lower()
                inferred_type = "StoryText"
                if "swiper" in lower_id: inferred_type = "CoverSwiper"
                elif "title" in lower_id: inferred_type = "TitleBlock"
                elif "product" in lower_id: inferred_type = "ProductCard"
                elif "spec" in lower_id: inferred_type = "ProductSpecCard"
                elif "tags" in lower_id: inferred_type = "TagList"
                elif "location" in lower_id: inferred_type = "LocationBlock"
                elif "social" in lower_id or "interaction" in lower_id: inferred_type = "InteractionsBar"
                
                new_order.append({"id": item_id, "type": inferred_type})
            return new_order
        return v

class ComponentData(BaseModel):
    """组件参数规范 (ComponentPayload)"""
    type: Literal["CoverSwiper", "TitleBlock", "StoryText", "ProductCard", "TagList", "LocationBlock", "ProductSpecCard", "InteractionsBar"] = Field(..., description="组件类型标识符")
    title: Optional[str] = Field(None, description="主标题内容")
    subtitle: Optional[str] = Field(None, description="副标题内容")
    paragraphs: Optional[List[str]] = Field(None, description="正文文本段落")
    image_url: Optional[str] = Field(None, description="单图 URL")
    image_urls: Optional[List[str]] = Field(None, description="多图 URL 数组")
    price: Optional[str] = Field(None, description="价格信息（如 ￥99.00）")
    desc: Optional[str] = Field(None, description="描述性短文案")
    tags: Optional[List[str]] = Field(None, description="话题标签数组")
    rating: Optional[float] = Field(None, description="评分（0-5）")
    
    # ✨ 坐标与地理位置增强
    location: Optional[str] = Field(None, description="详细地址信息")
    poi_name: Optional[str] = Field(None, description="POI 地点名称（用于搜索）")
    lat: Optional[float] = Field(None, description="纬度")
    lng: Optional[float] = Field(None, description="经度")

    # ✨ 事实增强与参数卡片
    core_features: Optional[List[str]] = Field(None, description="核心参数/特性列表（用于 ProductSpecCard）")

    # ✨ 互动数据增强
    likes: Optional[Union[str, int]] = Field(None, description="点赞数（如 1.2w）")
    collects: Optional[Union[str, int]] = Field(None, description="收藏数")
    comments: Optional[Union[str, int]] = Field(None, description="评论数")

    @field_validator('likes', 'collects', 'comments', mode='before')
    @classmethod
    def ensure_string_metrics(cls, v: Any) -> Optional[str]:
        """【强制补丁】：如果模型吐了数字，自动转为字符串"""
        if v is None: return None
        return str(v)

    @field_validator('rating', mode='before')
    @classmethod
    def clean_rating(cls, v: Any) -> Any:
        """【鲁棒性增强】：自动清洗大模型输出的带单位评分（如 '4.7分' -> 4.7）"""
        if isinstance(v, str):
            # 使用正则提取数字部分
            match = re.search(r"[-+]?\d*\.\d+|\d+", v)
            if match:
                return float(match.group())
        return v

class StructurePatchOutput(BaseModel):
    """排版大脑输出的 DSL 宪法结构"""
    thought_process: str = Field(description="排版决策推理过程")
    page_title: str = Field(..., description="网页标签标题")
    page_order: List[str] = Field(..., description="组件 ID 的线性排列顺序")
    components: Dict[str, ComponentData] = Field(..., description="组件的具体数据负载")
    detected_archetype: ArchetypeEnum = Field(default=ArchetypeEnum.GENERAL, description="本次排版最终确定的业务原型")

class SurgicalPatchOutput(BaseModel):
    """【手术刀模式】专用输出模型：仅修改单个组件内容"""
    thought_process: str = Field(description="局部修改决策推理过程")
    reason: str = Field(..., description="修改该组件的极简理由。")
    updated_component: ComponentData = Field(..., description="被选中的组件更新后的完整数据对象。")

# --- ✨ 维度四：意图路由 —— Intent 宪法 ---

class IntentOutput(BaseModel):
    """意图分析大脑的输出结构"""
    thought_process: str = Field(description="思维链推理过程")
    reason: str = Field(..., description="极简理由（10字以内）。")
    intent_route: Literal["content_node", "structure_node", "style_node", "rag_node", "patch_node"] = Field(..., description="决定路由的节点名")
    scenarios: List[str] = Field(default_factory=list, description="识别的业务场景标签")
    detected_archetype: ArchetypeEnum = Field(default=ArchetypeEnum.GENERAL, description="识别出的业务场景原型")

    @field_validator('scenarios', mode='before')
    @classmethod
    def validate_scenarios(cls, v: Any) -> List[str]:
        if not isinstance(v, list): return []
        ALLOWED = {"travel", "food", "seeding", "news"}
        return [item for item in v if item in ALLOWED]

class StyleVibeTokens(BaseModel):
    """视觉感知引擎生成的 Vibe Tokens（呼吸感核心）"""
    primary_color: str = Field("#ff2442", description="提取的主题色/品牌色")
    primary_color_light: str = Field("rgba(255, 36, 66, 0.1)", description="浅色背景变体（呼吸感背景用）")
    primary_color_dark: str = Field("#e01d37", description="深色点击变体")
    background_vibe: str = Field("#ffffff", description="背景调性色")
    text_hierarchy: Dict[str, str] = Field(
        default={"title": "#111111", "body": "#333333", "dim": "#999999"},
        description="文字颜色层级"
    )

class ComponentStyle(BaseModel):
    """单组件样式协议"""
    css_classes: str = Field("", description="Tailwind CSS 类名")
    inline_styles: Dict[str, str] = Field(default_factory=dict, description="动态注入的内联样式")

class StylePatchOutput(BaseModel):
    """样式大脑输出的视觉宪法结构"""
    thought_process: str = Field(description="视觉样式推理过程")
    global_tokens: StyleVibeTokens = Field(default_factory=StyleVibeTokens, description="从图片提取的全局视觉 Token")
    global_vars: Dict[str, str] = Field(default_factory=dict, description="注入 CSS 的全局变量")
    components: Dict[str, ComponentStyle] = Field(default_factory=dict, description="各组件的样式补丁")
