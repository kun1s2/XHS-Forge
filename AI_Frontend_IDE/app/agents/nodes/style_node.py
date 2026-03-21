from copy import deepcopy

from app.agents.state import UIProjectState
from app.core.note_document import (
    build_note_document_layout,
    build_note_document_from_state,
    update_note_document_block,
    update_note_document_theme,
)


THEME_PRESETS = {
    "general": {
        "theme_name": "general_editorial",
        "vars": {
            "--bg-color": "#f5f7fb",
            "--bg-gradient": "linear-gradient(180deg, #f8fafc 0%, #eef2ff 100%)",
            "--primary-vibe": "#ff2442",
            "--primary-vibe-light": "rgba(255, 36, 66, 0.14)",
            "--text-color": "#0f172a",
            "--text-muted": "#64748b",
            "--card-bg": "rgba(255,255,255,0.92)",
            "--card-bg-soft": "rgba(255,255,255,0.72)",
            "--card-border": "rgba(148,163,184,0.18)",
            "--card-shadow": "0 20px 50px rgba(15,23,42,0.08)",
            "--chrome-bg": "rgba(255,255,255,0.88)",
            "--chrome-border": "rgba(148,163,184,0.16)",
            "--surface-hero": "linear-gradient(135deg, rgba(255,255,255,0.96), rgba(255,241,244,0.98))",
            "--story-bg": "rgba(255,255,255,0.78)",
            "--story-hover": "rgba(15,23,42,0.03)",
            "--hero-shadow": "0 24px 80px rgba(255,36,66,0.12)",
            "--pro-color": "#f43f5e",
            "--con-color": "#0f172a",
        },
    },
    "seeding": {
        "theme_name": "seeding_hot",
        "vars": {
            "--bg-color": "#fff7f4",
            "--bg-gradient": "radial-gradient(circle at top, rgba(251,146,60,0.2), transparent 38%), linear-gradient(180deg, #fff7f4 0%, #fff1f2 100%)",
            "--primary-vibe": "#ef4444",
            "--primary-vibe-light": "rgba(239,68,68,0.16)",
            "--text-color": "#1f2937",
            "--text-muted": "#7c2d12",
            "--card-bg": "rgba(255,255,255,0.94)",
            "--card-bg-soft": "rgba(255,247,237,0.86)",
            "--card-border": "rgba(251,113,133,0.18)",
            "--card-shadow": "0 24px 70px rgba(239,68,68,0.12)",
            "--chrome-bg": "rgba(255,250,250,0.88)",
            "--chrome-border": "rgba(251,113,133,0.18)",
            "--surface-hero": "linear-gradient(135deg, rgba(255,255,255,0.95), rgba(255,237,213,0.96))",
            "--story-bg": "rgba(255,252,252,0.82)",
            "--story-hover": "rgba(239,68,68,0.05)",
            "--hero-shadow": "0 26px 90px rgba(239,68,68,0.16)",
            "--pro-color": "#fb7185",
            "--con-color": "#111827",
        },
    },
    "travel": {
        "theme_name": "travel_clean",
        "vars": {
            "--bg-color": "#f3fbfb",
            "--bg-gradient": "radial-gradient(circle at top, rgba(45,212,191,0.18), transparent 32%), linear-gradient(180deg, #f3fbfb 0%, #eff6ff 100%)",
            "--primary-vibe": "#0f766e",
            "--primary-vibe-light": "rgba(15,118,110,0.14)",
            "--text-color": "#102a43",
            "--text-muted": "#52796f",
            "--card-bg": "rgba(255,255,255,0.9)",
            "--card-bg-soft": "rgba(240,253,250,0.84)",
            "--card-border": "rgba(94,234,212,0.24)",
            "--card-shadow": "0 24px 60px rgba(15,118,110,0.1)",
            "--chrome-bg": "rgba(250,255,255,0.84)",
            "--chrome-border": "rgba(125,211,252,0.18)",
            "--surface-hero": "linear-gradient(135deg, rgba(255,255,255,0.94), rgba(236,253,245,0.98))",
            "--story-bg": "rgba(255,255,255,0.72)",
            "--story-hover": "rgba(15,118,110,0.05)",
            "--hero-shadow": "0 24px 80px rgba(15,118,110,0.14)",
            "--pro-color": "#14b8a6",
            "--con-color": "#0f172a",
        },
    },
    "daily_share": {
        "theme_name": "daily_soft",
        "vars": {
            "--bg-color": "#fffaf8",
            "--bg-gradient": "radial-gradient(circle at top, rgba(244,114,182,0.14), transparent 34%), linear-gradient(180deg, #fffaf8 0%, #fdf4ff 100%)",
            "--primary-vibe": "#db2777",
            "--primary-vibe-light": "rgba(219,39,119,0.12)",
            "--text-color": "#3f3f46",
            "--text-muted": "#71717a",
            "--card-bg": "rgba(255,255,255,0.88)",
            "--card-bg-soft": "rgba(253,242,248,0.82)",
            "--card-border": "rgba(244,114,182,0.16)",
            "--card-shadow": "0 22px 60px rgba(219,39,119,0.1)",
            "--chrome-bg": "rgba(255,255,255,0.82)",
            "--chrome-border": "rgba(244,114,182,0.14)",
            "--surface-hero": "linear-gradient(135deg, rgba(255,255,255,0.94), rgba(253,242,248,0.98))",
            "--story-bg": "rgba(255,255,255,0.72)",
            "--story-hover": "rgba(219,39,119,0.05)",
            "--hero-shadow": "0 24px 72px rgba(219,39,119,0.12)",
            "--pro-color": "#f472b6",
            "--con-color": "#52525b",
        },
    },
}

