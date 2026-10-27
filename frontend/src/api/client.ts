import type { components } from './schema'

export type Schemas = components['schemas']

/** Error raised for any non-2xx response, carrying the backend's error envelope. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string,
  ) {
    super(message)
  }
}

type Params = Record<string, string | undefined>

async function request<T>(url: string, init: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(url, init)
  } catch (e) {
    if (e instanceof DOMException && e.name === 'AbortError') throw e
    throw new ApiError('Cannot reach the server. Check your connection and retry.', 0, 'network')
  }
  if (!res.ok) {
    // Any non-envelope body (proxy, CDN, another server on the port) is tolerated.
    const body = (await res.json().catch(() => null)) as Partial<Schemas['ErrorResponse']> | null
    throw new ApiError(
      body?.error?.message ?? `Request failed (${res.status})`,
      res.status,
      body?.error?.code ?? 'unknown',
      body?.error?.request_id,
    )
  }
  return (res.status === 204 ? undefined : await res.json()) as T
}

export function get<T>(path: string, params: Params = {}, signal?: AbortSignal): Promise<T> {
  const qs = new URLSearchParams(
    Object.entries(params).filter((e): e is [string, string] => e[1] !== undefined && e[1] !== ''),
  ).toString()
  return request<T>(`/api/v1${path}${qs ? `?${qs}` : ''}`, { signal })
}

export function post<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(`/api/v1${path}`, {
    method: 'POST',
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}
