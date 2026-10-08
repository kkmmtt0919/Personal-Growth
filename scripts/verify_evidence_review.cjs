const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

async function main() {
  const caps = (await (await fetch('http://127.0.0.1:8000/api/goals/goal_m4d/capabilities')).json()).capabilities
  const page = await (await fetch('http://127.0.0.1:9228/json/new?about:blank', { method: 'PUT' })).json()
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }))
  let id = 0
  const pending = new Map()
  ws.addEventListener('message', ({ data }) => {
    const r = JSON.parse(data), waiter = pending.get(r.id)
    if (waiter) { pending.delete(r.id); r.error ? waiter.reject(r.error) : waiter.resolve(r.result) }
  })
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject }); ws.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async expression => {
    const r = await call('Runtime.evaluate', { expression, returnByValue: true })
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
    return r.result.value
  }
  const out = path.resolve(__dirname, '../artifacts/evidence-review')
  fs.mkdirSync(out, { recursive: true })
  const checks = []
  try {
    for (const name of ['受控攻击复核场景', '受控无攻击场景']) {
      const capability = caps.find(c => c.name === name)
      const evidence = await (await fetch(`http://127.0.0.1:8000/api/evidence/${capability.id}`)).json()
      fs.writeFileSync(path.join(out, name === '受控攻击复核场景' ? 'attack-api.json' : 'empty-api.json'), JSON.stringify(evidence, null, 2))
      await call('Page.navigate', { url: `http://127.0.0.1:4173/evidence/${capability.id}` })
      let ready = false
      for (let i = 0; i < 100; i++) {
        if (await evaluate('Boolean(document.querySelector(".assessment-details"))')) { ready = true; break }
        await sleep(100)
      }
      assert(ready)
      await evaluate('document.querySelectorAll(".assessment-details details").forEach(d=>d.open=true)')
      for (const text of ['反向证据', '已排除的证据', '规则版本', '报告不构成对系统整体评估可靠性的结论']) {
        assert(await evaluate(`document.body.innerText.includes(${JSON.stringify(text)})`)); checks.push(`${name}: ${text}`)
      }
      if (name === '受控攻击复核场景') {
        assert(await evaluate('document.body.innerText.includes("已失效")'))
        assert(await evaluate('document.body.innerText.includes("等级上限 2")'))
        const excluded = new Set(evidence.report.excluded.map(item => item.claim_id))
        assert(evidence.supports.every(item => !excluded.has(item.claim_id)))
        checks.push('裁决与封顶显示', '失效证据不列支持依据')
      } else {
        assert(await evaluate('document.body.innerText.includes("不能据此认定证据已通过攻击")'))
        assert(await evaluate('document.body.innerText.includes("尚无评定结果")'))
        checks.push('无攻击不伪报通过', '无评级不伪报零级')
      }
      for (const width of [1440, 390]) {
        await call('Emulation.setDeviceMetricsOverride', { width, height: 1500, deviceScaleFactor: 1, mobile: false })
        await sleep(200)
        assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'))
        const png = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
        fs.writeFileSync(path.join(out, `${name === '受控攻击复核场景' ? 'attack' : 'empty'}-${width}.png`), Buffer.from(png.data, 'base64'))
        checks.push(`${name}: ${width}px无溢出`)
      }
    }
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify({ passed: true, checks, constructed: true, real_model_calls: 0 }, null, 2))
    console.log(`${checks.length} evidence browser checks passed`)
  } finally { ws.close(); await fetch(`http://127.0.0.1:9228/json/close/${page.id}`) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
