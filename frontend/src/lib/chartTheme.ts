export const C = {
  forecast: 'var(--c-forecast)',
  actual: 'var(--c-actual)',
  band: 'var(--c-band)',
  over: 'var(--c-over)',
  under: 'var(--c-under)',
  grid: 'var(--c-grid)',
  axis: 'var(--c-axis)',
}
export const axisProps = {
  stroke: 'var(--c-axis)',
  tick: { fill: 'var(--c-axis)', fontSize: 12 },
  tickLine: false,
}
/** Y-axis tick: MW as GW, e.g. 13500 -> "13.5 GW". */
export const gwTick = (v: number) => `${parseFloat((v / 1000).toFixed(1))} GW`
