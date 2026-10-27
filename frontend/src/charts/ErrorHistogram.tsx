import { memo } from 'react'
import {
  Bar,
  CartesianGrid,
  Cell,
  ComposedChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import type { Schemas } from '../api/client'
import { axisProps, C, gwTick } from '../lib/chartTheme'

export const ErrorHistogram = memo(function ErrorHistogram({
  data,
}: {
  data: Schemas['ErrorHistogram']
}) {
  const rows = data.bins.map((b) => ({
    mid: b.start_mw + data.bin_width_mw / 2,
    count: b.count,
    start: b.start_mw,
    end: b.end_mw,
  }))
  return (
    <div className="chart" role="img" aria-label="Distribution of forecast errors">
      <ResponsiveContainer width="100%" height={260}>
        <ComposedChart
          data={rows}
          margin={{ top: 8, right: 12, left: 0, bottom: 0 }}
          barCategoryGap={1}
        >
          <CartesianGrid stroke={C.grid} vertical={false} />
          <XAxis dataKey="mid" {...axisProps} tickFormatter={gwTick} interval="preserveStartEnd" />
          <YAxis {...axisProps} width={36} allowDecimals={false} />
          <Tooltip
            labelFormatter={(_, p) => `${p?.[0]?.payload.start} to ${p?.[0]?.payload.end} MW`}
            formatter={(v) => [v, 'hours']}
          />
          <Bar dataKey="count" isAnimationActive={false}>
            {rows.map((r) => (
              <Cell key={r.start} fill={r.mid >= 0 ? C.over : C.under} />
            ))}
          </Bar>
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
})
