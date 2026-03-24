import { ref } from 'vue'
import type {
  AgentBackends,
  AgentMeta,
  ArtifactSummary,
  ArtifactVersion,
  ChatMessage,
  ConversationCheckpointAction,
  ImageAsset,
  InspectorSummary,
  NoteDocument,
  PlannerOutput,
  PlannerPolicy,
  RevisionPlan,
  RevisionResult,
  RevisionStatus,
  TrendItem,
  TurnTrace,
} from '../types/chat'

export const createSessionWorkspaceState = () => {
  const threadId = ref<string>('')
  const messages = ref<ChatMessage[]>([])
  const previewUrl = ref<string | null>(null)
  const activePanel = ref<string>('main')
  const imageAssets = ref<ImageAsset[]>([])
  const sourceCode = ref<string>('')
  const nodePrompts = ref<Record<string, unknown>>({})
  const noteDocument = ref<NoteDocument>({})
  const artifact = ref<ArtifactSummary | null>(null)
  const artifactVersion = ref<ArtifactVersion | null>(null)
  const revisionPlan = ref<RevisionPlan | null>(null)
  const revisionResult = ref<RevisionResult | null>(null)
  const revisionStatus = ref<RevisionStatus | null>(null)
  const plannerOutput = ref<PlannerOutput>({})
  const plannerPolicy = ref<PlannerPolicy>({})
  const turnTrace = ref<TurnTrace>({})
  const agentBackends = ref<AgentBackends>({})
  const inspectorSummary = ref<InspectorSummary>({})
  const activeCheckpointId = ref<string | null>(null)
  const lastAcceptedSessionSnapshotCheckpointId = ref<string | null>(null)
  const lastAcceptedSessionSnapshotSource = ref<'workspace' | 'turn_end' | 'inspect' | 'recover' | 'init'>('init')
  const pendingBlockingCheckpointAction = ref<ConversationCheckpointAction | null>(null)
  const rollbackUndoTarget = ref<{ checkpointId: string } | null>(null)
  const recentlyChangedBlockDetails = ref<Record<string, { fields: string[]; paragraph_indices?: number[]; item_indices?: number[] }>>({})
  const hotTrends = ref<TrendItem[]>([])
  const agentMeta = ref<AgentMeta>({
    creator_persona: '',
    active_archetype: '',
    intent_route: '',
    retrieved_knowledge: {},
    scenarios: [],
    has_controversy: false,
    needs_disambiguation: false,
    agent_backends: {},
    turn_trace: {},
    inspector_summary: {},
  })

  return {
    threadId,
    messages,
    previewUrl,
    activePanel,
    imageAssets,
    sourceCode,
    nodePrompts,
    noteDocument,
    artifact,
    artifactVersion,
    revisionPlan,
    revisionResult,
    revisionStatus,
    plannerOutput,
    plannerPolicy,
    turnTrace,
    agentBackends,
    inspectorSummary,
    activeCheckpointId,
    lastAcceptedSessionSnapshotCheckpointId,
    lastAcceptedSessionSnapshotSource,
    pendingBlockingCheckpointAction,
    rollbackUndoTarget,
    recentlyChangedBlockDetails,
    hotTrends,
    agentMeta,
  }
}
