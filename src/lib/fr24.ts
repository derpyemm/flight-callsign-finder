import type { CallsignHit } from '../types'

type Fr24Flight = {
  callsign?: string | null
  flight?: string | null
  type?: string | null
  orig_icao?: string | null
  dest_icao?: string | null
  dest_icao_actual?: string | null
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

function destinationOf(row: Fr24Flight): string {
  return (row.dest_icao_actual || row.dest_icao || '').toUpperCase()
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

export async function searchFr24Arrivals(
  token: string,
  types: string[],
  airport: string,
  lookbackDays: number,
  onProgress?: (done: number, total: number) => void,
): Promise<{ hits: CallsignHit[]; flights: number; truncated: boolean }> {
  const slices = daySlices(lookbackDays)
  const hits: CallsignHit[] = []
  let flights = 0
  let truncated = false
  let airportParam = `inbound:${airport}`

  for (let index = 0; index < slices.length; index += 1) {
    const slice = slices[index]
    const params = new URLSearchParams({
      flight_datetime_from: slice.from,
      flight_datetime_to: slice.to,
      aircraft: types.join(','),
      airports: airportParam,
      limit: '20',
    })

    let rows: Fr24Flight[]
    try {
      rows = await fetchSummary(token, params)
    } catch (error) {
      if (index === 0 && airportParam.startsWith('inbound:')) {
        airportParam = airport
        params.set('airports', airport)
        rows = await fetchSummary(token, params)
      } else {
        throw error
      }
    }

    const inbound = rows.filter((row) => {
      const dest = destinationOf(row)
      return !dest || dest === airport
    })
    if (rows.length >= 20) truncated = true
    flights += inbound.length

    for (const row of inbound) {
      const callsign = (row.callsign || row.flight || '').trim().toUpperCase()
      if (!callsign) continue
      hits.push({
        callsign,
        type: (row.type || types[0]).toUpperCase(),
        origin: row.orig_icao?.toUpperCase(),
        count: 1,
        lastSeen: row.datetime_landed || row.datetime_takeoff || undefined,
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
