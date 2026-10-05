import { useEffect, useState } from 'react'
import { useParams } from 'react-router-dom'
import { loadEvidence } from '../api/growth'
import { EvidenceChain } from '../components/EvidenceChain'
import { PageState } from '../components/PageState'
import type { Evidence } from '../types/growth'

export function EvidenceExplorer() {
  const { capabilityId = '' } = useParams()
  const [result, setResult] = useState<{ id: string; evidence?: Evidence; error?: string }>()
  useEffect(() => {
    let active = true
    loadEvidence(capabilityId).then(evidence => { if (active) setResult({ id: capabilityId, evidence }) })
      .catch((reason: Error) => { if (active) setResult({ id: capabilityId, error: reason.message }) })
    return () => { active = false }
  }, [capabilityId])
  if (result?.id !== capabilityId) return <PageState />
  if (result.error) return <PageState error={result.error} />
  return result.evidence ? <EvidenceChain evidence={result.evidence} /> : <PageState />
}
