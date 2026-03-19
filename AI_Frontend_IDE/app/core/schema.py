from typing import List, Dict, Optional, Literal, Any, Union
from pydantic import BaseModel, Field, field_validator
import re

# --- ✨ 维度一：业务建模 —— 动态协议 ---

# 🚀 Vulcan-Prime: 彻底废弃 ArchetypeEnum，改用动态字符串以实现场景完全自治。

class ArchetypeContract(BaseModel):
    """场景契约模型：定义该赛道下的组件黑白名单与推荐序列"""
    scenario_id: str
    required_components: List[str] = Field(default_factory=list)
    suggested_order: List[str] = Field(default_factory=list)
    description: str = ""

# --- ✨ 维度二：工程契约 —— DSL 规范 ---

class UIBlock(BaseModel):
    """一维线性 UI 积木块"""
    id: str = Field(..., description="组件全局唯一ID，如 title_1, vs_card_1")
    component_type: str = Field(..., description="前端组件类型，如 TitleBlock, VersusCard, StoryText, CoverSwiper 等")
    content_brief: str = Field(..., description="给下游工兵的文案撰写简报与要求。请描述该组件在页面中的职责。")

class OutlineOutput(BaseModel):
    """大纲大脑输出的页面结构 (基于线性区块流)"""
    thought_process: str = Field(description="大纲排版与组件选型的推理过程")
    page_title: str = Field(..., description="网页标签标题")
    page_theme: Dict[str, str] = Field(default_factory=dict, description="全局 CSS 变量字典，如 {'--primary': '#FF2D55', '--radius': '16px'}")
    blocks: List[UIBlock] = Field(..., description="自上而下、一维线性排布的 UI 积木区块列表")
    
    # ✅ 已重构：ArchetypeEnum -> str
    detected_archetype: str = Field(default="general", description="本次排版最终确定的业务原型 ID")

class ComponentData(BaseModel):
    """组件参数规范 (ComponentPayload)"""
    # ✨ 哨兵容错：将 type 改为可选，防止工兵节点因漏掉此字段而导致 Pydantic 校验失败
    type: Optional[str] = Field(None, description="组件类型标识符")
    title: Optional[str] = Field(None, description="主标题内容")
    subtitle: Optional[str] = Field(None, description="副标题内容")
    paragraphs: Optional[List[str]] = Field(None, description="正文文本段落")
    
    # ✨ 为 VersusCard 补上专属武器！
    proText: Optional[str] = Field(None, description="红榜/优势描述（仅 VersusCard 可用，严禁写成数组）")
    conText: Optional[str] = Field(None, description="黑榜/劣势描述（仅 VersusCard 可用，严禁写成数组）")
    
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

    # --- 🚀 扩军计划：高阶互动与可视化组件专属字段 ---
    
    # 1. 📊 雷达图 (RadarChartBlock)
    dimensions: Optional[List[str]] = Field(None, description="评估维度数组，如 ['性能', '续航', '拍照']")
    scores: Optional[List[int]] = Field(None, description="维度对应的分数数组 (0-100)")
    
    # 2. 🗳️ 互动投票卡 (PollBlock)
    question: Optional[str] = Field(None, description="极具争议性的投票问题")
    option_a: Optional[str] = Field(None, description="正方选项，极具煽动性")
    option_b: Optional[str] = Field(None, description="反方选项，极具煽动性")
    
    # 3. 🎁 惊喜礼盒 (GiftBox) 专属
    box_cover_text: Optional[str] = Field(None, description="礼盒外部的引导文案，如'点击拆开粉丝福利'")
    box_inside_content: Optional[str] = Field(None, description="礼盒拆开后的惊喜内容")

    # 🃏 翻转真相卡 (FlipCard) 专属
    front_text: Optional[str] = Field(None, description="卡片正面的悬念文案")
    back_text: Optional[str] = Field(None, description="卡片背面的真相/反转文案")
    
    # 4. ⏱️ 编年史/时间轴 (TimelineBlock)
    events: Optional[List[Dict[str, str]]] = Field(None, description="时间轴事件数组，含 timestamp, title, description")
    
    # 5. 📸 天气拍立得 (WeatherPolaroid)
    temperature: Optional[str] = Field(None, description="温度，如 24°C")
    weather: Optional[str] = Field(None, description="天气状况，如 小雨, 晴天")
    time: Optional[str] = Field(None, description="时间标签，如 下午 3:15")
    
    # 6. 💬 痛点金句放大卡 (QuoteBlock)
    quote: Optional[str] = Field(None, description="极具情绪感染力的金句，必须带双引号")
    author: Optional[str] = Field(None, description="金句的出处或发言人")
    
    # 7. 🗣️ 评价弹幕条 (UserReviewMarquee)
    reviews: Optional[List[str]] = Field(None, description="真实网友评价的短句数组")
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
    thought_process: Optional[str] = Field(None, description="组件数据与全局文案/知识库对齐的思考过程")
    data: ComponentData = Field(..., description="组件的具体数据负载")
    style: Optional[ComponentStyle] = Field(None, description="组件的样式数据")

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
    blocks: List[UIBlock] = Field(..., description="组件 ID 的线性排列顺序与积木定义")
    components: Dict[str, ComponentData] = Field(..., description="组件的具体数据负载")
    
    # ✅ 已重构：ArchetypeEnum -> str
    detected_archetype: str = Field(default="general", description="本次排版最终确定的业务原型 ID")

