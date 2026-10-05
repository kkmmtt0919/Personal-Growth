import { useEffect } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { EvidenceExplorer } from './pages/EvidenceExplorer'
import { GrowthLoop } from './pages/GrowthLoop'

function RouteScroll() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

export default function App() {
  return <BrowserRouter>
    <RouteScroll />
    <a className="skip-link" href="#main-content">跳至主要内容</a>
    <header className="site-header">
      <NavLink className="brand" to="/" aria-label="Growth OS 首页"><svg viewBox="0 0 42 30" aria-hidden="true"><path d="M0 28 15 2 30 28Z M23 12 30 0 42 22 34 28Z" fill="currentColor" /></svg><strong>Growth OS</strong></NavLink>
      <nav aria-label="主导航"><NavLink to="/" end>总览</NavLink><Link to="/#capability-map">能力</Link><NavLink to="/growth/goal_demo">任务</NavLink></nav>
      <span className="demo-badge" title="受控 Demo，不代表真实用户成果">DEMO</span>
    </header>
    <div id="main-content" tabIndex={-1}><Routes>
      <Route path="/" element={<Dashboard />} />
      <Route path="/evidence/:capabilityId" element={<EvidenceExplorer />} />
      <Route path="/growth/:goalId" element={<GrowthLoop />} />
    </Routes></div>
    <footer className="site-footer">受控 Demo · 示例数据，不代表真实用户成果</footer>
  </BrowserRouter>
}
