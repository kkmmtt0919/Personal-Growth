export interface Goal { id: string; title: string; status: string }
export interface Capability { id: string; name: string; target_level: number; understanding: number | null; practice: number | null; open_gaps: { dimension: string; severity: string }[] }
export interface Evidence { capability: string; assessment: { understanding: number | null; practice: number | null }; supports: { claim_id: string; source: { name: string | null; type: string | null }; quote: { text: string | null; locator: unknown }; binding_reason: string }[]; gaps: string[] }
export interface GrowthTask { id: string; title: string; status: string; submissions: { source_id: string }[] }
