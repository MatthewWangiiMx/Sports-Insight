import { useState } from 'react'
import { headshotUrl, teamIdFor, teamLogoUrl } from '../branding'

interface TeamLogoProps {
  abbreviation: string
  // Pass when known; otherwise looked up from the abbreviation.
  teamId?: number
  size?: number
  className?: string
}

export function TeamLogo({ abbreviation, teamId, size = 22, className }: TeamLogoProps) {
  const [failed, setFailed] = useState(false)
  const id = teamId ?? teamIdFor(abbreviation)
  const style = { width: size, height: size }

  // Unknown team or blocked CDN: fall back to the abbreviation so layouts don't jump.
  if (id == null || failed) {
    return (
      <span className={`logo-fallback ${className ?? ''}`} style={{ ...style, fontSize: size * 0.32 }}>
        {abbreviation}
      </span>
    )
  }
  return (
    <img
      className={`team-logo ${className ?? ''}`}
      src={teamLogoUrl(id)}
      alt={`${abbreviation} logo`}
      style={style}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}

interface HeadshotProps {
  playerId: number
  name: string
  size?: number
  // 'circle' = small avatar in tables; 'portrait' = full photo, cropped like nba.com.
  shape?: 'circle' | 'portrait'
  className?: string
}

// The CDN photos are 1040x760; portrait mode keeps that ratio.
const PHOTO_RATIO = 1040 / 760

export function Headshot({ playerId, name, size = 28, shape = 'circle', className }: HeadshotProps) {
  const [failed, setFailed] = useState(false)
  const portrait = shape === 'portrait'
  const style = { width: portrait ? Math.round(size * PHOTO_RATIO) : size, height: size }
  const classes = `headshot ${portrait ? 'portrait' : ''} ${className ?? ''}`

  // Older/two-way players sometimes have no photo on the CDN.
  if (failed) {
    const initials = name
      .split(' ')
      .map((part) => part[0])
      .slice(0, 2)
      .join('')
    return (
      <span className={`${classes} headshot-fallback`} style={{ ...style, fontSize: size * (portrait ? 0.3 : 0.36) }}>
        {initials}
      </span>
    )
  }
  return (
    <img
      className={classes}
      src={headshotUrl(playerId, portrait)}
      alt={name}
      style={style}
      loading="lazy"
      onError={() => setFailed(true)}
    />
  )
}
