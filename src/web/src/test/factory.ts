import type { Job } from '../types'

export function makeJob(overrides: Partial<Job> = {}): Job {
  return {
    id: 'job-1',
    prompt: 'cars',
    status: 'pending',
    mask_count: null,
    processing_ms: null,
    uploaded_at: new Date().toISOString(),
    completed_at: null,
    error: null,
    raw_url: 'http://localhost:9000/raw/job-1.png',
    annotated_url: null,
    ...overrides,
  }
}
