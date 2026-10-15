/**
 * 验证 ElMessage 在 headless=new（完整渲染、计时器不节流）下的表现。
 * 运行：node test/e2e/ab-message2.mjs
 */
import puppeteer from 'puppeteer-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5000'

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: 'new',
  args: ['--no-sandbox'],
})
const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  await page.goto('about:blank')

  // 场景 A：无 dialog 的错误提示
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', 'admin')
  await page.type('input[type="password"]', 'wrong-pass')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  for (const t of [200, 450, 3200]) {
    await sleep(t === 200 ? 200 : t - (t === 450 ? 200 : 450))
    const data = await page.evaluate(() =>
      [...document.querySelectorAll('.el-message')].map((el) => ({
        text: el.textContent.trim().slice(0, 20),
        opacity: getComputedStyle(el).opacity,
      })),
    )
    console.log(`[A 无dialog ${t}ms]`, JSON.stringify(data))
  }
  await page.screenshot({ path: 'test/e2e/shot-a-new-headless.png' })

  // 场景 B：dialog 内错误提示（先整页刷新到干净登录态）
  await page.evaluate(() => localStorage.clear())
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', '13800001234')
  await page.type('input[type="password"]', 'abc123456')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  await page.waitForSelector('.resource-card')
  await sleep(3200) // 等登录成功消息消失
  let data = await page.evaluate(() => [...document.querySelectorAll('.el-message')].length)
  console.log('[B 登录3.2s后残留消息数]', data)

  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('查看资源')).click(),
  )
  await page.waitForSelector('.el-dialog input[type="password"]')
  await page.type('.el-dialog input[type="password"]', '000000')
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.includes('确认解锁')).click(),
  )
  await sleep(250)
  data = await page.evaluate(() =>
    [...document.querySelectorAll('.el-message')].map((el) => ({
      text: el.textContent.trim().slice(0, 20),
      opacity: getComputedStyle(el).opacity,
      z: getComputedStyle(el).zIndex,
    })),
  )
  console.log('[B dialog错误 250ms]', JSON.stringify(data))
  await page.screenshot({ path: 'test/e2e/shot-b-new-headless.png' })
  await sleep(3200)
  data = await page.evaluate(() => [...document.querySelectorAll('.el-message')].length)
  console.log('[B 错误消息3.4s后残留数（应为0）]', data)
} finally {
  await browser.close()
}
