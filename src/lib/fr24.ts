import type { CallsignHit } from '../types'
import { durationMinutesBetween, normalizeFlightNumber } from './flightIdentity'

type Fr24Flight = {
  callsign?: string | null
  flight?: string | null
  type?: string | null
  orig_icao?: string | null
  origin_icao?: string | null
  dest_icao?: string | null
  destination_icao?: string | null
  dest_icao_actual?: string | null
  destination_icao_actual?: string | null
  datetime_landed?: string | null
  datetime_takeoff?: string | null
}

type Fr24Summary = {
  data?: Fr24Flight[]
}

function daySlices(lookbackDays: number): { from: string; to: string }[] {
  const slices: { from: string; to: string }[] = []
  const days = Math.min(Math.max(lookbackDays, 1), 30)
  for (let offset = 0; offset < days; offset += 1) {
    const day = new Date()
    day.setUTCDate(day.getUTCDate() - offset)
    const from = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 0, 0, 0))
    const to = new Date(Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 23, 59, 59))
    slices.push({ from: from.toISOString().slice(0, 19), to: to.toISOString().slice(0, 19) })
  }
  return slices
}

function destinationOf(row: Fr24Flight): string | undefined {
  const dest = (row.dest_icao_actual || row.destination_icao_actual || row.dest_icao || row.destination_icao || '').toUpperCase()
  return dest || undefined
}

function originOf(row: Fr24Flight): string | undefined {
  const origin = (row.orig_icao || row.origin_icao || '').toUpperCase()
  return origin || undefined
}

async function fetchSummary(token: string, params: URLSearchParams): Promise<Fr24Flight[]> {
  const response = await fetch(`/fr24/api/flight-summary/light?${params}`, {
    headers: {
      Accept: 'application/json',
      Authorization: `Bearer ${token}`,
      'Accept-Version': 'v1',
    },
  })
  if (response.status === 401) {
    throw new Error('Flightradar24 token was rejected. Check the API token in settings.')
  }
  if (response.status === 429) {
    throw new Error('Flightradar24 rate or credit limit reached. Wait and try a shorter lookback.')
  }
  if (!response.ok) {
    throw new Error(`Flightradar24 search failed (${response.status})`)
  }
  const json = (await response.json()) as Fr24Summary
  return json.data ?? []
}

export async function searchFr24Flights(
  token: string,
  types: string[],
  origin: string | undefined,
  destination: string | undefined,
  lookbackDays: number,
  onProgress?: (done: number, total: number) => void,
): Promise<{ hits: CallsignHit[]; flights: number; truncated: boolean }> {
  const slices = daySlices(lookbackDays)
  const hits: CallsignHit[] = []
  let flights = 0
  let truncated = false
  const bothEnds = Boolean(origin && destination)
  let airports = bothEnds ? undefined : destination ? `inbound:${destination}` : `outbound:${origin}`
  let routes = bothEnds ? `${origin}-${destination}` : undefined

  for (let index = 0; index < slices.length; index += 1) {
    const slice = slices[index]
    const params = new URLSearchParams({
      flight_datetime_from: slice.from,
      flight_datetime_to: slice.to,
      aircraft: types.join(','),
      limit: '20',
    })
    if (airports) params.set('airports', airports)
    if (routes) params.set('routes', routes)

    let rows: Fr24Flight[]
    try {
      rows = await fetchSummary(token, params)
    } catch (error) {
      if (index === 0 && airports?.startsWith('inbound:') && destination) {
        airports = destination
        params.set('airports', destination)
        rows = await fetchSummary(token, params)
      } else if (index === 0 && airports?.startsWith('outbound:') && origin) {
        airports = origin
        params.set('airports', origin)
        rows = await fetchSummary(token, params)
      } else if (index === 0 && routes && destination) {
        routes = undefined
        airports = `inbound:${destination}`
        params.delete('routes')
        params.set('airports', airports)
        rows = await fetchSummary(token, params)
      } else {
        throw error
      }
    }

    const matched = rows.filter((row) => {
      const dest = destinationOf(row)
      const from = originOf(row)
      if (destination && dest && dest !== destination) return false
      if (origin && from && from !== origin) return false
      return true
    })
    if (rows.length >= 20) truncated = true
    flights += matched.length

    for (const row of matched) {
      const callsign = (row.callsign || row.flight || '').trim().toUpperCase()
      if (!callsign) continue
      const takeoff = row.datetime_takeoff || undefined
      const landed = row.datetime_landed || undefined
      hits.push({
        callsign,
        type: (row.type || types[0]).toUpperCase(),
        origin: originOf(row) || origin,
        destination: destinationOf(row) || destination,
        iata: normalizeFlightNumber(row.flight),
        durationMinutes: durationMinutesBetween(row.datetime_takeoff, row.datetime_landed),
        count: 1,
        lastSeen: takeoff || landed,
        sources: ['fr24'],
      })
    }

    onProgress?.(index + 1, slices.length)
    if (index < slices.length - 1) {
      await new Promise((resolve) => setTimeout(resolve, 6500))
    }
  }

  return { hits, flights, truncated }
}
