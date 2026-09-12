const TYPE_CACHE_KEY = 'hex-type-cache-v1'

type TypeCache = Record<string, string>

function readCache(): TypeCache {
  try {
    const raw = localStorage.getItem(TYPE_CACHE_KEY)
    return raw ? (JSON.parse(raw) as TypeCache) : {}
  } catch {
    return {}
  }
}

function writeCache(cache: TypeCache) {
  localStorage.setItem(TYPE_CACHE_KEY, JSON.stringify(cache))
}

type AdsbdbAircraft = {
  response?: {
    aircraft?: {
      icao_type?: string
    }
  }
}

async function lookupHex(hex: string): Promise<string | undefined> {
  const response = await fetch(`/adsbdb/v0/aircraft/${encodeURIComponent(hex)}`)
  if (!response.ok) return undefined
  const json = (await response.json()) as AdsbdbAircraft
  return json.response?.aircraft?.icao_type?.toUpperCase()
}

export async function resolveTypes(
  hexes: string[],
  onProgress?: (done: number, total: number) => void,
): Promise<Map<string, string>> {
  const cache = readCache()
  const resolved = new Map<string, string>()
  const missing: string[] = []

  for (const hex of hexes) {
    const key = hex.toLowerCase()
    if (cache[key]) resolved.set(key, cache[key])
    else missing.push(key)
  }

  const concurrency = 6
  let done = hexes.length - missing.length
  onProgress?.(done, hexes.length)

  for (let i = 0; i < missing.length; i += concurrency) {
    const chunk = missing.slice(i, i + concurrency)
    const found = await Promise.all(chunk.map((hex) => lookupHex(hex)))
    chunk.forEach((hex, index) => {
      const type = found[index]
      if (type) {
        cache[hex] = type
        resolved.set(hex, type)
      }
    })
    done += chunk.length
    onProgress?.(done, hexes.length)
  }

  writeCache(cache)
  return resolved
}
