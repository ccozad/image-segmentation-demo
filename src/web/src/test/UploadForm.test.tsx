import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { UploadForm } from '../components/UploadForm'

describe('UploadForm', () => {
  it('disables submit until both a file and a prompt are provided', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn().mockResolvedValue(undefined)
    render(<UploadForm onUpload={onUpload} />)

    const submit = screen.getByRole('button', { name: /segment/i })
    expect(submit).toBeDisabled()

    const file = new File([new Uint8Array([1])], 'x.png', { type: 'image/png' })
    await user.upload(screen.getByLabelText('Image'), file)
    expect(submit).toBeDisabled() // prompt still empty

    await user.type(screen.getByLabelText('Concept prompt'), 'cars')
    expect(submit).toBeEnabled()

    await user.click(submit)
    expect(onUpload).toHaveBeenCalledWith(file, 'cars')
  })

  it('does not submit a whitespace-only prompt', async () => {
    const user = userEvent.setup()
    const onUpload = vi.fn()
    render(<UploadForm onUpload={onUpload} />)

    const file = new File([new Uint8Array([1])], 'x.png', { type: 'image/png' })
    await user.upload(screen.getByLabelText('Image'), file)
    await user.type(screen.getByLabelText('Concept prompt'), '   ')

    expect(screen.getByRole('button', { name: /segment/i })).toBeDisabled()
  })
})
