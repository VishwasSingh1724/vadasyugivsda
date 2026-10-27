import { keepPreviousData, useQuery } from '@tanstack/react-query'
import { get, type Schemas } from './client'

export interface Range {
  from?: string
  to?: string
}

export const useDeliveryDays = () =>
  useQuery({
    queryKey: ['days'],
    queryFn: ({ signal }) => get<Schemas['DeliveryDays']>('/delivery-days', {}, signal),
  })

export const useForecast = (date: string | undefined) =>
  useQuery({
    queryKey: ['forecast', date],
    queryFn: ({ signal }) =>
      get<Schemas['ForecastDay']>('/forecast', { delivery_date: date }, signal),
    enabled: !!date,
    placeholderData: keepPreviousData,
  })

export const useVintages = (target: string | undefined) =>
  useQuery({
    queryKey: ['vintages', target],
    queryFn: ({ signal }) => get<Schemas['Vintages']>('/forecast/vintages', { target }, signal),
    enabled: !!target,
    placeholderData: keepPreviousData,
  })

type AccuracyKind = 'summary' | 'daily' | 'by-horizon' | 'by-hour' | 'by-wind-level' | 'errors'
type AccuracyResult = {
  summary: Schemas['AccuracySummary']
  daily: Schemas['AccuracyGroups']
  'by-horizon': Schemas['AccuracyGroups']
  'by-hour': Schemas['AccuracyGroups']
  'by-wind-level': Schemas['AccuracyGroups']
  errors: Schemas['ErrorHistogram']
}

export const useAccuracy = <K extends AccuracyKind>(kind: K, range: Range) =>
  useQuery({
    queryKey: ['accuracy', kind, range.from, range.to],
    queryFn: ({ signal }) => get<AccuracyResult[K]>(`/accuracy/${kind}`, { ...range }, signal),
    placeholderData: keepPreviousData,
  })
