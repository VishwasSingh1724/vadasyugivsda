import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, vi } from 'vitest'
import { createQueryClient } from '../api/queryClient'
import App from '../App'

// Recharts' ResponsiveContainer needs layout, which jsdom lacks.
vi.mock('recharts', async (orig) => ({
  ...(await orig<typeof import('recharts')>()),
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))

const days = {
  timezone: 'Europe/London',
  cutoff_local: '09:00',
  days: ['2026-01-02', '2026-01-03', '2026-01-04'].map((date) => ({
    date,
    cutoff_time: `${date}T09:00:00Z`,
    hours_with_forecast: 24,
    hours_with_actual: 24,
  })),
}
const point = (h: number) => ({
  start_time: `2026-01-04T${String(h).padStart(2, '0')}:00:00Z`,
  forecast_mw: 10000 + h * 100,
  actual_mw: null,
  publish_time: '2026-01-03T08:00:00Z',
  horizon_h: 20,
  band_lower_mw: null,
  band_upper_mw: null,
})
const forecast = (risk: object, missing = 0) => ({
  delivery_date: '2026-01-04',
  cutoff_time: '2026-01-03T09:00:00Z',
  timezone: 'Europe/London',
  points: Array.from({ length: 24 }, (_, h) => point(h)),
  summary: {
    mean_mw: 11150,
    peak_mw: 12300,
    trough_mw: 10000,
    energy_mwh: 267600,
    hours_missing: missing,
  },
  risk,
})

function mockApi(routes: Record<string, () => Response>) {
  routes = { '/auth/me': json({ username: 'desk' }), ...routes }
  const fetchMock = vi.fn(async (url: string) => {
    const path = Object.keys(routes).find((k) => url.includes(k))
    return path ? routes[path]() : new Response('{}', { status: 404 })
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}
const json =
  (body: unknown, status = 200) =>
  () =>
    new Response(JSON.stringify(body), { status })

function renderAt(path: string) {
  const client = createQueryClient({ noRetry: true })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}
afterEach(() => vi.unstubAllGlobals())

describe('Decision page', () => {
  it('shows the cutoff and KPIs for the URL date', async () => {
    const f = mockApi({
      '/delivery-days': json(days),
      '/forecast': json(
        forecast({ available: true, confidence: 0.8, history_days: 5, suggested_buffer_mw: 4100 }),
      ),
    })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByText(/Decision cutoff:/)).toHaveTextContent('09:00')
    expect(screen.getByText('4,100 MW')).toBeInTheDocument()
    expect(f).toHaveBeenCalledWith(
      expect.stringContaining('delivery_date=2026-01-04'),
      expect.anything(),
    )
  })

  it('explains why the risk band is hidden instead of leaving a blank', async () => {
    mockApi({
      '/delivery-days': json(days),
      '/forecast': json(forecast({ available: false, reason: 'Needs 3 complete prior days' })),
    })
    renderAt('/decision?date=2026-01-04')
    expect(
      await screen.findByText(/Risk band hidden: Needs 3 complete prior days/),
    ).toBeInTheDocument()
  })

  it('warns when hours have no usable forecast', async () => {
    mockApi({
      '/delivery-days': json(days),
      '/forecast': json(forecast({ available: false, reason: 'x' }, 2)),
    })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByRole('status')).toHaveTextContent('2 hour(s) had no forecast')
  })

  it('steps to the previous day and disables the boundary button', async () => {
    const f = mockApi({
      '/delivery-days': json(days),
      '/forecast': json(forecast({ available: false, reason: 'x' })),
    })
    renderAt('/decision?date=2026-01-03')
    await screen.findByText(/Decision cutoff:/)
    await userEvent.click(screen.getByLabelText('Previous day'))
    await waitFor(() =>
      expect(f).toHaveBeenCalledWith(
        expect.stringContaining('delivery_date=2026-01-02'),
        expect.anything(),
      ),
    )
    expect(screen.getByLabelText('Previous day')).toBeDisabled()
  })

  it('survives an error body that is not our envelope', async () => {
    mockApi({
      '/delivery-days': json(days),
      '/forecast': json({ detail: 'Not Found' }, 404),
    })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByRole('alert')).toHaveTextContent('Request failed (404)')
  })

  it('shows the API error message with its request id and a retry', async () => {
    mockApi({
      '/delivery-days': json(days),
      '/forecast': json(
        { error: { code: 'internal_error', message: 'Boom', request_id: 'abc123' } },
        500,
      ),
    })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByRole('alert')).toHaveTextContent('Boom')
    expect(screen.getByRole('alert')).toHaveTextContent('abc123')
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })
})

describe('Authentication', () => {
  const signedOut = () =>
    new Response(
      JSON.stringify({
        error: { code: 'unauthenticated', message: 'Sign in required', request_id: 'r1' },
      }),
      { status: 401 },
    )

  it('shows the sign-in form instead of the app when there is no session', async () => {
    mockApi({ '/auth/me': signedOut })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
    expect(screen.queryByText(/Decision cutoff/)).not.toBeInTheDocument()
  })

  it('rejects bad credentials with a clear message and stays on the form', async () => {
    mockApi({
      '/auth/me': signedOut,
      '/auth/login': () => signedOut(),
    })
    renderAt('/decision')
    await userEvent.type(await screen.findByLabelText('Username'), 'desk')
    await userEvent.type(screen.getByLabelText('Password'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect username or password.')
  })

  it('signs in, keeps the deep link, and loads the protected data', async () => {
    let signedIn = false
    mockApi({
      '/auth/me': () => (signedIn ? json({ username: 'desk' })() : signedOut()),
      '/auth/login': () => {
        signedIn = true
        return json({ username: 'desk' })()
      },
      '/delivery-days': json(days),
      '/forecast': json(forecast({ available: false, reason: 'x' })),
    })
    renderAt('/decision?date=2026-01-04')
    await userEvent.type(await screen.findByLabelText('Username'), 'desk')
    await userEvent.type(screen.getByLabelText('Password'), 'pw')
    await userEvent.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText(/Decision cutoff:/)).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign out' })).toBeInTheDocument()
  })

  it('returns to sign-in when the session expires mid-use (401 from a data call)', async () => {
    mockApi({ '/delivery-days': json(days), '/forecast': signedOut })
    renderAt('/decision?date=2026-01-04')
    expect(await screen.findByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })
})
