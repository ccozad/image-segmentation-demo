import { afterEach, describe, expect, it, vi } from 'vitest'

import { getImage, listImages, uploadImage } from '../api/client'

afterEach(() => {
  vi.restoreAllMocks()
})

function mockFetch(body: unknown, ok = true, status = 200) {
  const fetchMock = vi.fn().mockResolvedValue({
    ok,
    status,
    json: async () => body,
  } as Response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

describe('apiClient', () => {
  it('uploadImage posts multipart form to /images', async () => {
    const fetchMock = mockFetch({ job_id: 'abc', status: 'pending' })
    const file = new File([new Uint8Array([1, 2, 3])], 'x.png', { type: 'image/png' })

    const res = await uploadImage(file, 'cars')

    expect(res).toEqual({ job_id: 'abc', status: 'pending' })
    const [url, init] = fetchMock.mock.calls[0]
    expect(String(url)).toMatch(/\/images$/)
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('prompt')).toBe('cars')
  })

  it('listImages requests the history with a limit', async () => {
    const fetchMock = mockFetch([])
    await listImages(25)
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/images\?limit=25$/)
  })

  it('getImage requests a single job', async () => {
    const fetchMock = mockFetch({ id: 'job-1' })
    await getImage('job-1')
    expect(String(fetchMock.mock.calls[0][0])).toMatch(/\/images\/job-1$/)
  })

  it('throws on a non-ok response', async () => {
    mockFetch({}, false, 500)
    await expect(listImages()).rejects.toThrow(/list failed \(500\)/)
  })
})
