import { describe, expect, it } from 'vitest'
import { num, pct, rankTone, signed } from './format'

describe('number formatting', () => {
  it('rounds to the requested digits', () => {
    expect(num(31.149)).toBe('31.1')
    expect(num(1512.6, 0)).toBe('1513')
  })

  it('puts a + on positive values only', () => {
    expect(signed(4.25)).toBe('+4.3')
    expect(signed(-2)).toBe('-2.0')
    expect(signed(0)).toBe('0.0')
  })

  it('shows a dash when a percentage is missing', () => {
    expect(pct(0.4567)).toBe('45.7%')
    // e.g. a player with zero 3-point attempts has no 3P%.
    expect(pct(null)).toBe('–')
  })
})

describe('rankTone', () => {
  it('colors the top and bottom five of 30 teams', () => {
    expect(rankTone(1)).toBe('good')
    expect(rankTone(5)).toBe('good')
    expect(rankTone(6)).toBe('')
    expect(rankTone(25)).toBe('')
    expect(rankTone(26)).toBe('bad')
    expect(rankTone(30)).toBe('bad')
  })
})
