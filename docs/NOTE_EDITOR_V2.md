# Note Editor V2

## Why change

The current system can generate notes, but the control model is still pipeline-first:

`intent -> research -> distill -> outline -> component_builder -> style -> render`

This works for one-shot generation, but it is not the best fit for a product whose core promise is:

"Users can create and modify a note through natural language."

The main problems with the current architecture are:

1. Too many stage-specific agents.
2. User intent is translated into a fixed production line too early.
3. Global edits and local edits are split into different mental models.
4. Structured data is created by multiple nodes with partially overlapping responsibility.
5. Flexibility drops when the user asks for mixed operations like:
   "保留标题，但把第二段改得更像吐槽，再加一个投票，整体风格更像数码黑红榜。"

## Core judgement

The project is **not technically obsolete**, but the **interaction architecture is dated**.

- LangGraph is still the right low-level runtime for durable, stateful workflows.
- The old part is the usage style: too much prebuilt ReAct + too many fixed stage nodes.
- Official LangChain v1 guidance recommends `langchain.agents.create_agent` as the standard agent entrypoint, replacing `langgraph.prebuilt.create_react_agent`.

## Target architecture

Move from "production pipeline" to "editor runtime".

### New core loop

`intent -> note_editor -> verifier -> render`

### Responsibilities

#### 1. intent

Only decide:

- create new note
- patch existing note
- refusal
- optional: whether research is needed

It should **not** decide the whole downstream production line.

#### 2. note_editor

This becomes the main brain.

It should:

- inspect current canvas state
- decide whether to search facts
- add/update/remove/reorder blocks
- fill required block payload fields
- set theme/style hints
- stop only when the note is internally consistent

The note editor should operate on a single canonical Note DSL.

#### 3. verifier

A lightweight deterministic validator that checks:

- every block type is supported
- required fields exist for each block
- no placeholder text remains
- renderable HTML can be produced

This should be mostly code, not another creative LLM node.

#### 4. render

Pure renderer. No recovery logic beyond minimal safety guards.

## Canonical state

The system should converge on one canonical editable object:

```python
{
  "page_title": str,
  "theme": {...},
  "blocks": [
    {
      "id": str,
      "component_type": str,
      "props": {...}
    }
  ]
}
```

Recommended direction:

- keep `blocks` as the source of layout order
- keep per-block payload colocated conceptually with the block
- avoid splitting semantic ownership across too many state keys

If backward compatibility is needed, adapters can still project this structure into the current `data_dsl`.

## Tooling model

The main editor should use bounded tools, not many downstream freeform workers.

Recommended tool set:

1. `inspect_note`
2. `search_facts`
3. `append_block`
4. `insert_block`
5. `remove_block`
6. `update_block`
7. `move_block`
8. `set_theme`
9. `finalize_note`

Optional:

10. `inspect_component`
11. `patch_component_fields`

## What should remain deterministic

Do not use LLMs for everything.

Use deterministic code for:

- schema enforcement
- block field completion
- style fallback
- render safety
- unsupported component rejection

Use the model mainly for:

- interpreting user intent
- deciding edits
- summarizing facts into note content
- choosing which blocks to use

## Migration path

### Phase 1

Stabilize the current system.

Already underway:

- entity normalization
- stronger component contracts
- renderer/component alignment
- smoke tests for generation path

### Phase 2

Introduce a `note_editor_node` behind a feature flag.

The new node should absorb:

- global note creation
- global note modification
- mixed structural + content edits

Keep the old graph as fallback during rollout.

### Phase 3

Retire:

- separate `outline -> component_builder -> style` multi-hop orchestration for mainline note generation

Keep only:

- note editor
- verifier
- render

### Phase 4

Migrate deprecated prebuilt agents to LangChain v1 `create_agent` where appropriate.

## Project-specific recommendation

For this repository, the best next refactor is **not** "add more agents".

The best next refactor is:

1. keep LangGraph
2. reduce the number of creative nodes
3. introduce one unified note editor agent
4. make the rest validation and rendering infrastructure

That will make the product feel much closer to "natural language directly edits a note" instead of "a hidden assembly line happens after every message".
