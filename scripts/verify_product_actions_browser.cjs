const fs = require('node:fs')
const path = require('node:path')
const assert = require('node:assert/strict')
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms))

async function main() {
  const page = await (await fetch('http://127.0.0.1:9228/json/new?about:blank', { method: 'PUT' })).json()
  const ws = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise(resolve => ws.addEventListener('open', resolve, { once: true }))
  let id = 0
  let loads = 0
  const pending = new Map()
  const consoleErrors = []
  ws.addEventListener('message', ({ data }) => {
    const r = JSON.parse(data), waiter = pending.get(r.id)
    if (r.method === "Page.loadEventFired") loads++
    if (r.method === "Runtime.consoleAPICalled" && r.params.type === "error") consoleErrors.push(r.params.args.map(item=>item.value ?? item.description).join(" "))
    if (r.method === "Runtime.exceptionThrown") consoleErrors.push(r.params.exceptionDetails.text)
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
    for (let i = 0; i < 100; i++) { if (await evaluate(`Boolean(${expression})`)) return; await sleep(100) }
    throw new Error(`Timed out: ${expression}`)
  }
  const reload = async () => { const before = loads; await call("Page.reload"); for(let i=0;i<100;i++){if(loads>before)return;await sleep(100)}throw new Error("Reload did not finish") }
  const click = async text => {
    await until(`Array.from(document.querySelectorAll('button')).some(b=>b.textContent===${JSON.stringify(text)} && !b.disabled)`)
    return evaluate(`Array.from(document.querySelectorAll('button')).find(b=>b.textContent===${JSON.stringify(text)}).click()`)
  }
  const fill = async text => {
    await until('document.querySelector("#goal-text") && !document.querySelector("#goal-text").disabled')
    return evaluate(`(() => { const t=document.querySelector('#goal-text'); Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,${JSON.stringify(text)});t.dispatchEvent(new Event('input',{bubbles:true})); })()`)
  }
  const out = path.resolve(__dirname, '../artifacts/product/browser-actions')
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
  await call("Page.enable")
  await call("Runtime.enable")
  const title = '受控浏览器：成为AI应用工程师 ' + Date.now()
  try {
    await call('Page.navigate', { url: 'http://127.0.0.1:5173/' })
    await until('document.body.innerText.includes("从你的目标开始")')
    assert(await evaluate('!document.body.innerText.includes("RAG 实践")'))
    checks.push('空库首页引导新用户，未展示Demo能力')
    await capture('empty-home')
    await call('Page.navigate', { url: 'http://127.0.0.1:5173/start' })
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
        await reload()
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
    await reload()
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
    await reload()
    await until('document.querySelectorAll(".onboarding-tree article").length === 21')
    checks.push('实际目标URL刷新恢复能力树')
    await capture('tree')
    const goalId = await evaluate('new URL(location.href).searchParams.get("goal")')
    await call('Page.navigate', { url: `http://127.0.0.1:5173/?goal=${goalId}` })
    await until('document.querySelector("#capability-map") && document.querySelector(".home-next")')
    assert(await evaluate(`document.querySelector('.page-hero h1').textContent===${JSON.stringify(title)}`))
    checks.push('真实目标个人首页、能力地图与下一步')
    await capture('personal-home')
    await evaluate(`Array.from(document.querySelectorAll('a')).find(a=>a.textContent==='AI 导师').click()`)
    await until('document.querySelector("#mentor-message")')
    await evaluate('document.querySelector(".mentor-preference summary").click()')
    const fillSelector = async (selector, value) => {
      await until(`document.querySelector(${JSON.stringify(selector)}) && !document.querySelector(${JSON.stringify(selector)}).disabled`)
      await evaluate(`(() => {const t=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype,'value').set.call(t,${JSON.stringify(value)});t.dispatchEvent(new Event('input',{bubbles:true}));})()`)
    }
    await fillSelector('#mentor-preference', '偏好代码实践，先看架构')
    await click('保存偏好')
    await until('document.body.innerText.includes("偏好已保存")')
    checks.push('用户显式保存长期学习偏好')
    for (const [index, message] of ['我现在应该先做什么？', '沿着刚才的建议具体一些。'].entries()) {
      await fillSelector('#mentor-message', message)
      await click('发送消息')
      await until(`document.querySelectorAll('.mentor-answer').length===${index + 1} && Array.from(document.querySelectorAll('.mentor-answer')).every(n=>n.innerText.includes('离线演示'))`)
      checks.push(`导师第${index + 1}轮可见且清楚标注离线演示`)
    }
    await reload()
    await until('document.querySelectorAll(".mentor-turn").length===2')
    await until('document.querySelector("#mentor-preference").value.includes("偏好代码实践")')
    checks.push('刷新恢复连续对话与偏好')
    await capture('mentor')
    await evaluate(`Array.from(document.querySelectorAll('a')).find(a=>a.textContent==='返回个人首页 ↗').click()`)
    await until('document.querySelector(".home-next")')
    checks.push('导师返回实际目标个人首页')

    await call('Page.navigate',{url:'http://127.0.0.1:5173/mentor/'+goalId+'?goal='+goalId});
    await until('document.querySelector(".mentor-task-planner summary")');
    await evaluate('document.querySelector(".mentor-task-planner summary").click()');
    await click('核对任务生成');
    assert(await evaluate('document.querySelector(".action-review").innerText.includes("实践任务")'));
    checks.push('导师生成任务前显示能力/维度确认');
    await click('确认生成任务');await until('document.body.innerText.includes("已保存任务：")');
    checks.push('确认后生成任务，未自动启动');
    const beforeTask=await (await fetch('http://127.0.0.1:8000/api/growth-loop/'+goalId)).json();
    assert(beforeTask.tasks.length===1&&beforeTask.tasks[0].status==='proposed');
    await click('核对任务生成');await click('确认生成任务');await until('!document.querySelector(".action-review")');
    const afterTask=await (await fetch('http://127.0.0.1:8000/api/growth-loop/'+goalId)).json();
    assert(afterTask.tasks.length===1&&afterTask.tasks[0].id===beforeTask.tasks[0].id);
    checks.push('重复确认复用未完成任务');
    await capture('mentor-task');
    await evaluate('Array.from(document.querySelectorAll("a")).find(a=>a.textContent==="查看并启动任务 ↗").click()');
    await until('document.body.innerText.includes("开始任务")');
    checks.push('生成结果可进入任务页');
    await call('Page.navigate',{url:'http://127.0.0.1:5173/start?goal='+goalId});
    await until('document.querySelectorAll(".onboarding-tree article").length===21');
    const firstCap=await evaluate('document.querySelector(".capability-depth-3 select").id.replace("level-", "")');
    await evaluate('Array.from(document.querySelectorAll(".capability-depth-3 summary")).find(n=>n.textContent==="调整此能力的目标要求").click()');
    await evaluate('(()=>{const t=document.querySelector(".capability-depth-3 select");Object.getOwnPropertyDescriptor(HTMLSelectElement.prototype,"value").set.call(t,"5");t.dispatchEvent(new Event("change",{bubbles:true}));})()');
    await fillSelector('#note-'+firstCap,'把重点能力要求提高到高级岗位标准');
    await click('核对要求调整');
    assert(await evaluate('document.querySelector(".action-review").innerText.includes("3 → 5")'));
    await click('确认调整要求');await until('document.body.innerText.includes("目标要求已调整并记录理由")');
    assert(await evaluate('document.querySelector(".capability-depth-3").innerText.includes("理解：未知 · 实践：未知")'));
    checks.push('能力要求显式确认、记录理由且未抬高当前等级');
    await capture('capability-adjustment');
    await reload();await until('document.querySelectorAll(".onboarding-tree article").length===21');
    assert(await evaluate('document.querySelector(".capability-depth-3").innerText.includes("目标要求 5")'));
    checks.push('刷新保留调整后的目标要求');
    await call('Page.navigate',{url:'http://127.0.0.1:5173/?goal='+goalId});await until('document.querySelector(".goal-revision summary")');
    await evaluate('document.querySelector(".goal-revision summary").click()');
    await fillSelector('#revision-text','转向AI测试工程师，六个月完成两份测试报告');
    await click('核对目标调整');await click('确认开始调整');
    await until('document.body.innerText.includes("这是调整后的目标版本")');
    const childId=await evaluate('new URL(location.href).searchParams.get("goal")');assert(childId!==goalId);
    assert(await evaluate('!document.querySelector(".onboarding-tree")'));
    checks.push('目标调整建立需澄清的新版本，不继承旧能力等级');
    await capture('goal-revision');
    await evaluate('Array.from(document.querySelectorAll("a")).find(a=>a.textContent==="查看保留的原目标 →").click()');
    await until('document.querySelectorAll(".onboarding-tree article").length===21');
    assert(await evaluate('document.body.innerText.includes("目标要求 5")'));
    checks.push('新版本可返回原目标，原能力树和调整仍保留');
    const saved=await (await fetch('http://127.0.0.1:8000/api/product/goals/'+goalId+'/actions')).json();
    assert(saved.actions.length===2);
    checks.push('目标调整与能力要求操作历史均可核对');
    assert.deepEqual(consoleErrors, []);checks.push('全旅程无浏览器异常或React重复键错误');
    fs.writeFileSync(path.join(out, 'browser-verification.json'), JSON.stringify({ passed: true, checks, mode: 'fixed_questions', real_model_calls: 0, console_errors: consoleErrors, goal_id: goalId, revision_goal_id: childId }, null, 2))
    console.log(`${checks.length} onboarding browser checks passed`)
  } finally { ws.close(); await fetch(`http://127.0.0.1:9228/json/close/${page.id}`) }
}
main().catch(error => { console.error(error); process.exitCode = 1 })

