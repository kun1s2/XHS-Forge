# app/schemas/requests.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ForkRequest(BaseModel):
    old_thread_id: str = Field(..., description="要分叉的历史会话 ID")
    checkpoint_id: str = Field(..., description="要基于哪个历史节点的 ID 进行分叉")
    panel: str = Field("main", description="触发分叉的面板 (main, content, style 等)")
    # 改为选填，如果不填，仅仅做状态的平移克隆 (纯复制项目)；如果填了，则是回滚并重发新指令
    new_instruction: Optional[str] = Field(None, description="用户回滚后输入的新提问")


class ThreadRollbackRequest(BaseModel):
    checkpoint_id: str = Field(..., description="要回到的历史节点 ID")
    panel: str = Field("main", description="触发回滚的面板")

class SelectRegionRequest(BaseModel):
    thread_id: str = Field(..., description="当前会话 ID")
    element_id: str = Field(..., description="用户在前端选中的 DOM 元素 ID")

class ChatWSPayload(BaseModel):
    """用于 WebSocket 接收消息的结构"""
    content: str = Field(..., description="用户输入的文本")
    panel: str = Field("main", description="当前所在的对话面板")
    # 【核心游标】：如果不传，顺延最新节点；如果传了，从该历史节点开启软分叉覆盖！
    parent_checkpoint_id: Optional[str] = Field(None, description="要回滚到的父级历史节点 ID")
    # 接收前端传来的锁定组件 ID，供 structure_node / theme_compiler 做局部修改
    selected_element_id: Optional[str] = Field(None, description="当前在画布中锁定的组件ID")
    # 当前线程资产池：这是本轮图片上下文的唯一真相源，每次发信覆盖 state.image_assets
    current_assets: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="当前线程素材池，会作为本轮图片上下文整体同步给运行时",
    )
    # 本轮新上传的图片 URL，仅供 asset_node 打标，不再承担“已选素材”语义
    image_urls: Optional[List[str]] = Field(default_factory=list, description="本轮新上传、待打标的新图片 URL 列表")
    message_kind: Optional[str] = Field("user_prompt", description="当前消息的交互类型，用于 agent 叙事和定向协作")
    # ✨ 长期记忆新增
    creator_persona: Optional[str] = Field("硬核数码博主", description="创作者人设")
    custom_note: Optional[str] = Field(None, description="checkpoint 的其他补充说明")
