/**
 * new headless 下验证 dialog 内错误密码提示的真实表现（截图 + 样式 + 自动关闭）。
 * 运行：node test/e2e/dialog-shot.mjs
 */
import puppeteer from 'puppeteer-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5000'
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: 'new',
  args: ['--no-sandbox'],
})

try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  await page.goto('about:blank')
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', '13800001234')
  await page.type('input[type="password"]', 'abc123456')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  await page.waitForSelector('.resource-card')
  await sleep(3800) // 登录成功消息消失

  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('查看资源')).click(),
  )
  await page.waitForSelector('.el-dialog input[type="password"]')
  await page.type('.el-dialog input[type="password"]', '000000')
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.includes('确认解锁')).click(),
  )
  await sleep(1200)

  const info = await page.evaluate(() => {
    const msgs = [...document.querySelectorAll('.el-message')].map((el) => {
      const cs = getComputedStyle(el)
      const r = el.getBoundingClientRect()
      return {
        text: el.textContent.trim(),
        opacity: cs.opacity,
        z: cs.zIndex,
        y: Math.round(r.y),
        visible: cs.visibility === 'visible' && Number(cs.opacity) > 0.9,
      }
    })
    const overlay = document.querySelector('.el-overlay')
    return { msgs, overlayZ: overlay ? getComputedStyle(overlay).zIndex : null }
  })
  console.log('1.2s 时消息状态:', JSON.stringify(info, null, 2))
  await page.screenshot({ path: 'test/e2e/shot-dialog-error-new.png' })

  await sleep(3200)
  const left = await page.$$eval('.el-message', (els) => els.length)
  console.log('再过 3.2s 残留消息数（应为 0）:', left)
} finally {
  await browser.close()
}
