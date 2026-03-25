import { expect, test } from '@playwright/test'

const CREATE_PROMPT =
  '我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。'
const IMAGE_PROMPT = '这份档案图片太少了，补几张更像真机质感的图片。'
const SALES_BLOCK_PROMPT = '在现有档案后面补一个新块，专门讲华为 Mate 60 的销量。'
const HISTORY_BLOCK_PROMPT = '继续补一个新块，专门讲华为 Mate 60 的发展史。'
const AUDIENCE_BLOCK_PROMPT = '再补一个新块，专门讲华为 Mate 60 适合什么人群。'
const REVIEW_PROMPT = '帮我再检查一遍，看看这份档案最值得优化的一点是什么。'

type WorkspaceSnapshot = Record<string, any>
let lastKnownThreadId = ''

async function capture(page: import('@playwright/test').Page, name: string, testInfo: import('@playwright/test').TestInfo) {
  const pagePath = testInfo.outputPath(`${name}-page.png`)
  await page.screenshot({ path: pagePath, fullPage: true })
  await testInfo.attach(`${name}-page`, {
    path: pagePath,
    contentType: 'image/png',
  })

  const preview = page.getByTestId('preview-shell')
  const previewContainer = page.getByTestId('session-preview-container')
  const knowledgeWorkbench = page.getByTestId('session-knowledge-workbench')

  let target = preview
  if (await preview.isVisible().catch(() => false)) {
    target = preview
  } else if (await previewContainer.isVisible().catch(() => false)) {
    target = previewContainer
  } else {
    await expect(knowledgeWorkbench).toBeVisible()
    target = knowledgeWorkbench
  }

  const focusPath = testInfo.outputPath(`${name}-focus.png`)
  await target.screenshot({ path: focusPath })
  await testInfo.attach(`${name}-focus`, {
    path: focusPath,
    contentType: 'image/png',
  })
}

async function sendComposer(page: import('@playwright/test').Page, content: string) {
  const composer = page.getByTestId('composer-input')
  await expect(composer).toBeVisible()
  await composer.fill(content)
  await page.getByTestId('composer-send').click()
}

async function waitForRenderablePreview(page: import('@playwright/test').Page) {
  const preview = page.getByTestId('preview-shell')
  await expect(preview).toBeVisible({ timeout: 120_000 })
  await expect(preview).not.toContainText('Waiting for Agent to generate UI structure...', { timeout: 120_000 })
  return preview
}

async function getActiveThreadId(page: import('@playwright/test').Page) {
  const immediateThreadId = await page.evaluate(() => {
    const fromStorage = window.localStorage.getItem('xhs_forge_active_thread') || ''
    if (fromStorage) return fromStorage
    try {
      return new URL(window.location.href).searchParams.get('thread') || ''
    } catch {
      return ''
    }
  })
  if (immediateThreadId) {
    lastKnownThreadId = immediateThreadId
    return immediateThreadId
  }
  if (lastKnownThreadId) return lastKnownThreadId
  await expect
    .poll(async () => {
      return await page.evaluate(() => {
        const fromStorage = window.localStorage.getItem('xhs_forge_active_thread') || ''
        if (fromStorage) return fromStorage
        try {
          const fromQuery = new URL(window.location.href).searchParams.get('thread') || ''
          if (fromQuery) return fromQuery
        } catch {}
        return ''
      })
    }, { timeout: 30_000 })
    .not.toBe('')
  const nextThreadId = await page.evaluate(() => {
    const fromStorage = window.localStorage.getItem('xhs_forge_active_thread') || ''
    if (fromStorage) return fromStorage
    try {
      return new URL(window.location.href).searchParams.get('thread') || ''
    } catch {
      return ''
    }
  })
  if (nextThreadId) lastKnownThreadId = nextThreadId
  return nextThreadId || lastKnownThreadId
}

async function fetchWorkspaceSnapshot(page: import('@playwright/test').Page, threadId: string): Promise<WorkspaceSnapshot> {
  const response = await page.request.get(`http://127.0.0.1:8000/workspace/${threadId}`)
  expect(response.ok()).toBeTruthy()
  return await response.json()
}

