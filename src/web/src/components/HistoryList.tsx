import type { Job } from '../types'
import { formatDuration, relativeTime } from '../format'
import { StatusBadge } from './StatusBadge'

interface Props {
  jobs: Job[]
  onSelect: (id: string) => void
}

export function HistoryList({ jobs, onSelect }: Props) {
  if (jobs.length === 0) {
    return <p className="empty">No images yet — upload one above to get started.</p>
  }

  return (
    <ul className="history" aria-label="Upload history">
      {jobs.map((job) => (
        <li key={job.id}>
          <button className="history-row" onClick={() => onSelect(job.id)}>
            {job.raw_url ? (
              <img className="thumb" src={job.raw_url} alt={`Upload for “${job.prompt}”`} />
            ) : (
              <span className="thumb thumb-placeholder" aria-hidden="true" />
            )}
            <span className="history-main">
              <span className="history-prompt">{job.prompt}</span>
              <span className="history-meta">
                {job.status === 'done' && (
                  <>
                    <span>{job.mask_count} masks</span>
                    {formatDuration(job.processing_ms) && (
                      <span>· {formatDuration(job.processing_ms)}</span>
                    )}
                    <span>· </span>
                  </>
                )}
                <span>{relativeTime(job.uploaded_at)}</span>
              </span>
            </span>
            <StatusBadge status={job.status} title={job.error} />
          </button>
        </li>
      ))}
    </ul>
  )
}
