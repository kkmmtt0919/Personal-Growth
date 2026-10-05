export function PageState({ error }: { error?: string }) {
  return <main className="page-state" role={error ? 'alert' : 'status'}>
    <p className="eyebrow">GROWTH OS / {error ? 'UNAVAILABLE' : 'LOADING'}</p>
    <h1>{error ? '暂时无法读取数据' : '正在整理成长记录…'}</h1>
    <p>{error ? '请确认本地服务已启动，再重试。' : '能力、证据和任务即将呈现。'}</p>
    {error && <><details><summary>查看错误详情</summary><p>{error}</p></details><button className="button primary" onClick={() => window.location.reload()}>重新加载 ↗</button></>}
  </main>
}
