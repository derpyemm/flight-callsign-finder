import type { CallsignHit, SearchSource } from '../types'

const STORAGE_KEY = 'sim-arrivals-cache-v1'

type CacheStore = Record<string, CallsignHit[]>

function cacheKey(aircraft: string, airport: string): string {
  return `${aircraft}|${airport}`
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

export function loadCachedHits(aircraft: string, airport: string): CallsignHit[] {
  return readStore()[cacheKey(aircraft, airport)] ?? []
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
      count: prev.count + hit.count,
      lastSeen: [prev.lastSeen, hit.lastSeen].filter(Boolean).sort().at(-1),
      sources: [...sources],
    })
  }
  return [...byCallsign.values()].sort((a, b) => a.callsign.localeCompare(b.callsign))
}

export function saveHits(aircraft: string, airport: string, hits: CallsignHit[]) {
  const store = readStore()
  store[cacheKey(aircraft, airport)] = hits
  writeStore(store)
}
