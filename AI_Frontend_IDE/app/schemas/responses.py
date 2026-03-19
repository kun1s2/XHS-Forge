from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class BaseResponse(BaseModel):
    status: str = "success"
    message: Optional[str] = None

class ForkResponse(BaseResponse):
    new_thread_id: str
    parent_checkpoint: str

class CheckpointInfo(BaseModel):
    checkpoint_id: str
    intent: str

class WorkspaceDataResponse(BaseResponse):
    """首屏加载的完整状态数据"""
    is_new: bool
    messages: Dict[str, List[Dict[str, Any]]]  # 分面板的结构化聊天记录
    active_panel: str
    selected_element_id: Optional[str]
    data_dsl: Dict[str, Any]
    style_dsl: Dict[str, Any]
    image_assets: List[Dict[str, Any]] = []
    node_prompts: Dict[str, Any] = {}
    oss_url: Optional[str]
    source_code: str = ""
    checkpoints: List[CheckpointInfo]
