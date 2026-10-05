// 使用本机 Edge 的 DevTools 协议验证真实页面；无需浏览器依赖包。
const fs = require('node:fs')
const path = require('node:path')

async function main() {
  const page = await (await fetch('http://127.0.0.1:9227/json/new?about:blank', { method: 'PUT' })).json()
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { ws.addEventListener('open', resolve, { once: true }); ws.addEventListener('error', reject, { once: true }) })
  let id = 0
  const pending = new Map()
  const networkErrors = []
  const requests = new Map()
  ws.addEventListener('message', ({ data }) => {
    const response = JSON.parse(data)
    if (response.method === 'Network.requestWillBeSent') requests.set(response.params.requestId, { url: response.params.request.url, headers: response.params.request.headers })
    if (response.method === 'Network.loadingFailed') networkErrors.push({ ...response.params, request: requests.get(response.params.requestId) })
    const waiting = pending.get(response.id)
    if (!waiting) return
    pending.delete(response.id)
    if (response.error) waiting.reject(new Error(JSON.stringify(response.error)))
    else waiting.resolve(response.result)
  })
  function call(method, params = {}) {
    return new Promise((resolve, reject) => {
      const request = ++id
      pending.set(request, { resolve, reject })
      ws.send(JSON.stringify({ id: request, method, params }))
    })
  }
  const directory = path.resolve(__dirname, '../artifacts/gates/G6/screenshots')
  fs.mkdirSync(directory, { recursive: true })
  const measurements = []
  try {
    await call('Page.enable')
    await call('Runtime.enable')
    await call('Network.enable')
    for (const [name, width, height, expanded] of [
      ['return-desktop', 1280, 1300, false],
      ['return-mobile', 390, 1600, false],
      ['return-sources', 1280, 1700, true],
    ]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false })
      const navigation = await call('Page.navigate', { url: 'http://127.0.0.1:4173/' })
      if (navigation.errorText) throw new Error(navigation.errorText)
      let ready = false
      for (let i = 0; i < 100; i++) {
        const state = await call('Runtime.evaluate', { expression: 'Boolean(document.querySelector(".return-summary"))', returnByValue: true })
        if (state.result.value) { ready = true; break }
        await new Promise(resolve => setTimeout(resolve, 100))
      }
      if (!ready) {
        const diagnostic = await call('Runtime.evaluate', { expression: '({url: location.href, text: document.body.innerText})', returnByValue: true })
        throw new Error(`返回摘要未加载：${JSON.stringify({ page: diagnostic.result.value, networkErrors })}`)
      }
      if (expanded) await call('Runtime.evaluate', { expression: 'document.querySelector(".return-summary details").open = true' })
      const result = await call('Runtime.evaluate', {
        expression: '({viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth, headings: [...document.querySelectorAll(".return-summary h3")].map(e => e.textContent), text: document.querySelector(".return-summary").innerText})',
        returnByValue: true,
      })
      const measurement = { name, ...result.result.value }
      measurement.fitsWidth = measurement.scrollWidth <= width
      measurements.push(measurement)
      const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false })
      fs.writeFileSync(path.join(directory, `${name}.png`), Buffer.from(screenshot.data, 'base64'))
    }
    fs.writeFileSync(path.join(directory, 'viewport-checks.json'), JSON.stringify(measurements, null, 2) + '\n')
    console.log(JSON.stringify(measurements.map(({ name, viewport, scrollWidth, fitsWidth }) => ({ name, viewport, scrollWidth, fitsWidth }))))
    if (measurements.some(item => !item.fitsWidth)) process.exitCode = 1
  } finally {
    await call('Page.close')
    ws.close()
  }
}

main().catch(error => { console.error(error.message); process.exitCode = 1 })
