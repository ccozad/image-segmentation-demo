import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ImageDetailView } from '../components/ImageDetailView'
import { makeJob } from './factory'

describe('ImageDetailView', () => {
  it('shows a polling indicator while processing instead of the annotation', () => {
    render(<ImageDetailView job={makeJob({ status: 'processing' })} onBack={() => {}} />)
    expect(screen.getByRole('status')).toHaveTextContent(/segmenting/i)
    expect(screen.queryByAltText(/segmentation of/i)).not.toBeInTheDocument()
  })

  it('shows the annotated image when done', () => {
    const job = makeJob({
      status: 'done',
      mask_count: 2,
      annotated_url: 'http://localhost:9000/annotated/job-1.png',
    })
    render(<ImageDetailView job={job} onBack={() => {}} />)
    expect(screen.getByAltText(/segmentation of/i)).toBeInTheDocument()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('shows the error reason when failed', () => {
    const job = makeJob({ status: 'failed', error: 'inference failed: boom' })
    render(<ImageDetailView job={job} onBack={() => {}} />)
    expect(screen.getAllByText(/inference failed: boom/i).length).toBeGreaterThan(0)
  })

  it('calls onBack from the back link', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()
    render(<ImageDetailView job={makeJob()} onBack={onBack} />)
    await user.click(screen.getByRole('button', { name: /back to history/i }))
    expect(onBack).toHaveBeenCalled()
  })
})
