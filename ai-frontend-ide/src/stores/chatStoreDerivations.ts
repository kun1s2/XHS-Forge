// Pure derivation helpers for the chat/workspace store.
// Keep protocol picking, NoteDocument summaries, and lightweight text summaries
// here so `useChatStore.ts` can remain the orchestration entrypoint.
import type {
  AgentNarrativeCard,
  AgentBackends,
  ArtifactSummary,
  ArtifactVersion,
  ChangedBlockTrace,
  ConversationCheckpointAction,
  ConversationCheckpointOption,
  ImageAsset,
  InspectorSummary,
  NoteDocument,
  NoteDocumentAsset,
  NoteDocumentBlock,
  PlannerOutput,
  PlannerPolicy,
  RevisionPlan,
  RevisionResult,
  RevisionStatus,
  RetrievedKnowledge,
  ShowcaseProfile,
  TurnTrace,
} from '../types/chat'

type WsData = Record<string, unknown>

const isPlaceholderImageUrl = (value: unknown) => {
  const url = String(value || '').trim().toLowerCase()
  if (!url) return false
  return ['example.com', 'picsum.photos', 'placeholder'].some(token => url.includes(token))
}

const sanitizeNoteDocumentPayload = (doc: NoteDocument | null | undefined): NoteDocument => {
  const safeDoc = (doc || {}) as NoteDocument
  const blocks = getDocumentBlocks(safeDoc).map((block) => {
    const props = { ...((block?.props || {}) as Record<string, unknown>) }
    const rawImageUrls = Array.isArray(props.image_urls) ? props.image_urls : []
    props.image_urls = rawImageUrls.filter((item) => String(item || '').trim() && !isPlaceholderImageUrl(item))
    if (isPlaceholderImageUrl(props.image_url)) {
      delete props.image_url
    }
    const rawAssetRefs = Array.isArray(props.asset_refs) ? props.asset_refs : []
    props.asset_refs = rawAssetRefs.filter((item) => String(item || '').trim() && !isPlaceholderImageUrl(item))
    return {
      ...block,
      props,
    }
  })
  const assets = (Array.isArray(safeDoc.assets) ? safeDoc.assets : []).filter((asset) => !isPlaceholderImageUrl(asset?.url))
  const coverAssetUrl = isPlaceholderImageUrl(safeDoc.ui_state?.cover_asset_url) ? '' : String(safeDoc.ui_state?.cover_asset_url || '')
  return {
    ...safeDoc,
    blocks,
    assets,
    ui_state: {
      ...(safeDoc.ui_state || {}),
      cover_asset_url: coverAssetUrl,
    },
  } as NoteDocument
}

const componentLabelMap: Record<string, string> = {
  CoverSwiper: '封面轮播',
  VersusCard: '对比卡',
  PollBlock: '投票卡',
  RadarChartBlock: '雷达图',
  ProductSpecCard: '参数卡',
  StoryText: '正文区',
  TitleBlock: '标题块',
  LocationBlock: '地点卡',
  WeatherPolaroid: '氛围图卡',
}

const archetypeLabels: Record<string, string> = {
  seeding: '数码购买决策档案',
}

const statusFallbackByNode: Record<string, string> = {
  supervisor_agent: '我正在判断这轮最该先推进哪一步。',
  intent_worker: '我正在理解你这轮到底想把档案往哪个方向推进。',
  retrieval_worker: '我正在补搜这轮最关键的参数、证据或图片。',
  review_worker: '我正在整理待审知识和冲突事实。',
  asset_worker: '我正在补齐这轮最缺的图片和素材。',
  composition_worker: '我正在按你的要求定向修改购买决策档案。',
  critique_worker: '我正在复盘当前成品还有哪些缺口。',
}

export const pickCheckpointId = (data: WsData) => (
  data.checkpoint_id
  ?? data.checkpointId
  ?? data.current_checkpoint_id
  ?? data.currentCheckpointId
  ?? null
)
export const pickOssUrl = (data: WsData) => data.oss_url ?? data.ossUrl ?? null
export const pickNodePrompts = (data: WsData) => data.node_prompts ?? data.nodePrompts ?? {}
export const pickImageAssets = (data: WsData) => data.image_assets ?? data.imageAssets ?? []
export const pickSourceCode = (data: WsData) => data.source_code ?? data.sourceCode ?? data.htmlPreview ?? ''
export const pickNoteDocument = (data: WsData): NoteDocument =>
  sanitizeNoteDocumentPayload((data.note_document ?? data.noteDocument ?? {}) as NoteDocument)
