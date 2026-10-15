/**
 * 精确定位 ElMessage 延迟来源：
 * - JS 主线程心跳（检测是否被阻塞）
 * - /auth/login 的网络耗时
 * - DOM 中 .el-message 出现的精确时刻
 * 运行：node test/e2e/timing.mjs
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

  const reqTiming = []
  page.on('requestfinished', async (req) => {
    if (req.url().includes('/api/')) {
      const timing = JSON.parse(JSON.stringify(req.response().timing()))
      reqTiming.push({ url: req.url().slice(-40), status: req.response().status(), timing })
    }
  })

  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', 'admin')
  await page.type('input[type="password"]', 'wrong-pass')

  // 在页面内植入心跳与 MutationObserver（t=0 为点击时刻）
  await page.evaluate(() => {
    window.__marks = []
    const t0 = performance.now()
    window.__t0 = t0
    setInterval(() => {
      window.__marks.push({ kind: 'heartbeat', t: Math.round(performance.now() - t0) })
    }, 100)
    const observer = new MutationObserver((muts) => {
      for (const m of muts) {
        for (const node of m.addedNodes) {
          if (node.nodeType === 1 && node.classList && node.classList.contains('el-message')) {
            window.__marks.push({ kind: 'message-mounted', t: Math.round(performance.now() - t0) })
          }
        }
      }
    })
    observer.observe(document.body, { childList: true, subtree: true })
  })

  const clickAt = Date.now()
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )

  await sleep(6000)
  const result = await page.evaluate(() => {
    const heartbeats = window.__marks.filter((m) => m.kind === 'heartbeat').map((m) => m.t)
    const mounted = window.__marks.filter((m) => m.kind === 'message-mounted').map((m) => m.t)
    // 检测心跳空洞（>300ms 视为阻塞）
    const gaps = []
    for (let i = 1; i < heartbeats.length; i++) {
      if (heartbeats[i] - heartbeats[i - 1] > 300) gaps.push([heartbeats[i - 1], heartbeats[i]])
    }
    return { mounted, gaps, hbCount: heartbeats.length, firstHb: heartbeats[0], lastHb: heartbeats.at(-1) }
  })

  console.log('点击墙钟时间:', clickAt)
  console.log('消息挂载相对时刻(ms):', result.mounted)
  console.log('心跳空洞(>300ms):', JSON.stringify(result.gaps))
  console.log('心跳数量:', result.hbCount, '范围:', result.firstHb, '-', result.lastHb)
  console.log('API timing:')
  for (const item of reqTiming) {
    const t = item.timing
    const total = t.receiveHeadersEnd > 0 ? Math.round(t.receiveHeadersEnd) : null
    console.log(`  ${item.status} ${item.url} 总耗时≈${total}ms (dns=${Math.round(t.dnsEnd || 0)}, connect=${Math.round(t.connectEnd || 0)}, send=${Math.round(t.sendEnd || 0)}, resp=${total})`)
  }
} finally {
  await browser.close()
}
