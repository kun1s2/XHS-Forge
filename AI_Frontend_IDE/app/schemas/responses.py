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
    node: Optional[str] = None
    timestamp: Optional[str] = None

class WorkspaceDataResponse(BaseResponse):
    """首屏加载的完整状态数据"""
    is_new: bool
    messages: Dict[str, List[Dict[str, Any]]]  # 分面板的结构化聊天记录
    active_panel: str
    selected_element_id: Optional[str]
    image_assets: List[Dict[str, Any]] = []
    node_prompts: Dict[str, Any] = {}
    note_document: Dict[str, Any] = {}
    planner_output: Dict[str, Any] = {}
    planner_policy: Dict[str, Any] = {}
    turn_trace: Dict[str, Any] = {}
    agent_backends: Dict[str, Any] = {}
    inspector_summary: Dict[str, Any] = {}
    oss_url: Optional[str]
    source_code: str = ""
    checkpoints: List[CheckpointInfo]


class BenchmarkOverviewResponse(BaseResponse):
    data: Dict[str, Any] = {}


class EvaluationOverviewResponse(BaseResponse):
    data: Dict[str, Any] = {}


class TrendItemResponse(BaseModel):
    keyword: str
    score: float = 0.0
    scenario_hint: str = "general"
    entity_type: str = "general_topic"
    source: str = "organic"
    freshness: str = "unknown"
    cache_freshness: str = "miss"
    record_count: int = 0
    recommended_prompt: str = ""


class TrendListResponse(BaseResponse):
    trends: List[TrendItemResponse] = []


class BlockGalleryComponentResponse(BaseModel):
    component_type: str
    label: str
    semantic_role: str
    supported_scenarios: List[str] = []
    summary: str = ""
    fixture: Dict[str, Any] = {}


class BlockGalleryScenarioResponse(BaseModel):
    scenario_id: str
    title: str
    description: str = ""
    fixture: Dict[str, Any] = {}


class BlockGalleryOverviewResponse(BaseResponse):
    data: Dict[str, Any] = {}


class BlockGalleryComponentPayloadResponse(BaseResponse):
    data: Dict[str, Any] = {}


class BlockGalleryScenarioPayloadResponse(BaseResponse):
    data: Dict[str, Any] = {}
