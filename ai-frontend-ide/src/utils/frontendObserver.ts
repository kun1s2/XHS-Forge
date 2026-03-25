import { watch } from 'vue'
import { storeToRefs } from 'pinia'
import type { Pinia } from 'pinia'
import { useChatStore } from '../stores/useChatStore'
import { reportFrontendObservation } from './frontendReport'
import type { NoteDocument } from '../types/chat'

export const setupFrontendObserver = (pinia: Pinia) => {
  const chatStore = useChatStore(pinia)
  const {
    threadId,
    activeWorker,
    selectedComponentId,
    hasRenderableDocument,
    renderPageData,
    noteDocument,
    sourceCode,
    workerPrompts,
    previewUrl,
  } = storeToRefs(chatStore)

  const sendHealthSnapshot = (reason: string) => {
    const page = (renderPageData.value || {}) as Record<string, unknown>
    const doc = ((noteDocument.value || {}) as NoteDocument)
    const blocks = Array.isArray(page.blocks) ? page.blocks.length : 0
    const docBlocks = Array.isArray(doc.blocks) ? doc.blocks.length : 0
    void reportFrontendObservation({
      thread_id: threadId.value || '',
      event_type: 'health_snapshot',
      message: reason,
      payload: {
        active_worker: activeWorker.value || '',
        selected_component_id: selectedComponentId.value || '',
        has_renderable_document: Boolean(hasRenderableDocument.value),
        render_blocks: blocks,
        note_document_blocks: docBlocks,
        worker_prompt_count: Object.keys((workerPrompts.value || {}) as Record<string, unknown>).length,
        has_source_code: Boolean(sourceCode.value),
        has_preview_url: Boolean(previewUrl.value),
      },
    })
  }

  let renderAnomalyTimer: number | null = null
  const getRenderBlockCount = () => {
    const page = (renderPageData.value || {}) as Record<string, unknown>
    return Array.isArray(page.blocks) ? page.blocks.length : 0
  }
  const scheduleRenderAnomalyCheck = () => {
    if (renderAnomalyTimer !== null) {
      window.clearTimeout(renderAnomalyTimer)
    }
    renderAnomalyTimer = window.setTimeout(() => {
      if ((previewUrl.value || sourceCode.value) && !hasRenderableDocument.value) {
        void reportFrontendObservation({
          thread_id: threadId.value || '',
          event_type: 'render_output_missing_in_ui',
          message: '后端已返回 preview/sourceCode，但前端仍不可渲染',
          payload: {
            active_worker: activeWorker.value || '',
            selected_component_id: selectedComponentId.value || '',
            render_blocks: getRenderBlockCount(),
            note_document_blocks: Array.isArray(((noteDocument.value as NoteDocument | undefined) || {})?.blocks)
              ? (((noteDocument.value as NoteDocument | undefined) || {})?.blocks?.length || 0)
              : 0,
            has_source_code: Boolean(sourceCode.value),
            has_preview_url: Boolean(previewUrl.value),
            worker_prompt_count: Object.keys((workerPrompts.value || {}) as Record<string, unknown>).length,
          },
        })
      }
    }, 1200)
  }

  watch(
    [threadId, activeWorker, selectedComponentId, hasRenderableDocument, previewUrl, sourceCode],
    () => {
      sendHealthSnapshot('state_changed')
      scheduleRenderAnomalyCheck()
    },
    { immediate: true },
  )

  window.addEventListener('error', (event) => {
    const filename = String(event.filename || '')
    if (filename.startsWith('chrome-extension://') || filename.startsWith('moz-extension://')) {
      return
    }
    void reportFrontendObservation({
      thread_id: threadId.value || '',
      event_type: 'window_error',
      message: String(event.message || '未知前端错误'),
      payload: {
        filename,
        lineno: event.lineno || 0,
        colno: event.colno || 0,
        active_worker: activeWorker.value || '',
        selected_component_id: selectedComponentId.value || '',
      },
    })
  })

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event.reason instanceof Error ? event.reason.message : String(event.reason || 'Promise rejected')
    void reportFrontendObservation({
      thread_id: threadId.value || '',
      event_type: 'unhandled_rejection',
      message: reason,
      payload: {
        active_worker: activeWorker.value || '',
        selected_component_id: selectedComponentId.value || '',
      },
    })
  })
}
