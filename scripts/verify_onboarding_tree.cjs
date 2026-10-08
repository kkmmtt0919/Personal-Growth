const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

async function main() {
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
  const until = async expression => {
    for (let i = 0; i < 100; i++) { if (await evaluate(expression)) return; await sleep(100) }
    throw new Error(`Timed out: ${expression}`)
  }
  const click = async text => {
    await until(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent===${JSON.stringify(text)} && !b.disabled)`)
    return evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent===${JSON.stringify(text)}).click()`)
  }
  const fill = async text => {
    await until('document.querySelector("#goal-text") && !document.querySelector("#goal-text").disabled')
    return evaluate(`(() => { const t=document.querySelector('#goal-text'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,${JSON.stringify(text)});t.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  }
  const out = path.resolve(__dirname, '../artifacts/onboarding/o2')
  fs.mkdirSync(out, { recursive: true })
  const checks = []
  async function capture(prefix) {
    for (const width of [1440, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: 1500, deviceScaleFactor: 1, mobile: false })
      await sleep(200)
      assert(await evaluate('document.documentElement.scrollWidth <= innerWidth'))
      const png = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      fs.writeFileSync(path.join(out, `${prefix}-${width}.png`), Buffer.from(png.data, 'base64'))
      checks.push(`${prefix}: ${width}px无溢出`)
    }
  }
  const title = '受控浏览器：成为AI应用工程师 ' + Date.now()
  try {
    await call('Page.navigate', { url: 'http://127.0.0.1:4173/start' })
    await until('document.body.innerText.includes("固定问句实验")')
    assert(await evaluate('document.querySelector("form button").disabled'))
    checks.push('空目标禁止提交')
    await fill(title); await click('开始澄清')
    await until('document.body.innerText.includes("你希望发展的具体方向是什么")')
    checks.push('创建目标并提问')
    for (const [index, answer] of ['AI应用开发', '求职', '六个月', '完成两个可演示项目'].entries()) {
      await fill(answer); await click('提交回答')
      await until(`document.querySelectorAll('.goal-turn').length === ${index + 2}`)
      checks.push(`保存第${index + 1}轮回答`)
      if (index === 1) {
        await call('Page.reload')
        await until(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent===${JSON.stringify(title)})`)
        await click(title)
        await until('document.querySelectorAll(".goal-turn").length === 3')
        checks.push('中途刷新恢复会话')
      }
    }
    assert(await evaluate('document.body.innerText.includes("待确认")'))
    assert(await evaluate('!document.body.innerText.includes("目标已确认并保存")'))
    checks.push('不自动确认')
    await capture('proposed')
    await fill('我确认以六个月内完成两个AI应用项目为目标'); await click('确认目标')
    await until('document.body.innerText.includes("目标已确认并保存")')
    assert(await evaluate('document.body.innerText.includes("确认原话：我确认以六个月内完成两个AI应用项目为目标")'))
    checks.push('显式确认并保留原话')
    await call('Page.reload')
    await until(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent===${JSON.stringify(title)})`)
    await click(title)
    await until('document.body.innerText.includes("目标已确认并保存")')
    assert(await evaluate('!document.querySelector("#goal-text")'))
    checks.push('确认结果刷新后仍可读')
    await click('生成结构演示模板')
    await until('document.querySelectorAll(".onboarding-tree article").length === 21')
    assert(await evaluate('document.querySelectorAll(".capability-depth-3").length === 12'))
    assert(await evaluate('document.body.innerText.includes("目标等级为占位值")'))
    assert(await evaluate('Array.from(document.querySelectorAll(".onboarding-tree article")).every(n=>n.innerText.includes("当前未知"))'))
    checks.push('显式生成三层树，来源与未知等级可见')
    assert(await evaluate('new URL(location.href).searchParams.get("goal").startsWith("goal_")'))
    await call('Page.reload')
    await until('document.querySelectorAll(".onboarding-tree article").length === 21')
    checks.push('实际目标URL刷新恢复能力树')
    await capture('tree')
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify({ passed: true, checks, mode: 'fixed_questions', real_model_calls: 0 }, null, 2))
    console.log(`${checks.length} onboarding browser checks passed`)
  } finally { ws.close(); await fetch(`http://127.0.0.1:9228/json/close/${page.id}`) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })

