import { useCallback, useEffect, useMemo } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useDeliveryDays, useForecast } from '../api/hooks'
import { ForecastChart } from '../charts/ForecastChart'
import { VintagePanel } from '../charts/VintagePanel'
import { Async, ChartCard, Kpi } from '../components/ui'
import { addDays, fmtDay, fmtGwh, fmtInstant, fmtMw } from '../lib/format'

// A symmetric central band of `c` covers P(50 + 50c) on the upper side.
const coveragePct = (c: number | null | undefined) => Math.round(50 + 50 * (c ?? 0))

export function DecisionPage() {
  const [params, setParams] = useSearchParams()
  const days = useDeliveryDays()
  const list = useMemo(() => days.data?.days.map((d) => d.date) ?? [], [days.data])
  const first = list[0]
  const last = list.at(-1)
  const date = params.get('date') ?? last
  const hour = params.get('hour') ?? undefined
  const showActual = params.get('actual') !== '0'
  const forecast = useForecast(date)

  const update = useCallback(
    (patch: Record<string, string | null>) =>
      setParams((p) => {
        const n = new URLSearchParams(p)
        for (const [k, v] of Object.entries(patch)) {
          if (v === null) n.delete(k)
          else n.set(k, v)
        }
        return n
      }),
    [setParams],
  )
  const go = useCallback(
    (delta: number) => {
      if (!date) return
      const next = addDays(date, delta)
      if (list.includes(next)) update({ date: next, hour: null })
    },
    [date, list, update],
  )

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.target as HTMLElement).tagName === 'INPUT') return
      if (e.key === 'ArrowLeft') go(-1)
      if (e.key === 'ArrowRight') go(1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [go])

  const onSelect = useCallback((iso: string) => update({ hour: iso }), [update])

  return (
    <>
      <header className="page-head">
        <div>
          <h1>Tomorrow’s wind, as you’d have known it</h1>
          <p className="muted">
            Pick a delivery day to see the latest wind forecast available at bid time, and how much
            to trust it.
          </p>
        </div>
        <nav className="date-nav" aria-label="Delivery day">
          <button
            onClick={() => go(-1)}
            disabled={!date || date === first}
            aria-label="Previous day"
          >
            ←
          </button>
          <input
            type="date"
            value={date ?? ''}
            min={first}
            max={last}
            aria-label="Delivery date"
            onChange={(e) =>
              list.includes(e.target.value) && update({ date: e.target.value, hour: null })
            }
          />
          <button onClick={() => go(1)} disabled={!date || date === last} aria-label="Next day">
            →
          </button>
        </nav>
      </header>

      {days.isError && (
        <div className="banner error" role="alert">
          {days.error.message}
        </div>
      )}

      <Async query={forecast}>
        {(f) => (
          <>
            <div className="banner info">
              <strong>Decision cutoff: {fmtInstant(f.cutoff_time)}.</strong> Delivery day{' '}
              {fmtDay(f.delivery_date)}. Only forecasts published up to that moment are shown.
            </div>
            {f.summary.hours_missing > 0 && (
              <div className="banner warn" role="status">
                {f.summary.hours_missing} hour(s) had no forecast published before the cutoff.
              </div>
            )}
            <div className="kpis">
              <Kpi
                label="Expected wind energy"
                value={fmtGwh(f.summary.energy_mwh)}
                hint={`Avg ${fmtMw(f.summary.mean_mw)}`}
              />
              <Kpi label="Peak" value={fmtMw(f.summary.peak_mw)} />
              <Kpi label="Trough" value={fmtMw(f.summary.trough_mw)} />
              {f.risk.available ? (
                <Kpi
                  label="Suggested buffer"
                  value={fmtMw(f.risk.suggested_buffer_mw)}
                  tone="warn"
                  hint={`Wind fell short of forecast by no more than this in ${coveragePct(f.risk.confidence)}% of past hours`}
                />
              ) : (
                <Kpi label="Suggested buffer" value="–" hint="Not enough history yet" />
              )}
            </div>
            {!f.risk.available && (
              <div className="banner info">Risk band hidden: {f.risk.reason}</div>
            )}

            <ChartCard
              title="Hourly forecast at the cutoff"
              question="How much wind should I expect tomorrow, and how wrong could it be?"
              table={{
                head: ['Hour', 'Forecast MW', 'Range low', 'Range high', 'Actual MW'],
                rows: f.points.map((p) => [
                  p.start_time.slice(11, 16),
                  p.forecast_mw ?? '–',
                  Math.round(p.band_lower_mw ?? NaN) || '–',
                  Math.round(p.band_upper_mw ?? NaN) || '–',
                  p.actual_mw ?? '–',
                ]),
              }}
            >
              <label className="toggle">
                <input
                  type="checkbox"
                  checked={showActual}
                  onChange={(e) => update({ actual: e.target.checked ? null : '0' })}
                />
                Show actual generation
              </label>
              <ForecastChart
                points={f.points}
                showActual={showActual}
                selected={hour}
                onSelect={onSelect}
              />
            </ChartCard>
          </>
        )}
      </Async>
      <VintagePanel target={hour} />
    </>
  )
}
