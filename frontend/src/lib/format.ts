const TZ = 'Europe/London'

export const fmtMw = (v: number | null | undefined, digits = 0) =>
  v == null ? '–' : `${v.toLocaleString('en-GB', { maximumFractionDigits: digits })} MW`

export const fmtGwh = (mwh: number | null | undefined) =>
  mwh == null ? '–' : `${(mwh / 1000).toLocaleString('en-GB', { maximumFractionDigits: 1 })} GWh`

export const fmtPct = (v: number | null | undefined, digits = 1) =>
  v == null ? '–' : `${v.toLocaleString('en-GB', { maximumFractionDigits: digits })}%`

export const signed = (v: number | null | undefined) =>
  v == null ? '–' : `${v > 0 ? '+' : ''}${Math.round(v).toLocaleString('en-GB')} MW`

export const fmtHour = (t: number | string) =>
  new Date(t).toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', timeZone: TZ })

export const fmtDay = (iso: string) =>
  new Date(`${iso}T12:00:00Z`).toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    year: 'numeric',
    timeZone: 'UTC',
  })

/** e.g. "Wed 14 Jan, 09:00 GMT" — the cutoff instant as the desk's local clock shows it. */
export const fmtInstant = (iso: string | number) => {
  const d = new Date(iso)
  const day = d.toLocaleDateString('en-GB', {
    weekday: 'short',
    day: 'numeric',
    month: 'short',
    timeZone: TZ,
  })
  const time = d.toLocaleTimeString('en-GB', {
    hour: '2-digit',
    minute: '2-digit',
    timeZoneName: 'short',
    timeZone: TZ,
  })
  // Intl prints London as "GMT+0"/"GMT+1"; desks say GMT/BST.
  return `${day}, ${time}`.replace('GMT+1', 'BST').replace('GMT+0', 'GMT')
}

export const addDays = (iso: string, n: number) => {
  const d = new Date(`${iso}T00:00:00Z`)
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

/** Share of mean absolute error that is one-directional (systematic) rather than random. */
export const biasShare = (bias: number | null, mae: number | null) =>
  bias == null || !mae ? null : Math.min(100, (Math.abs(bias) / mae) * 100)

/** e.g. "14 Jan 09:00" */
export const fmtShort = (t: number | string) =>
  new Date(t).toLocaleString('en-GB', {
    day: 'numeric',
    month: 'short',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: TZ,
  })
