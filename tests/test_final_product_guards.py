from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_main_runtime_uses_supervisor_runtime_instead_of_graph():
    main_text = (ROOT / "AI_Frontend_IDE" / "app" / "main.py").read_text(encoding="utf-8")
    assert "app.agents.runtime" in main_text
    assert "build_supervisor_runtime" in main_text


def test_supervisor_runtime_no_longer_imports_graph_nodes():
    runtime_text = (ROOT / "AI_Frontend_IDE" / "app" / "agents" / "runtime" / "supervisor_runtime.py").read_text(encoding="utf-8")
    assert "app.agents.nodes" not in runtime_text
    assert "intent_worker" in runtime_text
    assert "retrieval_worker" in runtime_text
    assert "composition_worker" in runtime_text
    assert "critique_worker" in runtime_text


def test_formal_frontend_runtime_labels_use_supervisor_workers():
    chat_store_text = (ROOT / "ai-frontend-ide" / "src" / "stores" / "useChatStore.ts").read_text(encoding="utf-8")
    assert "supervisor_agent" in chat_store_text
    assert "retrieval_worker" in chat_store_text
    assert "composition_worker" in chat_store_text
    assert "document_renderer" not in chat_store_text


def test_formal_skill_snapshot_uses_worker_role_names():
    snapshot_text = (ROOT / "AI_Frontend_IDE" / "app" / "skills" / "SKILLS_SNAPSHOT.md").read_text(encoding="utf-8")
    assert "retrieval_worker" in snapshot_text
    assert "composition_worker" in snapshot_text
    assert "critique_worker" in snapshot_text
    assert "retrieval_agent" not in snapshot_text
