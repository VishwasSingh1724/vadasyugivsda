import { memo, useMemo } from 'react'
import {
  CartesianGrid,
  ComposedChart,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import { useVintages } from '../api/hooks'
import { Async, ChartCard } from '../components/ui'
import { axisProps, C, gwTick } from '../lib/chartTheme'
import { fmtInstant, fmtMw, fmtShort } from '../lib/format'

/** How the forecast for one target hour moved as new revisions were published. */
export const VintagePanel = memo(function VintagePanel({ target }: { target?: string }) {
  const q = useVintages(target)
  if (!target)
    return (
      <ChartCard
        title="Forecast revisions"
        question="How did the forecast for a given hour change over time?"
      >
        <p className="muted">
          Click an hour on the chart above to see every revision published for it.
        </p>
      </ChartCard>
    )
  return (
    <ChartCard
      title={`Forecast revisions for ${fmtInstant(target)}`}
      question="Did newer forecasts move the number? Revisions after the cutoff can’t be used for this bid."
    >
      <Async query={q}>{(d) => <Revisions d={d} />}</Async>
    </ChartCard>
  )
})

function Revisions({ d }: { d: NonNullable<ReturnType<typeof useVintages>['data']> }) {
  const rows = useMemo(
    () =>
      d.vintages.map((v) => ({
        t: Date.parse(v.publish_time),
        mw: v.forecast_mw,
        ok: v.available_at_cutoff,
      })),
    [d],
  )
  const cutoff = Date.parse(d.cutoff_time)
  const usable = rows.filter((r) => r.ok)
  const last = usable.at(-1)
  return (
    <>
      <p>
        Used for the bid: <strong>{fmtMw(last?.mw)}</strong>
        {d.actual_mw != null && (
          <>
            {' '}
            · Actual: <strong>{fmtMw(d.actual_mw)}</strong>
          </>
        )}{' '}
        · {rows.length - usable.length} later revision(s) not available at cutoff
      </p>
      <div className="chart" role="img" aria-label="Forecast revisions over time">
        <ResponsiveContainer width="100%" height={200}>
          <ComposedChart data={rows} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
            <CartesianGrid stroke={C.grid} vertical={false} />
            <XAxis
              dataKey="t"
              type="number"
              scale="time"
              domain={['dataMin', 'dataMax']}
              tickFormatter={fmtShort}
              {...axisProps}
            />
            <YAxis {...axisProps} width={72} domain={['auto', 'auto']} tickFormatter={gwTick} />
            <Tooltip
              formatter={(v) => fmtMw(Number(v))}
              labelFormatter={(t) => `Published ${fmtShort(Number(t))}`}
            />
            <ReferenceLine
              x={cutoff}
              stroke={C.over}
              strokeDasharray="4 3"
              label={{ value: 'Cutoff', fill: C.over, fontSize: 12, position: 'insideTopRight' }}
            />
            {d.actual_mw != null && (
              <ReferenceLine y={d.actual_mw} stroke={C.actual} strokeDasharray="5 3" />
            )}
            <Line
              dataKey="mw"
              stroke={C.forecast}
              strokeWidth={2}
              type="stepAfter"
              dot={{ r: 3 }}
              isAnimationActive={false}
            />
            <Scatter dataKey="mw" fill={C.forecast} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>
    </>
  )
}
