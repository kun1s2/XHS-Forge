from enum import Enum
from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, field_validator
import re

# --- ✨ 维度一：业务建模 —— 动态协议 ---

class ArchetypeEnum(str, Enum):
    """业务场景标签 (保留常用语义标识，底层已改为动态加载)"""
    GENERAL = "general"
    GOURMET = "gourmet"
    TRAVEL = "travel"
    SEEDING = "seeding"
    NEWS = "news"

class ArchetypeContract(BaseModel):
    """场景契约模型：定义该赛道下的组件黑白名单与推荐序列"""
    scenario_id: str
    required_components: List[str] = Field(default_factory=list)
    suggested_order: List[str] = Field(default_factory=list)
    description: str = ""

# --- ✨ 维度二：工程契约 —— DSL 规范 ---

class UINode(BaseModel):
    """UI 抽象语法树的核心节点"""
    id: str = Field(description="组件全局唯一ID，如 hero_bento_1, text_intro")
    component_type: str = Field(description="前端组件字典中的类型，如 Container, BentoGrid, ProductCard, StoryText")
    
    # 核心：用语义化 Props 替代 Tailwind class
    props: Dict[str, Any] = Field(
        default_factory=dict, 
        description="语义化属性。例如 {'variant': 'glassmorphism', 'layout': 'row', 'emphasis': 'high', 'animation': 'fade-up'}"
    )
    
    # 核心：上下文切片（仅对需要生成内容的叶子节点有效）
    content_brief: Optional[str] = Field(
        None, 
        description="任务简报。如果该组件需要并发工兵填充内容，在此写明指令（如：'仅撰写屏幕参数，限50字'）"
    )
    
    # 核心：无限嵌套能力
    children: Optional[List['UINode']] = Field(None, description="嵌套的子组件列表")

# 解决 Pydantic 的递归类型引用
UINode.model_rebuild()

class OutlineOutput(BaseModel):
    """大纲大脑输出的页面结构 (基于 AST)"""
    thought_process: str = Field(description="大纲排版与组件选型的推理过程")
    page_title: str = Field(..., description="网页标签标题")
    page_theme: Dict[str, str] = Field(default_factory=dict, description="全局 CSS 变量字典，如 {'--primary': '#FF2D55', '--radius': '16px'}")
    root: UINode = Field(description="页面的根节点，通常是一个 Container")
    detected_archetype: ArchetypeEnum = Field(default=ArchetypeEnum.GENERAL, description="本次排版最终确定的业务原型")

class ComponentData(BaseModel):
    """组件参数规范 (ComponentPayload)"""
    # ✨ 哨兵容错：将 type 改为可选，防止工兵节点因漏掉此字段而导致 Pydantic 校验失败
    type: Optional[str] = Field(None, description="组件类型标识符")
    title: Optional[str] = Field(None, description="主标题内容")
    subtitle: Optional[str] = Field(None, description="副标题内容")
    paragraphs: Optional[List[str]] = Field(None, description="正文文本段落")
    
    # ✨ Generative UI 升维字段
    align: Optional[str] = Field(None, description="文本对齐 (left/center)")
    killer_tags: Optional[List[str]] = Field(None, description="杀手锏高亮标签")
    mood: Optional[str] = Field(None, description="情绪基调")
    
    image_url: Optional[str] = Field(None, description="单图 URL")
    image_urls: Optional[List[str]] = Field(None, description="多图 URL 数组")
    price: Optional[str] = Field(None, description="价格信息（如 ￥99.00）")
    desc: Optional[str] = Field(None, description="描述性短文案")
    tags: Optional[List[str]] = Field(None, description="话题标签数组")
    rating: Optional[float] = Field(None, description="评分（0-5）")
    location: Optional[str] = Field(None, description="详细地址信息")
    poi_name: Optional[str] = Field(None, description="POI 地点名称（用于搜索）")
    lat: Optional[float] = Field(None, description="纬度")
    lng: Optional[float] = Field(None, description="经度")
    core_features: Optional[List[str]] = Field(None, description="核心参数/特性列表（用于 ProductSpecCard）")
    likes: Optional[Union[str, int]] = Field(None, description="点赞数（如 1.2w）")
    collects: Optional[Union[str, int]] = Field(None, description="收藏数")
    comments: Optional[Union[str, int]] = Field(None, description="评论数")

    @field_validator('likes', 'collects', 'comments', mode='before')
    @classmethod
    def ensure_string_metrics(cls, v: Any) -> Optional[str]:
        if v is None: return None
        return str(v)

    @field_validator('rating', mode='before')
    @classmethod
    def clean_rating(cls, v: Any) -> Any:
        if isinstance(v, str):
            match = re.search(r"[-+]?\d*\.\d+|\d+", v)
            if match:
                return float(match.group())
        return v

class ComponentStyle(BaseModel):
    """单组件样式协议"""
    css_classes: str = Field("", description="Tailwind CSS 类名")
    inline_styles: Dict[str, str] = Field(default_factory=dict, description="动态注入的内联样式")

