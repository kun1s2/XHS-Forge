from app.services.knowledge_hub import (
    KnowledgeHubService,
    ParsedKnowledgeSource,
    KNOWLEDGE_SCOPE_CANDIDATE,
    KNOWLEDGE_SCOPE_PERSISTENT,
    REVIEW_PENDING,
    apply_knowledge_review_decision,
    knowledge_hub_service,
    merge_candidate_records_into_retrieved,
    select_records_from_session,
)


def _record(*, record_id: str, entity: str, field: str, value: str, scope: str = KNOWLEDGE_SCOPE_CANDIDATE, status: str = REVIEW_PENDING):
    return {
        "record_id": record_id,
        "knowledge_id": record_id,
        "normalized_entity": entity,
        "entity_type": "product/model",
        "field_or_topic": field,
        "field_label": field,
        "value": value,
        "summary": value,
        "knowledge_scope": scope,
        "review_status": status,
        "source_type": "web_search",
        "source_title": "demo",
    }


def test_merge_candidate_records_keeps_pending_items_in_candidate_bucket():
    knowledge = merge_candidate_records_into_retrieved(
        {},
        candidate_records=[
            _record(record_id="r1", entity="华为 Mate 60", field="price", value="5999"),
            _record(record_id="r2", entity="华为 Mate 60", field="battery", value="4750mAh"),
        ],
    )

    assert knowledge["candidate_session_kb"]["record_count"] == 2
    assert knowledge["candidate_session_kb"]["pending_count"] == 2
    assert knowledge["session_kb"]["record_count"] == 0
    assert len(knowledge["candidate_session_kb"]["groups"]) == 2


def test_approve_recommended_moves_candidate_records_into_session_bucket():
    knowledge = merge_candidate_records_into_retrieved(
        {},
        candidate_records=[
            _record(record_id="r1", entity="华为 Mate 60", field="price", value="5999"),
            _record(record_id="r2", entity="华为 Mate 60", field="battery", value="4750mAh"),
        ],
    )

    next_knowledge = apply_knowledge_review_decision(knowledge, decision="approve_recommended")

    assert next_knowledge["candidate_session_kb"]["pending_count"] == 0
    assert next_knowledge["session_kb"]["record_count"] == 2
    assert {item["field_or_topic"] for item in next_knowledge["session_kb"]["records"]} == {"price", "battery"}


def test_select_records_from_session_supports_entity_and_field_level_precision():
    knowledge = apply_knowledge_review_decision(
        merge_candidate_records_into_retrieved(
            {},
            candidate_records=[
                _record(record_id="h1", entity="华为 Mate 60", field="price", value="5999"),
                _record(record_id="h2", entity="华为 Mate 60", field="battery", value="4750mAh"),
                _record(record_id="x1", entity="小米 14", field="price", value="4299"),
            ],
        ),
        decision="approve_recommended",
    )

    xiaomi_records = select_records_from_session(knowledge, normalized_entity="小米 14")
    huawei_battery = select_records_from_session(knowledge, normalized_entity="华为 Mate 60", field_or_topic="battery")

    assert len(xiaomi_records) == 1
    assert xiaomi_records[0]["normalized_entity"] == "小米 14"
    assert len(huawei_battery) == 1
    assert huawei_battery[0]["field_or_topic"] == "battery"


def test_demo_pack_specs_include_consistent_entity_hints_for_mock_ingestion():
    packs = knowledge_hub_service.build_demo_pack_specs()
    digital = next(item for item in packs if item["pack_id"] == "digital_mate60")
    competitor = next(item for item in packs if item["pack_id"] == "digital_xiaomi14")

    assert {doc.get("entity_hint") for doc in digital["documents"]} == {"华为 Mate 60"}
    assert {doc.get("entity_hint") for doc in competitor["documents"]} == {"小米 14"}


def test_selected_candidate_records_can_be_rejected_or_deferred():
    knowledge = merge_candidate_records_into_retrieved(
        {},
        candidate_records=[
            _record(record_id="r1", entity="华为 Mate 60", field="price", value="5999"),
            _record(record_id="r2", entity="华为 Mate 60", field="battery", value="4750mAh"),
        ],
    )

    rejected = apply_knowledge_review_decision(knowledge, decision="reject_selected", record_ids=["r1"])
    deferred = apply_knowledge_review_decision(knowledge, decision="defer_selected", record_ids=["r2"])

    rejected_status = {
        item["record_id"]: item["review_status"]
        for item in rejected["candidate_session_kb"]["records"]
    }
    deferred_status = {
        item["record_id"]: item["review_status"]
        for item in deferred["candidate_session_kb"]["records"]
    }

    assert rejected_status["r1"] == "rejected"
    assert deferred_status["r2"] == "deferred"


def test_demo_eval_sets_cover_retrieval_and_generation_expectations():
    eval_sets = knowledge_hub_service.build_demo_eval_sets()
    digital = next(item for item in eval_sets if item["pack_id"] == "digital_mate60")
    competitor = next(item for item in eval_sets if item["pack_id"] == "digital_xiaomi14")

    assert digital["questions"][0]["expected_facts"]["price"] == "5999"
    assert "编造具体跑分" in digital["questions"][0]["forbidden_hallucinations"]
    assert "提到价格门槛更低" in competitor["questions"][0]["expected_answer_points"]


def test_register_persistent_document_writes_product_index(tmp_path):
    service = KnowledgeHubService()
    raw_path = tmp_path / "mate60.md"
    raw_path.write_text("Mate 60 参数资料", encoding="utf-8")
    parsed = ParsedKnowledgeSource(
        document_id="doc-mate60",
        title="华为 Mate 60 参数包",
        file_name="mate60.md",
        source_type="user_kb_curated",
        kb_scope=KNOWLEDGE_SCOPE_PERSISTENT,
        raw_path=str(raw_path),
        text="Mate 60 参数资料",
        chunks=[{"chunk_id": "chunk-1", "text": "价格 5999"}],
        records=[
            {
                "field_or_topic": "price",
                "normalized_entity": "华为 Mate 60",
            },
            {
                "field_or_topic": "battery",
                "normalized_entity": "华为 Mate 60",
            },
        ],
        entity_hint="华为 Mate 60",
        scene_hint="seeding",
    )

    import asyncio

    asyncio.run(service.register_persistent_document(parsed))
    stored = service._persistent_docs["doc-mate60"]
    index_path = stored["document_index_path"]

    assert index_path
    content = raw_path.with_name("mate60.product_index.md").read_text(encoding="utf-8")
    assert "华为 Mate 60 参数包" in content
    assert "`price`" in content
    assert stored["document_index"]["entity"] == "华为 Mate 60"
