from app.core import runtime_log


def test_runtime_log_writes_latest_console_and_html(tmp_path, monkeypatch):
    log_dir = tmp_path / 'log'
    monkeypatch.setattr(runtime_log, 'LOG_DIR', log_dir)
    monkeypatch.setattr(runtime_log, 'LATEST_CONSOLE_LOG_PATH', log_dir / '控制台输出')
    monkeypatch.setattr(runtime_log, 'LATEST_HTML_PATH', log_dir / 'html生成')

    runtime_log.reset_latest_console_log('[DEBUG] header')
    runtime_log.append_log_divider('REQUEST')
    runtime_log.append_latest_console_log('first line')
    runtime_log.write_latest_html('<html>ok</html>')

    console_text = (log_dir / '控制台输出').read_text(encoding='utf-8')
    html_text = (log_dir / 'html生成').read_text(encoding='utf-8')

    assert '[DEBUG] header' in console_text
    assert 'REQUEST' in console_text
    assert 'first line' in console_text
    assert html_text == '<html>ok</html>'


def test_runtime_log_summarizers_are_human_readable():
    render_summary = runtime_log.summarize_node_output('render', {
        'final_html': '<html>' + 'x' * 20 + '</html>',
        'final_oss_url': 'data:text/html;base64,abc',
        'note_document': {'blocks': [{}, {}]},
    })
    generic_summary = runtime_log.summarize_node_output('planner', {
        'planner_output': {'block_intents': [1, 2]},
        'node_prompts': {'planner_agent': []},
    })
    turn_summary = runtime_log.summarize_turn_completion(
        {
            'note_editor': {'action': 'update_block', 'block_id': 'story_1'},
            'changed_blocks': [{'id': 'story_1'}],
            'warnings': ['noop'],
        },
        {'note_document': {'blocks': [{}, {}, {}]}},
    )

    assert 'html=' in render_summary and 'blocks=2' in render_summary
    assert 'planner.block_intents=2' in generic_summary and 'node_prompts=1' in generic_summary
    assert 'action=update_block' in turn_summary and 'warnings=1' in turn_summary


def test_runtime_log_writes_latest_frontend_observation(tmp_path, monkeypatch):
    log_dir = tmp_path / 'log'
    monkeypatch.setattr(runtime_log, 'LOG_DIR', log_dir)
    monkeypatch.setattr(runtime_log, 'LATEST_FRONTEND_OBSERVATION_PATH', log_dir / '前端观测.json')

    runtime_log.write_latest_frontend_observation({'thread_id': 'thread_x', 'event_type': 'window_error'})
    payload = (log_dir / '前端观测.json').read_text(encoding='utf-8')

    assert 'thread_x' in payload
    assert 'window_error' in payload
    assert 'captured_at' in payload


def test_runtime_log_turn_summary_supports_workspace_actions():
    turn_summary = runtime_log.summarize_turn_completion(
        {
            'workspace_action': {'action': 'workspace_rollback_component', 'target_block_id': 'story_1'},
            'changed_blocks': [{'id': 'story_1'}],
            'warnings': [],
        },
        {'note_document': {'blocks': [{}, {}]}},
    )

    assert 'action=workspace_rollback_component' in turn_summary
    assert 'target=story_1' in turn_summary
