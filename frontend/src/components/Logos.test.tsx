import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { Headshot, TeamLogo } from './Logos'

describe('TeamLogo', () => {
  it('loads the official logo for a known team', () => {
    render(<TeamLogo abbreviation="OKC" />)
    expect(screen.getByRole('img', { name: 'OKC logo' })).toHaveAttribute(
      'src',
      'https://cdn.nba.com/logos/nba/1610612760/global/L/logo.svg',
    )
  })

  it('falls back to the abbreviation if the image fails', () => {
    render(<TeamLogo abbreviation="OKC" />)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('OKC')).toBeInTheDocument()
  })

  it('shows the abbreviation for a team it has no logo for', () => {
    render(<TeamLogo abbreviation="XYZ" />)
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    expect(screen.getByText('XYZ')).toBeInTheDocument()
  })
})

describe('Headshot', () => {
  it('uses the small photo for avatars and the large one for portraits', () => {
    const { rerender } = render(<Headshot playerId={1628983} name="Shai Gilgeous-Alexander" />)
    expect(screen.getByRole('img')).toHaveAttribute('src', expect.stringContaining('/260x190/1628983.png'))
    rerender(<Headshot playerId={1628983} name="Shai Gilgeous-Alexander" shape="portrait" />)
    expect(screen.getByRole('img')).toHaveAttribute('src', expect.stringContaining('/1040x760/1628983.png'))
  })

  it("falls back to the player's initials", () => {
    render(<Headshot playerId={1} name="Luka Doncic" />)
    fireEvent.error(screen.getByRole('img'))
    expect(screen.getByText('LD')).toBeInTheDocument()
  })
})
