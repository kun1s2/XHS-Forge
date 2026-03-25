from __future__ import annotations

from typing import Any, Optional

from langchain.agents.middleware.types import AgentState
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, NotRequired

from app.agents.runtime.state_helpers import (
    merge_image_assets,
    merge_patch_tracks,
    merge_state_patch,
    merge_turn_anchors,
    merge_unique_strings,
    overwrite_state_value,
)


class SupervisorSessionState(AgentState[dict[str, Any]]):
    main_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    user_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    content_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    image_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    structure_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    style_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]

    intent_route: NotRequired[Annotated[str, overwrite_state_value]]
    scenarios: NotRequired[list[str]]
    active_archetype: NotRequired[str]
    active_panel: NotRequired[str]
    selected_element_id: NotRequired[Optional[str]]
    creator_persona: NotRequired[Optional[str]]

    intent_decision: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    intent_source_query: NotRequired[Annotated[str, overwrite_state_value]]
    knowledge_plan: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    knowledge_plan_query: NotRequired[Annotated[str, overwrite_state_value]]
    planner_output: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    planner_policy: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    scenario_scores: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    conversation_checkpoint: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    checkpoint_progress: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    checkpoint_decision: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    pending_checkpoint: NotRequired[Annotated[dict[str, Any] | None, overwrite_state_value]]
    resume_directive: NotRequired[Annotated[dict[str, Any] | None, overwrite_state_value]]
    representation_preferences: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    user_provided_facts: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    note_document: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    artifact: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    artifact_version: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    artifact_quality: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    revision_plan: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    revision_result: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    revision_status: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    turn_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    tool_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    agent_backends: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    selected_skills: NotRequired[Annotated[list[str], merge_unique_strings]]
    skill_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    persistent_refs: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    last_worker_result: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]

    image_assets: NotRequired[Annotated[list[dict[str, Any]], merge_image_assets]]
    pending_images: NotRequired[list[str]]
    patch_tracks: NotRequired[Annotated[dict[str, Any], merge_patch_tracks]]
    turn_anchors: NotRequired[Annotated[list[dict[str, Any]], merge_turn_anchors]]
    worker_prompts: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    retrieved_knowledge: NotRequired[Annotated[Any, overwrite_state_value]]
    final_oss_url: NotRequired[Annotated[Optional[str], overwrite_state_value]]
    final_html: NotRequired[Annotated[Optional[str], overwrite_state_value]]
    critique_feedback: NotRequired[Annotated[dict[str, Any], overwrite_state_value]]
    needs_revision: NotRequired[Annotated[bool, overwrite_state_value]]
    current_phase: NotRequired[Annotated[str, overwrite_state_value]]
    active_worker: NotRequired[Annotated[Optional[str], overwrite_state_value]]
    version_history_head: NotRequired[list[dict[str, Any]]]

