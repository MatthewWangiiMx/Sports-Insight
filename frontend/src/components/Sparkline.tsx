interface SparklineProps {
  values: number[]
  wins: boolean[]
  width?: number
  height?: number
}

export function Sparkline({ values, wins, width = 320, height = 56 }: SparklineProps) {
  if (values.length === 0) return null

  const max = Math.max(...values, 0)
  const min = Math.min(...values, 0)
  const range = max - min || 1
  const stepX = width / Math.max(values.length - 1, 1)
  const pad = 3
  const toY = (v: number) => pad + (1 - (v - min) / range) * (height - pad * 2)

  const points = values.map((v, i) => [i * stepX, toY(v)] as const)
  const zeroY = toY(0)
  const path = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ')
  const lastX = points[points.length - 1][0]
  const fillPath = `${path} L${lastX.toFixed(1)},${zeroY.toFixed(1)} L0,${zeroY.toFixed(1)} Z`

  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      <line x1={0} x2={width} y1={zeroY} y2={zeroY} className="sparkline-zero" />
      <path d={fillPath} className="sparkline-fill" stroke="none" />
      <path d={path} className="sparkline-line" fill="none" />
      {points.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={2.5} className={wins[i] ? 'sparkline-dot win' : 'sparkline-dot loss'} />
      ))}
    </svg>
  )
}
