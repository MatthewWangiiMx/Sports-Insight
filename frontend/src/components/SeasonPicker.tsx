// Earliest season we have ingested data for (see ml/ingest) - the lower bound
// for stepping back, so the picker can't be clicked into a season with no data.
const EARLIEST_SEASON = 2016

interface SeasonPickerProps {
  season: number | null
  onChange: (season: number) => void
}

export function SeasonPicker({ season, onChange }: SeasonPickerProps) {
  return (
    <div className="season-picker">
      <button
        type="button"
        aria-label="Previous season"
        disabled={season == null || season <= EARLIEST_SEASON}
        onClick={() => season != null && onChange(season - 1)}
      >
        <ChevronLeft />
      </button>
      <span className="season-picker-value">{season ?? '…'}</span>
      <button
        type="button"
        aria-label="Next season"
        disabled={season == null}
        onClick={() => season != null && onChange(season + 1)}
      >
        <ChevronRight />
      </button>
    </div>
  )
}

function ChevronLeft() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M10 3 5 8l5 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}

function ChevronRight() {
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.75">
      <path d="M6 3l5 5-5 5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  )
}