VIBE_OVERRIDES = {
    "minimalist": {
        "--bg-gradient": "linear-gradient(180deg, #ffffff 0%, #f8fafc 100%)",
        "--card-bg": "rgba(255,255,255,0.98)",
        "--card-bg-soft": "rgba(255,255,255,0.92)",
        "--card-border": "rgba(148,163,184,0.16)",
        "--card-shadow": "0 10px 24px rgba(15,23,42,0.06)",
        "--chrome-bg": "rgba(255,255,255,0.96)",
    },
    "cyberpunk": {
        "--bg-color": "#030712",
        "--bg-gradient": "radial-gradient(circle at top, rgba(34,211,238,0.2), transparent 30%), linear-gradient(180deg, #020617 0%, #0f172a 100%)",
        "--primary-vibe": "#22d3ee",
        "--primary-vibe-light": "rgba(34,211,238,0.16)",
        "--text-color": "#e0f2fe",
        "--text-muted": "#7dd3fc",
        "--card-bg": "rgba(2,6,23,0.82)",
        "--card-bg-soft": "rgba(15,23,42,0.72)",
        "--card-border": "rgba(34,211,238,0.22)",
        "--card-shadow": "0 0 36px rgba(34,211,238,0.16)",
        "--chrome-bg": "rgba(2,6,23,0.86)",
        "--chrome-border": "rgba(34,211,238,0.2)",
        "--surface-hero": "linear-gradient(135deg, rgba(2,6,23,0.96), rgba(8,47,73,0.92))",
        "--story-bg": "rgba(15,23,42,0.74)",
        "--story-hover": "rgba(34,211,238,0.08)",
        "--hero-shadow": "0 24px 90px rgba(34,211,238,0.16)",
        "--pro-color": "#22d3ee",
        "--con-color": "#f472b6",
    },
    "vintage": {
        "--bg-color": "#f8f2e8",
        "--bg-gradient": "linear-gradient(180deg, #fbf6ec 0%, #f4efe1 100%)",
        "--primary-vibe": "#8b5e3c",
        "--primary-vibe-light": "rgba(139,94,60,0.14)",
        "--text-color": "#4b3621",
        "--text-muted": "#7c5c3d",
        "--card-bg": "rgba(255,250,241,0.9)",
        "--card-bg-soft": "rgba(245,239,225,0.86)",
        "--card-border": "rgba(146,64,14,0.14)",
        "--card-shadow": "0 18px 40px rgba(92,63,33,0.10)",
        "--chrome-bg": "rgba(255,250,241,0.88)",
        "--chrome-border": "rgba(146,64,14,0.12)",
        "--surface-hero": "linear-gradient(135deg, rgba(255,251,235,0.96), rgba(251,243,219,0.98))",
        "--story-bg": "rgba(255,250,241,0.8)",
        "--story-hover": "rgba(139,94,60,0.05)",
        "--hero-shadow": "0 24px 64px rgba(92,63,33,0.12)",
        "--pro-color": "#b45309",
        "--con-color": "#5b3b1d",
    },
    "luxury": {
        "--bg-color": "#111111",
        "--bg-gradient": "linear-gradient(180deg, #161616 0%, #050505 100%)",
        "--primary-vibe": "#d4af37",
        "--primary-vibe-light": "rgba(212,175,55,0.16)",
        "--text-color": "#f8f5ef",
        "--text-muted": "#d6c7a1",
        "--card-bg": "rgba(24,24,27,0.88)",
        "--card-bg-soft": "rgba(39,39,42,0.78)",
        "--card-border": "rgba(212,175,55,0.18)",
        "--card-shadow": "0 28px 70px rgba(0,0,0,0.35)",
        "--chrome-bg": "rgba(12,12,12,0.9)",
        "--chrome-border": "rgba(212,175,55,0.14)",
        "--surface-hero": "linear-gradient(135deg, rgba(24,24,27,0.96), rgba(63,63,70,0.86))",
        "--story-bg": "rgba(24,24,27,0.72)",
        "--story-hover": "rgba(212,175,55,0.06)",
        "--hero-shadow": "0 26px 86px rgba(0,0,0,0.34)",
        "--pro-color": "#fbbf24",
        "--con-color": "#fafafa",
    },
}