export const pickPlannerOutput = (data: WsData): PlannerOutput => (data.planner_output ?? data.plannerOutput ?? {}) as PlannerOutput
export const pickPlannerPolicy = (data: WsData): PlannerPolicy => (data.planner_policy ?? data.plannerPolicy ?? {}) as PlannerPolicy
export const pickAgentBackends = (data: WsData): AgentBackends => (data.agent_backends ?? data.agentBackends ?? {}) as AgentBackends
export const pickTurnTrace = (data: WsData): TurnTrace => (data.turn_trace ?? data.turnTrace ?? {}) as TurnTrace
export const pickInspectorSummary = (data: WsData): InspectorSummary => (data.inspector_summary ?? data.inspectorSummary ?? {}) as InspectorSummary
export const pickArtifact = (data: WsData): ArtifactSummary | null => ((data.artifact ?? null) as ArtifactSummary | null)
export const pickArtifactVersion = (data: WsData): ArtifactVersion | null => ((data.artifact_version ?? data.artifactVersion ?? null) as ArtifactVersion | null)
export const pickRevisionPlan = (data: WsData): RevisionPlan | null => ((data.revision_plan ?? data.revisionPlan ?? null) as RevisionPlan | null)
export const pickRevisionResult = (data: WsData): RevisionResult | null => ((data.revision_result ?? data.revisionResult ?? null) as RevisionResult | null)
export const pickRevisionStatus = (data: WsData): RevisionStatus | null => ((data.revision_status ?? data.revisionStatus ?? null) as RevisionStatus | null)

export const getRecentlyChangedBlockIds = (trace: TurnTrace | null | undefined, artifactVersion?: ArtifactVersion | null) => {
  const ids = new Set<string>()
  const artifactChangedBlocks = Array.isArray(artifactVersion?.changed_blocks)
    ? (artifactVersion?.changed_blocks as ChangedBlockTrace[])
    : []
  const traceChangedBlocks = Array.isArray(trace?.changed_blocks) ? (trace.changed_blocks as ChangedBlockTrace[]) : []
  const changedBlocks = artifactChangedBlocks.length ? artifactChangedBlocks : traceChangedBlocks

  for (const item of changedBlocks) {
    const id = String(item?.id || '').trim()
    if (id && id !== 'global') ids.add(id)
  }

  const compositionTarget = String(trace?.composition_worker?.target_block_id || trace?.composition_worker?.block_id || '').trim()
  if (compositionTarget && compositionTarget !== 'global') ids.add(compositionTarget)

  const workspaceTarget = String(trace?.workspace_action?.target_block_id || trace?.workspace_action?.block_id || '').trim()
  if (workspaceTarget && workspaceTarget !== 'global') ids.add(workspaceTarget)

  return Array.from(ids)
}

export const getComponentLabel = (componentType: string | null | undefined) =>
  componentLabelMap[String(componentType || '')] || String(componentType || '当前积木')

