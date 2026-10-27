import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { SeasonPicker } from './SeasonPicker'

const prev = () => screen.getByRole('button', { name: 'Previous season' })
const next = () => screen.getByRole('button', { name: 'Next season' })

describe('SeasonPicker', () => {
  it('steps one season at a time', () => {
    const onChange = vi.fn()
    render(<SeasonPicker season={2020} onChange={onChange} max={2025} />)
    expect(screen.getByText('2020')).toBeInTheDocument()
    fireEvent.click(prev())
    fireEvent.click(next())
    expect(onChange.mock.calls).toEqual([[2019], [2021]])
  })

  it('stops at the earliest and latest seasons', () => {
    const { rerender } = render(<SeasonPicker season={2016} onChange={vi.fn()} max={2025} />)
    expect(prev()).toBeDisabled()
    rerender(<SeasonPicker season={2025} onChange={vi.fn()} max={2025} />)
    expect(next()).toBeDisabled()
  })

  // Regression: before data loaded, stepping used to jump to season "0".
  it('does nothing until the season is known', () => {
    const onChange = vi.fn()
    render(<SeasonPicker season={null} onChange={onChange} />)
    expect(prev()).toBeDisabled()
    expect(next()).toBeDisabled()
    fireEvent.click(next())
    expect(onChange).not.toHaveBeenCalled()
  })
})
