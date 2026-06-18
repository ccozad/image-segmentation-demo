import type { Job } from '../types'

// In the browser the API is reached on the host; override via VITE_API_URL
// (e.g. in prod). Defaults to the local compose port.
const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'

export interface UploadResponse {
  job_id: string
  status: string
}

async function asJson<T>(resp: Response, what: string): Promise<T> {
  if (!resp.ok) {
    throw new Error(`${what} failed (${resp.status})`)
  }
  return resp.json() as Promise<T>
}

export async function uploadImage(file: File, prompt: string): Promise<UploadResponse> {
  const form = new FormData()
  form.append('file', file)
  form.append('prompt', prompt)
  const resp = await fetch(`${BASE_URL}/images`, { method: 'POST', body: form })
  return asJson<UploadResponse>(resp, 'upload')
}

export async function listImages(limit = 50): Promise<Job[]> {
  const resp = await fetch(`${BASE_URL}/images?limit=${limit}`)
  return asJson<Job[]>(resp, 'list')
}

export async function getImage(id: string): Promise<Job> {
  const resp = await fetch(`${BASE_URL}/images/${encodeURIComponent(id)}`)
  return asJson<Job>(resp, 'get')
}

export const apiBaseUrl = BASE_URL
