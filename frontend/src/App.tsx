import { useEffect } from 'react'
import { BrowserRouter, Link, NavLink, Route, Routes, useLocation } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { EvidenceExplorer } from './pages/EvidenceExplorer'
import { GrowthLoop } from './pages/GrowthLoop'
import { Onboarding } from './pages/Onboarding'
import { Home } from './pages/Home'
import { Mentor } from './pages/Mentor'
import { useProduct } from './api/product'
import { ProductProvider } from './components/ProductProvider'

function RouteScroll() {
  const { pathname } = useLocation()
  useEffect(() => { window.scrollTo(0, 0) }, [pathname])
  return null
}

function ContextBadge() {
  const { product } = useProduct()
  const location = useLocation()
  const onboarding = location.pathname === '/start' || new URLSearchParams(location.search).has('goal')
  if (!product) return null
  if (product.enabled && location.pathname !== '/demo') return <span className="demo-badge">{product.mode === 'model' ? '模型' : '离线演示'}</span>
  return <span className="demo-badge" title={onboarding ? '本地目标澄清实验' : '受控 Demo，不代表真实用户成果'}>{onboarding ? '实验' : 'DEMO'}</span>
}

function PrimaryNavigation() {
  const { product } = useProduct()
  const location = useLocation()
  const goal = new URLSearchParams(location.search).get('goal')
  const onboarding = location.pathname === '/start' || !!goal
  if (product?.enabled && location.pathname !== '/demo') return <nav aria-label="主导航"><NavLink to={goal ? `/?goal=${goal}` : '/'} end>首页</NavLink><NavLink to={goal ? `/start?goal=${goal}` : '/start'}>目标与材料</NavLink>{goal && <><NavLink to={`/mentor/${goal}?goal=${goal}`}>导师</NavLink><NavLink to={`/growth/${goal}?goal=${goal}`}>任务</NavLink></>}</nav>
  return <nav aria-label="主导航">{!onboarding && <><NavLink to="/" end>总览</NavLink><Link to="/#capability-map">能力</Link><NavLink to="/growth/goal_demo">任务</NavLink></>}{goal && <NavLink to={`/growth/${goal}?goal=${goal}`}>任务</NavLink>}<NavLink to={goal ? `/start?goal=${goal}` : '/start'}>目标</NavLink></nav>
}

function Brand() {
  const { product } = useProduct()
  const location = useLocation()
  const onboarding = location.pathname === '/start' || new URLSearchParams(location.search).has('goal')
  return <NavLink className="brand" to={product?.enabled ? '/' : onboarding ? '/start' : '/'} aria-label="Growth OS 首页"><svg viewBox="0 0 42 30" aria-hidden="true"><path d="M0 28 15 2 30 28Z M23 12 30 0 42 22 34 28Z" fill="currentColor" /></svg><strong>Growth OS</strong></NavLink>
}

function ContextFooter() {
  const { product } = useProduct()
  const location = useLocation()
  const onboarding = location.pathname === '/start' || new URLSearchParams(location.search).has('goal')
  return <footer className="site-footer">{product?.enabled && location.pathname !== '/demo' ? '本地个人成长空间 · 等级依据已记录的证据' : onboarding ? '本地目标澄清实验 · 目标与回答来自你的输入' : '受控 Demo · 示例数据，不代表真实用户成果'}</footer>
}

export default function App() {
  return <ProductProvider><BrowserRouter>
    <RouteScroll />
    <a className="skip-link" href="#main-content">跳至主要内容</a>
    <header className="site-header">
      <Brand />
      <PrimaryNavigation />
      <ContextBadge />
    </header>
    <div id="main-content" tabIndex={-1}><Routes>
      <Route path="/" element={<Home />} />
      <Route path="/demo" element={<Dashboard />} />
      <Route path="/mentor/:goalId" element={<Mentor />} />
      <Route path="/evidence/:capabilityId" element={<EvidenceExplorer />} />
      <Route path="/growth/:goalId" element={<GrowthLoop />} />
      <Route path="/start" element={<Onboarding />} />
    </Routes></div>
    <ContextFooter />
  </BrowserRouter></ProductProvider>
}
