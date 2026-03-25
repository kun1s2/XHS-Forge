import { expect, test } from '@playwright/test'

const CREATE_PROMPT =
  '我想买一台 4500 元左右的手机，主要看重拍照和续航。先帮我判断华为 Mate 60 现在值不值得买，并生成一份购买决策档案。'

const IMAGE_PROMPT = '这份档案图片太少了，补几张更像真机质感的图片。'
const DIRECT_EDIT_PROMPT = '把结论改得更直接一点'

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
  let previewTarget = preview

  if (await preview.isVisible().catch(() => false)) {
    previewTarget = preview
  } else if (await previewContainer.isVisible().catch(() => false)) {
    previewTarget = previewContainer
  } else {
    await expect(knowledgeWorkbench).toBeVisible()
    previewTarget = knowledgeWorkbench
  }
  const previewPath = testInfo.outputPath(`${name}-preview.png`)
  await previewTarget.screenshot({ path: previewPath })
  await testInfo.attach(`${name}-preview`, {
    path: previewPath,
    contentType: 'image/png',
  })
}

async function sendComposer(page: import('@playwright/test').Page, content: string) {
  const composer = page.getByTestId('composer-input')
  await expect(composer).toBeVisible()
  await composer.fill(content)
  await page.getByTestId('composer-send').click()
}

test.describe('digital purchase browser e2e', () => {
  test('user can create, confirm, enrich, revise, and inspect one artifact across versions', async ({ page }, testInfo) => {
    await page.goto('/')

    await expect(page.getByText('ONLINE')).toBeVisible({ timeout: 15_000 })
    await expect(page.getByTestId('composer-input')).toBeVisible()

    await sendComposer(page, CREATE_PROMPT)

    const checkpointCard = page.getByTestId('checkpoint-card')
    await expect(checkpointCard).toBeVisible()
    await expect(checkpointCard).toContainText('这页先按哪种方向搭骨架？')
    await capture(page, '01-structure-checkpoint', testInfo)

    await page.getByTestId('checkpoint-option-seeding_compare').click()

    const preview = page.getByTestId('preview-shell')
    await expect(preview).toContainText('华为 Mate 60')
    await expect(preview).toContainText('4500 元左右')
    await expect(preview).not.toContainText('StoryText')
    await expect(preview).not.toContainText('TitleBlock')
    await capture(page, '02-created-artifact', testInfo)

    await sendComposer(page, IMAGE_PROMPT)
    await expect(page.locator('[data-comp-id="cover_1"]')).toBeVisible()
    await expect(preview).toContainText('华为 Mate 60 真机观感')
    await capture(page, '03-asset-enriched', testInfo)

    await sendComposer(page, DIRECT_EDIT_PROMPT)
    await expect(preview).toContainText('依然值得优先看')
    await expect(preview).not.toContainText('Find X8 Ultra')
    await capture(page, '04-direct-edit', testInfo)

    const revisionPanel = page.getByTestId('revision-assist')
    await expect(revisionPanel).toBeVisible()
    await expect(revisionPanel).toContainText('把结论说得更直接')
    await page.getByTestId('revision-accept').click()

    await expect(preview).toContainText('如果你朋友现在就拿着 4500 元来问我')
    await capture(page, '05-revision-applied', testInfo)

    await page.getByTestId('workspace-tab-session-knowledge').click()
    await expect(page.getByText('当前版本 version_004')).toBeVisible()
    await expect(page.getByText('父版本 version_003')).toBeVisible()
    await expect(page.getByText('知识版本 session-kb::3')).toBeVisible()
    await expect(page.getByText('最近变更：story_1')).toBeVisible()
    await capture(page, '06-session-knowledge-versioning', testInfo)
  })
})
