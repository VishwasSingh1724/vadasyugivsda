import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAccuracy, useDeliveryDays } from '../api/hooks'
import { ErrorHistogram } from '../charts/ErrorHistogram'
import { GroupChart, type Series } from '../charts/GroupChart'
import { Async, ChartCard, Kpi } from '../components/ui'
import { C } from '../lib/chartTheme'
import { biasShare, fmtMw, fmtPct, signed } from '../lib/format'
import type { Schemas } from '../api/client'

const MAE_BIAS: Series[] = [
  { field: 'mae_mw', label: 'Mean abs error', color: C.forecast, type: 'bar' },
  { field: 'bias_mw', label: 'Bias (fcst − actual)', color: C.over, type: 'bar' },
]
const toTable = (g: Schemas['AccuracyGroups']) => ({
  head: ['Group', 'Hours', 'MAE (MW)', 'Bias (MW)', 'P90 abs (MW)'],
  rows: g.groups.map((x) => [
    x.key,
    x.metrics.n,
    Math.round(x.metrics.mae_mw ?? 0),
    Math.round(x.metrics.bias_mw ?? 0),
    Math.round(x.metrics.p90_abs_mw ?? 0),
  ]),
})

export function AccuracyPage() {
  const [params, setParams] = useSearchParams()
  const navigate = useNavigate()
  const days = useDeliveryDays().data?.days
  const range = { from: params.get('from') ?? undefined, to: params.get('to') ?? undefined }
  const setRange = (k: 'from' | 'to', v: string) =>
    setParams((p) => {
      const n = new URLSearchParams(p)
      if (v) n.set(k, v)
      else n.delete(k)
      return n
    })
  const invalid = !!range.from && !!range.to && range.from > range.to

  const valid = invalid ? {} : range // never send an inverted range to the API
  const summary = useAccuracy('summary', valid)
  const daily = useAccuracy('daily', valid)
  const horizon = useAccuracy('by-horizon', valid)
  const hour = useAccuracy('by-hour', valid)
  const wind = useAccuracy('by-wind-level', valid)
  const errors = useAccuracy('errors', valid)

  return (
    <>
      <header className="page-head">
        <div>
          <h1>How good was the forecast?</h1>
          <p className="muted">
            Scored on the forecast you actually had at each cutoff, not the best one in hindsight.
            Error = forecast − actual, so positive means wind came in below the plan.
          </p>
        </div>
        <div className="date-nav" role="group" aria-label="Date range">
          <input
            type="date"
            aria-label="From"
            value={range.from ?? ''}
            min={days?.[0].date}
            max={days?.at(-1)?.date}
            onChange={(e) => setRange('from', e.target.value)}
          />
          <span className="muted">to</span>
          <input
            type="date"
            aria-label="To"
            value={range.to ?? ''}
            min={days?.[0].date}
            max={days?.at(-1)?.date}
            onChange={(e) => setRange('to', e.target.value)}
          />
          {(range.from || range.to) && <button onClick={() => setParams({})}>Reset</button>}
        </div>
      </header>
      {invalid && (
        <div className="banner warn" role="alert">
          “From” is after “to”. Showing the last valid range.
        </div>
      )}

      <Async query={summary}>
        {(s) => {
          const m = s.metrics
          const share = biasShare(m.bias_mw, m.mae_mw)
          return (
            <div className="kpis six">
              <Kpi
                label="Mean abs error"
                value={fmtMw(m.mae_mw)}
                hint={`${fmtPct(m.nmae_pct)} of avg wind`}
              />
              <Kpi label="RMSE" value={fmtMw(m.rmse_mw)} hint="Penalises big misses" />
              <Kpi
                label="Bias"
                value={signed(m.bias_mw)}
                tone={share && share > 60 ? 'warn' : undefined}
                hint={share ? `${Math.round(share)}% of MAE is one-directional` : undefined}
              />
              <Kpi
                label="P90 abs error"
                value={fmtMw(m.p90_abs_mw)}
                hint="9 in 10 hours miss by less"
              />
              <Kpi label="P99 abs error" value={fmtMw(m.p99_abs_mw)} hint="Rare worst case" />
              <Kpi label="Coverage" value={fmtPct(s.coverage_pct)} hint={`${m.n} hours scored`} />
            </div>
          )
        }}
      </Async>

      <div className="grid">
        <ChartCard
          title="Error by day"
          question="Which days hurt, and which way did we miss?"
          table={daily.data && toTable(daily.data)}
        >
          <Async query={daily}>
            {(d) => (
              <GroupChart
                groups={d.groups}
                series={[...MAE_BIAS]}
                label="Error by day"
                onSelect={(k) => navigate(`/decision?date=${k}`)}
              />
            )}
          </Async>
          <p className="muted small">Click a day to open its decision view.</p>
        </ChartCard>
        <ChartCard
          title="Error by forecast horizon"
          question="Does waiting for a fresher forecast help?"
          table={horizon.data && toTable(horizon.data)}
        >
          <Async query={horizon}>
            {(d) => <GroupChart groups={d.groups} series={MAE_BIAS} label="Error by horizon" />}
          </Async>
          <p className="muted small">
            All published revisions, grouped by how far ahead of the target hour they were made.
          </p>
        </ChartCard>
        <ChartCard
          title="Error by hour of day"
          question="Are some times of day riskier to buy?"
          table={hour.data && toTable(hour.data)}
        >
          <Async query={hour}>
            {(d) => <GroupChart groups={d.groups} series={MAE_BIAS} label="Error by hour of day" />}
          </Async>
        </ChartCard>
        <ChartCard
          title="Error by wind level"
          question="Is the forecast worse in calm or windy conditions?"
          table={wind.data && toTable(wind.data)}
        >
          <Async query={wind}>
            {(d) => <GroupChart groups={d.groups} series={MAE_BIAS} label="Error by wind level" />}
          </Async>
        </ChartCard>
        <ChartCard title="Error distribution" question="How big are the misses, and how lopsided?">
          <Async query={errors}>{(d) => <ErrorHistogram data={d} />}</Async>
          <p className="muted small">
            Right of zero: over-forecast (shortfall to cover). Left: under-forecast (surplus).
          </p>
        </ChartCard>
      </div>
    </>
  )
}