export const buildAgentPlanCard = (params: {
  query: string
  trace?: TurnTrace | null
  selectedBlockLabel?: string | null
  selectedElementId?: string | null
  messageKind?: string | null
}) : AgentNarrativeCard => {
  const trace = params.trace || {}
  const plan = trace.agent_plan || {}
  const selectedBlockLabel = String(params.selectedBlockLabel || '').trim()
  if (plan.title) {
    const bullets = [
      ...((Array.isArray(plan.steps) ? plan.steps : []).map((item) => String(item || '').trim()).filter(Boolean)),
      ...((Array.isArray(plan.watch_points) ? plan.watch_points : []).map((item) => String(item || '').trim()).filter(Boolean)),
    ]
    return {
      title: String(plan.title),
      summary: String(plan.summary || ''),
      bullets: bullets.slice(0, 4),
    }
  }

  if (params.messageKind === 'critique_action') {
    return {
      title: '我先按你刚才选中的复盘建议继续收口',
      summary: '这次我会沿着最影响完成度的问题继续优化，而不是整页重来。',
      bullets: ['先锁定修改范围', '再按建议定向收紧页面', '最后确认这一轮是否还留有明显缺口'],
    }
  }

  if (selectedBlockLabel && params.selectedElementId && !['无', '无 (全局修改)', 'none', 'global'].includes(params.selectedElementId)) {
    return {
      title: `我会先处理你刚选中的「${selectedBlockLabel}」`,
      summary: '这次优先按局部编辑来做，尽量不扩大到整页重写。',
      bullets: ['先锁定这块当前承担的作用', '只改你提到的内容区域', '改完再把变化明确标出来给你看'],
    }
  }

  const active = String(trace.route?.active_archetype || 'seeding')
  const archetypeLabel = archetypeLabels[active] || '内容页'
  return {
    title: `我先按${archetypeLabel}的思路把这页搭起来`,
    summary: `我理解你这轮想处理的是：${params.query || '当前页面'}。`,
    bullets: [
      '先判断这页最适合哪种结构方向',
      '再补当前最影响质量的事实或素材',
      '最后把结构、语气和重点收成完整页面',
    ],
  }
}

export const buildAgentStatusCard = (params: {
  currentNode?: string | null
  thoughtText?: string | null
}) : AgentNarrativeCard => {
  const summary = String(params.thoughtText || '').trim() || statusFallbackByNode[String(params.currentNode || '')] || '我正在继续推进这一轮。'
  return {
    title: '我正在继续推进这一轮',
    summary,
  }
}

export const buildAgentSummaryCard = (trace: TurnTrace | null | undefined): AgentNarrativeCard | null => {
  const summary = trace?.agent_summary
  if (!summary) return null
  const bullets = [
    ...((Array.isArray(summary.remaining_gaps) ? summary.remaining_gaps : []).map((item) => `还剩：${String(item || '').trim()}`).filter(Boolean)),
    ...((Array.isArray(summary.next_actions) ? summary.next_actions : []).map((item) => `下一步可做：${String(item || '').trim()}`).filter(Boolean)),
  ]
  return {
    title: String(summary.title || '这一轮我已经先帮你推进到这里'),
    summary: String(summary.summary || ''),
    bullets: bullets.slice(0, 4),
  }
}

export const buildCheckpointReceiptCard = (
  action: ConversationCheckpointAction,
  option: ConversationCheckpointOption,
  customNote?: string,
): AgentNarrativeCard => {
  const bullets = [String(option.description || '').trim(), customNote ? `你的补充：${customNote}` : '']
    .filter(Boolean)
  return {
    title: `我会按「${option.label}」继续`,
    summary: String(action.title || action.summary || '我已经接收到这次关键决策。'),
    bullets,
  }
}

export const buildCritiqueReceiptCard = (recipe: {
  label: string
  prompt?: string
  scope?: string
  why_now?: string
  expected_effect?: string
  expected_blocks?: string[]
}): AgentNarrativeCard => ({
  title: `我会按「${recipe.label}」继续处理`,
  summary: String(recipe.why_now || '这次我会按你刚才选中的复盘建议继续收口。'),
  bullets: [
    String(recipe.expected_effect || '').trim(),
    recipe.scope ? `处理范围：${recipe.scope}` : '',
    (recipe.expected_blocks || []).length ? `预计会动到：${(recipe.expected_blocks || []).join(' / ')}` : '',
  ].filter(Boolean),
})

export const buildLocalEditReceiptCard = (params: {
  selectionLabel: string
  prompt: string
}) : AgentNarrativeCard => ({
  title: `这次我先处理「${params.selectionLabel}」`,
  summary: '我会优先按这块的局部目标来改，不顺手扩大到无关区域。',
  bullets: [String(params.prompt || '').trim()],
})

type RecentBlockHighlight = {
  fields: string[]
  paragraph_indices?: number[]
  item_indices?: number[]
}

const stableStringify = (value: unknown) => JSON.stringify(value ?? null)

const valuesDiffer = (before: unknown, after: unknown) => stableStringify(before) !== stableStringify(after)

