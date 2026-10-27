import { memo } from 'react'
import {
  Bar,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Schemas } from '../api/client'
import { axisProps, C, gwTick } from '../lib/chartTheme'
import { signed } from '../lib/format'

type Group = Schemas['GroupMetrics']
export interface Series {
  field: 'mae_mw' | 'bias_mw' | 'p90_abs_mw'
  label: string
  color: string
  type: 'bar' | 'line'
}

interface Props {
  groups: Group[]
  series: Series[]
  label: string
  onSelect?: (key: string) => void
  height?: number
}

/** Metrics per group (day, horizon bucket, hour, wind level) as bars and/or lines. */
export const GroupChart = memo(function GroupChart({
  groups,
  series,
  label,
  onSelect,
  height = 260,
}: Props) {
  const data = groups.map((g) => ({
    key: g.key,
    n: g.metrics.n,
    ...Object.fromEntries(series.map((s) => [s.field, g.metrics[s.field]])),
  }))
  return (
    <div className="chart" role="img" aria-label={label}>
      <ResponsiveContainer width="100%" height={height}>
        <ComposedChart
          data={data}
          margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
          onClick={(s) => onSelect && s?.activeLabel != null && onSelect(String(s.activeLabel))}
          style={onSelect ? { cursor: 'pointer' } : undefined}
        >
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis
            dataKey="key"
            {...axisProps}
            interval="preserveStartEnd"
            tickFormatter={(k: string) => (/^\d{4}-\d\d-\d\d$/.test(k) ? k.slice(8) : k)}
          />
          <YAxis {...axisProps} width={52} tickFormatter={gwTick} />
          <Tooltip
            formatter={(v, name) => [signed(Number(v)), name]}
            labelFormatter={(k) => String(k)}
          />
          <Legend iconType="square" wrapperStyle={{ fontSize: 12 }} />
          <ReferenceLine y={0} stroke={C.axis} />
          {series.map((s) =>
            s.type === 'bar' ? (
              <Bar
                key={s.field}
                dataKey={s.field}
                name={s.label}
                fill={s.color}
                isAnimationActive={false}
              />
            ) : (
              <Line
                key={s.field}
                dataKey={s.field}
                name={s.label}
                stroke={s.color}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
              />
            ),
          )}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
})
