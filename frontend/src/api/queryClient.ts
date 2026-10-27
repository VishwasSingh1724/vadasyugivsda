import { QueryCache, QueryClient } from '@tanstack/react-query'
import { ApiError } from './client'

export interface ClientOptions {
  /** Disable retries (tests). */
  noRetry?: boolean
}

export function createQueryClient({ noRetry = false }: ClientOptions = {}): QueryClient {
  // A 401 from any data request means the session ended: drop back to the sign-in screen.
  const client: QueryClient = new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) client.setQueryData(['me'], null)
      },
    }),
    defaultOptions: {
      queries: {
        // The dataset is an immutable snapshot, so responses stay fresh for the whole session.
        staleTime: Infinity,
        // Client errors (4xx) are deterministic and not retried; server/network errors retry twice.
        retry: (n, e) =>
          !noRetry && !(e instanceof ApiError && e.status > 0 && e.status < 500) && n < 2,
      },
    },
  })
  return client
}
