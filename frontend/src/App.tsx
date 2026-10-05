import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { Dashboard } from './pages/Dashboard'
import { EvidenceExplorer } from './pages/EvidenceExplorer'
import { GrowthLoop } from './pages/GrowthLoop'

export default function App() {
  return (
    <BrowserRouter>
      <header>
        <strong>Growth OS</strong>
        <nav><NavLink to="/">能力</NavLink><NavLink to="/growth/goal_demo">任务</NavLink></nav>
      </header>
      <Routes>
        <Route path="/" element={<Dashboard />} />
        <Route path="/evidence/:capabilityId" element={<EvidenceExplorer />} />
        <Route path="/growth/:goalId" element={<GrowthLoop />} />
      </Routes>
    </BrowserRouter>
  )
}
