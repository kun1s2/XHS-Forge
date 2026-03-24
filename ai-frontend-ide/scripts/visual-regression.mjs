import { spawn } from 'node:child_process'
import { mkdirSync, existsSync, rmSync, readFileSync, writeFileSync } from 'node:fs'
import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

import { chromium } from '@playwright/test'
import pixelmatch from 'pixelmatch'
import { PNG } from 'pngjs'

const __dirname = dirname(fileURLToPath(import.meta.url))
const ROOT = join(__dirname, '..')
const BASELINE_DIR = join(ROOT, 'visual-regression', 'baseline')
const CURRENT_DIR = join(ROOT, 'visual-regression', 'current')
const DIFF_DIR = join(ROOT, 'visual-regression', 'diff')
const REVIEW_DIR = join(ROOT, 'visual-regression', 'review')
const BLOCK_REVIEW_DIR = join(REVIEW_DIR, 'blocks')
const REPORT_PATH = join(ROOT, 'visual-regression', 'report.json')
const PORT = 4173 + Math.floor(Math.random() * 1000)
const BASE_URL = `http://127.0.0.1:${PORT}`
const UPDATE_BASELINE = process.argv.includes('--update')

const fixtures = [
  { id: 'seeding_compare', label: '数码对比种草' },
  { id: 'seeding_camera_focus', label: '数码影像焦点页' },
  { id: 'seeding_budget_pick', label: '数码预算决策页' },
  { id: 'knowledge_digest', label: '知识摘要与时间线页' },
  { id: 'all_blocks_gallery', label: '全积木总览页' },
]

const viewports = [
  { name: 'mobile', width: 430, height: 932 },
  { name: 'desktop', width: 1440, height: 1200 },
]

const ensureDir = (dir) => mkdirSync(dir, { recursive: true })

const waitForServer = async (url, timeoutMs = 20000) => {
  const start = Date.now()
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(url)
      if (res.ok) return
    } catch {}
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error(`Visual regression server did not start in time: ${url}`)
}

const startPreviewServer = () => {
  const child = spawn('python3', ['-m', 'http.server', String(PORT), '--bind', '127.0.0.1', '--directory', 'dist'], {
    cwd: ROOT,
    stdio: 'pipe',
    env: {
      ...process.env,
      NODE_ENV: 'production',
    },
  })
  child.stdout.on('data', (chunk) => process.stdout.write(chunk))
  child.stderr.on('data', (chunk) => process.stderr.write(chunk))
  return child
}

const screenshotPath = (dir, fixtureId, viewportName) =>
  join(dir, `${fixtureId}__${viewportName}.png`)

const buildReviewSheet = (sourcePath, targetPath) => {
  const source = PNG.sync.read(readFileSync(sourcePath))
  const sliceHeight = Math.min(420, source.height)
  const sections = [
    0,
    Math.max(0, Math.floor((source.height - sliceHeight) / 2)),
    Math.max(0, source.height - sliceHeight),
  ]
  const sheet = new PNG({
    width: source.width,
    height: sliceHeight * sections.length,
  })
  sections.forEach((startY, index) => {
    for (let y = 0; y < sliceHeight; y += 1) {
      for (let x = 0; x < source.width; x += 1) {
        const srcIdx = ((startY + y) * source.width + x) * 4
        const dstIdx = ((index * sliceHeight + y) * sheet.width + x) * 4
        sheet.data[dstIdx] = source.data[srcIdx]
        sheet.data[dstIdx + 1] = source.data[srcIdx + 1]
        sheet.data[dstIdx + 2] = source.data[srcIdx + 2]
        sheet.data[dstIdx + 3] = source.data[srcIdx + 3]
      }
    }
  })
  writeFileSync(targetPath, PNG.sync.write(sheet))
}