function collectBlockTexts(snapshot: WorkspaceSnapshot): string[] {
  const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
  return blocks.map((block) => {
    const parts: string[] = []
    const visit = (value: unknown) => {
      if (typeof value === 'string') {
        parts.push(value)
        return
      }
      if (Array.isArray(value)) {
        value.forEach(visit)
        return
      }
      if (value && typeof value === 'object') {
        Object.values(value as Record<string, unknown>).forEach(visit)
      }
    }
    visit(block.content_brief)
    visit(block.props || {})
    return parts.join(' ')
  })
}

async function waitForWorkspaceBlock(
  page: import('@playwright/test').Page,
  options: {
    minBlockCount: number
    keyword: RegExp
    timeoutMs?: number
  },
) {
  const { minBlockCount, keyword, timeoutMs = 180_000 } = options
  await expect
    .poll(async () => {
      const threadId = await getActiveThreadId(page)
      const snapshot = await fetchWorkspaceSnapshot(page, threadId)
      const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
      const blockTexts = collectBlockTexts(snapshot)
      return {
        threadId,
        count: blocks.length,
        hasKeyword: blockTexts.some((text) => keyword.test(text)),
      }
    }, { timeout: timeoutMs, intervals: [1500, 2000, 2500] })
    .toMatchObject({
      count: expect.any(Number),
      hasKeyword: true,
    })

  const threadId = await getActiveThreadId(page)
  const snapshot = await fetchWorkspaceSnapshot(page, threadId)
  const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
  expect(blocks.length).toBeGreaterThanOrEqual(minBlockCount)
  return snapshot
}

async function expectPurchaseDecisionQuality(
  preview: import('@playwright/test').Locator,
  options: {
    requireImages?: boolean
    requireExpandedBlocks?: boolean
  } = {},
) {
  const { requireImages = false, requireExpandedBlocks = false } = options
  await expect(preview).toContainText(/mate 60|华为 mate 60/i, { timeout: 120_000 })
  await expect(preview).not.toContainText(/Find X8 Ultra|iPhone 15|小米 14/i)
  await expect(preview).not.toContainText('TitleBlock')
  await expect(preview).not.toContainText('StoryText')
  await expect(preview).not.toContainText('等待封面图片接入...')
  await expect(preview).toContainText(/值不值得买|购买结论|关键参数|参数卡|已确认/, { timeout: 120_000 })
  await expect(preview).toContainText(/优缺点|优缺点速览|路线对比|怎么选|主推路线|保守路线/, { timeout: 120_000 })
  await expect(preview).toContainText(/代价|不适合|边界|妥协|短板/, { timeout: 120_000 })
  if (requireExpandedBlocks) {
    await expect(preview).toContainText(/销量/, { timeout: 120_000 })
    await expect(preview).toContainText(/发展史/, { timeout: 120_000 })
    await expect(preview).toContainText(/适合什么人群|适合人群/, { timeout: 120_000 })
  }
  if (requireImages) {
    await expect(preview.locator('img').first()).toBeVisible({ timeout: 120_000 })
  }
}

async function resolveCheckpointLoop(
  page: import('@playwright/test').Page,
  testInfo: import('@playwright/test').TestInfo,
  options: {
    label: string
    until: () => Promise<boolean>
    maxRounds?: number
    timeoutMs?: number
  },
) {
  const { label, until, maxRounds = 6, timeoutMs = 180_000 } = options
  const checkpointCard = page
    .getByTestId('checkpoint-card')
    .filter({ has: page.locator('[data-testid^="checkpoint-option-"]') })
    .last()
  let resolvedRounds = 0
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    if (await until()) return
    const visible = await checkpointCard.isVisible().catch(() => false)
    if (!visible) {
      await page.waitForTimeout(2000)
      if (await until()) return
      continue
    }
    resolvedRounds += 1
    if (resolvedRounds > maxRounds) {
      throw new Error(`Checkpoint loop exceeded ${maxRounds} rounds for ${label}`)
    }
    await capture(page, `${label}-checkpoint-${resolvedRounds}`, testInfo)
    const optionsLocator = checkpointCard.locator('[data-testid^="checkpoint-option-"]')
    await expect(optionsLocator.first()).toBeVisible({ timeout: 30_000 })
    await optionsLocator.first().click()
    await page.waitForTimeout(1500)
  }
  throw new Error(`Timed out waiting for ${label} after ${timeoutMs}ms`)
}

