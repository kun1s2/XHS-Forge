import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages

def merge_dsl(left: dict, right: dict) -> dict:
    """
    深度合并字典（增加防御性编程）
    """
    # 【防御1】：确保 left 永远是字典
    if not isinstance(left, dict):
        left = {}
        
    merged = left.copy()
    
    # 【防御2】：如果大模型发神经返回了 list 或 None，直接忽略本次更新，防止系统崩溃
    if not isinstance(right, dict):
        print(f"⚠️ [状态机警告] 丢弃非字典类型的更新包: {type(right)}")
        return merged
    
    for k, v in right.items():
        if v is None:
            merged.pop(k, None)
        elif isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = merge_dsl(merged[k], v)
        else:
            merged[k] = v
            
    return merged

def merge_patch_tracks(left: dict, right: dict) -> dict:
    """
    专门为生长档案设计的合并器：将新记录追加到对应组件的 list 中
    """
    if not isinstance(left, dict): left = {}
    if not isinstance(right, dict): return left
    
    merged = left.copy()
    for k, v in right.items():
        if isinstance(v, list):
            if k in merged and isinstance(merged[k], list):
                merged[k] = merged[k] + v
            else:
                merged[k] = v
    return merged

def restore_component_version(state: Any, element_id: str, version_index: int) -> dict:
    """
    【局部回溯逻辑】：从 patch_tracks 中提取特定版本的数据并覆盖 data_dsl
    """
    tracks = state.get("patch_tracks", {})
    if element_id not in tracks or version_index >= len(tracks[element_id]):
        print(f"⚠️ [回溯失败] 未找到组件 {element_id} 的版本 {version_index}")
        return {}
    
    target_version = tracks[element_id][version_index]
    data_snapshot = target_version.get("data_snapshot")
    
    if not data_snapshot:
        return {}
        
    return {
        "data_dsl": {element_id: data_snapshot}
    }

class UIProjectState(TypedDict):
    # 5大独立消息通道 (自带 add_messages 聚合器，自动追加防覆盖)
    main_messages: Annotated[list[BaseMessage], add_messages]
    content_messages: Annotated[list[BaseMessage], add_messages]
    image_messages: Annotated[list[BaseMessage], add_messages]
    structure_messages: Annotated[list[BaseMessage], add_messages]
    style_messages: Annotated[list[BaseMessage], add_messages]
    
    # 兼容与路由
    messages: Annotated[list[BaseMessage], add_messages]
    intent_route: str 
    # ✨ 核心新增：场景标签数组，支持混合场景 (如: ["travel", "food"])
    scenarios: List[str]
    # ✨ 核心新增：当前激活的业务原型 (Archetype)
    active_archetype: str
    active_panel: str 
    selected_element_id: Optional[str]

    # 素材与产物
    image_urls: List[str]
    
    # ====== ✨ 现代化进化：加入 operator.add ======
    # 全局图库资产池 [{"url": "...", "desc": "..."}]
    # 加上 operator.add 后，asset_node 只需要 return {"image_assets": [新图]}
    # LangGraph 底层会自动把新图 append 到老数组后面，绝对不会再发生覆盖丢失了！
    image_assets: Annotated[List[Dict[str, str]], operator.add]
    
    # 待打标的图片队列（本轮新上传的 URL，asset_node 处理完会清空）
    pending_images: List[str]
    
    entity_knowledge: Dict[str, Any]
    visual_perception: List[Dict[str, Any]]
    
    content_template_id: str
    style_template_id: str
    
    # 核心字典，绑定了你极其强大的深度合并 Reducer
    data_dsl: Annotated[dict, merge_dsl]
    style_dsl: Annotated[dict, merge_dsl]
    
    # ✨ 核心新增：组件级生长档案
    patch_tracks: Annotated[dict, merge_patch_tracks]
    
    # ✨ 新增：用于调试的提示词检查槽位 { "node_name": "full_prompt_text" }
    node_prompts: Annotated[dict, merge_dsl]
    
    # ✨ 核心新增：RAG 检索到的私域知识
    retrieved_knowledge: str
    
    # ✨ HITL 机制新增
    has_controversy: bool      # 标记是否发现争议
    user_stance: Optional[str] # 接收人类选择的立场（如“黑榜吐槽”或“红榜种草”）
    
    # ✨ 长期记忆：创作者人设 (Persona)
    creator_persona: Optional[str] # 如 "硬核数码博主", "毒舌美妆专家", "温柔探店达人"
    
    # ✨ 动态实体消歧与自适应 HITL 新增
    needs_disambiguation: bool      # 是否需要人类协助消歧
    disambiguation_options: List[Dict[str, str]] # 消歧选项列表 [{"label": "...", "value": "..."}]
    
    # ✨ 战役 D：Map-Reduce 动态并发引擎新增
    page_outline: List[Dict[str, str]] # 页面大纲 [{"id": "title_1", "type": "TitleBlock"}, ...]
    
    final_oss_url: Optional[str]
    # 生成的 HTML 源码，供前端「源码」面板展示与时间胶囊回滚
    final_html: Optional[str]

# ✨ 战役 D：为并发任务定义的专用子状态
class ComponentTaskState(TypedDict):
    component_id: str
    component_type: str
    user_query: str
    active_archetype: str
    retrieved_knowledge: str
    creator_persona: str