import { expect, test } from '@playwright/test'

const CREATE_PROMPT =
  '我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。'
const IMAGE_PROMPT = '这份档案图片太少了，补几张更像真机质感的图片。'
const REVIEW_PROMPT = '帮我再检查一遍，看看这份档案最值得优化的一点是什么。'

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

  const previewPath = testInfo.outputPath(`${name}-focus.png`)
  await target.screenshot({ path: previewPath })
  await testInfo.attach(`${name}-focus`, {
    path: previewPath,
    contentType: 'image/png',
  })
}

async function sendComposer(page: import('@playwright/test').Page, content: string) {
  console.log(`[E2E] sendComposer start: ${content}`)
  const composer = page.getByTestId('composer-input')
  await expect(composer).toBeVisible()
  await composer.fill(content)
  await page.getByTestId('composer-send').click()
  console.log(`[E2E] sendComposer sent: ${content}`)
}

async function waitForRenderablePreview(page: import('@playwright/test').Page) {
  const preview = page.getByTestId('preview-shell')
  await expect(preview).toBeVisible({ timeout: 120_000 })
  await expect(preview).not.toContainText('Waiting for Agent to generate UI structure...', { timeout: 120_000 })
  return preview
}

async function expectPurchaseDecisionQuality(
  preview: import('@playwright/test').Locator,
  options: {
    requireImages?: boolean
  } = {},
) {
  const { requireImages = false } = options
  await expect(preview).toContainText(/Mate 60|华为 Mate 60/, { timeout: 120_000 })
  await expect(preview).not.toContainText(/Find X8 Ultra|iPhone 15|小米 14/i)
  await expect(preview).not.toContainText('TitleBlock')
  await expect(preview).not.toContainText('StoryText')
  await expect(preview).not.toContainText('等待封面图片接入...')
  await expect(preview).toContainText(/值不值得买，先看这几条|关键信息|参数依据|已确认/, { timeout: 120_000 })
  await expect(preview).toContainText(/路线对比|优缺点|怎么选|主推路线|保守路线/, { timeout: 120_000 })
  await expect(preview).toContainText(/风险|代价|不适合|边界/, { timeout: 120_000 })
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
    const checkpointKey = await checkpointCard.evaluate((node) => {
      const title = node.querySelector('[data-testid^="checkpoint-option-"]')?.getAttribute('data-testid') || ''
      const content = (node.textContent || '').replace(/\s+/g, ' ').trim()
      return `${content.slice(0, 80)}::${title}`
    }).catch(() => `round-${resolvedRounds}`)
    await capture(page, `${label}-checkpoint-${resolvedRounds}`, testInfo)
    const options = checkpointCard.locator('[data-testid^="checkpoint-option-"]')
    await expect(options.first()).toBeVisible({ timeout: 30_000 })
    await options.first().click()
    const postClickDeadline = Date.now() + 60_000
    while (Date.now() < postClickDeadline) {
      if (await until()) return
      const stillVisible = await checkpointCard.isVisible().catch(() => false)
      if (!stillVisible) break
      const nextKey = await checkpointCard.evaluate((node) => {
        const title = node.querySelector('[data-testid^="checkpoint-option-"]')?.getAttribute('data-testid') || ''
        const content = (node.textContent || '').replace(/\s+/g, ' ').trim()
        return `${content.slice(0, 80)}::${title}`
      }).catch(() => '')
      if (nextKey && nextKey !== checkpointKey) break
      await page.waitForTimeout(1500)
    }
  }
  throw new Error(`Timed out waiting for ${label} after ${timeoutMs}ms`)
}

