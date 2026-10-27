import { expect, it } from 'vitest'
import { toCsv } from './csv'

it('builds CSV and escapes commas and quotes', () => {
  expect(toCsv(['Group', 'MAE (MW)'], [['a,b', 1], ['say "hi"', 2]])).toBe(
    'Group,MAE (MW)\n"a,b",1\n"say ""hi""",2',
  )
})
