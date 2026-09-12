import type { CallsignHit } from '../types'

type AdsbAircraft = {
  hex?: string
  flight?: string
  t?: string
  lat?: number
  lon?: number
  dst?: number
  alt_baro?: number | string
}

type AdsbTypeResponse = {
  ac?: AdsbAircraft[]
}

type AirportInfo = {
  icao?: string
  iata?: string
  lat?: number
  lon?: number
}

type RouteAirport = {
  icao?: string
}

type RouteRow = {
  callsign?: string
  airport_codes?: string
  _airports?: RouteAirport[]
}

function trimCallsign(value: string | undefined): string | null {
  const callsign = value?.trim().toUpperCase()
  return callsign ? callsign : null
}

async function readJson<T>(response: Response): Promise<T | null> {
  const text = await response.text()
  if (!text.trim()) return null
  return JSON.parse(text) as T
}

async function fetchAirport(icao: string): Promise<AirportInfo> {
  const response = await fetch(`/adsb/api/0/airport/${encodeURIComponent(icao)}`)
  if (!response.ok) {
    throw new Error(`Unknown airport ${icao} (${response.status})`)
  }
  const json = await readJson<AirportInfo>(response)
  if (json?.lat == null || json.lon == null) {
    throw new Error(`No coordinates for ${icao}.`)
  }
  return json
}

async function fetchNearby(lat: number, lon: number, dist: number): Promise<AdsbAircraft[]> {
  for (let attempt = 0; attempt < 3; attempt += 1) {
    const response = await fetch(`/adsb/v2/lat/${lat}/lon/${lon}/dist/${dist}`)
    if (response.status === 429) {
      await new Promise((resolve) => setTimeout(resolve, 1500 * (attempt + 1)))
      continue
    }
    if (!response.ok) {
      throw new Error(`Live area search failed (${response.status})`)
    }
    const json = await readJson<AdsbTypeResponse>(response)
    return json?.ac ?? []
  }
  return []
}

async function fetchRoutes(planes: { callsign: string; lat: number; lng: number }[]): Promise<RouteRow[]> {
  const routes: RouteRow[] = []
  const chunkSize = 15
  for (let i = 0; i < planes.length; i += chunkSize) {
    const chunk = planes.slice(i, i + chunkSize)
    const response = await fetch('/adsb/api/0/routeset', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'application/json' },
      body: JSON.stringify({ planes: chunk }),
    })
    if (response.status === 429) {
      await new Promise((resolve) => setTimeout(resolve, 1500))
      i -= chunkSize
      continue
    }
    if (!response.ok) continue
    const json = await readJson<RouteRow[]>(response)
    if (Array.isArray(json)) routes.push(...json)
  }
  return routes
}

function destinationIcao(row: RouteRow): string | undefined {
  const fromList = row._airports?.at(-1)?.icao?.toUpperCase()
  if (fromList) return fromList
  const codes = row.airport_codes?.split('-').map((part) => part.trim().toUpperCase())
  return codes?.at(-1)
}

function isAtAirport(item: AdsbAircraft | undefined): boolean {
  if (!item || item.dst == null) return false
  const onGround = item.alt_baro === 'ground' || item.alt_baro === 0
  return onGround && item.dst < 8
}

function originIcao(row: RouteRow): string | undefined {
  const fromList = row._airports?.[0]?.icao?.toUpperCase()
  if (fromList) return fromList
  const codes = row.airport_codes?.split('-').map((part) => part.trim().toUpperCase())
  return codes?.[0]
}

async function fetchTypeWorldwide(type: string): Promise<AdsbAircraft[]> {
  const response = await fetch(`/adsb/v2/type/${encodeURIComponent(type)}`)
  if (!response.ok) return []
  const json = await readJson<AdsbTypeResponse>(response)
  return json?.ac ?? []
}

async function airportCodes(icao: string): Promise<Set<string>> {
  const info = await fetchAirport(icao)
  return new Set([icao, info.icao, info.iata].filter(Boolean).map((code) => code!.toUpperCase()))
}

export async function searchLiveFlights(
  types: string[],
  origin?: string,
  destination?: string,
): Promise<{ hits: CallsignHit[]; checked: number; matched: number }> {
  const nearbyAirport = destination || origin
  if (!nearbyAirport) return { hits: [], checked: 0, matched: 0 }

  const info = await fetchAirport(nearbyAirport)
  const wanted = new Set(types)
  const nearby = await fetchNearby(info.lat as number, info.lon as number, 250)
  const worldwide: AdsbAircraft[] = []
  for (const type of types) {
    const all = await fetchTypeWorldwide(type)
    if (all.length && all.length <= 80) worldwide.push(...all)
  }
  const ofType = [...nearby, ...worldwide].filter((item) => item.t && wanted.has(item.t.toUpperCase()))

  const byCallsign = new Map<string, AdsbAircraft>()
  for (const item of ofType) {
    const callsign = trimCallsign(item.flight)
    if (!callsign) continue
    byCallsign.set(callsign, item)
  }

  const planes = [...byCallsign.entries()].map(([callsign, item]) => ({
    callsign,
    lat: item.lat ?? 0,
    lng: item.lon ?? 0,
  }))
  const routes = planes.length ? await fetchRoutes(planes) : []
  const destCodes = destination ? await airportCodes(destination) : undefined
  const originCodes = origin ? await airportCodes(origin) : undefined
  const hits: CallsignHit[] = []
  const matched = new Set<string>()

  for (const row of routes) {
    const callsign = trimCallsign(row.callsign)
    if (!callsign) continue
    const dest = destinationIcao(row)
    const from = originIcao(row)
    const destOk = !destCodes || (dest ? destCodes.has(dest) : isAtAirport(byCallsign.get(callsign)))
    const originOk = !originCodes || (from ? originCodes.has(from) : isAtAirport(byCallsign.get(callsign)))
    if (!destOk || !originOk) continue
    if (origin && destination && (!from || !dest)) continue
    matched.add(callsign)
    hits.push({
      callsign,
      type: byCallsign.get(callsign)?.t?.toUpperCase() ?? types[0],
      origin: from,
      destination: dest,
      count: 1,
      sources: ['live'],
    })
  }

  if (!(origin && destination)) {
    for (const [callsign, item] of byCallsign) {
      if (matched.has(callsign) || !isAtAirport(item)) continue
      hits.push({
        callsign,
        type: item.t?.toUpperCase() ?? types[0],
        origin: origin,
        destination: destination,
        count: 1,
        sources: ['live'],
      })
    }
  }

  return { hits, checked: byCallsign.size, matched: hits.length }
}
