// Read-only browser checks and screenshots for the Growth OS redesign.
// Requires the frontend at :4173, return Demo at :8000, base Demo at :8001,
// and a headless Edge DevTools endpoint at :9228.
const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const pause = ms => new Promise(resolve => setTimeout(resolve, ms))

async function main() {
  const directory = path.resolve(__dirname, '../artifacts/frontend-redesign')
  fs.mkdirSync(directory, { recursive: true })
  const capabilities = await (await fetch('http://127.0.0.1:8000/api/goals/goal_demo/capabilities')).json()
  const growth = await (await fetch('http://127.0.0.1:8000/api/growth-loop/goal_demo')).json()
  const returned = await (await fetch('http://127.0.0.1:8000/api/return-demo/goal_demo')).json()
  const capabilityId = capabilities.capabilities[0].id
  const taskId = growth.tasks[0].id
  const page = await (await fetch('http://127.0.0.1:9228/json/new?about:blank', { method: 'PUT' })).json()
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }) })
  let sequence = 0
  let mode = 'live'
  const pending = new Map()
  const errors = []
  const requests = []
  const checks = []
  const screenshots = []
  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = ++sequence
      pending.set(id, { resolve, reject })
      ws.send(JSON.stringify({ id, method, params }))
    })
  }
  async function handleRequest(params) {
    requests.push({ mode, url: params.request.url })
    const url = new URL(params.request.url)
    const endpoint = url.pathname
    if (mode === 'live') return call('Fetch.continueRequest', { requestId: params.requestId })
    if (mode === 'loading') { await pause(600); return call('Fetch.continueRequest', { requestId: params.requestId }) }
    if (mode === 'error') return call('Fetch.fulfillRequest', { requestId: params.requestId, responseCode: 503, body: Buffer.from('{}').toString('base64'), responseHeaders: [{ name: 'Access-Control-Allow-Origin', value: '*' }] })
    const response = await fetch('http://127.0.0.1:' + (mode === 'base' ? '8001' : '8000') + endpoint)
    let body = await response.text()
    let code = response.status
    if (mode !== 'base') {
      if (endpoint.includes('/capabilities')) {
        if (mode === 'empty') body = JSON.stringify({ capabilities: [] })
        else body = JSON.stringify({ capabilities: [
          { id: 'fixture_complete', name: '已达标能力（测试）', target_level: 4, understanding: 4, practice: 4, open_gaps: [] },
          ...(mode === 'achieved' ? [] : capabilities.capabilities),
          ...(mode === 'achieved' ? [] : [{ id: 'fixture_unknown', name: '未评估能力（测试）', target_level: 4, understanding: null, practice: null, open_gaps: [] }]),
          ...(mode === 'many' ? Array.from({ length: 7 }, (_, i) => ({ id: 'fixture_' + i, name: '多能力布局验证 / ' + i, target_level: 4, understanding: 2, practice: 3, open_gaps: [] })) : []),
        ] })
      }
      if (endpoint.includes('/growth-loop')) body = JSON.stringify({ tasks: mode === 'empty' ? [] : mode === 'active' ? [{ ...growth.tasks[0], id: 'fixture-active', status: 'active', attribution: null, submissions: [] }] : growth.tasks })
      if (endpoint.includes('/return-demo')) {
        if (mode === 'recommended') body = JSON.stringify({ ...returned, report: { ...returned.report, next_steps: [{ gap_id: 'fixture-gap', task_id: taskId }] } })
        else { body = '{}'; code = 404 }
      }
      if (mode === 'empty' && endpoint.includes('/evidence/')) body = JSON.stringify({ capability: '空证据测试', assessment: { understanding: null, practice: null }, supports: [], gaps: [] })
    }
    return call('Fetch.fulfillRequest', {
      requestId: params.requestId, responseCode: code, body: Buffer.from(body).toString('base64'),
      responseHeaders: [{ name: 'Content-Type', value: 'application/json' }, { name: 'Access-Control-Allow-Origin', value: '*' }],
    })
  }
  ws.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data)
    if (message.method === 'Fetch.requestPaused') handleRequest(message.params).catch(error => errors.push(error.message))
    if (message.method === 'Runtime.exceptionThrown') errors.push(message.params.exceptionDetails.text + ' ' + (message.params.exceptionDetails.exception?.description ?? ''))
    const request = pending.get(message.id)
    if (!request) return
    pending.delete(message.id)
    if (message.error) request.reject(new Error(JSON.stringify(message.error)))
    else request.resolve(message.result)
  })
  async function evaluate(expression) {
    const response = await call('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
    if (response.exceptionDetails) throw new Error(JSON.stringify(response.exceptionDetails))
    return response.result.value
  }
  async function waitFor(expression) {
    for (let i = 0; i < 100; i++) {
      if (await evaluate(expression)) return
      await pause(60)
    }
    throw new Error('Timed out: ' + expression + '\n' + await evaluate('document.body.textContent') + '\n' + JSON.stringify(requests))
  }
  async function navigate(route = '/', selector = '.map-workspace') {
    await call('Page.navigate', { url: 'http://127.0.0.1:4173' + route })
    await waitFor('Boolean(document.querySelector(' + JSON.stringify(selector) + '))')
    await pause(90)
  }
  function check(name, value) { assert.ok(value, name); checks.push({ name, passed: true }) }
  async function screenshot(name) {
    const dimensions = await evaluate('({width: innerWidth, scrollWidth: document.documentElement.scrollWidth, height: innerHeight})')
    check(name + ': no horizontal overflow', dimensions.scrollWidth <= dimensions.width)
    const layout = await call('Page.getLayoutMetrics')
    const content = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true, clip: { x: 0, y: 0, width: dimensions.width, height: layout.cssContentSize.height, scale: 1 } })
    fs.writeFileSync(path.join(directory, name + '.png'), Buffer.from(content.data, 'base64'))
    screenshots.push({ name, ...dimensions })
  }
  try {
    await call('Page.enable'); await call('Runtime.enable')
    await call('Fetch.enable', { patterns: [{ urlPattern: '*:8000/api/*', requestStage: 'Request' }] })
    for (const width of [1440, 1024, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: width === 390 ? 2100 : 1100, deviceScaleFactor: 1, mobile: false })
      await navigate()
      check('real data only at ' + width, await evaluate('document.querySelectorAll("[data-capability]").length') === capabilities.capabilities.length)
      check('return summary at ' + width, await evaluate('document.querySelector(".return-summary").innerText.includes("核对这份摘要的来源")'))
      await screenshot('dashboard-' + width)
      await evaluate('document.querySelector(".summary-sources").open = true')
      check('source trace preserved', await evaluate('document.querySelector(".summary-sources").innerText.includes("后快照")'))
      await evaluate('document.querySelector(".capability-detail .text-link").click()')
      await waitFor('Boolean(document.querySelector(".evidence-section"))')
      check('evidence route at ' + width, await evaluate('location.pathname') === '/evidence/' + capabilityId)
      await screenshot('evidence-' + width)
      await navigate()
      await evaluate('document.querySelector(".capability-detail .primary").click()')
      await waitFor('Boolean(document.querySelector(".task-article"))')
      check('task anchor and focus at ' + width, await evaluate('location.hash === ' + JSON.stringify('#task-' + taskId) + ' && document.activeElement.id === ' + JSON.stringify('task-' + taskId)))
      await screenshot('tasks-' + width)
    }
    await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1100, deviceScaleFactor: 1, mobile: false })
    mode = 'base'
    await navigate()
    check('base Demo without return data', await evaluate('document.querySelector(".return-summary").innerText.includes("暂无返回摘要")'))
    await screenshot('base-dashboard')
    mode = 'multi'
    await navigate()
    check('default selects first gap', await evaluate('document.querySelector("[aria-pressed=true]").textContent.includes("RAG")'))
    await call('Page.bringToFront')
    await evaluate('window.scrollTo(0, 100); document.querySelector("[data-capability]:last-child").focus({preventScroll: true})')
    check('keyboard focus reaches capability', await evaluate('document.activeElement.textContent.includes("未评估能力")'))
    const before = await evaluate('scrollY')
    await call('Input.dispatchKeyEvent', { type: 'rawKeyDown', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await call('Input.dispatchKeyEvent', { type: 'char', text: '\r', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await call('Input.dispatchKeyEvent', { type: 'keyUp', key: 'Enter', code: 'Enter', windowsVirtualKeyCode: 13 })
    await waitFor('document.querySelector(".inspector h2").textContent.includes("未评估能力")')
    check('keyboard selection preserves scroll', await evaluate('scrollY') === before)
    check('selection stays on same route', await evaluate('location.pathname') === '/')
    check('unassessed values and no task', await evaluate('document.querySelector(".inspector").innerText.includes("未评估") && document.querySelector(".inspector").innerText.includes("尚未生成关联任务")'))
    check('unknown is not displayed as zero meter', await evaluate('document.querySelectorAll(".inspector [role=meter]").length') === 0)
    await evaluate('document.querySelector(".page-hero .primary").click()')
    await waitFor('location.hash === "#capability-detail" && document.activeElement.id === "capability-detail"')
    check('next step without task focuses detail', true)
    await navigate()
    await evaluate('document.querySelector("[data-capability]").click()')
    await waitFor('document.querySelector(".inspector h2").textContent.includes("已达标能力")')
    check('achieved skill status', await evaluate('document.querySelector("[data-capability]").innerText.includes("已达标")'))
    await screenshot('multiple-capabilities')
    mode = 'recommended'
    await navigate()
    check('recommended task wins over completed fallback', await evaluate('document.querySelector(".page-hero .primary").getAttribute("href")') === '/growth/goal_demo#task-' + taskId)
    mode = 'active'
    await navigate()
    check('selected capability active task fallback', await evaluate('document.querySelector(".page-hero .primary").getAttribute("href")') === '/growth/goal_demo#task-fixture-active')
    await evaluate('document.querySelector(".page-hero .primary").click()')
    await waitFor('Boolean(document.querySelector(".task-article"))')
    check('no submission or reassessment handled', await evaluate('document.querySelector(".task-article").innerText.includes("等待提交") && document.querySelector(".task-article").innerText.includes("等待重评")'))
    mode = 'achieved'
    await navigate()
    check('without gaps first capability is selected', await evaluate('document.querySelector("[aria-pressed=true]").textContent.includes("已达标能力")'))
    mode = 'empty'
    await navigate()
    check('empty capability and summary handled', await evaluate('document.querySelector(".inspector").innerText.includes("尚无能力记录") && document.querySelector(".return-summary").innerText.includes("暂无返回摘要")'))
    await navigate('/growth/goal_demo', '.task-stages, .empty-state')
    check('empty tasks handled', await evaluate('document.body.innerText.includes("暂无成长任务")'))
    await navigate('/evidence/' + capabilityId, '.evidence-section')
    check('empty evidence handled', await evaluate('document.body.innerText.includes("尚无支持证据")'))
    mode = 'many'
    for (const width of [1440, 1024, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: 1100, deviceScaleFactor: 1, mobile: false })
      await navigate()
      check('many skills no overflow at ' + width, await evaluate('document.documentElement.scrollWidth <= innerWidth'))
    }
    mode = 'error'
    for (const route of ['/', '/growth/goal_demo', '/evidence/' + capabilityId]) {
      await navigate(route, '[role=alert]')
      check('error state ' + route, await evaluate('document.body.innerText.includes("暂时无法读取数据") && document.querySelector("button").textContent.includes("重新加载")'))
    }
    mode = 'live'
    await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1000, deviceScaleFactor: 1, mobile: false })
    await call('Emulation.setEmulatedMedia', { features: [{ name: 'prefers-reduced-motion', value: 'reduce' }] })
    await navigate()
    check('reduced motion respected', await evaluate('getComputedStyle(document.querySelector(".button")).transitionDuration') === '0s')
    check('document language is Chinese', await evaluate('document.documentElement.lang') === 'zh-CN')
    mode = 'loading'
    await navigate('/', '[role=status]')
    check('loading state is visible', await evaluate('document.body.innerText.includes("正在整理成长记录")'))
    await waitFor('Boolean(document.querySelector(".map-workspace"))')
    mode = 'error'
    await navigate('/', '[role=alert]')
    mode = 'live'
    await evaluate('document.querySelector(".page-state button").click()')
    await waitFor('Boolean(document.querySelector(".map-workspace"))')
    check('retry recovers after service becomes available', true)
    check('no browser runtime errors', errors.length === 0)
    fs.writeFileSync(path.join(directory, 'verification.json'), JSON.stringify({ checks, screenshots, browserErrors: errors, fixtureNote: 'Only real Demo data in dashboard/evidence/tasks/base screenshots. Multi/empty/many/error/recommended/active checks use response fixtures.' }, null, 2) + '\n')
    console.log(JSON.stringify({ passed: checks.length, screenshots: screenshots.length, browserErrors: errors }))
  } finally {
    await call('Page.close')
    ws.close()
  }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
