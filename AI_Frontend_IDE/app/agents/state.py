import operator
from typing import Annotated, Any, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from app.core.note_document import build_note_document_from_state, update_note_document_block


def merge_image_assets(left: list[dict[str, Any]] | None, right: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """
    图片资产的状态合并器。

    默认行为仍然是 append，兼容“新增一张图”的轻量 patch；
    当右侧列表首项带有 `__replace__` 标记时，改为整表替换，供工作台删除/重排资产使用。
    """
    safe_left = [item for item in (left or []) if isinstance(item, dict)]
    safe_right = [item for item in (right or []) if isinstance(item, dict)]
    if safe_right and safe_right[0].get("__replace__"):
        return [
            {k: v for k, v in item.items() if k != "__replace__"}
            for item in safe_right[1:]
        ]
    return safe_left + safe_right


def merge_state_patch(left: dict, right: dict) -> dict:
    """
    深度合并字典（增加防御性编程与列表覆盖机制）
    """
    if not isinstance(left, dict):
        left = {}
        
    merged = left.copy()
    
    if not isinstance(right, dict):
        print(f"⚠️ [状态机警告] 丢弃非字典类型的更新包: {type(right)}")
        return merged
    
    # ✨ 核心加固：处理画布手术刀发来的【原子级】并发修改指令
    if "_block_append" in right:
        if "blocks" not in merged: merged["blocks"] = []
        merged["blocks"].append(right["_block_append"])
        right.pop("_block_append", None)

    if "_block_insert" in right:
        if "blocks" not in merged: merged["blocks"] = []
        idx = right["_block_insert"].get("index", 0)
        block = right["_block_insert"].get("block", {})
        idx = min(max(0, idx), len(merged["blocks"]))
        merged["blocks"].insert(idx, block)
        right.pop("_block_insert", None)

    if "_block_remove" in right:
        if "blocks" in merged:
            merged["blocks"] = [b for b in merged["blocks"] if b.get("id") != right["_block_remove"]]
        right.pop("_block_remove", None)

    if "_block_update" in right:
        if "blocks" in merged:
            target_id = right["_block_update"].get("id")
            for b in merged["blocks"]:
                if b.get("id") == target_id:
                    b.update(right["_block_update"].get("data", {}))
        right.pop("_block_update", None)

    # 兼容旧版的覆盖指令
    if right.get("_blocks_override"):
        if "blocks" in right:
            merged["blocks"] = right["blocks"]
        right.pop("_blocks_override", None)
        right.pop("blocks", None)
    
    for k, v in right.items():
        if v is None:
            merged.pop(k, None)
        elif isinstance(v, dict) and isinstance(merged.get(k), dict):
            merged[k] = merge_state_patch(merged[k], v)
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


def merge_turn_anchors(
    left: list[dict[str, Any]] | None,
    right: list[dict[str, Any]] | None,
) -> list[dict[str, Any]]:
    """
    对话历史锚点合并器。

    每个锚点对应某个消息面板里的一个用户轮次，记录“这一轮最终可回退/可分支的历史点”。
    这里按 `(panel, turn_index)` 做 upsert，确保同一轮不会无限追加重复锚点。
    """
    merged: list[dict[str, Any]] = [
        dict(item)
        for item in (left or [])
        if isinstance(item, dict)
    ]

    for candidate in right or []:
        if not isinstance(candidate, dict):
            continue
        panel = str(candidate.get("panel") or "main")
        turn_index = int(candidate.get("turn_index") or 0)
        replaced = False
        for idx, existing in enumerate(merged):
            if str(existing.get("panel") or "main") == panel and int(existing.get("turn_index") or 0) == turn_index:
                merged[idx] = dict(candidate)
                replaced = True
                break
        if not replaced:
            merged.append(dict(candidate))
    return merged

def restore_component_version(state: Any, element_id: str, version_index: int) -> dict:
    """
    【局部回溯逻辑】：从 patch_tracks 提取快照，并构造绝对覆盖的补丁，消除幽灵数据。
    """
    tracks = state.get("patch_tracks", {})
    if element_id not in tracks or version_index >= len(tracks[element_id]):
        print(f"⚠️ [回溯失败] 未找到组件 {element_id} 的版本 {version_index}")
        return {}
    
    target_version = tracks[element_id][version_index]
    data_snapshot = target_version.get("data_snapshot")
    
    if not data_snapshot:
        return {}
        
    note_document = build_note_document_from_state(state)
    current_block = next((block for block in (note_document.get("blocks") or []) if block.get("id") == element_id), {})
    current_component_data = current_block.get("props") or {}
    rollback_patch = data_snapshot.copy()

    for k in current_component_data.keys():
        if k not in data_snapshot:
            rollback_patch[k] = None

    rollback_patch = {k: v for k, v in rollback_patch.items() if v is not None}

    return {
        "note_document": update_note_document_block(note_document, element_id, props=rollback_patch)
    }

class UIProjectState(TypedDict):
    # 5大独立消息通道 (自带 add_messages 聚合器，自动追加防覆盖)
    main_messages: Annotated[list[BaseMessage], add_messages]
    content_messages: Annotated[list[BaseMessage], add_messages]
    image_messages: Annotated[list[BaseMessage], add_messages]
    structure_messages: Annotated[list[BaseMessage], add_messages]
    style_messages: Annotated[list[BaseMessage], add_messages]
    
    # ✨ 核心恢复：系统总线消息池 (LangGraph 工具调用专用)
    messages: Annotated[list[BaseMessage], add_messages]
    
    # 兼容与路由
    intent_route: str 
    # ✨ 核心新增：场景标签数组，支持混合场景 (如: ["travel", "food"])
    scenarios: List[str]
    # ✨ 核心新增：当前激活的业务原型 (Archetype)
    active_archetype: str
    active_panel: str 
    selected_element_id: Optional[str]
    
    intent_result_v2: Optional[Any]
    planner_output: Optional[Any]
    planner_policy: Annotated[dict, merge_state_patch]
    scenario_scores: Annotated[dict, merge_state_patch]
    conversation_checkpoint: Annotated[dict, merge_state_patch]
    checkpoint_progress: Annotated[dict, merge_state_patch]
    checkpoint_decision: Annotated[dict, merge_state_patch]
    note_document: Annotated[dict, merge_state_patch]
    turn_trace: Annotated[dict, merge_state_patch]
    agent_backends: Annotated[dict, merge_state_patch]
    
    # ====== ✨ 现代化进化：加入 operator.add ======
    # 全局图库资产池 [{"url": "...", "desc": "..."}]
    # 加上 operator.add 后，asset_node 只需要 return {"image_assets": [新图]}
    # LangGraph 底层会自动把新图 append 到老数组后面，绝对不会再发生覆盖丢失了！
    image_assets: Annotated[List[Dict[str, Any]], merge_image_assets]
    
    # 待打标的图片队列（本轮新上传的 URL，asset_node 处理完会清空）
    pending_images: List[str]
    
    content_template_id: str
    style_template_id: str
    
    # ✨ 核心新增：组件级生长档案
    patch_tracks: Annotated[dict, merge_patch_tracks]
    turn_anchors: Annotated[List[Dict[str, Any]], merge_turn_anchors]
    
    # ✨ 新增：用于调试的提示词检查槽位 { "node_name": "full_prompt_text" }
    node_prompts: Annotated[dict, merge_state_patch]
    
    # ✨ 核心重构：RAG 检索到的私域知识 (现已支持结构化字典)
    # 大一统知识背包：整合了 RAG 结果、实体属性和外部事实
    retrieved_knowledge: Any
    
    # ✨ HITL 机制新增
    has_controversy: bool      # 标记是否发现争议
    user_stance: Optional[str] # 接收人类选择的立场（如“黑榜吐槽”或“红榜种草”）
    
    # ✨ 长期记忆：创作者人设 (Persona)
    creator_persona: Optional[str] # 如 "硬核数码博主", "毒舌美妆专家", "温柔探店达人"
    
    # ✨ 动态实体消歧与自适应 HITL 新增
    needs_disambiguation: bool      # 是否需要人类协助消歧
    disambiguation_options: List[Dict[str, str]] # 消歧选项列表 [{"label": "...", "value": "..."}]
    
    final_oss_url: Optional[str]
    # 生成的 HTML 源码，供前端「源码」面板展示与时间胶囊回滚
    final_html: Optional[str]

# ✨ 战役 D：为并发任务定义的专用子状态
class ComponentTaskState(TypedDict):
    component_id: str
    component_type: str
    content_brief: str # ✨ 哨兵新增：承载主编下发的任务简报
    user_query: str
    active_archetype: str
    retrieved_knowledge: Any
    creator_persona: str
    image_assets: List[Dict[str, Any]]
    planner_policy: Dict[str, Any]
    content_messages: List[BaseMessage]
