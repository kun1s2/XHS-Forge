# app/schemas/requests.py
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class ForkRequest(BaseModel):
    old_thread_id: str = Field(..., description="要分叉的历史会话 ID")
    checkpoint_id: str = Field(..., description="要基于哪个历史节点的 ID 进行分叉")
    panel: str = Field("main", description="触发分叉的面板 (main, content, style 等)")
    # 改为选填，如果不填，仅仅做状态的平移克隆 (纯复制项目)；如果填了，则是回滚并重发新指令
    new_instruction: Optional[str] = Field(None, description="用户回滚后输入的新提问")

class SelectRegionRequest(BaseModel):
    thread_id: str = Field(..., description="当前会话 ID")
    element_id: str = Field(..., description="用户在前端选中的 DOM 元素 ID")

class ChatWSPayload(BaseModel):
    """用于 WebSocket 接收消息的结构"""
    content: str = Field(..., description="用户输入的文本")
    panel: str = Field("main", description="当前所在的对话面板")
    # 【核心游标】：如果不传，顺延最新节点；如果传了，从该历史节点开启软分叉覆盖！
    parent_checkpoint_id: Optional[str] = Field(None, description="要回滚到的父级历史节点 ID")
    # 接收前端传来的锁定组件 ID，供 structure_node / style_node 做局部修改
    selected_element_id: Optional[str] = Field(None, description="当前在画布中锁定的组件ID")
    # 全局图库资产池：前端同步的 [{"url": "...", "desc": "语义"}]，每次发信覆盖 state.image_assets
    current_assets: Optional[List[Dict[str, Any]]] = Field(
        default_factory=list,
        description="当前图库列表，每项含 url 与 desc，生成的页面必须用上全部图片",
    )
    # 本轮新上传的图片 URL，塞进 pending_images 由 asset_node 打标后并入 image_assets
    image_urls: Optional[List[str]] = Field(default_factory=list, description="待打标的新图片 URL 列表")
    # ✨ 长期记忆新增
    creator_persona: Optional[str] = Field("硬核数码博主", description="创作者人设")