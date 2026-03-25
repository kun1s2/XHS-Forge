import { ref } from 'vue'
import type {
  ImageAsset,
  PreviewInteractionMode,
  WorkspaceViewMode,
} from '../types/chat'

export const createTransientUiState = () => {
  const isSidebarOpen = ref(true)
  const wsStatus = ref<'disconnected' | 'connecting' | 'connected'>('disconnected')
  const activeWorker = ref<string>('')
  const thoughtText = ref<string>('')
  const nodeStreamOutput = ref<string>('')
  const workspaceMode = ref<WorkspaceViewMode>('session_preview')
  const previewInteractionMode = ref<PreviewInteractionMode>('browse')
  const selectedComponentId = ref<string | null>(null)
  const selectedParagraphIndex = ref<number | null>(null)
  const composerDraft = ref<string>('')
  const pendingUploadUrls = ref<string[]>([])
  const searchedAssets = ref<ImageAsset[]>([])
  const assetSearchLoading = ref(false)
  const factConfirmingField = ref<string | null>(null)
  const hoveredComponentId = ref<string | null>(null)
  const submittingCheckpointId = ref<string | null>(null)

  return {
    isSidebarOpen,
    wsStatus,
    activeWorker,
    thoughtText,
    nodeStreamOutput,
    workspaceMode,
    previewInteractionMode,
    selectedComponentId,
    selectedParagraphIndex,
    composerDraft,
    pendingUploadUrls,
    searchedAssets,
    assetSearchLoading,
    factConfirmingField,
    hoveredComponentId,
    submittingCheckpointId,
  }
}