test.describe('digital purchase real advanced browser e2e', () => {
  test('runs a longer multi-step refinement workflow against the real backend', async ({ page }, testInfo) => {
    test.setTimeout(420_000)
    console.log('[ADV E2E] goto /')
    await page.goto('/')
    await expect(page.getByTestId('composer-input')).toBeVisible({ timeout: 30_000 })

    const newProject = page.getByRole('button', { name: /\+ New Project/i })
    if (await newProject.isVisible().catch(() => false)) {
      console.log('[ADV E2E] click new project')
      await newProject.click()
    }
    await expect(page.getByText('已连接')).toBeVisible({ timeout: 30_000 })

    console.log('[ADV E2E] create prompt')
    await sendComposer(page, CREATE_PROMPT)

    const preview = page.getByTestId('preview-shell')
    await resolveCheckpointLoop(page, testInfo, {
      label: '01-advanced-create',
      until: async () => {
        const threadId = await getActiveThreadId(page)
        const snapshot = await fetchWorkspaceSnapshot(page, threadId)
        const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
        const blockTexts = collectBlockTexts(snapshot)
        return (
          blocks.length >= 5
          && blockTexts.some((text) => /Mate 60|华为 Mate 60/i.test(text))
          && blockTexts.some((text) => /优缺点|路线|对比|风险|代价|边界/i.test(text))
        )
      },
      timeoutMs: 240_000,
    })
    console.log('[ADV E2E] create resolved')
    await waitForRenderablePreview(page)
    await expectPurchaseDecisionQuality(preview)
    await capture(page, '02-advanced-created-artifact', testInfo)

    console.log('[ADV E2E] image prompt')
    await sendComposer(page, IMAGE_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '03-advanced-asset',
      until: async () => {
        const threadId = await getActiveThreadId(page)
        const snapshot = await fetchWorkspaceSnapshot(page, threadId)
        const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
        const cover = blocks.find((block) => String(block.type || block.block_type || '') === 'CoverSwiper') || null
        const coverImages = Array.isArray(cover?.props?.image_urls) ? cover?.props?.image_urls || [] : []
        return coverImages.length > 0
      },
      maxRounds: 4,
      timeoutMs: 240_000,
    })
    console.log('[ADV E2E] asset resolved')
    await expect(preview.locator('img').first()).toBeVisible({ timeout: 120_000 })
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '03-advanced-asset-enriched', testInfo)

    const selectionToggle = page.getByTestId('preview-selection-toggle')
    const selectionToggleText = (await selectionToggle.textContent().catch(() => '')) || ''
    if (!selectionToggleText.includes('退出选择模式')) {
      await selectionToggle.click()
    }
    await expect(selectionToggle).toContainText('退出选择模式')
    const preferredBlock =
      (await preview.locator('[data-comp-id="story_2"]').count()) > 0
        ? preview.locator('[data-comp-id="story_2"]').first()
        : preview.locator('[data-comp-id="story_1"]').first()
    await expect(preferredBlock).toBeVisible({ timeout: 30_000 })
    await preferredBlock.getByRole('button', { name: '选择当前积木' }).click({ force: true })

    console.log('[ADV E2E] local edit prompt')
    await sendComposer(page, '把这个对比块改得更直接一点，更像给朋友的购买建议。')
    await expect(preview).toContainText(/朋友|更直接|值得/, { timeout: 120_000 })
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '04-advanced-local-edit', testInfo)

    const toggleAfterEdit = page.getByTestId('preview-selection-toggle')
    if (((await toggleAfterEdit.textContent().catch(() => '')) || '').includes('退出选择模式')) {
      await toggleAfterEdit.click()
    }

    let blockCountBeforeExpansion = await preview.locator('[data-comp-id]').count()

    console.log('[ADV E2E] sales block prompt')
    await sendComposer(page, SALES_BLOCK_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '05-advanced-sales-block',
      until: async () => {
        const threadId = await getActiveThreadId(page)
        const snapshot = await fetchWorkspaceSnapshot(page, threadId)
        const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
        const blockTexts = collectBlockTexts(snapshot)
        return blocks.length > blockCountBeforeExpansion && blockTexts.some((text) => /销量/.test(text))
      },
      maxRounds: 4,
      timeoutMs: 240_000,
    })
    const salesSnapshot = await waitForWorkspaceBlock(page, {
      minBlockCount: blockCountBeforeExpansion + 1,
      keyword: /销量/,
      timeoutMs: 240_000,
    })
    blockCountBeforeExpansion = ((salesSnapshot.note_document || {}).blocks || []).length
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '05-advanced-sales-block', testInfo)

    console.log('[ADV E2E] history block prompt')
    await sendComposer(page, HISTORY_BLOCK_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '06-advanced-history-block',
      until: async () => {
        const threadId = await getActiveThreadId(page)
        const snapshot = await fetchWorkspaceSnapshot(page, threadId)
        const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
        const blockTexts = collectBlockTexts(snapshot)
        return blocks.length > blockCountBeforeExpansion && blockTexts.some((text) => /发展史/.test(text))
      },
      maxRounds: 4,
      timeoutMs: 240_000,
    })
    const historySnapshot = await waitForWorkspaceBlock(page, {
      minBlockCount: blockCountBeforeExpansion + 1,
      keyword: /发展史/,
      timeoutMs: 240_000,
    })
    blockCountBeforeExpansion = ((historySnapshot.note_document || {}).blocks || []).length
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '06-advanced-history-block', testInfo)

    console.log('[ADV E2E] audience block prompt')
    await sendComposer(page, AUDIENCE_BLOCK_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '07-advanced-audience-block',
      until: async () => {
        const threadId = await getActiveThreadId(page)
        const snapshot = await fetchWorkspaceSnapshot(page, threadId)
        const blocks = ((snapshot.note_document || {}).blocks || []) as Array<Record<string, any>>
        const blockTexts = collectBlockTexts(snapshot)
        return blocks.length > blockCountBeforeExpansion && blockTexts.some((text) => /适合什么人群|适合人群/.test(text))
      },
      maxRounds: 4,
      timeoutMs: 240_000,
    })
    await waitForWorkspaceBlock(page, {
      minBlockCount: blockCountBeforeExpansion + 1,
      keyword: /适合什么人群|适合人群/,
      timeoutMs: 240_000,
    })
    console.log('[ADV E2E] expanded blocks resolved')
    await expectPurchaseDecisionQuality(preview, { requireImages: true, requireExpandedBlocks: true })
    await capture(page, '07-advanced-audience-block', testInfo)

    console.log('[ADV E2E] review prompt')
    await sendComposer(page, REVIEW_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '08-advanced-review',
      until: async () => await page.getByTestId('revision-accept').isVisible().catch(() => false),
      maxRounds: 3,
      timeoutMs: 240_000,
    })
    const revisionPanel = page.getByTestId('revision-assist')
    await expect(revisionPanel).toBeVisible({ timeout: 120_000 })
    const previousRevisionVersion = ((await revisionPanel.textContent().catch(() => '')) || '').match(/version_[a-z0-9]+/i)?.[0] || ''
    await capture(page, '08-advanced-revision-suggested', testInfo)

    console.log('[ADV E2E] accept revision')
    await page.getByTestId('revision-accept').click()
    await expect(revisionPanel).toContainText(/已应用|观察中|可继续/, { timeout: 120_000 })
    if (previousRevisionVersion) {
      await expect(revisionPanel).not.toContainText(previousRevisionVersion, { timeout: 120_000 })
    }
    await expectPurchaseDecisionQuality(preview, { requireImages: true, requireExpandedBlocks: true })
    await capture(page, '09-advanced-revision-applied', testInfo)

    console.log('[ADV E2E] session knowledge')
    await page.getByTestId('workspace-tab-session-knowledge').click()
    const knowledgeWorkbench = page.getByTestId('session-knowledge-workbench')
    await expect(knowledgeWorkbench).toBeVisible({ timeout: 30_000 })
    await expect(knowledgeWorkbench).toContainText(/当前版本/)
    await expect(knowledgeWorkbench).toContainText(/父版本/)
    await expect(knowledgeWorkbench).toContainText(/知识版本/)
    await capture(page, '10-advanced-session-knowledge', testInfo)

    const newProjectAgain = page.getByRole('button', { name: /\+ New Project/i })
    await expect(newProjectAgain).toBeVisible({ timeout: 30_000 })
    await newProjectAgain.click()
    await expect(page.getByTestId('composer-input')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('revision-assist')).toBeHidden({ timeout: 30_000 })
    await page.getByTestId('workspace-tab-session-knowledge').click()
    const emptyKnowledgeWorkbench = page.getByTestId('session-knowledge-workbench')
    await expect(emptyKnowledgeWorkbench).toBeVisible({ timeout: 30_000 })
    await expect(emptyKnowledgeWorkbench).not.toContainText(/当前版本|父版本|知识版本/)
    await capture(page, '11-advanced-fresh-session-cleared', testInfo)
  })
})
