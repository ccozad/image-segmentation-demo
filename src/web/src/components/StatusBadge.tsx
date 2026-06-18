import type { JobStatus } from '../types'

const LABELS: Record<JobStatus, string> = {
  pending: 'Pending',
  processing: 'Processing',
  done: 'Done',
  failed: 'Failed',
}

interface Props {
  status: JobStatus
  /** Failure reason; shown on hover for failed jobs. */
  title?: string | null
}

export function StatusBadge({ status, title }: Props) {
  return (
    <span
      className={`badge badge-${status}`}
      title={status === 'failed' ? (title ?? 'Failed') : undefined}
    >
      {LABELS[status]}
    </span>
  )
}
