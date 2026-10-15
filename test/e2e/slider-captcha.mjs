// 滑动验证码端到端测试：真实 CDP 鼠标拖动（puppeteer-core + 系统 Edge）
// 用法：node slider-captcha.mjs [baseURL]
// 前置：后端已在 5000 端口运行（python app.py）
// 白盒：拦截 /api/captcha/new 响应取得 challenge_id，用项目 venv 的 python
//       从 db/sourcelink.db 读取正确坐标 answer_x，实现精确拖动命中。

import puppeteer from 'puppeteer-core'
import { execSync } from 'node:child_process'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const BASE = process.argv[2] || 'http://127.0.0.1:5000'
const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '../..')
const PY = path.join(ROOT, '.venv', 'Scripts', 'python.exe')

function findEdge() {
  const candidates = [
    'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',
    'C:/Program Files/Microsoft/Edge/Application/msedge.exe',
  ]
  for (const p of candidates) {
    try {
      execSync(`if exist "${p}" echo ok`, { shell: 'cmd.exe' })
      return p
    } catch {
      /* continue */
    }
  }
  throw new Error('未找到 Edge 浏览器')
}

function readAnswerX(challengeId) {
  const db = path.join(ROOT, 'db', 'sourcelink.db').replace(/\\/g, '/')
  const out = execSync(
    `"${PY}" -c "import sqlite3, json; c = sqlite3.connect(r'${db}'); print(json.dumps(c.execute('select answer_x from captcha_record where token=?', ('${challengeId}',)).fetchone()))"`,
    { encoding: 'utf8', timeout: 15000, shell: 'cmd.exe' },
  )
  return JSON.parse(out.trim())[0]
}

function readLatestChallenge() {
  const db = path.join(ROOT, 'db', 'sourcelink.db').replace(/\\/g, '/')
  const out = execSync(
    `"${PY}" -c "import sqlite3, json; c = sqlite3.connect(r'${db}'); print(json.dumps(c.execute(\\"select token, answer_x from captcha_record where kind='challenge' and consumed_at is null order by created_at desc limit 1\\").fetchone()))"`,
    { encoding: 'utf8', timeout: 15000, shell: 'cmd.exe' },
  )
  return JSON.parse(out.trim())
}

const browser = await puppeteer.launch({
  executablePath: findEdge(),
  headless: 'new',
})
const page = await browser.newPage()
await page.setViewport({ width: 500, height: 860 })

const pageErrors = []
page.on('pageerror', (e) => pageErrors.push(String(e)))

page.on('request', (req) => {
  if (req.url().includes('/api/captcha/verify')) {
    try {
      console.log(`  [debug] 提交 x=${JSON.parse(req.postData()).x}`)
    } catch {
      /* ignore */
    }
  }
})

let passed = 0
const check = (name, cond) => {
  console.log(`[${cond ? 'PASS' : 'FAIL'}] ${name}`)
  if (!cond) process.exitCode = 1
  else passed++
}

await page.goto(`${BASE}/#/register`, { waitUntil: 'networkidle2' })
await page.waitForSelector('.captcha-handle', { timeout: 15000 })
await new Promise((r) => setTimeout(r, 800))

async function dragBy(offsetPx) {
  const handle = await page.$('.captcha-handle')
  const box = await handle.boundingBox()
  const startX = box.x + box.width / 2
  const startY = box.y + box.height / 2
  await page.mouse.move(startX, startY)
  await page.mouse.down()
  const steps = 20
  for (let i = 1; i <= steps; i++) {
    await page.mouse.move(startX + (offsetPx * i) / steps, startY)
  }
  await page.mouse.up()
}

// 1. 错误坐标：拖到明显偏离的位置，应出现红色「未对准缺口」提示并自动刷新
await dragBy(40)
await new Promise((r) => setTimeout(r, 350))
const sawError = (await page.$('.captcha-flag.error')) !== null
await page.screenshot({ path: 'shot-slider-wrong.png' })
check('错误坐标触发校验失败提示', sawError)
await page.waitForFunction(() => document.querySelector('.captcha-flag.error') === null, { timeout: 8000 })
await new Promise((r) => setTimeout(r, 700))

// 2. 正确坐标：点击刷新换新题 -> 白盒读库取最新挑战的 answer_x -> 按 canvas 缩放比例精确拖动
await page.click('.captcha-refresh')
await new Promise((r) => setTimeout(r, 1200))
const [, answerX] = readLatestChallenge()
console.log(`  [debug] answer_x=${answerX}`)
const canvas = await page.$('canvas')
const canvasBox = await canvas.boundingBox()
const scale = canvasBox.width / 300
await dragBy(answerX * scale)
await new Promise((r) => setTimeout(r, 600))
const sawSuccess = (await page.$('.captcha-flag.success')) !== null
await page.screenshot({ path: 'shot-slider-success.png' })
check('正确坐标滑动验证通过', sawSuccess)

// 3. 登录页新设备触发滑动验证
await page.evaluate(() => localStorage.clear())
await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
await page.type('input[placeholder="用户名 / 手机号 / 邮箱"]', 'admin')
await page.type('input[placeholder="请输入密码"]', '1q2w3e4r')
await page.click('.el-button--primary')
await page.waitForSelector('.captcha-handle', { timeout: 10000 })
await page.screenshot({ path: 'shot-login-captcha.png' })
check('登录页新设备触发滑动验证区域', true)

check('页面无 JS 运行时错误', pageErrors.length === 0)

await browser.close()
console.log(`\n滑动验证码 E2E 完成，通过 ${passed} 项。`)