class SurgicalPatchOutput(BaseModel):
    """【手术刀模式】专用输出模型：仅修改单个组件内容"""
    thought_process: str = Field(description="局部修改决策推理过程")
    reason: str = Field(..., description="修改该组件的极简理由。")
    updated_component: ComponentData = Field(..., description="被选中的组件更新后的完整数据对象。")

# --- ✨ 维度四：视觉视觉 —— Style 宪法 ---

class StyleVibeTokens(BaseModel):
    """【面试级原子化视觉令牌】：彻底松绑，支持无限多样性"""
    # 🚀 Vulcan-Prime: 废弃 Literal 限制，允许场景插件自定义任何材质与颜色标签
    color_palette: str = Field(description="全局品牌主色系标签")
    bg_material: str = Field(description="页面整体背景材质与明暗标签")
    
    # 2. 几何与深度旋钮
    corner_style: str = Field(description="组件边缘的锋利程度标签")
    shadow_vibe: str = Field(description="页面组件的立体悬浮感标签")
    
    # 3. 动效节奏旋钮
    animation_rhythm: str = Field(description="组件进场与悬停时的动效基调标签")
    
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
    domain_category: str = Field(..., description="强制锁定的业务场景标签")
    entity_name: str = Field(..., description="识别出的核心主体名称")
    core_attributes: Dict[str, Any] = Field(default_factory=dict, description="核心参数键值对")
    key_selling_points: List[str] = Field(default_factory=list, description="核心卖点/亮点列表")
    known_issues: List[str] = Field(default_factory=list, description="客观缺点/避雷点")
    summary: str = Field(..., description="一句话情报摘要")
    fact_sources: List[Dict[str, Any]] = Field(default_factory=list, description="结构化事实来源列表")
    fact_conflicts: List[Dict[str, Any]] = Field(default_factory=list, description="已识别的事实冲突列表")
    confirmed_facts: Dict[str, Any] = Field(default_factory=dict, description="已经过人工确认的事实键值")
    fact_confidence: str = Field(default="medium", description="当前事实置信度：low/medium/high")
    needs_fact_confirmation: bool = Field(default=False, description="是否建议进行人工确认")
    fact_review_status: str = Field(default="clear", description="事实审核状态：clear/pending/confirmed")

    @field_validator('domain_category')
    @classmethod
    def validate_domain_category(cls, v: str) -> str:
        banned_markers = ("非法", "违规", "违法", "金融", "医疗诊断")
        if any(marker in v for marker in banned_markers):
            raise ValueError("domain_category 命中受限领域")
        return v

class IntentOutput(BaseModel):
    """意图分析大脑的输出结构 (4.0 六维意图雷达版)"""
    thought_process: str = Field(description="思维链推理过程")
    reason: str = Field(..., description="极简理由（10字以内）。")
    intent_route: Literal["content_node", "structure_node", "style_node", "rag_node", "patch_node"] = Field(..., description="决定路由的节点名")
    
    # ✨ 维度 1/2: 基础叙事协议
    narrative_mode: Literal["contrast", "sequential", "suspense", "spatial"] = Field(
        default="spatial", 
        description="叙事模式"
    )
    intensity_level: float = Field(default=0.0, description="情绪烈度")

    # ✨ 维度 3: 视觉美学风向
    visual_vibe: Literal["general", "minimalist", "vintage", "cyberpunk", "y2k", "natural", "kawaii", "luxury"] = Field(
        default="general", 
        description="视觉美学风向（如：极简、复古、千禧风等）"
    )
    
    # ✨ 维度 4: 受众画像靶向
    target_audience: str = Field(
        default="泛人群", 
        description="推测的目标受众画像（如：早八大学生、中产宝妈、硬核极客等）"
    )

    # ✨ 维度 5: 核心互动目标 (CTA)
    call_to_action: Literal["none", "engagement", "conversion", "follower", "help"] = Field(
        default="none", 
        description="核心互动目标：engagement(骗评互动), conversion(种草带货), follower(涨粉), help(求助答疑)"
    )

    # ✨ 维度 6: 时态与环境感知
    temporal_context: Optional[str] = Field(
        default=None, 
        description="时态/环境感知（如：清晨、深夜放毒、周末、雨天等），用于触发环境氛围组件"
    )

    # ✨ 物理探针
    asset_request: Literal["NONE", "SEARCH", "GENERATE"] = Field(
        default="NONE", 
        description="资产请求：NONE(默认), SEARCH(搜图), GENERATE(AI生图)"
    )
    
    detected_element_id: Optional[str] = Field(None, description="识别出的潜在修改目标 ID")
    scenarios: List[str] = Field(default_factory=list, description="识别的业务场景标签")
    detected_archetype: str = Field(default="general", description="识别出的业务场景原型 ID")

    @field_validator('scenarios', mode='before')
    @classmethod
    def validate_scenarios(cls, v: Any) -> List[str]:
        # ✨ 哨兵重构：不再校验硬编码集合，直接透传字符串列表，由 Node 层动态校验
        if not isinstance(v, list): return ["general"]
        return [str(item) for item in v]
