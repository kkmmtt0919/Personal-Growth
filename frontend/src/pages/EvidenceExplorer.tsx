import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { loadEvidence } from '../api/growth'
import { EvidenceChain } from '../components/EvidenceChain'
import type { Evidence } from '../types/growth'

export function EvidenceExplorer() {
  const { capabilityId = '' } = useParams()
  const [evidence, setEvidence] = useState<Evidence>()
  const [error, setError] = useState('')
  useEffect(() => { loadEvidence(capabilityId).then(setEvidence).catch((reason: Error) => setError(reason.message)) }, [capabilityId])
  if (error) return <p>{error}</p>
  return evidence ? <EvidenceChain evidence={evidence} /> : <p>加载中</p>
}
