import { addDays, biasShare, fmtInstant, fmtMw, signed } from './format'

describe('format', () => {
  it('formats missing values as a dash, never NaN', () => {
    expect(fmtMw(null)).toBe('–')
    expect(signed(undefined)).toBe('–')
  })
  it('adds a sign to positive values', () => {
    expect(signed(1748.4)).toBe('+1,748 MW')
    expect(signed(-20)).toBe('-20 MW')
  })
  it('shifts dates across month boundaries without timezone drift', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
    expect(addDays('2026-01-01', -1)).toBe('2025-12-31')
  })
  it('renders the cutoff in London time', () => {
    expect(fmtInstant('2026-01-14T09:00:00Z')).toContain('09:00')
    expect(fmtInstant('2026-07-01T08:00:00Z')).toContain('09:00') // BST
  })
  it('computes bias share, guarding division by zero', () => {
    expect(biasShare(50, 100)).toBe(50)
    expect(biasShare(500, 100)).toBe(100)
    expect(biasShare(1, 0)).toBeNull()
  })
})
