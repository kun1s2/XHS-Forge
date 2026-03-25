"""Note Quality Critique Agent."""

import json
import re
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import create_llm
from app.core.prompt_engineering import load_prompt_template
from app.services.skill_registry import build_skill_context


class CritiqueFeedback(BaseModel):
    """Structured feedback from the critique agent."""
    score: int = Field(..., ge=0, le=100, description="Overall quality score 0-100")
    emoji_density: float = Field(..., description="Emoji count per 100 characters")
    emotional_intensity: str = Field(..., description="Low/Medium/High")
    has_hook: bool = Field(..., description="Whether the opening has a strong hook")
    has_call_to_action: bool = Field(..., description="Whether there's a CTA at the end")
    factual_issues: List[str] = Field(default_factory=list, description="可信度会受影响的事实风险")
    completeness_issues: List[str] = Field(default_factory=list, description="真正影响用户理解或判断的信息缺口")
    suggestions: List[str] = Field(default_factory=list, description="Actionable improvement suggestions")
    needs_revision: bool = Field(..., description="Whether the note needs revision")


class NoteCritiqueAgent:
    """Critique agent that reviews note quality."""
    
    SYSTEM_PROMPT = load_prompt_template("workers/critique_system.md")

    def __init__(self):
        self.llm = create_llm(temperature=0.3)
    
    async def critique(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Review the current note and provide feedback."""
        
        # Extract note content
        note_doc = state.get("note_document")
        if not note_doc:
            return {"critique_feedback": None, "needs_revision": False}
        
        # Render note to text for evaluation
        note_text = self._render_note_text(note_doc)
        if len(note_text.strip()) < 50:
            # Too short to evaluate meaningfully
            return {"critique_feedback": None, "needs_revision": False}
        
        # Get citations if available
        citations = state.get("citations", [])
        if not citations:
            citations = (((note_doc.get("provenance") or {}).get("fact_sources")) or [])[:5]
        citation_texts = [json.dumps(cit, ensure_ascii=False) for cit in citations[:5] if isinstance(cit, dict)]
        
        # Build prompt
        user_prompt = f"""请评估以下当前页面成品：

【笔记内容】
{note_text}

【参考信息来源】（如果有）
{chr(10).join(citation_texts) if citation_texts else '无'}

请严格按照系统prompt中的评估维度进行打分，并输出JSON格式的结果。"""
        
        try:
            # Call LLM
            messages = [
                SystemMessage(content=self.SYSTEM_PROMPT),
                HumanMessage(content=user_prompt)
            ]
            
            response = await self.llm.ainvoke(messages)
            content = response.content if hasattr(response, 'content') else str(response)
            
            # Parse JSON response
            feedback_data = self._parse_json_response(content)
            feedback_data = self._coerce_feedback_data(
                feedback_data,
                note_text=note_text,
                citations=citations,
            )
            feedback = CritiqueFeedback(**feedback_data)
            
            # Log critique result
            print(f"[CRITIQUE] Score: {feedback.score}/100, Needs Revision: {feedback.needs_revision}")
            
            finalized = self._finalize_feedback(
                feedback.model_dump(),
                note_doc=note_doc,
                active_archetype=str(state.get("active_archetype") or ""),
            )
            return {
                "critique_feedback": finalized,
                "needs_revision": bool(finalized.get("needs_revision")),
            }
            
        except Exception as e:
            print(f"[CRITIQUE] Error during evaluation: {e}")
            fallback = self._build_fallback_feedback(
                note_text=note_text,
                citations=citations,
                note_doc=note_doc,
                active_archetype=str(state.get("active_archetype") or ""),
            )
            return {
                "critique_feedback": fallback,
                "needs_revision": bool(fallback.get("needs_revision")),
            }

    def _coerce_feedback_data(
        self,
        feedback_data: Dict[str, Any],
        *,
        note_text: str,
        citations: list[Any],
    ) -> Dict[str, Any]:
        """Fill missing required fields so partial model output does not explode the turn."""
        base = self._build_fallback_feedback(note_text=note_text, citations=citations)
        merged = {**base, **(feedback_data or {})}
        merged["score"] = max(0, min(100, int(merged.get("score") or base.get("score") or 72)))
        merged["emoji_density"] = float(merged.get("emoji_density") or 0.0)
        merged["emotional_intensity"] = str(merged.get("emotional_intensity") or base.get("emotional_intensity") or "Medium")
        merged["has_hook"] = bool(merged.get("has_hook"))
        merged["has_call_to_action"] = bool(merged.get("has_call_to_action"))
        merged["needs_revision"] = bool(merged.get("needs_revision"))
        for key in ("factual_issues", "completeness_issues", "suggestions"):
            merged[key] = [str(item).strip() for item in (merged.get(key) or []) if str(item).strip()]
        return merged
    
    def _render_note_text(self, note_doc: Dict[str, Any]) -> str:
        """Render note document to plain text for evaluation."""
        parts = []
        
        # Title
        title = str(((note_doc.get("document_meta") or {}).get("title")) or note_doc.get("page_title") or "").strip()
        if title:
            parts.append(f"# {title}")
        
        # Blocks
        blocks = note_doc.get("blocks", [])
        for block in blocks:
            block_type = block.get("type", "")
            data = block.get("props", {}) or block.get("data", {}) or {}
            
            if block_type == "StoryText":
                paragraphs = data.get("paragraphs", []) or [item.get("paragraph") for item in (data.get("sections") or []) if isinstance(item, dict)]
                parts.extend(paragraphs)
            elif block_type == "TitleBlock":
                title = data.get("title", "")
                subtitle = data.get("subtitle", "")
                parts.append(f"{title}\n{subtitle}" if subtitle else title)
            elif block_type == "VersusCard":
                pros = data.get("pros", {}).get("summary", "") or data.get("proText", "")
                cons = data.get("cons", {}).get("summary", "") or data.get("conText", "")
                parts.append(f"正方：{pros}\n反方：{cons}")
            elif block_type == "TimelineBlock":
                for event in data.get("events", []) or []:
                    if not isinstance(event, dict):
                        continue
                    timestamp = str(event.get("timestamp") or "").strip()
                    title = str(event.get("title") or "").strip()
                    description = str(event.get("description") or "").strip()
                    event_line = " ".join(part for part in (timestamp, title, description) if part)
                    if event_line:
                        parts.append(event_line)
            elif block_type == "LocationBlock":
                poi_name = str(data.get("poi_name") or "").strip()
                location = str(data.get("location") or "").strip()
                if poi_name or location:
                    parts.append(" / ".join(part for part in (poi_name, location) if part))
            elif block_type == "PollBlock":
                question = str(data.get("question") or "").strip()
                options = [str(item).strip() for item in (data.get("options") or []) if str(item).strip()]
                if question:
                    parts.append(question)
                if options:
                    parts.append(" / ".join(options))
        
        return "\n\n".join(parts)

    def _build_fallback_feedback(
        self,
        *,
        note_text: str,
        citations: list[Any],
        note_doc: Dict[str, Any] | None = None,
        active_archetype: str = "",
    ) -> Dict[str, Any]:
        """Provide deterministic critique output when LLM critique fails."""
        text_length = len(note_text)
        paragraph_count = max(1, len([item for item in re.split(r"\n{2,}", note_text) if item.strip()]))
        citation_count = len([item for item in citations if item])
        factual_issues = [] if citation_count else ["当前页面缺少清晰可见的事实来源支撑。"]
        completeness_issues = []
        if text_length < 180:
            completeness_issues.append("内容偏短，页面信息量还不够完整。")
        if paragraph_count < 3:
            completeness_issues.append("结构层次偏少，建议补充更多正文或判断块。")
        suggestions = [
            "开头可以更快给出结论或路线建议，让用户更快知道这页想表达什么。",
            "如果这页依赖事实信息，建议优先补已确认来源，而不是继续堆表达。",
            "可以补一个更明确的判断块或路线块，让结构更像完整页面，而不是草稿。",
        ]
        score = 72
        if citation_count >= 3:
            score += 8
        if text_length >= 260:
            score += 6
        if paragraph_count >= 4:
            score += 4
        score = max(0, min(100, score))
        return self._finalize_feedback(
            CritiqueFeedback(
                score=score,
                emoji_density=0.0,
                emotional_intensity="Medium" if text_length >= 180 else "Low",
                has_hook=bool(note_text.strip().splitlines()[:2]),
                has_call_to_action=any(token in note_text for token in ("评论区", "你会选", "欢迎", "留言", "冲")),
                factual_issues=factual_issues,
                completeness_issues=completeness_issues,
                suggestions=suggestions,
                needs_revision=score < 80,
            ).model_dump(),
            note_doc=note_doc,
            active_archetype=active_archetype,
        )

    def _augment_feedback_with_structure_fit(
        self,
        feedback: Dict[str, Any],
        *,
        note_doc: Dict[str, Any] | None,
        active_archetype: str,
    ) -> Dict[str, Any]:
        doc = note_doc or {}
        blocks = [item for item in (doc.get("blocks") or []) if isinstance(item, dict)]
        if not blocks:
            return feedback

        block_types = [str(item.get("type") or "").strip() for item in blocks]
        specialty_types = {
            "ProductSpecCard",
            "RadarChartBlock",
            "VersusCard",
            "PollBlock",
            "TimelineBlock",
            "LocationBlock",
            "WeatherPolaroid",
            "QuoteBlock",
        }
        specialty_count = sum(1 for item in block_types if item in specialty_types)
        story_count = sum(1 for item in block_types if item == "StoryText")
        suggestions = [str(item).strip() for item in (feedback.get("suggestions") or []) if str(item).strip()]
        completeness = [str(item).strip() for item in (feedback.get("completeness_issues") or []) if str(item).strip()]

        def _append_unique(target: list[str], message: str) -> None:
            normalized = str(message).strip()
            if normalized and normalized not in target:
                target.append(normalized)

        if specialty_count >= max(3, len(blocks) - 1) and story_count <= 1:
            _append_unique(
                suggestions,
                "这页对特殊积木的依赖有点重，建议把次要判断收回更自由的正文容器，让 agent 表达更自然。",
            )

        feedback["suggestions"] = suggestions[:3]
        feedback["completeness_issues"] = completeness[:3]
        if len(suggestions) > 0 and ("模板墙" in " ".join(suggestions) or "特殊积木的依赖有点重" in " ".join(suggestions)):
            score = int(feedback.get("score") or 0)
            feedback["score"] = max(0, min(100, score - 6))
            feedback["needs_revision"] = True
        return feedback

    def _infer_expected_blocks(
        self,
        *,
        scope: str,
        note_doc: Dict[str, Any] | None,
        active_archetype: str,
    ) -> List[str]:
        blocks = [item for item in ((note_doc or {}).get("blocks") or []) if isinstance(item, dict)]
        if not blocks:
            return []

        def _label(block: Dict[str, Any]) -> str:
            return str(block.get("label") or block.get("type") or "当前区块").strip()

        def _pick(types: set[str]) -> List[str]:
            selected = []
            for block in blocks:
                block_type = str(block.get("type") or "").strip()
                if block_type in types:
                    selected.append(_label(block))
            return selected[:3]

        if scope == "factual_issues":
            expected = _pick({"ProductSpecCard", "LocationBlock", "TimelineBlock", "QuoteBlock", "RadarChartBlock"})
            if expected:
                return expected
        if scope == "completeness_issues":
            expected = _pick({"StoryText", "LocationBlock", "TimelineBlock", "CoverSwiper"})
            if expected:
                return expected

        if active_archetype == "seeding":
            expected = _pick({"CoverSwiper", "ProductSpecCard", "VersusCard", "StoryText", "PollBlock"})
        else:
            expected = _pick({"TitleBlock", "StoryText", "CoverSwiper"})
        return expected[:3]

    def _finalize_feedback(
        self,
        feedback: Dict[str, Any],
        *,
        note_doc: Dict[str, Any] | None = None,
        active_archetype: str = "",
    ) -> Dict[str, Any]:
        feedback = dict(feedback or {})
        feedback["suggestions"] = [str(item).strip() for item in (feedback.get("suggestions") or []) if str(item).strip()][:3]
        feedback["factual_issues"] = [str(item).strip() for item in (feedback.get("factual_issues") or []) if str(item).strip()][:3]
        feedback["completeness_issues"] = [str(item).strip() for item in (feedback.get("completeness_issues") or []) if str(item).strip()][:3]
        feedback = self._augment_feedback_with_structure_fit(
            feedback,
            note_doc=note_doc,
            active_archetype=active_archetype,
        )
        feedback["action_recipes"] = self._build_action_recipes(
            feedback,
            note_doc=note_doc,
            active_archetype=active_archetype,
        )
        return feedback

    def _build_action_recipes(
        self,
        feedback: Dict[str, Any],
        *,
        note_doc: Dict[str, Any] | None = None,
        active_archetype: str = "",
    ) -> List[Dict[str, Any]]:
        suggestions = [str(item).strip() for item in (feedback.get("suggestions") or []) if str(item).strip()]
        factual_issues = [str(item).strip() for item in (feedback.get("factual_issues") or []) if str(item).strip()]
        completeness_issues = [str(item).strip() for item in (feedback.get("completeness_issues") or []) if str(item).strip()]

        recipes: List[Dict[str, Any]] = []
        if suggestions:
            joined = "；".join(suggestions[:3])
            recipes.append({
                "label": "按优先建议继续优化",
                "scope": "priority",
                "prompt": f"按这轮 Agent 复盘的优先建议继续优化当前页面，重点处理：{joined}。保持现有主题和结构基调，不要重起一页。",
                "why_now": suggestions[0],
                "expected_effect": "我会优先收紧这页最影响完成度的问题，让它更像一版可以直接展示的成品。",
                "expected_blocks": self._infer_expected_blocks(
                    scope="priority",
                    note_doc=note_doc,
                    active_archetype=active_archetype,
                ),
            })
        if factual_issues:
            joined = "；".join(factual_issues[:3])
            recipes.append({
                "label": "只修事实风险",
                "scope": "factual_issues",
                "prompt": f"只修当前页面里的事实风险，重点处理：{joined}。保留整体表达风格，不要顺手重写无关内容。",
                "why_now": factual_issues[0],
                "expected_effect": "我会把相关结论收回到已确认事实范围，并减少容易被误解的表达。",
                "expected_blocks": self._infer_expected_blocks(
                    scope="factual_issues",
                    note_doc=note_doc,
                    active_archetype=active_archetype,
                ),
            })
        if completeness_issues:
            joined = "；".join(completeness_issues[:3])
            recipes.append({
                "label": "只补信息缺口",
                "scope": "completeness_issues",
                "prompt": f"只补当前页面缺失的关键信息，重点处理：{joined}。保留已有结构和语气，不要扩大改动范围。",
                "why_now": completeness_issues[0],
                "expected_effect": "我会补齐最影响阅读和判断的缺口，但尽量不打乱当前页面结构。",
                "expected_blocks": self._infer_expected_blocks(
                    scope="completeness_issues",
                    note_doc=note_doc,
                    active_archetype=active_archetype,
                ),
            })
        recipes.append({
            "label": "先不处理，保留当前版本",
            "scope": "noop",
            "prompt": "",
            "why_now": "这版已经能继续往下协作，不必强制改动。",
            "expected_effect": "我会保留当前页面，等你下一次明确指定修改方向再继续。",
            "expected_blocks": [],
        })
        return recipes[:4]
    
    def _parse_json_response(self, content: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        import re
        
        # Try to extract JSON from markdown code block
        json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', content, re.DOTALL)
        if json_match:
            content = json_match.group(1)
        
        # Remove any trailing text after JSON
        try:
            # Find the last closing brace
            last_brace = content.rfind('}')
            if last_brace != -1:
                content = content[:last_brace + 1]
        except:
            pass
        
        return json.loads(content)


# Singleton instance
_critique_agent_instance: Optional[NoteCritiqueAgent] = None


def get_critique_agent() -> NoteCritiqueAgent:
    """Get or create the critique agent singleton."""
    global _critique_agent_instance
    if _critique_agent_instance is None:
        _critique_agent_instance = NoteCritiqueAgent()
    return _critique_agent_instance


async def critique_worker_payload(state: dict[str, Any]) -> Dict[str, Any]:
    """Worker wrapper for the critique agent."""
    knowledge_plan = (
        state.get("knowledge_plan")
        if isinstance(state.get("knowledge_plan"), dict)
        else ((state.get("retrieved_knowledge") or {}).get("knowledge_plan") if isinstance(state.get("retrieved_knowledge"), dict) else {})
    )
    skill_context = build_skill_context(
        role="critique_worker",
        intent_decision=state.get("intent_decision") if isinstance(state.get("intent_decision"), dict) else {},
        knowledge_plan=knowledge_plan if isinstance(knowledge_plan, dict) else {},
    )
    selected_skills = [str(item) for item in (skill_context.get("selected_skills") or []) if str(item).strip()]
    agent = get_critique_agent()
    payload = await agent.critique(state)
    feedback = payload.get("critique_feedback") if isinstance(payload.get("critique_feedback"), dict) else {}
    factual_issues = feedback.get("factual_issues") if isinstance(feedback.get("factual_issues"), list) else []
    completeness_issues = feedback.get("completeness_issues") if isinstance(feedback.get("completeness_issues"), list) else []
    failure_point = ""
    if bool(payload.get("needs_revision")):
        failure_point = str((factual_issues or completeness_issues or ["critique_requires_revision"])[0] or "")
    payload.setdefault("selected_skills", selected_skills)
    payload.setdefault("skill_trace", {})
    payload["skill_trace"]["critique_worker"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "needs_revision" if bool(payload.get("needs_revision")) else "pass",
        "skill_fallback": [],
    }
    payload.setdefault("turn_trace", {})
    payload["turn_trace"]["critique_worker"] = {
        "selected_skills": selected_skills,
        "skill_tool_plan": skill_context.get("tool_plan") or [],
        "skill_execution_result": "needs_revision" if bool(payload.get("needs_revision")) else "pass",
        "skill_fallback": [],
    }
    payload["turn_trace"]["agentic_runtime"] = {
        "current_stage": "critique",
        "current_agent": "critique_worker",
        "selected_skills": selected_skills,
        "failure_point": failure_point,
    }
    payload.setdefault("agent_backends", {})
    payload["agent_backends"]["critique_worker"] = "structured_quality_review"
    return payload


gaicritique_node = critique_worker_payload
