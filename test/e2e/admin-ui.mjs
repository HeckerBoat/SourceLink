/**
 * 管理后台 UI 流程验证：登录 -> 资源新建/删除 -> 站点配置 -> 访问记录，全程截图。
 * 运行：node test/e2e/admin-ui.mjs
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
const errors = []

try {
  const page = await browser.newPage()
  await page.setViewport({ width: 1440, height: 900 })
  page.on('console', (m) => m.type() === 'error' && errors.push(m.text()))
  page.on('pageerror', (e) => errors.push(`pageerror: ${e.message}`))

  await page.goto(`${BASE}/#/login`, { waitUntil: 'networkidle2' })
  await page.waitForSelector('input[placeholder*="用户名"]')
  await page.type('input[placeholder*="用户名"]', 'admin')
  await page.type('input[type="password"]', '1q2w3e4r')
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('登')).click(),
  )
  await page.waitForFunction(() => location.hash.includes('/admin/resources'), { timeout: 10000 })
  await sleep(1200)
  await page.screenshot({ path: 'test/e2e/shot-admin-resources.png' })
  console.log('资源管理行数:', await page.$$eval('.el-table__body-wrapper tr', (els) => els.length))

  // 新建资源块
  await page.evaluate(() =>
    [...document.querySelectorAll('button')].find((b) => b.textContent.includes('新建资源块')).click(),
  )
  await page.waitForSelector('.el-dialog')
  await sleep(400)
  await page.type('input[placeholder="请输入资源名称"]', 'E2E浏览器验证资源')
  await page.type('.el-dialog textarea', '由 puppeteer 自动化创建')
  // 对话框内文本输入框顺序：资源名称、网盘链接、购买链接
  const textInputs = await page.$$('.el-dialog input[type="text"]')
  await textInputs[1].type('https://pan.example.com/e2e')
  await textInputs[2].type('https://buy.example.com/e2e')
  await page.type('.el-dialog input[type="password"]', 'e2e-pass')
  await sleep(200)
  await page.screenshot({ path: 'test/e2e/shot-admin-create.png' })
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-dialog button')].find((b) => b.textContent.trim() === '保存').click(),
  )
  await sleep(1200)
  const created = await page.evaluate(() =>
    [...document.querySelectorAll('.el-table__body-wrapper tr')].some((tr) => tr.textContent.includes('E2E浏览器验证资源')),
  )
  console.log('新建后表格含目标行:', created)
  await page.screenshot({ path: 'test/e2e/shot-admin-after-create.png' })

  // 删除该资源
  await page.evaluate(() => {
    const row = [...document.querySelectorAll('.el-table__body-wrapper tr')].find((tr) =>
      tr.textContent.includes('E2E浏览器验证资源'),
    );
    [...row.querySelectorAll('button')].find((b) => b.textContent.includes('删除')).click();
  })
  await page.waitForSelector('.el-message-box', { timeout: 5000 })
  await sleep(300)
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-message-box__btns button')]
      .find((b) => b.textContent.trim() === '删除')
      .click(),
  )
  await sleep(1200)
  const deleted = await page.evaluate(() =>
    [...document.querySelectorAll('.el-table__body-wrapper tr')].every((tr) => !tr.textContent.includes('E2E浏览器验证资源')),
  )
  console.log('删除后表格不含目标行:', deleted)

  // 站点配置
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-menu-item')].find((b) => b.textContent.includes('站点配置')).click(),
  )
  await sleep(1000)
  const cfg = await page.evaluate(() => ({
    siteName: document.querySelector('input')?.value,
    switches: [...document.querySelectorAll('.el-switch')].map((s) => s.classList.contains('is-checked')),
  }))
  console.log('站点配置回显:', JSON.stringify(cfg))
  await page.screenshot({ path: 'test/e2e/shot-admin-settings.png' })

  // 访问记录
  await page.evaluate(() =>
    [...document.querySelectorAll('.el-menu-item')].find((b) => b.textContent.includes('访问记录')).click(),
  )
  await sleep(1000)
  const logRows = await page.$$eval('.el-table__body-wrapper tr', (els) => els.length)
  const tags = await page.$$eval('.el-table__body-wrapper .el-tag', (els) =>
    els.map((e) => e.textContent.trim()),
  )
  console.log('访问记录行数:', logRows, '标签集合:', JSON.stringify([...new Set(tags)]))
  await page.screenshot({ path: 'test/e2e/shot-admin-logs.png' })

  console.log('---- 全程 console/page 错误 ----')
  console.log(errors.length ? errors.join('\n') : '(无)')
} finally {
  await browser.close()
}
