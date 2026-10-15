/**
 * A/B 实验：ElMessage 在【无 dialog】与【有 dialog】场景下的生命周期对比。
 * 运行：node test/e2e/ab-message.mjs
 */
import puppeteer from 'puppeteer-core'

const EDGE = 'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe'
const BASE = 'http://127.0.0.1:5000'

const browser = await puppeteer.launch({
  executablePath: EDGE,
  headless: true,
  args: ['--no-sandbox'],
})

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

async function dumpMessages(page, label) {
  const data = await page.evaluate(() =>
    [...document.querySelectorAll('.el-message')].map((el) => {
      const cs = getComputedStyle(el)
      return {
        text: el.textContent.trim().slice(0, 20),
        opacity: cs.opacity,
        cls: String(el.className).replace('el-message ', ''),
        bodyCls: document.body.className,
      }
    }),
  )
  console.log(`[${label}]`, JSON.stringify(data))
}

try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })

  // ---------- 场景 A：登录页错误密码（无 dialog） ----------
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', 'admin')
  await page.type('input[type="password"]', 'wrong-pass')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  await sleep(300)
  await dumpMessages(page, 'A 无dialog 300ms')
  await sleep(700)
  await dumpMessages(page, 'A 无dialog 1000ms')
  await sleep(2500)
  await dumpMessages(page, 'A 无dialog 3500ms（应已消失）')

  // ---------- 场景 B：正确登录后，在解锁 dialog 内触发错误 ----------
  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', '13800001234')
  await page.type('input[type="password"]', 'abc123456')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  await page.waitForSelector('.resource-card')
  await sleep(3500) // 等登录成功 message 自然消失
  await dumpMessages(page, 'B 登录3.5s后（登录消息应消失）')

  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('查看资源')).click(),
  )
  await page.waitForSelector('.el-dialog input[type="password"]')
  await page.type('.el-dialog input[type="password"]', '000000')
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.includes('确认解锁')).click(),
  )
  await sleep(300)
  await dumpMessages(page, 'B dialog内错误 300ms')
  await sleep(700)
  await dumpMessages(page, 'B dialog内错误 1000ms')
  await sleep(2500)
  await dumpMessages(page, 'B dialog内错误 3500ms')

  // ---------- 场景 C：dialog 关闭后再触发（页面 message） ----------
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.trim() === '取消').click(),
  )
  await sleep(600)
  console.log('dialog 关闭后 body class:', await page.evaluate(() => document.body.className))
} finally {
  await browser.close()
}
