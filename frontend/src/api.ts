import type { Appliance, ExplainResponse, Health, Language } from './types'

async function errorMessage(res: Response): Promise<string> {
  try {
    const data = await res.json()
    if (typeof data?.detail === 'string') return data.detail
    if (data?.detail) return JSON.stringify(data.detail)
  } catch {
    // body was not JSON
  }
  return `Server error (${res.status})`
}

async function request(input: string, init?: RequestInit): Promise<Response> {
  try {
    return await fetch(input, init)
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err
    throw new Error('Cannot reach the app server. Is the backend running on port 8000?')
  }
}

// Your backend already serves appliance files at /static/appliances/<id>/...
export const panelUrl = (applianceId: string) =>
  `/static/appliances/${encodeURIComponent(applianceId)}/panel.jpg`

export async function getAppliances(): Promise<Appliance[]> {
  const res = await request('/api/appliances')
  if (!res.ok) throw new Error(await errorMessage(res))
  const data = await res.json()
  return Array.isArray(data) ? data : (data.appliances ?? [])
}

export async function getHealth(): Promise<Health> {
  const res = await request('/api/health')
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export interface ExplainArgs {
  applianceId?: string | null
  applianceType?: string | null
  x: number
  y: number
  language: Language
  useKb: boolean
  question?: string
  image?: File | null
}

export async function explain(args: ExplainArgs, signal?: AbortSignal): Promise<ExplainResponse> {
  const form = new FormData()
  if (args.applianceId) form.append('appliance_id', args.applianceId)
  if (args.applianceType) form.append('appliance_type', args.applianceType)
  form.append('x', args.x.toFixed(4))
  form.append('y', args.y.toFixed(4))
  form.append('language', args.language)
  form.append('use_kb', String(args.useKb))
  if (args.question) form.append('question', args.question)
  if (args.image) form.append('image', args.image)

  const res = await request('/api/explain', { method: 'POST', body: form, signal })
  if (!res.ok) throw new Error(await errorMessage(res))
  return res.json()
}

export async function sendFeedback(requestId: string, helpful: boolean): Promise<void> {
  const res = await request('/api/feedback', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ request_id: requestId, helpful }),
  })
  if (!res.ok) throw new Error(await errorMessage(res))
}