BLOCK_EMPHASIS = {
    "CoverSwiper": {"class": "mb-2", "padding": "0px", "radius": "32px", "background": "transparent", "border": "1px solid var(--card-border)", "boxShadow": "var(--hero-shadow)"},
    "TitleBlock": {"class": "pt-2 pb-1", "padding": "8px 6px 0px 6px", "background": "transparent", "border": "none", "boxShadow": "none"},
    "StoryText": {"class": "", "padding": "14px 14px 10px 14px", "background": "var(--story-bg)", "border": "1px solid var(--card-border)", "boxShadow": "0 12px 32px rgba(15,23,42,0.04)"},
    "ProductSpecCard": {"class": "", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "var(--card-shadow)"},
    "RadarChartBlock": {"class": "", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "var(--card-shadow)"},
    "PollBlock": {"class": "", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "var(--card-shadow)"},
    "VersusCard": {"class": "overflow-hidden", "padding": "0px", "background": "transparent", "border": "none", "boxShadow": "none"},
    "LocationBlock": {"class": "", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "0 16px 40px rgba(15,23,42,0.06)"},
    "WeatherPolaroid": {"class": "overflow-hidden", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "var(--card-shadow)"},
}


def _merge_theme(base: dict, override: dict) -> dict:
    merged = deepcopy(base)
    merged.update(override or {})
    return merged


def _infer_vibe_from_theme_policy(planner_policy: dict | None) -> str:
    theme_policy = (planner_policy or {}).get("theme_policy") or {}
    preset = str(theme_policy.get("preset") or "").lower()
    for vibe_name in VIBE_OVERRIDES:
        if vibe_name in preset:
            return vibe_name
    return ""



def _resolve_theme_signal(state: UIProjectState) -> tuple[str, float, str | None]:
    planner_policy = state.get("planner_policy") if isinstance(state.get("planner_policy"), dict) else {}
    theme_policy = (planner_policy or {}).get("theme_policy") or {}
    preset = str(theme_policy.get("preset") or "").strip() or None
    interaction_bias = str(theme_policy.get("interaction_bias") or "").lower()
    vibe = _infer_vibe_from_theme_policy(planner_policy) or "general"
    intensity_map = {"high": 0.85, "medium": 0.55, "low": 0.25}
    return vibe, intensity_map.get(interaction_bias, 0.0), preset



