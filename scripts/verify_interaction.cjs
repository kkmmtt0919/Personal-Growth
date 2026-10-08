const fs = require('node:fs')
const assert = require('node:assert/strict')
const path = require('node:path')
const sleep = ms => new Promise(r => setTimeout(r, ms))

async function main() {
  const page = await (await fetch('http://127.0.0.1:9228/json/new?about:blank', { method: 'PUT' })).json()
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise(r => ws.addEventListener('open', r, { once: true }))
  let id = 0
  const pending = new Map()
  ws.addEventListener('message', ({ data }) => {
    const message = JSON.parse(data)
    const p = pending.get(message.id)
    if (p) { pending.delete(message.id); message.error ? p.reject(message.error) : p.resolve(message.result) }
  })
  const call = (method, params = {}) => new Promise((resolve, reject) => {
    pending.set(++id, { resolve, reject }); ws.send(JSON.stringify({ id, method, params }))
  })
  const evaluate = async expression => {
    const r = await call('Runtime.evaluate', { expression, returnByValue: true })
    if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
    return r.result.value
  }
  async function until(expression) {
    for (let i = 0; i < 100; i++) {
      if (await evaluate(expression)) return
      await sleep(100)
    }
    throw new Error(`Timed out: ${expression}`)
  }
  const button = label => `Array.from(document.querySelectorAll('button')).find(b=>b.textContent===${JSON.stringify(label)}).click()`
  const directory = path.resolve(__dirname, '../artifacts/interaction')
  const fileMode = process.argv.includes('--files')
  fs.mkdirSync(directory, { recursive: true })
  try {
    await call('Page.enable')
    await call('Emulation.setDeviceMetricsOverride', { width: 1440, height: 1500, deviceScaleFactor: 1, mobile: false })
    await call('Page.navigate', { url: 'http://127.0.0.1:4173/growth/goal_demo' })
    if (fileMode) {
      await until(`document.body.innerText.includes('开始任务')`)
      await evaluate(button('开始任务'))
      await until(`Boolean(document.querySelector('input[type="file"]'))`)
      assert.equal(await evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent==='提交文件并重评').disabled`), true)
      const fixture = path.resolve(__dirname, '../tmp/file-browser/upload-report.md')
      fs.mkdirSync(path.dirname(fixture), { recursive: true })
      fs.writeFileSync(fixture, '# 受控 RAG 评测报告\n\n十条检索样本，引用对应来源，无匹配则报告不足。\n')
      const root = await call('DOM.getDocument')
      const input = await call('DOM.querySelector', { nodeId: root.root.nodeId, selector: 'input[type="file"]' })
      await call('DOM.setFileInputFiles', { nodeId: input.nodeId, files: [fixture] })
      await until(`document.body.innerText.includes('已选择：upload-report.md')`)
      async function capture(prefix) {
        for (const width of [1440, 390]) {
          await call('Emulation.setDeviceMetricsOverride', { width, height: 1500, deviceScaleFactor: 1, mobile: false })
          await sleep(200)
          assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true)
          const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
          fs.writeFileSync(path.join(directory, `${prefix}-${width}.png`), Buffer.from(screenshot.data, 'base64'))
        }
      }
      await capture('file-form')
      await evaluate(button('提交文件并重评'))
      await until(`Array.from(document.querySelectorAll('.level-change')).some(p=>/3\\s*→\\s*4/.test(p.textContent))`)
      await call('Page.reload')
      await until(`Array.from(document.querySelectorAll('.level-change')).some(p=>/3\\s*→\\s*4/.test(p.textContent))`)
      assert.equal(await evaluate(`document.querySelectorAll('input[type="file"]').length`), 0)
      assert.equal(await evaluate(`document.body.innerText.includes('理解等级：2 → 2')`), true)
      await capture('file-result')
      fs.writeFileSync(path.join(directory, 'file-browser-verification.json'), JSON.stringify({
        passed: true, checks: ['activate_practice', 'empty_selection_disabled', 'native_file_selection',
          'upload_complete', 'practice_3_to_4', 'understanding_unchanged', 'reload_persistence',
          'completed_form_hidden', 'desktop_form_no_overflow', 'mobile_form_no_overflow',
          'desktop_result_no_overflow', 'mobile_result_no_overflow'], constructed: true, real_model_calls: 0,
      }, null, 2))
      console.log('12 file browser checks passed')
      return
    }
    await until(`document.body.innerText.includes('开始任务')`)
    await evaluate(button('开始任务'))
    await until(`document.body.innerText.includes('提交并重评')`)
    await evaluate(button('标记受阻'))
    await until(`document.body.innerText.includes('请先填写')`)
    await evaluate(`(() => { const t=document.querySelector('[id^="reason-"]'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,'需要补充失败案例');t.dispatchEvent(new Event('input',{bubbles:true})); })()`)
    await evaluate(button('标记受阻'))
    await until(`document.body.innerText.includes('恢复任务')`)
    await evaluate(button('恢复任务'))
    await until(`Boolean(document.querySelector('[id^="answer-"]'))`)
    for (const width of [1440, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: 1500, deviceScaleFactor: 1, mobile: false })
      await sleep(200)
      assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true)
      const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      fs.writeFileSync(path.join(directory, `form-${width}.png`), Buffer.from(screenshot.data, 'base64'))
    }
    await evaluate(`(() => { const t=document.querySelector('[id^="answer-"]'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,'RAG先检索再生成，重排提升相关性。引用须对应来源，无匹配时报告证据不足。');t.dispatchEvent(new Event('input',{bubbles:true})); })()`)
    await evaluate(button('提交并重评'))
    await until(`document.body.innerText.includes('理解等级：2 → 3')`)
    await call('Page.reload')
    await until(`document.body.innerText.includes('理解等级：2 → 3')`)
    assert.equal(await evaluate(`document.querySelectorAll('[id^="answer-"]').length`), 0)
    for (const width of [1440, 390]) {
      await call('Emulation.setDeviceMetricsOverride', { width, height: 1500, deviceScaleFactor: 1, mobile: false })
      await sleep(200)
      assert.equal(await evaluate('document.documentElement.scrollWidth <= innerWidth'), true)
      const screenshot = await call('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true })
      fs.writeFileSync(path.join(directory, `submission-${width}.png`), Buffer.from(screenshot.data, 'base64'))
    }
    fs.writeFileSync(path.join(directory, 'browser-verification.json'), JSON.stringify({
      passed: true, checks: ['activate', 'required_reason', 'block', 'resume', 'submit', 'understanding_2_to_3', 'reload_persistence', 'hide_completed_form', 'desktop_no_overflow', 'mobile_no_overflow', 'desktop_form_no_overflow', 'mobile_form_no_overflow'], constructed: true, real_model_calls: 0,
    }, null, 2))
    console.log('12 browser checks passed')
  } finally { ws.close(); await fetch(`http://127.0.0.1:9228/json/close/${page.id}`) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })
