const cell = (v: string | number) => {
  const s = String(v)
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
}

export const toCsv = (head: string[], rows: (string | number)[][]) =>
  [head, ...rows].map((r) => r.map(cell).join(',')).join('\n')

export function downloadCsv(filename: string, head: string[], rows: (string | number)[][]) {
  const url = URL.createObjectURL(new Blob([toCsv(head, rows)], { type: 'text/csv' }))
  const a = Object.assign(document.createElement('a'), { href: url, download: filename })
  a.click()
  URL.revokeObjectURL(url)
}