class ComponentBuilderOutput(BaseModel):
    """单组件构建输出模型"""
    thought_process: str = Field(description="组件数据与全局文案/知识库对齐的思考过程")
    data: ComponentData = Field(..., description="组件的具体数据负载")
    style: ComponentStyle = Field(..., description="组件的样式数据")

    @field_validator('style', mode='before')
    @classmethod
    def ensure_style_object(cls, v: Any) -> Any:
        if isinstance(v, str):
            return {"css_classes": v, "inline_styles": {}}
        if isinstance(v, list):
            return {"css_classes": " ".join([str(i) for i in v]), "inline_styles": {}}
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

# --- ✨ 维度四：视觉视觉 —— Style 宪法 ---

class StyleVibeTokens(BaseModel):
    """【面试级原子化视觉令牌】：禁止输出 Hex，只允许语义控制"""
    # 1. 色彩与材质旋钮
    color_palette: Literal["slate", "zinc", "rose", "amber", "emerald", "cyan", "indigo", "fuchsia", "lime", "violet", "orange", "stone", "gold"] = Field(description="全局品牌主色系")
    bg_material: Literal["flat-light", "flat-dark", "glassmorphism", "neumorphic", "claymorphism", "paper-cut", "holographic"] = Field(description="页面整体背景材质与明暗")
    
    # 2. 几何与深度旋钮
    corner_style: Literal["rounded-none", "rounded-md", "rounded-2xl", "rounded-full", "asymmetric"] = Field(description="组件边缘的锋利程度")
    shadow_vibe: Literal["shadow-none", "shadow-sm", "shadow-xl", "shadow-2xl"] = Field(description="页面组件的立体悬浮感")
    
    # 3. 动效节奏旋钮
    animation_rhythm: Literal["none", "smooth-fade", "bouncy-pop", "cyber-glitch"] = Field(description="组件进场与悬停时的动效基调")
    
    # 4. 局部参数化覆写层
    component_overrides: Dict[str, str] = Field(
        default_factory=dict, 
        description="基于上述旋钮，为具体组件生成的专属 Tailwind class。必须包含 hover 状态、过渡和 delay。"
    )

class ComponentStylePatch(BaseModel):
    component_id: str = Field(..., description="组件的唯一 ID，例如 'cover_1', 'product_1'")
    style: ComponentStyle = Field(..., description="该组件的具体样式配置")

class StylePatchOutput(BaseModel):
    """样式大脑输出的视觉宪法结构"""
    thought_process: str = Field(description="视觉样式推理过程")
    global_tokens: StyleVibeTokens = Field(default_factory=StyleVibeTokens, description="从图片提取的全局视觉 Token")
    global_vars: Dict[str, str] = Field(default_factory=dict, description="注入 CSS 的全局变量")
    
    # 🌟 核心指令：将 Dict[str, ComponentStyle] 替换为 List[ComponentStylePatch]
    components: List[ComponentStylePatch] = Field(default_factory=list, description="各组件的样式补丁列表")

# --- ✨ 维度五：意图路由 —— Intent 宪法 ---

class FocusedKnowledge(BaseModel):
    """【面试级领域契约】：强制结构化的科研级知识模型"""
    domain_category: Literal["3C数码测评", "线下探店打卡", "美妆个护种草"] = Field(..., description="强制锁定的业务场景")
    entity_name: str = Field(..., description="识别出的核心主体名称（如：小米 17 Ultra）")
    core_attributes: Dict[str, Any] = Field(default_factory=dict, description="核心参数键值对（如：{'处理器': '骁龙8 Gen 4'}）")
    key_selling_points: List[str] = Field(default_factory=list, description="核心卖点/亮点列表")
    known_issues: List[str] = Field(default_factory=list, description="客观缺点/避雷点（用于维持测评客观性）")
    summary: str = Field(..., description="一句话情报摘要")

class IntentOutput(BaseModel):
    """意图分析大脑的输出结构"""
    thought_process: str = Field(description="思维链推理过程")
    reason: str = Field(..., description="极简理由（10字以内）。")
    intent_route: Literal["content_node", "structure_node", "style_node", "rag_node", "patch_node"] = Field(..., description="决定路由的节点名")
    detected_element_id: Optional[str] = Field(None, description="识别出的潜在修改目标 ID")
    scenarios: List[str] = Field(default_factory=list, description="识别的业务场景标签（字符串 ID）")
    detected_archetype: str = Field(default="general", description="识别出的业务场景原型 ID")

    @field_validator('scenarios', mode='before')
    @classmethod
    def validate_scenarios(cls, v: Any) -> List[str]:
        # ✨ 哨兵重构：不再校验硬编码集合，直接透传字符串列表，由 Node 层动态校验
        if not isinstance(v, list): return ["general"]
        return [str(item) for item in v]