test.describe('digital purchase real browser e2e', () => {
  test('runs the full real workflow against the real backend', async ({ page }, testInfo) => {
    console.log('[E2E] goto /')
    await page.goto('/')
    await expect(page.getByText('ONLINE')).toBeVisible({ timeout: 30_000 })
    console.log('[E2E] page online')

    const newProject = page.getByRole('button', { name: /\+ New Project/i })
    if (await newProject.isVisible().catch(() => false)) {
      console.log('[E2E] click new project')
      await newProject.click()
    }

    await sendComposer(page, CREATE_PROMPT)

    const preview = page.getByTestId('preview-shell')
    await resolveCheckpointLoop(page, testInfo, {
      label: '01-real-create',
      until: async () => {
        const visible = await preview.isVisible().catch(() => false)
        if (!visible) return false
        const text = (await preview.textContent().catch(() => '')) || ''
        return /Mate 60|华为 Mate 60/.test(text) && !/TitleBlock|StoryText/.test(text)
      },
    })
    console.log('[E2E] create flow resolved')
    await waitForRenderablePreview(page)
    await expectPurchaseDecisionQuality(preview)
    await capture(page, '02-real-created-artifact', testInfo)
    console.log('[E2E] created artifact captured')
    const blockCountBeforeAsset = await preview.locator('[data-comp-id]').count()

    await sendComposer(page, IMAGE_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '03-real-asset',
      until: async () => {
        return await preview.locator('img').first().isVisible().catch(() => false)
      },
      maxRounds: 4,
      timeoutMs: 240_000,
    })
    console.log('[E2E] asset flow resolved')
    await page.waitForTimeout(1500)
    expect(await preview.locator('[data-comp-id]').count()).toBeGreaterThanOrEqual(blockCountBeforeAsset)
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '03-real-asset-enriched', testInfo)
    console.log('[E2E] asset artifact captured')

    const selectionToggle = page.getByTestId('preview-selection-toggle')
    const selectionToggleText = (await selectionToggle.textContent().catch(() => '')) || ''
    if (!selectionToggleText.includes('退出选择模式')) {
      await selectionToggle.click()
    }
    await expect(selectionToggle).toContainText('退出选择模式')
    console.log('[E2E] selecting editable block start')
    const preferredBlock =
      (await preview.locator('[data-comp-id="story_2"]').count()) > 0
        ? preview.locator('[data-comp-id="story_2"]').first()
        : preview.locator('[data-comp-id="story_1"]').first()
    await expect(preferredBlock).toBeVisible({ timeout: 30_000 })
    await preferredBlock.getByRole('button', { name: '选择当前积木' }).click({ force: true })
    console.log('[E2E] selected editable block')

    await sendComposer(page, '把这个对比块改得更直接一点，更像给朋友的购买建议。')
    await expect(preview).toContainText(/朋友|更直接|值得/, { timeout: 120_000 })
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '04-real-local-edit', testInfo)
    console.log('[E2E] local edit captured')

    await sendComposer(page, REVIEW_PROMPT)
    await resolveCheckpointLoop(page, testInfo, {
      label: '05-real-review',
      until: async () => await page.getByTestId('revision-accept').isVisible().catch(() => false),
      maxRounds: 3,
      timeoutMs: 240_000,
    })
    console.log('[E2E] review flow resolved')
    const revisionPanel = page.getByTestId('revision-assist')
    await expect(revisionPanel).toBeVisible({ timeout: 120_000 })
    await expect(revisionPanel).toContainText(/修订|建议|可继续|观察中|待重试|已应用/)
    await capture(page, '05-real-revision-suggested', testInfo)
    console.log('[E2E] revision suggested captured')

    const revisionButton = page.getByTestId('revision-accept')
    const previousRevisionVersion = ((await revisionPanel.textContent().catch(() => '')) || '').match(/version_[a-z0-9]+/i)?.[0] || ''
    await expect(revisionButton).toBeVisible({ timeout: 30_000 })
    console.log('[E2E] click revision accept')
    await revisionButton.click()
    await expect(revisionPanel).toContainText(/已应用|观察中|可继续/, { timeout: 120_000 })
    if (previousRevisionVersion) {
      await expect(revisionPanel).not.toContainText(previousRevisionVersion, { timeout: 120_000 })
    }
    await expect(preview).toContainText(/朋友|值得|优先|结论/, { timeout: 120_000 })
    await expectPurchaseDecisionQuality(preview, { requireImages: true })
    await capture(page, '06-real-revision-applied', testInfo)
    console.log('[E2E] revision applied captured')

    await page.getByTestId('workspace-tab-session-knowledge').click()
    await expect(page.getByTestId('session-knowledge-workbench')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('session-knowledge-workbench')).toContainText(/当前版本/)
    await expect(page.getByTestId('session-knowledge-workbench')).toContainText(/父版本/)
    await expect(page.getByTestId('session-knowledge-workbench')).toContainText(/知识版本/)
    await capture(page, '07-real-session-knowledge', testInfo)
    console.log('[E2E] session knowledge captured')

    const newProjectAgain = page.getByRole('button', { name: /\+ New Project/i })
    await expect(newProjectAgain).toBeVisible({ timeout: 30_000 })
    await newProjectAgain.click()
    await expect(page.getByTestId('composer-input')).toBeVisible({ timeout: 30_000 })
    await expect(page.getByTestId('revision-assist')).toBeHidden({ timeout: 30_000 })
    await expect(page.getByTestId('session-knowledge-workbench')).not.toContainText(/当前版本|父版本|知识版本/)
    await capture(page, '08-real-fresh-session-cleared', testInfo)
    console.log('[E2E] fresh session cleared')
  })
})
