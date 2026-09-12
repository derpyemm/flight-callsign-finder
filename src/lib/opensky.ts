import type { CallsignHit } from '../types'
import { resolveTypes } from './typeLookup'

type OpenSkyFlight = {
  icao24?: string
  callsign?: string | null
  estDepartureAirport?: string | null
  estArrivalAirport?: string | null
  firstSeen?: number
  lastSeen?: number
}

type TokenResponse = {
  access_token: string
  expires_in?: number
}

let cachedToken: { value: string; expiresAt: number } | null = null

async function getToken(clientId: string, clientSecret: string): Promise<string> {
  if (cachedToken && Date.now() < cachedToken.expiresAt) return cachedToken.value

  const body = new URLSearchParams({
    grant_type: 'client_credentials',
    client_id: clientId,
    client_secret: clientSecret,
  })
  const response = await fetch('/opensky-auth/auth/realms/opensky-network/protocol/openid-connect/token', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body,
  })
  if (!response.ok) {
    throw new Error('OpenSky login failed. Check the free client ID and secret.')
  }
  const json = (await response.json()) as TokenResponse
  cachedToken = {
    value: json.access_token,
    expiresAt: Date.now() + ((json.expires_in ?? 1800) - 60) * 1000,
  }
  return cachedToken.value
}

function utcDayWindow(daysAgo: number): { begin: number; end: number } {
  const day = new Date()
  day.setUTCDate(day.getUTCDate() - daysAgo)
  const begin = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 0, 0, 0) / 1000
  const end = Date.UTC(day.getUTCFullYear(), day.getUTCMonth(), day.getUTCDate(), 23, 59, 59) / 1000
  return { begin, end }
}

async function fetchArrivals(token: string, airport: string, begin: number, end: number): Promise<OpenSkyFlight[]> {
  const response = await fetch(
    `/opensky/api/flights/arrival?airport=${encodeURIComponent(airport)}&begin=${begin}&end=${end}`,
    { headers: { Authorization: `Bearer ${token}` } },
  )
  if (response.status === 404) return []
  if (!response.ok) {
    throw new Error(`OpenSky arrivals failed (${response.status})`)
  }
  return (await response.json()) as OpenSkyFlight[]
}

export async function searchRecentArrivals(
  clientId: string,
  clientSecret: string,
  types: string[],
  airport: string,
  onProgress?: (message: string) => void,
): Promise<{ hits: CallsignHit[]; flights: number }> {
  const token = await getToken(clientId, clientSecret)
  const wanted = new Set(types)
  const flights: OpenSkyFlight[] = []

  for (const daysAgo of [1, 2]) {
    const { begin, end } = utcDayWindow(daysAgo)
    onProgress?.(`Loading completed arrivals from ${daysAgo === 1 ? 'yesterday' : 'the day before'}…`)
    flights.push(...(await fetchArrivals(token, airport, begin, end)))
  }

  const hexes = [...new Set(flights.map((flight) => flight.icao24?.toLowerCase()).filter(Boolean))] as string[]
  onProgress?.('Matching arrivals to aircraft types…')
  const typeByHex = await resolveTypes(hexes, (done, total) => {
    onProgress?.(`Matching arrivals to aircraft types… ${done}/${total}`)
  })

  const hits: CallsignHit[] = []
  for (const flight of flights) {
    const hex = flight.icao24?.toLowerCase()
    if (!hex) continue
    const type = typeByHex.get(hex)
    if (!type || !wanted.has(type)) continue
    const callsign = flight.callsign?.trim().toUpperCase()
    if (!callsign) continue
    const durationMinutes =
      flight.firstSeen && flight.lastSeen && flight.lastSeen > flight.firstSeen
        ? Math.round((flight.lastSeen - flight.firstSeen) / 60)
        : undefined
    hits.push({
      callsign,
      type,
      origin: flight.estDepartureAirport?.toUpperCase() || undefined,
      durationMinutes,
      count: 1,
      lastSeen: flight.lastSeen ? new Date(flight.lastSeen * 1000).toISOString() : undefined,
      sources: ['opensky'],
    })
  }

  return { hits, flights: hits.length }
}
