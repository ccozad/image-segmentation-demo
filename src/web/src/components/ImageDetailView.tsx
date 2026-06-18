import type { Job } from '../types'
import { formatDuration, relativeTime } from '../format'
import { isInFlight } from '../types'
import { StatusBadge } from './StatusBadge'

interface Props {
  job: Job
  onBack: () => void
}

export function ImageDetailView({ job, onBack }: Props) {
  const inFlight = isInFlight(job.status)

  return (
    <section className="detail" aria-label={`Details for ${job.prompt}`}>
      <button className="back" onClick={onBack}>
        ← Back to history
      </button>

      <header className="detail-header">
        <h2>{job.prompt}</h2>
        <StatusBadge status={job.status} title={job.error} />
      </header>

      <div className="detail-images">
        <figure>
          <figcaption>Original</figcaption>
          {job.raw_url ? (
            <img src={job.raw_url} alt={`Original upload for “${job.prompt}”`} />
          ) : (
            <div className="placeholder">No image</div>
          )}
        </figure>
        <figure>
          <figcaption>Annotated</figcaption>
          {inFlight ? (
            <div className="placeholder polling" role="status">
              <span className="spinner" aria-hidden="true" />
              {job.status === 'pending' ? 'Waiting to process…' : 'Segmenting…'}
            </div>
          ) : job.status === 'failed' ? (
            <div className="placeholder error">{job.error ?? 'Segmentation failed'}</div>
          ) : job.annotated_url ? (
            <img src={job.annotated_url} alt={`Segmentation of “${job.prompt}”`} />
          ) : (
            <div className="placeholder">No annotation</div>
          )}
        </figure>
      </div>

      <dl className="metadata">
        <dt>Status</dt>
        <dd>{job.status}</dd>
        <dt>Masks</dt>
        <dd>{job.mask_count ?? '—'}</dd>
        <dt>Processing time</dt>
        <dd>{formatDuration(job.processing_ms) ?? '—'}</dd>
        <dt>Uploaded</dt>
        <dd>{relativeTime(job.uploaded_at)}</dd>
        <dt>Completed</dt>
        <dd>{job.completed_at ? relativeTime(job.completed_at) : '—'}</dd>
        {job.status === 'failed' && job.error && (
          <>
            <dt>Error</dt>
            <dd className="error-text">{job.error}</dd>
          </>
        )}
      </dl>
    </section>
  )
}