const collectChangedIndices = (before: unknown[], after: unknown[]) => {
  const maxLength = Math.max(before.length, after.length)
  const changed: number[] = []
  for (let idx = 0; idx < maxLength; idx += 1) {
    if (valuesDiffer(before[idx], after[idx])) changed.push(idx)
  }
  return changed
}

export const buildRecentlyChangedBlockDetails = (
  previousDoc: NoteDocument | null | undefined,
  nextDoc: NoteDocument | null | undefined,
  trace: TurnTrace | null | undefined,
  artifactVersion?: ArtifactVersion | null,
) => {
  const result: Record<string, RecentBlockHighlight> = {}
  const changedIds = getRecentlyChangedBlockIds(trace, artifactVersion)

  for (const blockId of changedIds) {
    const previousBlock = getDocumentBlockById(previousDoc, blockId)
    const nextBlock = getDocumentBlockById(nextDoc, blockId)
    if (!nextBlock) continue

    const previousProps = (previousBlock?.props || {}) as Record<string, unknown>
    const nextProps = (nextBlock?.props || {}) as Record<string, unknown>
    const componentType = String(nextBlock.type || '')
    const meta: RecentBlockHighlight = { fields: [] }

    if (componentType === 'CoverSwiper') {
      if (valuesDiffer(previousProps.title, nextProps.title) || valuesDiffer(previousProps.subtitle, nextProps.subtitle)) meta.fields.push('title')
      if (valuesDiffer(previousProps.description, nextProps.description) || valuesDiffer(previousProps.frame_headlines, nextProps.frame_headlines) || valuesDiffer(previousProps.frame_captions, nextProps.frame_captions)) meta.fields.push('description')
      if (valuesDiffer(previousProps.deck_summary, nextProps.deck_summary)) meta.fields.push('deck_summary')
      if (valuesDiffer(previousProps.image_urls, nextProps.image_urls) || valuesDiffer(previousProps.image_url, nextProps.image_url)) meta.fields.push('images')
    } else if (componentType === 'VersusCard') {
      if (valuesDiffer(previousProps.title, nextProps.title)) meta.fields.push('title')
      if (valuesDiffer(previousProps.pros, nextProps.pros) || valuesDiffer(previousProps.proText, nextProps.proText)) meta.fields.push('pros')
      if (valuesDiffer(previousProps.cons, nextProps.cons) || valuesDiffer(previousProps.conText, nextProps.conText)) meta.fields.push('cons')
      if (valuesDiffer(previousProps.decision_hint, nextProps.decision_hint) || valuesDiffer(previousProps.risk_note, nextProps.risk_note)) meta.fields.push('decision')
    } else if (componentType === 'PollBlock') {
      if (valuesDiffer(previousProps.question, nextProps.question)) meta.fields.push('question')
      if (
        valuesDiffer(previousProps.options, nextProps.options)
        || valuesDiffer(previousProps.option_a, nextProps.option_a)
        || valuesDiffer(previousProps.option_b, nextProps.option_b)
        || valuesDiffer(previousProps.option_c, nextProps.option_c)
        || valuesDiffer(previousProps.option_cards, nextProps.option_cards)
      ) meta.fields.push('options')
    } else if (componentType === 'StoryText') {
      const paragraphIndex = Number(trace?.composition_worker?.paragraph_index)
      if (Number.isInteger(paragraphIndex) && paragraphIndex >= 0 && String(trace?.composition_worker?.target_block_id || '') === blockId) {
        meta.fields.push('paragraphs')
        meta.paragraph_indices = [paragraphIndex]
      } else {
        const previousParagraphs = Array.isArray(previousProps.paragraphs) ? previousProps.paragraphs : []
        const nextParagraphs = Array.isArray(nextProps.paragraphs) ? nextProps.paragraphs : []
        const changedParagraphs = collectChangedIndices(previousParagraphs, nextParagraphs)
        if (changedParagraphs.length) {
          meta.fields.push('paragraphs')
          meta.paragraph_indices = changedParagraphs
        }
      }
    } else if (componentType === 'ProductSpecCard') {
      if (valuesDiffer(previousProps.spec_items, nextProps.spec_items) || valuesDiffer(previousProps.core_features, nextProps.core_features)) {
        meta.fields.push('spec_items')
        const previousItems = Array.isArray(previousProps.spec_items) ? previousProps.spec_items : (Array.isArray(previousProps.core_features) ? previousProps.core_features : [])
        const nextItems = Array.isArray(nextProps.spec_items) ? nextProps.spec_items : (Array.isArray(nextProps.core_features) ? nextProps.core_features : [])
        meta.item_indices = collectChangedIndices(previousItems, nextItems)
      }
      if (valuesDiffer(previousProps.feature_meta, nextProps.feature_meta)) meta.fields.push('feature_meta')
    }

    if (!meta.fields.length) {
      const rawChangedFields = Array.isArray((trace?.changed_blocks || []).find((item) => String(item?.id || '') === blockId)?.changed_fields)
        ? (((trace?.changed_blocks || []).find((item) => String(item?.id || '') === blockId)?.changed_fields || []) as string[])
        : []
      meta.fields = rawChangedFields.length ? rawChangedFields.map((field) => String(field)) : ['content']
    }

    result[blockId] = meta
  }

  return result
}