const compareScreenshots = (baselinePath, currentPath, diffPath) => {
  const baseline = PNG.sync.read(readFileSync(baselinePath))
  const current = PNG.sync.read(readFileSync(currentPath))
  if (baseline.width !== current.width || baseline.height !== current.height) {
    throw new Error(`Screenshot size mismatch: ${baselinePath} vs ${currentPath}`)
  }
  const diff = new PNG({ width: baseline.width, height: baseline.height })
  const diffPixels = pixelmatch(
    baseline.data,
    current.data,
    diff.data,
    baseline.width,
    baseline.height,
    { threshold: 0.12 }
  )
  writeFileSync(diffPath, PNG.sync.write(diff))
  return {
    diffPixels,
    totalPixels: baseline.width * baseline.height,
    diffRatio: diffPixels / (baseline.width * baseline.height),
  }
}

const run = async () => {
  ensureDir(BASELINE_DIR)
  ensureDir(CURRENT_DIR)
  ensureDir(DIFF_DIR)
  rmSync(CURRENT_DIR, { recursive: true, force: true })
  rmSync(DIFF_DIR, { recursive: true, force: true })
  rmSync(REVIEW_DIR, { recursive: true, force: true })
  ensureDir(CURRENT_DIR)
  ensureDir(DIFF_DIR)
  ensureDir(REVIEW_DIR)
  ensureDir(BLOCK_REVIEW_DIR)

  const server = startPreviewServer()
  try {
    await waitForServer(BASE_URL)
    const browser = await chromium.launch({ headless: true })
    const results = []

    for (const viewport of viewports) {
      const page = await browser.newPage({ viewport: { width: viewport.width, height: viewport.height } })
      for (const fixture of fixtures) {
        const url = `${BASE_URL}/?visual_lab=1&fixture=${fixture.id}`
        await page.goto(url, { waitUntil: 'networkidle' })
        const fixtureRoot = page.locator('[data-visual-preview-shell]')
        await fixtureRoot.waitFor({ state: 'visible' })
        await page.waitForFunction(
          () => document.querySelectorAll('[data-comp-id]').length > 0,
          undefined,
          { timeout: 10000 }
        )
        await fixtureRoot.screenshot({
          path: screenshotPath(CURRENT_DIR, fixture.id, viewport.name),
        })

        const blockLocators = page.locator('[data-comp-id]')
        const blockCount = await blockLocators.count()
        for (let blockIndex = 0; blockIndex < blockCount; blockIndex += 1) {
          const block = blockLocators.nth(blockIndex)
          const blockId = (await block.getAttribute('data-comp-id')) || `block-${blockIndex + 1}`
          await block.screenshot({
            path: join(
              BLOCK_REVIEW_DIR,
              `${fixture.id}__${viewport.name}__${String(blockIndex + 1).padStart(2, '0')}__${blockId}.png`
            ),
          })
        }

        const baselinePath = screenshotPath(BASELINE_DIR, fixture.id, viewport.name)
        const currentPath = screenshotPath(CURRENT_DIR, fixture.id, viewport.name)
        const diffPath = screenshotPath(DIFF_DIR, fixture.id, viewport.name)
        const reviewPath = screenshotPath(REVIEW_DIR, fixture.id, viewport.name)

        buildReviewSheet(currentPath, reviewPath)

        if (UPDATE_BASELINE || !existsSync(baselinePath)) {
          writeFileSync(baselinePath, readFileSync(currentPath))
          results.push({
            fixture: fixture.id,
            viewport: viewport.name,
            status: 'baseline-updated',
            diffRatio: 0,
          })
          continue
        }

        const comparison = compareScreenshots(baselinePath, currentPath, diffPath)
        results.push({
          fixture: fixture.id,
          viewport: viewport.name,
          status: comparison.diffRatio <= 0.015 ? 'pass' : 'fail',
          ...comparison,
        })
      }
      await page.close()
    }

    await browser.close()
    writeFileSync(REPORT_PATH, JSON.stringify({ updated_at: new Date().toISOString(), results }, null, 2))

    const failures = results.filter((item) => item.status === 'fail')
    if (failures.length) {
      console.error('Visual regression failed:', failures)
      process.exitCode = 1
      return
    }

    console.log('Visual regression passed.')
  } finally {
    server.kill('SIGTERM')
  }
}

run().catch((error) => {
  console.error(error)
  process.exit(1)
})
