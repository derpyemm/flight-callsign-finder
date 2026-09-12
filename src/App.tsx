import { useMemo, useState } from 'react'
import { searchCallsigns } from './lib/search'
import { formatDepartureUtc, formatDuration, formatFlightDay, formatRoute, googleFlightUrl } from './lib/flightIdentity'
import type { SearchResult } from './types'

const TOKEN_KEY = 'fr24-api-token'
const OPENSKY_ID_KEY = 'opensky-client-id'
const OPENSKY_SECRET_KEY = 'opensky-client-secret'
function loadToken() {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

function routeSummary(origin?: string, destination?: string): string {
  if (origin && destination) return `${origin} → ${destination}`
  if (destination) return `into ${destination}`
  if (origin) return `out of ${origin}`
  return ''
}

export default function App() {
  const [aircraft, setAircraft] = useState('')
  const [origin, setOrigin] = useState('')
  const [destination, setDestination] = useState('')
  const [includeFamily, setIncludeFamily] = useState(true)
  const [token, setToken] = useState(loadToken)
  const [openskyId, setOpenskyId] = useState(() => localStorage.getItem(OPENSKY_ID_KEY) ?? '')
  const [openskySecret, setOpenskySecret] = useState(() => localStorage.getItem(OPENSKY_SECRET_KEY) ?? '')
  const [lookbackDays, setLookbackDays] = useState(2)
  const [showSettings, setShowSettings] = useState(() => !loadToken().trim())
  const [status, setStatus] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [result, setResult] = useState<SearchResult | null>(null)
  const [copied, setCopied] = useState('')

  const fr24Token = token.trim()

  const summary = useMemo(() => {
    if (!result) return ''
    const where = routeSummary(result.origin, result.destination)
    if (result.hits.length === 0) {
      return `No recent evidence that ${result.types.join('/')} operates ${where}.`
    }
    return `${result.hits.length} callsign${result.hits.length === 1 ? '' : 's'} for ${result.types.join('/')} ${where}.`
  }, [result])

  async function onSearch(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setStatus('Searching…')
    try {
      const next = await searchCallsigns({
        aircraft,
        origin,
        destination,
        includeFamily,
        openskyClientId: openskyId,
        openskyClientSecret: openskySecret,
        fr24Token: fr24Token || undefined,
        fr24LookbackDays: fr24Token ? lookbackDays : undefined,
        onProgress: setStatus,
      })
      setResult(next)
      setStatus(next.hits.length ? 'Done.' : 'Search finished with no matches.')
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Search failed.')
      setStatus('')
    } finally {
      setBusy(false)
    }
  }

  function saveToken() {
    localStorage.setItem(TOKEN_KEY, token.trim())
    localStorage.setItem(OPENSKY_ID_KEY, openskyId.trim())
    localStorage.setItem(OPENSKY_SECRET_KEY, openskySecret.trim())
    setShowSettings(false)
  }

  async function copyValue(value: string) {
    try {
      await navigator.clipboard.writeText(value)
      setCopied(value)
      window.setTimeout(() => setCopied(''), 1500)
    } catch {
      setCopied('')
    }
  }

  return (
    <main className="page">
      <header className="header">
        <div>
          <p className="kicker">Flight sim helper</p>
          <h1>Callsign finder</h1>
          <p className="lede">
            Live traffic shows aircraft still inbound. Landed flights from today and yesterday come
            from Flightradar24 history — paste an API token in settings.
          </p>
        </div>
        <button type="button" className="ghost" onClick={() => setShowSettings((open) => !open)}>
          API settings
        </button>
      </header>

      {showSettings ? (
        <section className="panel settings">
          <label>
            Flightradar24 API token
            <input
              type="password"
              autoComplete="off"
              value={token}
              onChange={(event) => setToken(event.target.value)}
              placeholder="Paste Explorer token"
            />
          </label>
          <p className="hint">
            Stored only in this browser. Silver website access is not an API token. Use an Explorer
            API token from fr24api.flightradar24.com — that is what sees today's and yesterday's
            landed flights.
          </p>
          <label>
            OpenSky client ID
            <input
              className="plain"
              type="text"
              autoComplete="off"
              value={openskyId}
              onChange={(event) => setOpenskyId(event.target.value)}
              placeholder="Optional"
            />
          </label>
          <label>
            OpenSky client secret
            <input
              type="password"
              autoComplete="off"
              value={openskySecret}
              onChange={(event) => setOpenskySecret(event.target.value)}
            />
          </label>
          <p className="hint">
            Optional. Free OpenSky arrivals can fill in extra days, but today usually appears only
            after the overnight batch.
          </p>
          <button type="button" onClick={saveToken}>
            Save keys
          </button>
        </section>
      ) : null}

      <form className="panel form" onSubmit={onSearch}>
        <label>
          Aircraft ICAO
          <input
            type="text"
            value={aircraft}
            onChange={(event) => setAircraft(event.target.value)}
            spellCheck={false}
            maxLength={4}
            required
          />
        </label>
        <label>
          Departure ICAO
          <input
            type="text"
            value={origin}
            onChange={(event) => setOrigin(event.target.value)}
            spellCheck={false}
            maxLength={4}
            placeholder="Any"
          />
        </label>
        <label>
          Arrival ICAO
          <input
            type="text"
            value={destination}
            onChange={(event) => setDestination(event.target.value)}
            spellCheck={false}
            maxLength={4}
            placeholder="Any"
          />
        </label>
        <label className="check">
          <input
            type="checkbox"
            checked={includeFamily}
            onChange={(event) => setIncludeFamily(event.target.checked)}
          />
          Include family variants (A320 + A20N, BCS3 + BCS1)
        </label>
        {fr24Token ? (
          <label>
            FR24 history days
            <input
              type="number"
              min={1}
              max={30}
              value={lookbackDays}
              onChange={(event) => setLookbackDays(Number(event.target.value))}
            />
          </label>
        ) : (
          <p className="hint form-hint">
            No Flightradar24 token yet — search will only see aircraft still in the air.
          </p>
        )}
        <button type="submit" disabled={busy}>
          {busy ? 'Searching…' : 'Search callsigns'}
        </button>
      </form>

      {status ? <p className="status">{status}</p> : null}
      {error ? <p className="error">{error}</p> : null}

      {result ? (
        <section className="panel results">
          <h2>{summary}</h2>
          <p className="meta">
            {[
              result.liveMatched ? `Live: ${result.liveMatched} matching now` : '',
              result.recentFlights != null ? `OpenSky: ${result.recentFlights} recent flights` : '',
              result.fr24Days ? `FR24: ${result.fr24Flights ?? 0} flights over ${result.fr24Days} days` : '',
              result.hits.length
                ? 'Block is actual takeoff-to-landing; click it for Google’s scheduled time.'
                : '',
            ]
              .filter(Boolean)
              .join(' · ')}
          </p>
          {result.warnings.map((warning) => (
            <p key={warning} className="warning">
              {warning}
            </p>
          ))}
          {result.hits.length ? (
            <table>
              <thead>
                <tr>
                  <th>Callsign</th>
                  <th>IATA</th>
                  <th>Block</th>
                  <th>Type</th>
                  <th>Route</th>
                  <th>Day</th>
                  <th>Dep UTC</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {result.hits.map((hit) => {
                  const copyText = hit.iata || hit.callsign
                  const googleUrl = googleFlightUrl(hit.iata)
                  const blockLabel = formatDuration(hit.durationMinutes)
                  return (
                    <tr key={hit.callsign}>
                      <td className="callsign">{hit.callsign}</td>
                      <td className="callsign">{hit.iata ?? '—'}</td>
                      <td>
                        {googleUrl ? (
                          <a className="flight-link" href={googleUrl} target="_blank" rel="noreferrer">
                            {blockLabel === '—' ? hit.iata : blockLabel}
                          </a>
                        ) : (
                          blockLabel
                        )}
                      </td>
                      <td>{hit.type}</td>
                      <td className="callsign">{formatRoute(hit.origin, hit.destination)}</td>
                      <td className="callsign">{formatFlightDay(hit.lastSeen)}</td>
                      <td className="callsign">{formatDepartureUtc(hit.lastSeen)}</td>
                      <td>
                        <button type="button" className="copy" onClick={() => copyValue(copyText)}>
                          {copied === copyText ? 'Copied' : 'Copy'}
                        </button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}
