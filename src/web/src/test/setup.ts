import '@testing-library/jest-dom/vitest'

// jsdom doesn't implement object URLs; stub for the optimistic-upload thumbnail.
if (!('createObjectURL' in URL)) {
  // @ts-expect-error test stub
  URL.createObjectURL = () => 'blob:stub'
}
