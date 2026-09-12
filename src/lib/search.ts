import { expandAircraftTypes, normalizeIcaoAirport, normalizeIcaoType } from './aircraftFamilies'
import { loadCachedHits, mergeHits, saveHits } from './cache'
import { searchLiveArrivals } from './adsb'
import { searchRecentArrivals } from './opensky'
import { searchFr24Arrivals } from './fr24'
import type { CallsignHit, SearchResult } from '../types'

export async function searchCallsigns(input: {
  aircraft: string
  airport: string
  includeFamily: boolean
  openskyClientId?: string
  openskyClientSecret?: string
  fr24Token?: string
  fr24LookbackDays?: number
  onProgress?: (message: string) => void
}): Promise<SearchResult> {
  const aircraft = normalizeIcaoType(input.aircraft)
  const airport = normalizeIcaoAirport(input.airport)
  const types = expandAircraftTypes(aircraft, input.includeFamily)
  const warnings: string[] = []

  if (!/^[A-Z0-9]{2,4}$/.test(aircraft)) {
    throw new Error('Enter an ICAO aircraft type such as A320 or B738.')
  }
  if (!/^[A-Z]{4}$/.test(airport)) {
    throw new Error('Enter a 4-letter ICAO airport code such as EHAM.')
  }

  input.onProgress?.('Checking live traffic…')
  const live = await searchLiveArrivals(types, airport)
  if (live.checked === 0) {
    warnings.push('No airborne aircraft of that type are visible right now.')
  } else if (live.matched === 0) {
    warnings.push(
      `Found ${live.checked} airborne ${types.join('/')} aircraft, but none currently routing to ${airport}. Landed flights from today or yesterday are not in the live feed.`,
    )
  }

  let recentFlights: number | undefined
  let recentHits: CallsignHit[] = []
  const clientId = input.openskyClientId?.trim()
  const clientSecret = input.openskyClientSecret?.trim()
  if (clientId && clientSecret) {
    const recent = await searchRecentArrivals(clientId, clientSecret, types, airport, input.onProgress)
    recentHits = recent.hits
    recentFlights = recent.flights
    if (recent.flights === 0) {
      warnings.push('OpenSky has no completed arrivals of that type in the last two UTC days. Today’s landings appear after the overnight batch.')
    }
  } else if (live.matched === 0 && !input.fr24Token?.trim()) {
    warnings.push(
      'Add a Flightradar24 API token in settings to include flights that already landed today or yesterday.',
    )
  }

  let fr24Days: number | undefined
  let fr24Flights: number | undefined
  let truncated = false
  let fr24Hits: CallsignHit[] = []

  const token = input.fr24Token?.trim()
  const lookback = input.fr24LookbackDays ?? 0
  if (token && lookback >= 1) {
    input.onProgress?.(
      lookback === 1
        ? 'Asking Flightradar24 for today…'
        : lookback === 2
          ? 'Asking Flightradar24 for today and yesterday…'
          : `Asking Flightradar24 for the last ${lookback} days…`,
    )
    const historic = await searchFr24Arrivals(token, types, airport, lookback, (done, total) => {
      input.onProgress?.(`Flightradar24 lookback ${done}/${total} days…`)
    })
    fr24Hits = historic.hits
    fr24Days = lookback
    fr24Flights = historic.flights
    truncated = historic.truncated
    if (truncated) {
      warnings.push('Flightradar24 Explorer returns at most 20 flights per day, so some busy days may be incomplete.')
    }
    if (historic.flights === 0) {
      warnings.push(
        `Flightradar24 found no ${types.join('/')} arrivals into ${airport} in that window.`,
      )
    }
  }

  const cached = loadCachedHits(aircraft, airport).filter((hit) =>
    hit.sources.some((source) => source === 'opensky' || source === 'fr24'),
  )
  const hits = mergeHits(cached, mergeHits(live.hits, mergeHits(recentHits, fr24Hits)))
  saveHits(aircraft, airport, hits)

  return {
    aircraft,
    airport,
    types,
    hits,
    liveChecked: live.checked,
    liveMatched: live.matched,
    recentFlights,
    fr24Days,
    fr24Flights,
    truncated,
    warnings,
  }
}