export const dedupeImageAssets = (assets: ImageAsset[]) => {
  const deduped = new Map<string, ImageAsset>()
  for (const asset of assets || []) {
    if (!asset?.url) continue
    const existing = deduped.get(asset.url)
    deduped.set(asset.url, {
      ...(existing || {}),
      ...asset,
      desc: asset.desc || existing?.desc || '素材图',
      role: existing?.role === 'cover' || asset.role === 'cover'
        ? 'cover'
        : (asset.role || existing?.role),
      used_by_blocks: Array.from(
        new Set([
          ...((existing?.used_by_blocks || []) as string[]),
          ...((asset.used_by_blocks || []) as string[]),
        ]),
      ),
    })
  }
  return Array.from(deduped.values())
}

export const getDocumentBlocks = (doc?: NoteDocument | null) =>
  (Array.isArray(doc?.blocks) ? doc?.blocks : []) as NoteDocumentBlock[]

export const getDocumentPayloadById = (doc: NoteDocument | null | undefined, blockId: string) => {
  const block = getDocumentBlocks(doc).find(item => String(item?.id || '') === blockId)
  return (block?.props || {}) as Record<string, unknown>
}

export const getDocumentBlockById = (doc: NoteDocument | null | undefined, blockId: string) =>
  getDocumentBlocks(doc).find(item => String(item?.id || '') === blockId) || null

export const getDocumentCoverUrl = (doc?: NoteDocument | null) => {
  const preferredCoverUrl = String(doc?.ui_state?.cover_asset_url || '')
  if (preferredCoverUrl) return preferredCoverUrl
  const coverBlock = getDocumentBlocks(doc).find(block => String(block?.type || '') === 'CoverSwiper')
  if (!coverBlock?.id) return ''
  const payload = (coverBlock?.props || {}) as { image_urls?: string[]; image_url?: string }
  return String(payload?.image_urls?.[0] || payload?.image_url || '')
}

export const getPreferredBlockById = (
  doc: NoteDocument | null | undefined,
  blockId: string,
) => {
  const docBlock = getDocumentBlockById(doc, blockId)
  if (docBlock) {
    return {
      ...docBlock,
      component_type: docBlock.type,
    } as Record<string, unknown>
  }
  return null
}

export const getPreferredPayloadById = (
  doc: NoteDocument | null | undefined,
  blockId: string,
) => {
  const docPayload = getDocumentPayloadById(doc, blockId)
  if (Object.keys(docPayload).length > 0) return docPayload
  return {}
}

export const getPreferredScenarioTags = (
  doc: NoteDocument | null | undefined,
  output: PlannerOutput | null | undefined,
  policy: PlannerPolicy | null | undefined,
) => {
  const docTags = doc?.document_meta?.scenarios
  if (Array.isArray(docTags) && docTags.length) return docTags as string[]
  const plannerScores = output?.scenario_scores || policy?.scenario_scores
  if (plannerScores && typeof plannerScores === 'object') {
    const inferred = Object.entries(plannerScores)
      .filter(([, score]) => Number(score) > 0)
      .sort((a, b) => Number(b[1]) - Number(a[1]))
      .map(([name]) => String(name))
    if (inferred.length) return inferred
  }
  return ['seeding']
}

