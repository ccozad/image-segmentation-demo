import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { HistoryList } from '../components/HistoryList'
import { makeJob } from './factory'

const noop = () => {}

describe('HistoryList', () => {
  it('renders an empty state with no jobs', () => {
    render(<HistoryList jobs={[]} onSelect={noop} onDelete={noop} />)
    expect(screen.getByText(/no images yet/i)).toBeInTheDocument()
  })

  it('shows prompt, status badge, and mask count/time for a done job', () => {
    const job = makeJob({
      id: 'j2',
      prompt: 'people',
      status: 'done',
      mask_count: 4,
      processing_ms: 1500,
    })
    render(<HistoryList jobs={[job]} onSelect={noop} onDelete={noop} />)

    expect(screen.getByText('people')).toBeInTheDocument()
    expect(screen.getByText('Done')).toBeInTheDocument()
    expect(screen.getByText('4 masks')).toBeInTheDocument()
    expect(screen.getByText(/1\.5 s/)).toBeInTheDocument()
    expect(screen.getByAltText(/upload for/i)).toBeInTheDocument()
  })

  it('exposes the failure reason on the failed badge', () => {
    const job = makeJob({ status: 'failed', error: 'inference failed: boom' })
    render(<HistoryList jobs={[job]} onSelect={noop} onDelete={noop} />)
    expect(screen.getByText('Failed')).toHaveAttribute('title', 'inference failed: boom')
  })

  it('calls onSelect when the row is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    render(<HistoryList jobs={[makeJob({ id: 'j9' })]} onSelect={onSelect} onDelete={noop} />)
    await user.click(screen.getAllByRole('button')[0]) // first button is the row
    expect(onSelect).toHaveBeenCalledWith('j9')
  })

  it('calls onDelete (not onSelect) when the delete button is clicked', async () => {
    const user = userEvent.setup()
    const onSelect = vi.fn()
    const onDelete = vi.fn()
    render(
      <HistoryList jobs={[makeJob({ id: 'j9', prompt: 'cars' })]} onSelect={onSelect} onDelete={onDelete} />,
    )
    await user.click(screen.getByRole('button', { name: /delete cars/i }))
    expect(onDelete).toHaveBeenCalledWith('j9')
    expect(onSelect).not.toHaveBeenCalled()
  })
})
