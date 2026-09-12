import { useMemo, useState } from 'react'
import { searchCallsigns } from './lib/search'
import type { SearchResult } from './types'

const TOKEN_KEY = 'fr24-api-token'
const OPENSKY_ID_KEY = 'opensky-client-id'
const OPENSKY_SECRET_KEY = 'opensky-client-secret'

function loadToken() {
  return localStorage.getItem(TOKEN_KEY) ?? ''
}

export default function App() {
  const [aircraft, setAircraft] = useState('A320')
  const [airport, setAirport] = useState('EHAM')
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
    if (result.hits.length === 0) {
      return `No recent evidence that ${result.types.join('/')} operates into ${result.airport}.`
    }
    return `${result.hits.length} callsign${result.hits.length === 1 ? '' : 's'} for ${result.types.join('/')} into ${result.airport}.`
  }, [result])

  async function onSearch(event: React.FormEvent) {
    event.preventDefault()
    setBusy(true)
    setError('')
    setStatus('Searching…')
    try {
      const next = await searchCallsigns({
        aircraft,
        airport,
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

  async function copyCallsign(callsign: string) {
    await navigator.clipboard.writeText(callsign)
    setCopied(callsign)
    window.setTimeout(() => setCopied(''), 1500)
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
          Arrival airport ICAO
          <input
            type="text"
            value={airport}
            onChange={(event) => setAirport(event.target.value)}
            spellCheck={false}
            maxLength={4}
            required
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
            Live: {result.liveMatched} inbound now / {result.liveChecked} of type airborne
            {result.recentFlights != null ? ` · OpenSky: ${result.recentFlights} recent arrivals` : ''}
            {result.fr24Days
              ? ` · FR24: ${result.fr24Flights ?? 0} flights over ${result.fr24Days} days`
              : ''}
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
                  <th>Type</th>
                  <th>Origin</th>
                  <th>Seen</th>
                  <th>Source</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {result.hits.map((hit) => (
                  <tr key={hit.callsign}>
                    <td className="callsign">{hit.callsign}</td>
                    <td>{hit.type}</td>
                    <td>{hit.origin ?? '—'}</td>
                    <td>{hit.count}</td>
                    <td>{hit.sources.join(', ')}</td>
                    <td>
                      <button type="button" className="copy" onClick={() => copyCallsign(hit.callsign)}>
                        {copied === hit.callsign ? 'Copied' : 'Copy'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </section>
      ) : null}
    </main>
  )
}
