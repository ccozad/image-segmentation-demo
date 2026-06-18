export type JobStatus = 'pending' | 'processing' | 'done' | 'failed'

export interface Job {
  id: string
  prompt: string
  status: JobStatus
  mask_count: number | null
  processing_ms: number | null
  uploaded_at: string
  completed_at: string | null
  error: string | null
  raw_url: string | null
  annotated_url: string | null
}

export const IN_FLIGHT: JobStatus[] = ['pending', 'processing']

export function isInFlight(status: JobStatus): boolean {
  return IN_FLIGHT.includes(status)
}
