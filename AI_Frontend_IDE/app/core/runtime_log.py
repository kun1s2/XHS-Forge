from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any
import json


LOG_DIR = Path(__file__).resolve().parents[2] / 'log'
LATEST_CONSOLE_LOG_PATH = LOG_DIR / '控制台输出'
LATEST_HTML_PATH = LOG_DIR / 'html生成'
LATEST_FRONTEND_OBSERVATION_PATH = LOG_DIR / '前端观测.json'


def _ensure_log_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _timestamp() -> str:
    return datetime.now().strftime('%Y-%m-%d %H:%M:%S')


def reset_latest_console_log(header: str | None = None) -> None:
    _ensure_log_dir()
    content = ''
    if header:
        content = f'{header}\n'
    LATEST_CONSOLE_LOG_PATH.write_text(content, encoding='utf-8')


def append_latest_console_log(message: str) -> None:
    _ensure_log_dir()
    with LATEST_CONSOLE_LOG_PATH.open('a', encoding='utf-8') as f:
        f.write(f'[{_timestamp()}] {message}\n')


def append_log_divider(title: str) -> None:
    append_latest_console_log(f"{'=' * 10} {title} {'=' * 10}")


def truncate_text(value: Any, max_len: int = 220) -> str:
    text = str(value or '')
    text = text.replace('\n', ' ').strip()
    if len(text) <= max_len:
        return text
    return text[: max_len - 3] + '...'


def summarize_worker_output(worker_name: str, output: Any) -> str:
    if not isinstance(output, dict):
        return truncate_text(output)

    summary_parts: list[str] = []

    if worker_name in {'supervisor_agent', 'composition_worker'}:
        html = output.get('final_html') or ''
        oss_url = output.get('final_oss_url') or ''
        note_document = output.get('note_document') or {}
        block_count = len((note_document.get('blocks') or [])) if isinstance(note_document, dict) else 0
        summary_parts.extend([
            f'html={len(str(html))} chars',
            f'oss={truncate_text(oss_url, 60) or "none"}',
            f'blocks={block_count}',
        ])
    else:
        if isinstance(output.get('note_document'), dict):
            summary_parts.append(f"note_document.blocks={len(output['note_document'].get('blocks') or [])}")
        if isinstance(output.get('worker_prompts'), dict):
            summary_parts.append(f"worker_prompts={len(output['worker_prompts'].keys())}")
        if isinstance(output.get('planner_output'), dict):
            summary_parts.append(f"planner.block_intents={len(output['planner_output'].get('block_intents') or [])}")
        if isinstance(output.get('retrieved_knowledge'), dict):
            summary_parts.append(f"knowledge.entity={truncate_text(output['retrieved_knowledge'].get('entity_name'), 40)}")
        for key in ['action', 'block_id', 'reason', 'checkpoint_id']:
            if output.get(key):
                summary_parts.append(f'{key}={truncate_text(output.get(key), 70)}')

    if not summary_parts:
        keys = list(output.keys())
        summary_parts.append(f'keys={keys[:8]}')
        if len(keys) > 8:
            summary_parts.append(f'+{len(keys) - 8} more')

    return ' | '.join(part for part in summary_parts if part)


def summarize_turn_completion(turn_trace: dict[str, Any] | None, after_values: dict[str, Any] | None) -> str:
    trace = turn_trace or {}
    composition_trace = (trace.get('composition_worker') or {}) if isinstance(trace, dict) else {}
    workspace_action = (trace.get('workspace_action') or {}) if isinstance(trace, dict) else {}
    execution = composition_trace or workspace_action
    after = after_values or {}
    note_document = (after.get('note_document') or {}) if isinstance(after.get('note_document'), dict) else {}
    blocks = note_document.get('blocks') or []
    warnings = trace.get('warnings') or []
    changed_blocks = trace.get('changed_blocks') or []
    action = execution.get('action') or 'unknown'
    target = execution.get('target_block_id') or composition_trace.get('block_id') or trace.get('selected_element_id') or 'global'
    return (
        f'action={action} | target={target} | '
        f'blocks={len(blocks)} | changed={len(changed_blocks)} | warnings={len(warnings)}'
    )


def write_latest_html(html: str) -> None:
    _ensure_log_dir()
    LATEST_HTML_PATH.write_text(html or '', encoding='utf-8')


def write_latest_frontend_observation(payload: dict[str, Any]) -> None:
    _ensure_log_dir()
    enriched = {
        'captured_at': _timestamp(),
        **(payload or {}),
    }
    LATEST_FRONTEND_OBSERVATION_PATH.write_text(
        json.dumps(enriched, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )


def read_latest_console_tail(*, max_lines: int = 120) -> str:
    _ensure_log_dir()
    if not LATEST_CONSOLE_LOG_PATH.exists():
        return ''
    lines = LATEST_CONSOLE_LOG_PATH.read_text(encoding='utf-8').splitlines()
    return '\n'.join(lines[-max_lines:])


def read_latest_html_preview(*, max_chars: int = 12000) -> str:
    _ensure_log_dir()
    if not LATEST_HTML_PATH.exists():
        return ''
    html = LATEST_HTML_PATH.read_text(encoding='utf-8')
    if len(html) <= max_chars:
        return html
    return html[:max_chars]
