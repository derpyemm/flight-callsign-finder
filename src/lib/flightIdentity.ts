const IATA_CACHE_KEY = 'callsign-iata-cache-v1'

type IataCache = Record<string, string>

type AdsbdbCallsign = {
  response?: {
    flightroute?: {
      callsign_iata?: string
    }
  }
}

function readCache(): IataCache {
  try {
    const raw = localStorage.getItem(IATA_CACHE_KEY)
    return raw ? (JSON.parse(raw) as IataCache) : {}
  } catch {
    return {}
  }
}

function writeCache(cache: IataCache) {
  localStorage.setItem(IATA_CACHE_KEY, JSON.stringify(cache))
}

export function normalizeFlightNumber(value: string | null | undefined): string | undefined {
  const flight = value?.replace(/\s+/g, '').toUpperCase()
  return flight || undefined
}

export function splitIataFlight(flight: string): { carrier: string; number: string } | undefined {
  const match = flight.trim().toUpperCase().match(/^([A-Z]{2}|[A-Z]\d|\d[A-Z])(\d{1,4}[A-Z]?)$/)
  if (!match) return undefined
  return { carrier: match[1], number: match[2] }
}

export function preferFlightNumber(a?: string, b?: string): string | undefined {
  const left = normalizeFlightNumber(a)
  const right = normalizeFlightNumber(b)
  if (!left) return right
  if (!right) return left
  const digits = (value: string) => (value.match(/\d+/)?.[0] ?? '').length
  return digits(right) > digits(left) ? right : left
}

export function durationMinutesBetween(from?: string | null, to?: string | null): number | undefined {
  if (!from || !to) return undefined
  const start = Date.parse(from.includes('T') ? from : from.replace(' ', 'T'))
  const end = Date.parse(to.includes('T') ? to : to.replace(' ', 'T'))
  if (!Number.isFinite(start) || !Number.isFinite(end) || end <= start) return undefined
  return Math.round((end - start) / 60000)
}

export function scheduledMinutesFromTimes(dep?: string | null, arr?: string | null): number | undefined {
  if (!dep || !arr) return undefined
  if (/\d{4}-\d{2}-\d{2}/.test(dep) && /\d{4}-\d{2}-\d{2}/.test(arr)) {
    return durationMinutesBetween(dep, arr)
  }
  const depClock = dep.match(/(\d{1,2}):(\d{2})\s*$/)
  const arrClock = arr.match(/(\d{1,2}):(\d{2})\s*$/)
  if (!depClock || !arrClock) return undefined
  let minutes =
    Number(arrClock[1]) * 60 + Number(arrClock[2]) - (Number(depClock[1]) * 60 + Number(depClock[2]))
  if (minutes <= 0) minutes += 24 * 60
  return minutes
}

export function googleFlightUrl(flight?: string): string | undefined {
  const iata = normalizeFlightNumber(flight)
  if (!iata || !splitIataFlight(iata)) return undefined
  return `https://www.google.com/search?q=${encodeURIComponent(iata)}`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

function utcDate(iso?: string): Date | undefined {
  if (!iso) return undefined
  const date = new Date(iso)
  return Number.isFinite(date.getTime()) ? date : undefined
}

export function formatFlightDay(iso?: string): string {
  const date = utcDate(iso)
  if (!date) return '—'
  return `${date.getUTCDate()} ${MONTHS[date.getUTCMonth()]} ${date.getUTCFullYear()}`
}

export function formatDepartureUtc(iso?: string): string {
  const date = utcDate(iso)
  if (!date) return '—'
  const hours = String(date.getUTCHours()).padStart(2, '0')
  const minutes = String(date.getUTCMinutes()).padStart(2, '0')
  return `${hours}:${minutes}`
}

export function formatRoute(origin?: string, destination?: string): string {
  if (origin && destination) return `${origin} → ${destination}`
  if (origin) return `${origin} →`
  if (destination) return `→ ${destination}`
  return '—'
}

export function formatDuration(minutes?: number): string {
  if (minutes == null || !Number.isFinite(minutes) || minutes <= 0) return '—'
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours === 0) return `${rest}m`
  if (rest === 0) return `${hours}h`
  return `${hours}h ${rest}m`
}

async function lookupIata(callsign: string): Promise<string | undefined> {
  const response = await fetch(`/adsbdb/v0/callsign/${encodeURIComponent(callsign)}`)
  if (!response.ok) return undefined
  const json = (await response.json()) as AdsbdbCallsign
  return normalizeFlightNumber(json.response?.flightroute?.callsign_iata)
}

export async function resolveIataNumbers(
  callsigns: string[],
  onProgress?: (done: number, total: number) => void,
): Promise<Map<string, string>> {
  const cache = readCache()
  const resolved = new Map<string, string>()
  const missing: string[] = []

  for (const raw of callsigns) {
    const callsign = raw.trim().toUpperCase()
    if (!callsign) continue
    if (cache[callsign]) resolved.set(callsign, cache[callsign])
    else missing.push(callsign)
  }

  const concurrency = 6
  let done = callsigns.length - missing.length
  onProgress?.(done, callsigns.length)

  for (let i = 0; i < missing.length; i += concurrency) {
    const chunk = missing.slice(i, i + concurrency)
    const found = await Promise.all(chunk.map((callsign) => lookupIata(callsign)))
    chunk.forEach((callsign, index) => {
      const iata = found[index]
      if (iata) {
        cache[callsign] = iata
        resolved.set(callsign, iata)
      }
    })
    done += chunk.length
    onProgress?.(done, callsigns.length)
  }

  writeCache(cache)
  return resolved
}
