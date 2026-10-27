import { memo, useMemo } from 'react'
import {
  Area,
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Schemas } from '../api/client'
import { axisProps, C, gwTick } from '../lib/chartTheme'
import { fmtHour, fmtMw, signed } from '../lib/format'

type Point = Schemas['ForecastPoint']
interface Row {
  t: number
  iso: string
  forecast: number | null
  actual: number | null
  band: [number, number] | null
  error: number | null
}

export const toRows = (points: Point[]): Row[] =>
  points.map((p) => ({
    t: Date.parse(p.start_time),
    iso: p.start_time,
    forecast: p.forecast_mw,
    actual: p.actual_mw,
    band:
      p.band_lower_mw != null && p.band_upper_mw != null
        ? [p.band_lower_mw, p.band_upper_mw]
        : null,
    error: p.forecast_mw != null && p.actual_mw != null ? p.forecast_mw - p.actual_mw : null,
  }))

// Half an hour of slack each side so the first/last bar is centred inside the plot at any width.
const HALF_STEP = 30 * 60 * 1000
const HALF_STEP_DOMAIN: [(min: number) => number, (max: number) => number] = [
  (min) => min - HALF_STEP,
  (max) => max + HALF_STEP,
]

const ticks = (rows: Row[]) => rows.filter((_, i) => i % 3 === 0).map((r) => r.t)

function Tip({ active, payload }: { active?: boolean; payload?: { payload: Row }[] }) {
  const r = active ? payload?.[0]?.payload : undefined
  if (!r) return null
  return (
    <div className="tooltip">
      <strong>{fmtHour(r.t)}</strong>
      <div>Forecast: {fmtMw(r.forecast)}</div>
      {r.band && (
        <div className="muted">
          Likely range: {fmtMw(r.band[0])} – {fmtMw(r.band[1])}
        </div>
      )}
      {r.actual != null && <div>Actual: {fmtMw(r.actual)}</div>}
      {r.error != null && <div>Error: {signed(r.error)}</div>}
    </div>
  )
}

interface Props {
  points: Point[]
  showActual: boolean
  selected?: string
  onSelect: (iso: string) => void
}

/** Decision-time forecast, risk band, and (optionally) actuals; a second linked chart shows error. */
export const ForecastChart = memo(function ForecastChart({
  points,
  showActual,
  selected,
  onSelect,
}: Props) {
  const rows = useMemo(() => toRows(points), [points])
  const xt = useMemo(() => ticks(rows), [rows])
  const hasActual = rows.some((r) => r.actual != null)
  const hasBand = rows.some((r) => r.band)
  const selT = selected ? Date.parse(selected) : undefined
  const pick = (s: { activeLabel?: string | number }) => {
    const row = rows.find((r) => r.t === Number(s.activeLabel))
    if (row) onSelect(row.iso)
  }
  const x = (
    <XAxis
      dataKey="t"
      type="number"
      scale="time"
      domain={HALF_STEP_DOMAIN}
      ticks={xt}
      tickFormatter={fmtHour}
      {...axisProps}
    />
  )

  return (
    <>
      <div className="legend" aria-hidden>
        <span>
          <i style={{ background: C.forecast }} /> Forecast at cutoff
        </span>
        {hasBand && (
          <span>
            <i style={{ background: C.band, opacity: 0.5 }} /> Likely range
          </span>
        )}
        {showActual && hasActual && (
          <span>
            <i style={{ background: C.actual }} /> Actual
          </span>
        )}
      </div>
      <div className="chart" role="img" aria-label="Hourly wind forecast with likely range">
        <ResponsiveContainer width="100%" height={320}>
          <ComposedChart
            data={rows}
            syncId="day"
            onClick={pick}
            margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
          >
            <CartesianGrid stroke={C.grid} vertical={false} />
            {x}
            <YAxis {...axisProps} width={76} tickFormatter={gwTick} domain={[0, 'auto']} />
            <Tooltip content={<Tip />} />
            <Area
              dataKey="band"
              stroke="none"
              fill={C.band}
              fillOpacity={0.35}
              isAnimationActive={false}
              connectNulls
            />
            <Line
              dataKey="forecast"
              stroke={C.forecast}
              strokeWidth={2.5}
              dot={false}
              isAnimationActive={false}
            />
            {showActual && (
              <Line
                dataKey="actual"
                stroke={C.actual}
                strokeWidth={2}
                dot={false}
                strokeDasharray="5 3"
                isAnimationActive={false}
              />
            )}
            {selT && <ReferenceLine x={selT} stroke={C.axis} strokeDasharray="2 2" />}
          </ComposedChart>
        </ResponsiveContainer>
      </div>
      {showActual && hasActual && (
        <div className="chart" role="img" aria-label="Hourly forecast error">
          <p className="muted small">
            Forecast error per hour (above zero = over-forecast, wind came in lower)
          </p>
          <ResponsiveContainer width="100%" height={130}>
            <ComposedChart
              data={rows}
              syncId="day"
              margin={{ top: 4, right: 12, left: 0, bottom: 0 }}
            >
              <CartesianGrid stroke={C.grid} vertical={false} />
              {x}
              <YAxis {...axisProps} width={76} tickCount={3} tickFormatter={gwTick} />
              <Tooltip content={<Tip />} />
              <ReferenceLine y={0} stroke={C.axis} />
              <Bar dataKey="error" isAnimationActive={false}>
                {rows.map((r) => (
                  <Cell key={r.t} fill={(r.error ?? 0) >= 0 ? C.over : C.under} />
                ))}
              </Bar>
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      )}
    </>
  )
})
