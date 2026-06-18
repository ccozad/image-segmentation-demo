import { useRef, useState } from 'react'

const ACCEPTED = 'image/jpeg,image/png,image/webp'
const PLACEHOLDERS = ['cars', 'red balloons', 'people']

interface Props {
  onUpload: (file: File, prompt: string) => Promise<void>
}

export function UploadForm({ onUpload }: Props) {
  const [file, setFile] = useState<File | null>(null)
  const [prompt, setPrompt] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const placeholder = `e.g. ${PLACEHOLDERS.join(', ')}`
  const ready = file !== null && prompt.trim().length > 0 && !submitting

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault()
    if (!ready || !file) return
    setSubmitting(true)
    setError(null)
    try {
      await onUpload(file, prompt.trim())
      setFile(null)
      setPrompt('')
      if (fileInput.current) fileInput.current.value = ''
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Upload failed')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit} aria-label="Upload image">
      <div className="field">
        <label htmlFor="file">Image</label>
        <input
          id="file"
          ref={fileInput}
          type="file"
          accept={ACCEPTED}
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
      </div>
      <div className="field">
        <label htmlFor="prompt">Concept prompt</label>
        <input
          id="prompt"
          type="text"
          value={prompt}
          placeholder={placeholder}
          onChange={(e) => setPrompt(e.target.value)}
        />
      </div>
      <button type="submit" disabled={!ready}>
        {submitting ? 'Uploading…' : 'Segment'}
      </button>
      {error && (
        <p className="form-error" role="alert">
          {error}
        </p>
      )}
    </form>
  )
}
