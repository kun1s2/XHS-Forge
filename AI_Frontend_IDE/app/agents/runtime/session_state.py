from __future__ import annotations

from typing import Any, Optional

from langchain.agents.middleware.types import AgentState
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from typing_extensions import Annotated, NotRequired

from app.agents.state import (
    merge_image_assets,
    merge_patch_tracks,
    merge_state_patch,
    merge_turn_anchors,
    merge_unique_strings,
)


class SupervisorSessionState(AgentState[dict[str, Any]]):
    main_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    content_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    image_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    structure_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]
    style_messages: NotRequired[Annotated[list[BaseMessage], add_messages]]

    intent_route: NotRequired[str]
    scenarios: NotRequired[list[str]]
    active_archetype: NotRequired[str]
    active_panel: NotRequired[str]
    selected_element_id: NotRequired[Optional[str]]
    creator_persona: NotRequired[Optional[str]]

    intent_decision: NotRequired[dict[str, Any]]
    intent_source_query: NotRequired[str]
    knowledge_plan: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    knowledge_plan_query: NotRequired[str]
    planner_output: NotRequired[dict[str, Any]]
    planner_policy: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    scenario_scores: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    conversation_checkpoint: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    checkpoint_progress: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    checkpoint_decision: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    pending_checkpoint: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    representation_preferences: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    user_provided_facts: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    note_document: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    artifact: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    artifact_version: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    revision_plan: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    revision_result: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    revision_status: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    turn_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    tool_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    agent_backends: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    selected_skills: NotRequired[Annotated[list[str], merge_unique_strings]]
    skill_trace: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    persistent_refs: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    last_worker_result: NotRequired[Annotated[dict[str, Any], merge_state_patch]]

    image_assets: NotRequired[Annotated[list[dict[str, Any]], merge_image_assets]]
    pending_images: NotRequired[list[str]]
    patch_tracks: NotRequired[Annotated[dict[str, Any], merge_patch_tracks]]
    turn_anchors: NotRequired[Annotated[list[dict[str, Any]], merge_turn_anchors]]
    node_prompts: NotRequired[Annotated[dict[str, Any], merge_state_patch]]
    retrieved_knowledge: NotRequired[Any]
    final_oss_url: NotRequired[Optional[str]]
    final_html: NotRequired[Optional[str]]
    critique_feedback: NotRequired[dict[str, Any]]
    needs_revision: NotRequired[bool]
    current_phase: NotRequired[str]
    active_worker: NotRequired[Optional[str]]
    version_history_head: NotRequired[list[dict[str, Any]]]
