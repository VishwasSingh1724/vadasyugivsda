import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { ApiError, get, post, type Schemas } from './client'

type Me = Schemas['Me']
const ME = ['me']
const notMe = (q: { queryKey: readonly unknown[] }) => q.queryKey[0] !== ME[0]

/** Current user, or null when signed out. Cookie is HttpOnly, so the server is the source of truth. */
export const useMe = () =>
  useQuery({
    queryKey: ME,
    queryFn: async ({ signal }) => {
      try {
        return await get<Me>('/auth/me', {}, signal)
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null
        throw e
      }
    },
  })

export function useLogin() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (v: { username: string; password: string }) => post<Me>('/auth/login', v),
    onSuccess: (me) => {
      qc.setQueryData(ME, me)
      // Anything that failed with 401 before sign-in must be fetched again.
      void qc.invalidateQueries({ predicate: notMe })
    },
  })
}

export function useLogout() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: () => post<void>('/auth/logout'),
    onSettled: () => {
      qc.setQueryData(ME, null)
      qc.removeQueries({ predicate: notMe }) // don't leave protected data in memory
    },
  })
}