export const getPreferredPatchTracks = (
  doc: NoteDocument | null | undefined,
) => (doc?.ui_state?.patch_tracks || {}) as Record<string, any[]>

export const getPreferredCoverUrl = (
  doc: NoteDocument | null | undefined,
  assets: ImageAsset[] | null | undefined,
) => {
  const docCover = getDocumentCoverUrl(doc)
  if (docCover) return docCover
  const assetCover = (assets || []).find(asset => asset?.role === 'cover')
  if (assetCover?.url) return assetCover.url
  return null
}

const pickCoverUrlFromAssets = (assets: Array<Record<string, any>> | null | undefined) =>
  String((assets || []).find((asset: Record<string, any>) => asset?.role === 'cover')?.url || '')

export const hasDocumentBlockType = (doc: NoteDocument | null | undefined, componentType: string) =>
  getDocumentBlocks(doc).some(block => String(block?.type || '') === componentType)

export const buildRenderablePageDataFromDocument = (doc?: NoteDocument | null) => {
  const blocks = getDocumentBlocks(doc)
  if (!blocks.length) return {} as Record<string, any>
  const mappedBlocks = blocks.map((block: Record<string, any>) => ({
    id: block.id,
    component_type: block.type,
    label: block.label,
    semantic_role: block.semantic_role,
    content_brief: block.content_brief || '',
    props: block.props || {},
    style: block.style || {},
    editable_targets: Array.isArray(block.editable_targets) ? block.editable_targets : [],
    fact_bindings: Array.isArray(block.fact_bindings) ? block.fact_bindings : [],
    asset_refs: Array.isArray(block.asset_refs) ? block.asset_refs : [],
  }))
  const payloadMap = Object.fromEntries(blocks.map((block: Record<string, any>) => [block.id, block.props || {}]))
  return {
    page_title: doc?.document_meta?.title || 'XHS-Forge Note',
    page_theme: doc?.theme?.page_theme || {},
    archetype_tags: doc?.document_meta?.scenarios || [],
    blocks: mappedBlocks,
    ...payloadMap,
  } as Record<string, any>
}

const buildComparablePageFromDocument = (doc?: NoteDocument | null) => {
  const blocks = getDocumentBlocks(doc)
  if (!blocks.length) return {} as Record<string, any>
  const payloadMap = Object.fromEntries(blocks.map((block: Record<string, any>) => [block.id, block.props || {}]))
  return {
    page_title: doc?.document_meta?.title || 'XHS-Forge Note',
    page_theme: doc?.theme?.page_theme || {},
    archetype_tags: doc?.document_meta?.scenarios || [],
    blocks: blocks.map((block: Record<string, any>) => ({
      id: block.id,
      component_type: block.type,
      content_brief: block.content_brief || '',
    })),
    ...payloadMap,
  } as Record<string, any>
}

export const resolveComparablePage = (doc: NoteDocument | null | undefined) => {
  const fromDoc = buildComparablePageFromDocument(doc)
  if (Object.keys(fromDoc).length > 0) return fromDoc
  return {} as Record<string, any>
}

export const buildRenderStyleDataFromDocument = (doc?: NoteDocument | null) => {
  const blocks = getDocumentBlocks(doc)
  if (!blocks.length) return {} as Record<string, any>
  const blockStyles = Object.fromEntries(blocks.map((block: Record<string, any>) => [block.id, block.style || {}]))
  return {
    global_vars: doc?.theme?.global_vars || {},
    ...blockStyles,
  } as Record<string, any>
}

export const getPreferredRenderPageData = (doc: NoteDocument | null | undefined) => {
  const fromDoc = buildRenderablePageDataFromDocument(doc)
  if (Object.keys(fromDoc).length > 0) return fromDoc
  return {} as Record<string, any>
}

export const getPreferredRenderStyleData = (doc: NoteDocument | null | undefined) => {
  const fromDoc = buildRenderStyleDataFromDocument(doc)
  if (Object.keys(fromDoc).length > 0) return fromDoc
  return {} as Record<string, any>
}

const getThemeSignature = (page?: Record<string, any> | null) =>
  JSON.stringify((page?.page_theme || {}) as Record<string, any>)

