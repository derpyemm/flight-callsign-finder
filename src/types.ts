export type SearchSource = 'live' | 'fr24' | 'cache'

export type CallsignHit = {
  callsign: string
  type: string
  origin?: string
  destination?: string
  iata?: string
  durationMinutes?: number
  count: number
  lastSeen?: string
  sources: SearchSource[]
}

export type SearchResult = {
  aircraft: string
  origin?: string
  destination?: string
  types: string[]
  hits: CallsignHit[]
  liveChecked: number
  liveMatched: number
  fr24Days?: number
  fr24Flights?: number
  truncated?: boolean
  warnings: string[]
}

export type Fr24Settings = {
  token: string
  lookbackDays: number
}
