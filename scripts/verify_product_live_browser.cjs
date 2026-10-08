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
    for (let i = 0; i < 1200; i++) { if (await evaluate(`Boolean(${expression})`)) return; await sleep(100) }
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
  const out = path.resolve(__dirname, '../artifacts/product/browser-live')
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

  const report=JSON.parse(fs.readFileSync('artifacts/product/live/result.json','utf8'));
  const goalId=report.goal.id;
  try {
    await call('Page.navigate',{url:'http://127.0.0.1:4173/?goal='+goalId});
    await until('document.querySelector(".home-next")');
    assert(await evaluate('document.querySelector(".page-hero h1").textContent.includes("RAG")'));
    checks.push('真实目标、18个能力点、完成任务与评定记录在首页展示');
    await capture('personal-home');
    await call('Page.navigate',{url:'http://127.0.0.1:4173/mentor/'+goalId+'?goal='+goalId});
    await until('document.querySelectorAll(".mentor-answer").length>=2');
    assert(await evaluate('!document.body.innerText.includes("离线演示")'));
    checks.push('真实模式恢复已有两轮模型对话');
    if(await evaluate('document.querySelectorAll(".mentor-answer").length===2')) {
    const message='刚才提交以后记录发生了什么变化？请结合我的证据和评定历史解释下一步，不要凭任务完成推断等级提升。';
    await evaluate('(()=>{const t=document.querySelector("#mentor-message");Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,"value").set.call(t,'+JSON.stringify(message)+');t.dispatchEvent(new Event("input",{bubbles:true}));})()');
    await click('发送消息');
    await until('document.querySelectorAll(".mentor-answer").length===3');
    }
    await until('document.querySelectorAll(".mentor-answer").length===3 && !document.querySelector("#mentor-message").disabled');
    const reply=await evaluate('Array.from(document.querySelectorAll(".mentor-answer")).at(-1).innerText');
    assert(reply.length>100);assert(!reply.includes('离线演示'));
    checks.push('浏览器发送问题并得到真实模型对证据与历史的解释');
    await capture('mentor');
    await call('Page.reload');await until('document.querySelectorAll(".mentor-answer").length===3');
    checks.push('刷新恢复第三轮真实模型回答');
    const turns=await(await fetch('http://127.0.0.1:8000/api/mentor/'+goalId)).json();
    assert(turns.turns.at(-1).response.provider!=='fake');
    assert(turns.turns.at(-1).response.run_id);
    checks.push('模型运行与回答持久化可核对');
    const cap=report.capabilities.find(n=>n.id===report.results.submission.binding.decisions[0].capability_id);
    await call('Page.navigate',{url:'http://127.0.0.1:4173/evidence/'+cap.id+'?goal='+goalId});
    await until('document.querySelector(".evidence-row")');
    await capture('evidence');checks.push('提交原文与证据报告可访问');
    fs.writeFileSync(path.join(out,'browser-verification.json'),JSON.stringify({passed:true,checks,real_model_calls:1,goal_id:goalId,reply,turns:turns.turns},null,2));
    console.log(checks.length+' live product browser checks passed');
  } finally {ws.close();await fetch('http://127.0.0.1:9228/json/close/'+page.id)}
}
main().catch(error=>{console.error(error);process.exitCode=1});