const pickContentSignature = (payload: Record<string, any> | null | undefined) => {
  if (!payload) return ''
  if (Array.isArray(payload.paragraphs)) return JSON.stringify(payload.paragraphs)
  if (typeof payload.question === 'string') return `${payload.question}|${payload.option_a || ''}|${payload.option_b || ''}`
  if (payload.pros || payload.cons) {
    return JSON.stringify({
      pros: payload.pros || {},
      cons: payload.cons || {},
      decision_hint: payload.decision_hint || '',
    })
  }
  if (typeof payload.proText === 'string' || typeof payload.conText === 'string') return `${payload.proText || ''}|${payload.conText || ''}`
  if (typeof payload.title === 'string') return payload.title
  return ''
}

export const getPendingFactConflictCount = (knowledge: RetrievedKnowledge | null | undefined) =>
  Array.isArray(knowledge?.fact_conflicts) ? knowledge.fact_conflicts.length : 0

const appendPendingFactHint = (text: string, knowledge: RetrievedKnowledge | null | undefined) => {
  const pendingCount = getPendingFactConflictCount(knowledge)
  if (!pendingCount) return text
  return `${text} 当前有 ${pendingCount} 个待确认事实，系统已自动采用保守表达，可以继续在聊天区确认或修正。`
}

export const buildAssistantResultText = (
  page: Record<string, any>,
  previousPage?: Record<string, any> | null,
  userText = '',
  knowledge?: RetrievedKnowledge | null,
) => {
  const blocks = Array.isArray(page?.blocks) ? page.blocks : []
  if (!blocks.length) return '页面已更新，可以继续查看和编辑。'

  const currentTypes = blocks
    .map((block: Record<string, any>) => String(block?.component_type || ''))
    .filter(Boolean)
  const currentLabels = currentTypes
    .map(type => componentLabelMap[type] || type)
    .filter(Boolean)

  const previousBlocks = Array.isArray(previousPage?.blocks) ? previousPage.blocks : []
  const previousTypes = previousBlocks
    .map((block: Record<string, any>) => String(block?.component_type || ''))
    .filter(Boolean)

  const currentIds = blocks.map(block => String(block?.id || '')).filter(Boolean)
  const previousIds = previousBlocks.map(block => String(block?.id || '')).filter(Boolean)
  const addedIds = currentIds.filter(id => !previousIds.includes(id))
  const removedIds = previousIds.filter(id => !currentIds.includes(id))

  for (const id of currentIds) {
    if (!previousIds.includes(id)) continue
    const previousType = String(previousBlocks.find((item: Record<string, any>) => item?.id === id)?.component_type || '')
    const currentType = String(blocks.find((item: Record<string, any>) => item?.id === id)?.component_type || '')
    if (previousType && currentType && previousType !== currentType) {
      return appendPendingFactHint(`页面已更新，已将${componentLabelMap[previousType] || previousType}替换为${componentLabelMap[currentType] || currentType}。`, knowledge)
    }
  }

  const previousCoverUrl = String(previousPage?.ui_state?.cover_asset_url || pickCoverUrlFromAssets(previousPage?.assets as Array<Record<string, any>> | undefined)
    || (previousPage?.blocks || []).find((block: Record<string, any>) => block?.component_type === 'CoverSwiper')?.props?.image_urls?.[0]
    || (previousPage?.blocks || []).find((block: Record<string, any>) => block?.component_type === 'CoverSwiper')?.props?.image_url || '')
  const currentCoverUrl = String(page?.ui_state?.cover_asset_url || pickCoverUrlFromAssets(page?.assets as Array<Record<string, any>> | undefined)
    || (page?.blocks || []).find((block: Record<string, any>) => block?.component_type === 'CoverSwiper')?.props?.image_urls?.[0]
    || (page?.blocks || []).find((block: Record<string, any>) => block?.component_type === 'CoverSwiper')?.props?.image_url || '')
  if (currentCoverUrl && currentCoverUrl !== previousCoverUrl) {
    return appendPendingFactHint(
      previousCoverUrl
        ? `页面已更新，封面图已替换，当前共 ${blocks.length} 个区块。`
        : `页面已更新，已添加封面图，当前共 ${blocks.length} 个区块。`,
      knowledge,
    )
  }

  if (removedIds.length) {
    const removedType = String(previousBlocks.find((item: Record<string, any>) => item?.id === removedIds[0])?.component_type || '')
    const stillHasSameType = removedType ? currentTypes.includes(removedType) : false
    if (!stillHasSameType) {
      return appendPendingFactHint(`页面已更新，删除了${componentLabelMap[removedType] || removedType || '一个区块'}，当前共 ${blocks.length} 个区块。`, knowledge)
    }
  }

  if (getThemeSignature(page) !== getThemeSignature(previousPage)) {
    if (/(灰蓝|主题|风格|配色|色调)/.test(userText)) {
      return appendPendingFactHint(`页面已更新，已按你的要求切换页面主题，当前共 ${blocks.length} 个区块。`, knowledge)
    }
    return appendPendingFactHint(`页面已更新，已切换页面主题，当前共 ${blocks.length} 个区块。`, knowledge)
  }

  for (const id of currentIds) {
    if (!previousIds.includes(id)) continue
    const prevPayload = previousBlocks.find((item: Record<string, any>) => item?.id === id)?.props as Record<string, any> | undefined
    const nextPayload = blocks.find((item: Record<string, any>) => item?.id === id)?.props as Record<string, any> | undefined
    const prevSig = pickContentSignature(prevPayload)
    const nextSig = pickContentSignature(nextPayload)
    if (prevSig && nextSig && prevSig !== nextSig) {
      const blockType = String(blocks.find((item: Record<string, any>) => item?.id === id)?.component_type || '')
      if (/(毒舌|尖锐|重写|润色|改写|文案)/.test(userText)) {
        return appendPendingFactHint(`页面已更新，已按你的要求调整${componentLabelMap[blockType] || blockType || '区块'}的文案内容。`, knowledge)
      }
      return appendPendingFactHint(`页面已更新，已调整${componentLabelMap[blockType] || blockType || '区块'}的文案内容。`, knowledge)
    }
  }

  const addedType = addedIds.length
    ? String(blocks.find((item: Record<string, any>) => item?.id === addedIds[0])?.component_type || '')
    : currentTypes.find(type => !previousTypes.includes(type))
  if (addedType) {
    return appendPendingFactHint(`页面已更新，新增了${componentLabelMap[addedType] || addedType}，当前共 ${blocks.length} 个区块。`, knowledge)
  }

  const firstTwo = currentLabels.slice(0, 2).join('、')
  if (firstTwo) {
    return appendPendingFactHint(`页面已更新，当前共 ${blocks.length} 个区块，包含 ${firstTwo}。`, knowledge)
  }

  return appendPendingFactHint(`页面已更新，当前共 ${blocks.length} 个区块。`, knowledge)
}

