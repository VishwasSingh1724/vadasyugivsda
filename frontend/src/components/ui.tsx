import { downloadCsv } from '../lib/csv'
import type { ReactNode } from 'react'
import type { UseQueryResult } from '@tanstack/react-query'
import { ApiError } from '../api/client'

export function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string
  value: string
  hint?: string
  tone?: 'warn'
}) {
  return (
    <div className={`kpi ${tone ?? ''}`}>
      <div className="kpi-label">{label}</div>
      <div className="kpi-value">{value}</div>
      {hint && <div className="kpi-hint">{hint}</div>}
    </div>
  )
}

export function ErrorBanner({ error, onRetry }: { error: Error; onRetry?: () => void }) {
  const id = error instanceof ApiError ? error.requestId : undefined
  return (
    <div className="banner error" role="alert">
      <div>
        <strong>Something went wrong.</strong> {error.message}
        {id && <span className="muted"> (ref {id})</span>}
      </div>
      {onRetry && <button onClick={onRetry}>Retry</button>}
    </div>
  )
}

/** Renders a query's states; keeps previous data visible (dimmed) while a new range loads. */
export function Async<T>({
  query,
  children,
}: {
  query: UseQueryResult<T>
  children: (data: T) => ReactNode
}) {
  if (query.isError && !query.data)
    return <ErrorBanner error={query.error} onRetry={() => query.refetch()} />
  if (!query.data) return <div className="skeleton" aria-busy="true" aria-label="Loading" />
  return (
    <div
      className={query.isPlaceholderData ? 'stale' : undefined}
      aria-busy={query.isPlaceholderData}
    >
      {children(query.data)}
    </div>
  )
}

export function ChartCard({
  title,
  question,
  children,
  table,
}: {
  title: string
  question: string
  children: ReactNode
  table?: { head: string[]; rows: (string | number)[][] }
}) {
  return (
    <section className="card">
      <h3>{title}</h3>
      <p className="muted question">{question}</p>
      {children}
      {table && (
        <details className="data-table" open>
          <summary>View data</summary>
          <table>
            <thead>
              <tr>
                {table.head.map((h) => (
                  <th key={h}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i}>
                  {r.map((c, j) => (
                    <td key={j}>{c}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      )}
      {table && (
        <button
          type="button"
          className="export"
          onClick={() =>
            downloadCsv(`${title.toLowerCase().replace(/\W+/g, '-')}.csv`, table.head, table.rows)
          }
        >
          Export CSV
        </button>
      )}
    </section>
  )
}
