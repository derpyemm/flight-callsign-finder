import type { CallsignHit, SearchSource } from '../types'
import { preferFlightNumber } from './flightIdentity'

const STORAGE_KEY = 'sim-arrivals-cache-v3'

type CacheStore = Record<string, CallsignHit[]>

function cacheKey(aircraft: string, origin?: string, destination?: string): string {
  return `${aircraft}|${origin ?? ''}|${destination ?? ''}`
}

function readStore(): CacheStore {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    return raw ? (JSON.parse(raw) as CacheStore) : {}
  } catch {
    return {}
  }
}

function writeStore(store: CacheStore) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(store))
}

export function loadCachedHits(aircraft: string, origin?: string, destination?: string): CallsignHit[] {
  return readStore()[cacheKey(aircraft, origin, destination)] ?? []
}

export function mergeHits(existing: CallsignHit[], incoming: CallsignHit[]): CallsignHit[] {
  const byCallsign = new Map<string, CallsignHit>()
  for (const hit of [...existing, ...incoming]) {
    const key = hit.callsign
    const prev = byCallsign.get(key)
    if (!prev) {
      byCallsign.set(key, { ...hit, sources: [...hit.sources] })
      continue
    }
    const sources = new Set<SearchSource>([...prev.sources, ...hit.sources])
    byCallsign.set(key, {
      callsign: key,
      type: prev.type || hit.type,
      origin: hit.origin || prev.origin,
      destination: hit.destination || prev.destination,
      iata: preferFlightNumber(prev.iata, hit.iata),
      durationMinutes: hit.durationMinutes ?? prev.durationMinutes,
      count: prev.count + hit.count,
      lastSeen: [prev.lastSeen, hit.lastSeen].filter(Boolean).sort().at(-1),
      sources: [...sources],
    })
  }
  return [...byCallsign.values()].sort((a, b) => a.callsign.localeCompare(b.callsign))
}

export function saveHits(aircraft: string, hits: CallsignHit[], origin?: string, destination?: string) {
  const store = readStore()
  store[cacheKey(aircraft, origin, destination)] = hits
  writeStore(store)
}