export const getConfiguredApiBase = () => {
  const configured = import.meta.env.VITE_API_BASE_URL
  if (configured && typeof configured === 'string') {
    return configured.replace(/\/$/, '')
  }
  if (import.meta.env.DEV) {
    return 'http://127.0.0.1:8000'
  }
  return ''
}

export const toWsBase = (httpBase: string) => {
  if (!httpBase) return ''
  if (httpBase.startsWith('https://')) return `wss://${httpBase.slice('https://'.length)}`
  if (httpBase.startsWith('http://')) return `ws://${httpBase.slice('http://'.length)}`
  return httpBase
}

export const normalizeShowcaseProfile = (profile: Record<string, any>): ShowcaseProfile => ({
  id: profile.id,
  scenarioId: profile.scenario_id ?? profile.scenarioId ?? '',
  title: profile.title ?? '',
  persona: profile.persona ?? '硬核数码博主',
  whyThisMatters: profile.why_this_matters ?? profile.whyThisMatters ?? '',
  highlightFeatures: profile.highlight_features ?? profile.highlightFeatures ?? [],
  talkingPoints: profile.talking_points ?? profile.talkingPoints ?? [],
  demoScript: profile.demo_script ?? profile.demoScript ?? [],
  starterPrompt: profile.starter_prompt ?? profile.starterPrompt ?? '',
  editPrompt: profile.edit_prompt ?? profile.editPrompt ?? '',
  themePrompt: profile.theme_prompt ?? profile.themePrompt ?? '',
  branchPrompt: profile.branch_prompt ?? profile.branchPrompt ?? ''
})
