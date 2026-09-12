export type SearchSource = 'live' | 'opensky' | 'fr24' | 'cache'

export type CallsignHit = {
  callsign: string
  type: string
  origin?: string
  count: number
  lastSeen?: string
  sources: SearchSource[]
}

export type SearchResult = {
  aircraft: string
  airport: string
  types: string[]
  hits: CallsignHit[]
  liveChecked: number
  liveMatched: number
  recentFlights?: number
  fr24Days?: number
  fr24Flights?: number
  truncated?: boolean
  warnings: string[]
}

export type Fr24Settings = {
  token: string
  lookbackDays: number
}
