/**
 * 诊断：错误资源块密码时 ElMessage 是否在 DOM 中、被什么遮挡。
 * 依赖：puppeteer-core + 系统 Microsoft Edge（headless）
 * 运行：node test/e2e/diagnose-message.mjs
 */
import puppeteer from 'puppeteer-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5000'

const logs = []
const unlockResponses = []

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--no-sandbox', '--disable-blink-features=AutomationControlled'],
})
try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })

  page.on('console', (m) => logs.push(`[console.${m.type()}] ${m.text()}`))
  page.on('pageerror', (e) => logs.push(`[pageerror] ${e.message}`))
  page.on('response', async (res) => {
    if (res.url().includes('/unlock')) {
      let body = ''
      try { body = await res.text() } catch {}
      unlockResponses.push({ status: res.status(), body })
    }
  })

  // 1. 登录
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]', { timeout: 10000 })
  await page.type('input[placeholder*="用户名"]', '13800001234')
  await page.type('input[type="password"]', 'abc123456')
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click()
  })
  await page.waitForFunction(() => location.hash === '#/', { timeout: 10000 })
  await page.waitForSelector('.resource-card', { timeout: 10000 })
  console.log('登录成功，资源卡片数量:', await page.$$eval('.resource-card', (els) => els.length))

  // 2. 打开解锁弹窗并输入错误密码
  await page.evaluate(() => {
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('查看资源')).click()
  })
  await page.waitForSelector('.el-dialog input[type="password"]', { timeout: 5000 })
  await page.type('.el-dialog input[type="password"]', '000000')
  await page.evaluate(() => {
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.includes('确认解锁')).click()
  })

  await new Promise((r) => setTimeout(r, 900))
  await page.screenshot({ path: 'test/e2e/shot-error.png' })

  const state900 = await page.evaluate(() => {
    const pick = (el) => {
      const cs = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return {
        cls: String(el.className).slice(0, 120),
        text: (el.textContent || '').trim().slice(0, 100),
        zIndex: cs.zIndex,
        opacity: cs.opacity,
        visibility: cs.visibility,
        display: cs.display,
        position: cs.position,
        top: cs.top,
        rect: { x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height) },
        parent: el.parentElement ? `${el.parentElement.tagName}.${String(el.parentElement.className).slice(0, 80)}` : null,
      }
    }
    return {
      messages: [...document.querySelectorAll('.el-message')].map(pick),
      overlays: [...document.querySelectorAll('.el-overlay')].map(pick),
      dialogs: [...document.querySelectorAll('.el-dialog')].map(pick),
      bodyChildren: [...document.body.children].map((c) => `${c.tagName}.${String(c.className).slice(0, 60)}`),
    }
  })

  console.log('---- unlock 接口响应 ----')
  console.log(JSON.stringify(unlockResponses, null, 2))
  console.log('---- 错误后 900ms DOM 状态 ----')
  console.log(JSON.stringify(state900, null, 2))

  // 3. 正确密码
  await page.evaluate(() => {
    const input = document.querySelector('.el-dialog input[type="password"]')
    input.value = ''
    input.dispatchEvent(new Event('input', { bubbles: true }))
  })
  await page.type('.el-dialog input[type="password"]', 'res-pass-123')
  await page.evaluate(() => {
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.includes('确认解锁')).click()
  })
  await new Promise((r) => setTimeout(r, 1200))
  const revealed = await page.$eval('.el-dialog', (el) => el.textContent.includes('解锁成功'))
  console.log('正确密码解锁成功状态:', revealed)
  await page.screenshot({ path: 'test/e2e/shot-success.png' })

  console.log('---- 浏览器日志 ----')
  console.log(logs.join('\n') || '(无)')
} finally {
  await browser.close()
}
