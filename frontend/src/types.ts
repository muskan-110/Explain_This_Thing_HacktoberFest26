export type Language = 'en' | 'hi'

export interface Appliance {
  id: string
  name: string
  brand?: string
  model?: string
  type?: string
  has_knowledge?: boolean
  chunk_count?: number
}

export interface Card {
  button_name: string
  what_it_does: string
  try_this: string
  confidence: 'high' | 'medium' | 'low'
  source: 'knowledge_base' | 'general_knowledge'
  source_ref?: string | null
  safety_flag: boolean
  hindi_failed?: boolean
}

export interface ExplainResponse {
  request_id: string
  card: Card
  read_result?: {
    label_text?: string
    icon_description?: string
    looks_like?: string
  }
  retrieved_chunks?: { filename: string; heading: string; score: number }[]
  timings?: Record<string, number>
  mode?: string
  cropped_image_base64?: string | null
}

export interface Health {
  status: string
  ollama: boolean
  vision_model?: string
  embed_model?: string
}
