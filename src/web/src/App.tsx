import { useCallback, useEffect, useMemo, useRef, useState } from 'react'

import { deleteImage, listImages, uploadImage } from './api/client'
import { HistoryList } from './components/HistoryList'
import { ImageDetailView } from './components/ImageDetailView'
import { UploadForm } from './components/UploadForm'
import type { Job } from './types'

const POLL_MS = 2000

// Stable signature: ignore presigned URLs (they change every poll) so we only
// re-render on a real state change.
function signature(jobs: Job[]): string {
  return JSON.stringify(
    jobs.map((j) => [
      j.id,
      j.status,
      j.mask_count,
      j.processing_ms,
      j.completed_at,
      j.error,
      j.prompt,
      j.uploaded_at,
    ]),
  )
}

let optimisticCounter = 0

export default function App() {
  const [jobs, setJobs] = useState<Job[]>([])
  const [optimistic, setOptimistic] = useState<Job[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const sigRef = useRef<string>('')

  useEffect(() => {
    let active = true
    async function poll() {
      try {
        const next = await listImages()
        if (!active) return
        const sig = signature(next)
        if (sig !== sigRef.current) {
          sigRef.current = sig
          setJobs(next)
        }
      } catch {
        // transient; next tick retries
      }
    }
    poll()
    const timer = setInterval(poll, POLL_MS)
    return () => {
      active = false
      clearInterval(timer)
    }
  }, [])

  // Drop optimistic rows once the server confirms the real job.
  const serverIds = useMemo(() => new Set(jobs.map((j) => j.id)), [jobs])
  const visible = useMemo(() => {
    const pending = optimistic.filter((o) => !serverIds.has(o.id))
    return [...pending, ...jobs].sort((a, b) => b.uploaded_at.localeCompare(a.uploaded_at))
  }, [optimistic, jobs, serverIds])

  const handleUpload = useCallback(async (file: File, prompt: string) => {
    // Optimistic: show a pending row immediately, before the server responds.
    const tempId = `optimistic-${optimisticCounter++}`
    const row: Job = {
      id: tempId,
      prompt,
      status: 'pending',
      mask_count: null,
      processing_ms: null,
      uploaded_at: new Date().toISOString(),
      completed_at: null,
      error: null,
      raw_url: URL.createObjectURL(file),
      annotated_url: null,
    }
    setOptimistic((prev) => [row, ...prev])
    try {
      const { job_id } = await uploadImage(file, prompt)
      // Re-key to the real id so the poll reconciles (and dedups) it.
      setOptimistic((prev) =>
        prev.map((o) => (o.id === tempId ? { ...o, id: job_id } : o)),
      )
    } catch (err) {
      setOptimistic((prev) =>
        prev.map((o) =>
          o.id === tempId
            ? { ...o, status: 'failed', error: err instanceof Error ? err.message : 'Upload failed' }
            : o,
        ),
      )
      throw err
    }
  }, [])

  const handleDelete = useCallback(
    async (id: string) => {
      // Optimistically drop it; clear the detail view if it was open.
      setJobs((prev) => prev.filter((j) => j.id !== id))
      setOptimistic((prev) => prev.filter((o) => o.id !== id))
      setSelectedId((cur) => (cur === id ? null : cur))
      try {
        await deleteImage(id)
      } catch {
        // If it failed, the next poll will bring it back.
      }
    },
    [],
  )

  const selected = selectedId ? visible.find((j) => j.id === selectedId) : undefined

  return (
    <div className="app">
      <header className="app-header">
        <h1>Image Segmentation Demo</h1>
        <p>Upload an image and a concept prompt; the worker highlights matching instances.</p>
      </header>

      {selected ? (
        <ImageDetailView
          job={selected}
          onBack={() => setSelectedId(null)}
          onDelete={handleDelete}
        />
      ) : (
        <>
          <UploadForm onUpload={handleUpload} />
          <HistoryList jobs={visible} onSelect={setSelectedId} onDelete={handleDelete} />
        </>
      )}
    </div>
  )
}
