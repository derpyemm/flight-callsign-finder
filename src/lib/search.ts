import { expandAircraftTypes, normalizeIcaoType, optionalIcaoAirport } from './aircraftFamilies'
import { loadCachedHits, mergeHits, saveHits } from './cache'
import { searchLiveFlights } from './adsb'
import { searchFr24Flights } from './fr24'
import { preferFlightNumber, resolveIataNumbers } from './flightIdentity'
import type { CallsignHit, SearchResult } from '../types'

function routePhrase(origin?: string, destination?: string): string {
  if (origin && destination) return `on ${origin} → ${destination}`
  if (destination) return `into ${destination}`
  return `out of ${origin}`
}

function validateAirport(code: string | undefined, role: 'departure' | 'arrival'): string | undefined {
  if (!code) return undefined
  if (!/^[A-Z]{4}$/.test(code)) {
    throw new Error(
      role === 'departure'
        ? 'Enter a 4-letter ICAO departure code such as LSZH, or leave it blank.'
        : 'Enter a 4-letter ICAO arrival code such as EHAM, or leave it blank.',
    )
  }
  return code
}

export async function searchCallsigns(input: {
  aircraft: string
  origin?: string
  destination?: string
  includeFamily: boolean
  fr24Token?: string
  fr24LookbackDays?: number
  onProgress?: (message: string) => void
}): Promise<SearchResult> {
  const aircraft = normalizeIcaoType(input.aircraft)
  const origin = validateAirport(optionalIcaoAirport(input.origin), 'departure')
  const destination = validateAirport(optionalIcaoAirport(input.destination), 'arrival')
  const types = expandAircraftTypes(aircraft, input.includeFamily)
  const warnings: string[] = []
  const where = routePhrase(origin, destination)

  if (!/^[A-Z0-9]{2,4}$/.test(aircraft)) {
    throw new Error('Enter an ICAO aircraft type such as A320 or B738.')
  }
  if (!origin && !destination) {
    throw new Error('Enter a departure airport, an arrival airport, or both.')
  }

  input.onProgress?.('Checking live traffic…')
  const live = await searchLiveFlights(types, origin, destination)
  if (live.checked === 0) {
    warnings.push('No airborne aircraft of that type are visible right now.')
  } else if (live.matched === 0) {
    const liveMiss =
      origin && destination
        ? `currently on ${origin} → ${destination}`
        : destination
          ? `currently routing to ${destination}`
          : `currently departing ${origin}`
    warnings.push(
      `No ${types.join('/')} aircraft ${liveMiss}. Landed flights from today or yesterday are not in the live feed.`,
    )
  }

  if (live.matched === 0 && !input.fr24Token?.trim()) {
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
    const historic = await searchFr24Flights(token, types, origin, destination, lookback, (done, total) => {
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
      warnings.push(`Flightradar24 found no ${types.join('/')} flights ${where} in that window.`)
    }
  }

  const cached = loadCachedHits(aircraft, origin, destination).filter((hit) =>
    hit.sources.some((source) => source === 'fr24'),
  )
  const hits = mergeHits(cached, mergeHits(live.hits, fr24Hits))
  const missingIata = hits.filter((hit) => !hit.iata).map((hit) => hit.callsign)
  if (missingIata.length) {
    input.onProgress?.('Looking up IATA flight numbers…')
    const iataByCallsign = await resolveIataNumbers(missingIata)
    for (const hit of hits) {
      hit.iata = preferFlightNumber(hit.iata, iataByCallsign.get(hit.callsign))
    }
  }

  saveHits(aircraft, hits, origin, destination)

  return {
    aircraft,
    origin,
    destination,
    types,
    hits,
    liveChecked: live.checked,
    liveMatched: live.matched,
    fr24Days,
    fr24Flights,
    truncated,
    warnings,
  }
}