def _pick_theme_vars(state: UIProjectState, vibe: str, theme_name_override: str | None = None) -> dict:
    archetype = str(state.get("active_archetype") or "general")
    base = THEME_PRESETS.get(archetype, THEME_PRESETS["general"])
    vars_map = deepcopy(base["vars"])
    if vibe in VIBE_OVERRIDES:
        vars_map = _merge_theme(vars_map, VIBE_OVERRIDES[vibe])
    if state.get("has_controversy"):
        vars_map["--hero-shadow"] = "0 28px 90px rgba(244,63,94,0.18)"
        vars_map["--card-border"] = "rgba(244,63,94,0.18)"
    vars_map["--theme-name"] = theme_name_override or base["theme_name"]
    return vars_map


def _build_block_style(block_type: str, intensity: float, vibe: str) -> dict:
    emphasis = BLOCK_EMPHASIS.get(block_type, {"class": "", "padding": "0px", "background": "var(--card-bg)", "border": "1px solid var(--card-border)", "boxShadow": "var(--card-shadow)"})
    scale = "translateY(-1px)" if intensity >= 0.75 and block_type in {"CoverSwiper", "PollBlock", "VersusCard"} else "none"
    radius = emphasis.get("radius", "28px")
    inline_styles = {
        "padding": emphasis.get("padding", "0px"),
        "background": emphasis.get("background", "var(--card-bg)"),
        "border": emphasis.get("border", "1px solid var(--card-border)"),
        "boxShadow": emphasis.get("boxShadow", "var(--card-shadow)"),
        "borderRadius": radius,
        "transform": scale,
    }
    if block_type == "TitleBlock":
        inline_styles.update({"marginTop": "6px"})
    if block_type == "StoryText":
        inline_styles.update({"backdropFilter": "blur(10px)"})
    if block_type == "CoverSwiper":
        inline_styles.update({"overflow": "hidden"})
    if vibe == "minimalist":
        inline_styles["borderRadius"] = "24px" if block_type != "CoverSwiper" else "28px"
    return {
        "css_classes": " ".join(part for part in ["transition-all duration-500", emphasis.get("class", "")] if part).strip(),
        "inline_styles": inline_styles,
    }


async def style_agent(state: UIProjectState) -> dict:
    print("🎨 [主题编译器] 开始为画布编译视觉主题...")
    note_document = build_note_document_from_state(state)
    execution_view = build_note_document_layout(note_document)
    blocks = execution_view.get("blocks", []) or []
    vibe, intensity, theme_name_override = _resolve_theme_signal(state)
    theme_vars = _pick_theme_vars(state, vibe, theme_name_override)
    page_theme = execution_view.get("page_theme") or {}

    styled_document = deepcopy(note_document)
    for block in blocks:
        block_id = block.get("id")
        block_type = block.get("component_type", "")
        if not block_id:
            continue
        styled_document = update_note_document_block(
            styled_document,
            block_id,
            style=_build_block_style(block_type, intensity, vibe),
        )

    styled_document = update_note_document_theme(
        styled_document,
        page_theme=page_theme,
        global_vars={**theme_vars, **page_theme},
    )
    print(f"✅ [主题编译器] 主题 {theme_vars.get('--theme-name')} 已应用，共处理 {len(blocks)} 个区块。")
    return {
        "note_document": styled_document,
        "turn_trace": {
            "theme_compiler": {
                "theme_name": theme_vars.get("--theme-name"),
                "vibe": vibe,
                "intensity": intensity,
                "block_count": len(blocks),
                "source": "planner_policy",
            }
        },
        "agent_backends": {"theme_compiler": "deterministic_compiler"},
    }


theme_compiler_node = style_agent
