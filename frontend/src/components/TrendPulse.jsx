import { useState } from 'react'
import { useTrend } from '../context/TrendContext'

// Parse trend data from tool_results. The backend returns TrendReport objects
// inside tool results — we look for anything with trend-like keys.
function extractTrends(toolResults) {
  if (!toolResults || !toolResults.length) return []
  const found = []

  for (const tr of toolResults) {
    let data = tr.result || tr.data || tr.output || tr
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch (_) { continue }
    }

    // If it's a trend report with a trends array
    if (data && data.trends && Array.isArray(data.trends)) {
      found.push(...data.trends)
      continue
    }

    // If the result itself is an array of trend-like objects
    if (Array.isArray(data)) {
      const trendLike = data.filter(d => d && (d.trend_name || d.name || d.spike_score !== undefined))
      found.push(...trendLike)
      continue
    }

    // Single trend object
    if (data && (data.trend_name || data.name) && (data.spike_score !== undefined || data.confidence)) {
      found.push(data)
    }
  }

  return found
}

const PLATFORM_ICONS = {
  reddit: { label: 'Reddit', color: '#FF4500' },
  google: { label: 'Google', color: '#4285F4' },
  google_trends: { label: 'Google', color: '#4285F4' },
  youtube: { label: 'YouTube', color: '#FF0000' },
  wikipedia: { label: 'Wikipedia', color: '#FFF' },
  tiktok: { label: 'TikTok', color: '#69C9D0' },
}

function ConfidenceBadge({ level }) {
  const l = (level || '').toUpperCase()
  const cls = l === 'HIGH' ? 'badge-green' : l === 'MEDIUM' ? 'badge-yellow' : 'badge-gray'
  return <span className={`confidence-badge ${cls}`}>{l || 'N/A'}</span>
}

function SpikeBar({ score }) {
  const capped = Math.min(score || 0, 20)
  const pct = (capped / 20) * 100
  return (
    <div className="spike-bar-track">
      <div className="spike-bar-fill" style={{ width: `${pct}%` }} />
    </div>
  )
}

function SentimentDisplay({ sentiment }) {
  if (!sentiment) return null
  const s = (typeof sentiment === 'string' ? sentiment : sentiment.label || '').toLowerCase()
  if (s.includes('positive') || s.includes('strong positive')) return <span title={s}>Positive</span>
  if (s.includes('negative')) return <span title={s}>Negative</span>
  return <span title={s}>Neutral</span>
}

function TrajectoryBadge({ trajectory }) {
  if (!trajectory) return null
  const t = (trajectory || '').toLowerCase()
  if (t.includes('accel')) return <span className="trajectory-badge accelerating">Accelerating</span>
  if (t.includes('stable') || t.includes('steady')) return <span className="trajectory-badge stable">Stable</span>
  if (t.includes('fad') || t.includes('declin')) return <span className="trajectory-badge fading">Fading</span>
  return <span className="trajectory-badge stable">{trajectory}</span>
}

function LongevityBadge({ prediction }) {
  if (!prediction) return null
  const p = (typeof prediction === 'string' ? prediction : prediction.answer || '').toUpperCase()
  if (p.includes('YES')) return <span className="longevity-badge yes">YES</span>
  if (p.includes('NO')) return <span className="longevity-badge no">NO</span>
  return <span className="longevity-badge maybe">MAYBE</span>
}

function TrendCard({ trend, onExpand, expanded, onMakeStickers }) {
  const name = trend.name || trend.trend_name || 'Unknown Trend'
  const spike = trend.spike_score || 0
  const velocity = trend.engagement_velocity || 0
  const comments = trend.comment_volume || 0
  const platforms = trend.platforms_confirmed || trend.source_platforms || []
  const confidence = trend.confidence || ''
  const sentiment = trend.sentiment_label || ''
  const sentimentScore = trend.sentiment_score
  const emotionalIntensity = trend.emotional_intensity
  const trajectory = trend.trajectory || trend.trend_direction || ''
  const longevity = trend.will_be_trending_in_3_days
  const poissonEta = trend.poisson_eta
  const postCount = trend.post_count || 0
  const platformCount = trend.platform_count || platforms.length
  const evidence = trend.evidence || []
  const evidenceCount = evidence.length

  return (
    <div className={`trend-card ${expanded ? 'expanded' : ''}`}>
      <div className="trend-card-main" onClick={onExpand}>
        <div className="trend-card-top">
          <h3 className="trend-name">{name}</h3>
          <ConfidenceBadge level={confidence} />
        </div>

        <SpikeBar score={spike} />

        <div className="trend-platforms">
          {(Array.isArray(platforms) ? platforms : []).map((p, i) => {
            const key = (typeof p === 'string' ? p : p.name || '').toLowerCase().replace(/\s/g, '_')
            const info = PLATFORM_ICONS[key] || { label: key, color: '#888' }
            return (
              <span key={i} className="platform-dot" style={{ background: info.color }} title={info.label}>
                {info.label.charAt(0)}
              </span>
            )
          })}
        </div>

        <div className="trend-metrics">
          <span title="Spike score (Poisson)">📊 spike: {spike.toFixed ? spike.toFixed(1) : spike}x</span>
          <span title="Engagement per hour">📈 {velocity.toFixed ? velocity.toFixed(1) : velocity}/hr</span>
          <span title="Total comments">💬 {comments}</span>
          <span title="Posts analyzed">📝 {postCount} posts</span>
        </div>

        <div className="trend-indicators">
          {sentiment && <SentimentDisplay sentiment={sentiment} />}
          {emotionalIntensity != null && (
            <span className="emotional-intensity" title="% of posts with strong emotion">
              🔥 {(emotionalIntensity * 100).toFixed(0)}% intense
            </span>
          )}
          <TrajectoryBadge trajectory={trajectory} />
          {longevity != null && (
            <span className="trend-longevity">
              ⏱ 3-day: <LongevityBadge prediction={longevity === true ? 'YES' : longevity === false ? 'NO' : 'MAYBE'} />
            </span>
          )}
        </div>

        {(evidenceCount > 0 || platformCount > 1) && (
          <div className="trend-evidence-count">
            {platformCount > 1 ? `Confirmed on ${platformCount} platforms · ` : ''}
            Backed by {evidenceCount} data points
          </div>
        )}
      </div>

      {expanded && Array.isArray(evidence) && evidence.length > 0 && (
        <div className="trend-evidence-list">
          <h4>Evidence</h4>
          {evidence.slice(0, 10).map((e, i) => (
            <div key={i} className="evidence-item">
              <span className="evidence-title">{e.title || e.text || e.content || JSON.stringify(e)}</span>
              {e.url && <a href={e.url} target="_blank" rel="noopener noreferrer" className="evidence-link">link</a>}
              {e.score && <span className="evidence-score">{e.score} pts</span>}
              {e.platform && <span className="evidence-platform">{e.platform}</span>}
            </div>
          ))}
        </div>
      )}

      <button className="make-stickers-btn" onClick={(e) => { e.stopPropagation(); onMakeStickers(trend) }}>
        Make Stickers &rarr;
      </button>
    </div>
  )
}

const BUZZ_COLORS = { HOT: '#ef4444', WARM: '#f59e0b', NICHE: '#3b82f6' }
const POTENTIAL_COLORS = { HIGH: '#22c55e', MEDIUM: '#eab308', LOW: '#6b7280' }

function MomentCard({ moment, onMakeStickers }) {
  const buzz = (moment.estimated_buzz || '').toUpperCase()
  const potential = (moment.sticker_potential || '').split(/[^A-Z]/i)[0].toUpperCase()

  return (
    <div className="moment-card">
      <div className="moment-card-top">
        <h3 className="moment-name">{moment.name}</h3>
        <span className="buzz-badge" style={{ background: `${BUZZ_COLORS[buzz] || '#6b7280'}22`, color: BUZZ_COLORS[buzz] || '#6b7280' }}>
          {buzz || 'N/A'}
        </span>
      </div>

      <p className="moment-description">{moment.description}</p>

      <div className="moment-why">
        <span className="moment-why-label">Why viral:</span> {moment.why_its_viral}
      </div>

      <div className="moment-badges">
        <span className="potential-badge" style={{ background: `${POTENTIAL_COLORS[potential] || '#6b7280'}22`, color: POTENTIAL_COLORS[potential] || '#6b7280' }}>
          Sticker: {potential || '?'}
        </span>
      </div>

      {moment.sample_quotes && moment.sample_quotes.length > 0 && (
        <div className="moment-quotes">
          {moment.sample_quotes.slice(0, 3).map((q, i) => (
            <blockquote key={i} className="moment-quote">&ldquo;{q}&rdquo;</blockquote>
          ))}
        </div>
      )}

      <button className="make-stickers-btn" onClick={(e) => { e.stopPropagation(); onMakeStickers() }}>
        Make Stickers &rarr;
      </button>
    </div>
  )
}

const PROGRESS_SOURCES = ['Reddit', 'Google Trends', 'YouTube', 'Wikipedia', 'Web Search']

function TrendPulse({ onNavigateStudio }) {
  const { trends, setTrends, setSelectedTrend, moments, setMoments } = useTrend()
  const [searchTopic, setSearchTopic] = useState('')
  const [lookback, setLookback] = useState('week')
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)
  const [progressMsg, setProgressMsg] = useState('')

  const handleAnalyze = async () => {
    if (!searchTopic.trim() || analyzing) return
    setAnalyzing(true)
    setTrends([])
    setMoments(null)
    setProgressMsg('Starting analysis across 5 platforms...')

    // Animate progress messages
    const msgs = [
      'Mining Reddit posts + comments...',
      'Checking Google Trends for search spikes...',
      'Scanning YouTube for viral videos...',
      'Analyzing Wikipedia pageview spikes...',
      'Searching web for cross-platform mentions...',
      'Detecting viral moments from Reddit comments (Gemini)...',
      'Cross-correlating signals across platforms...',
      'Running sentiment analysis...',
      'Scoring and ranking trends...',
    ]
    let msgIdx = 0
    const interval = setInterval(() => {
      msgIdx = Math.min(msgIdx + 1, msgs.length - 1)
      setProgressMsg(msgs[msgIdx])
    }, 3000)

    try {
      const res = await fetch('http://localhost:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: searchTopic, lookback }),
      })
      clearInterval(interval)

      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()

      if (data.report && data.report.trends) {
        setTrends(data.report.trends)
        if (data.moments) {
          setMoments(data.moments)
        }
        const errCount = (data.progress?.errors || []).length
        const momentCount = data.moments?.moments?.length || 0
        setProgressMsg(
          `Found ${data.report.trends.length} trends from ${data.report.total_posts_analyzed || 0} posts` +
          (momentCount > 0 ? ` + ${momentCount} viral moments from comments` : '') +
          (errCount > 0 ? ` (${errCount} source${errCount > 1 ? 's' : ''} had issues)` : '')
        )
      } else if (data.error) {
        setProgressMsg(`Analysis failed: ${data.error}`)
      } else {
        setProgressMsg('No trends found. Try a broader topic.')
      }
    } catch (err) {
      clearInterval(interval)
      setProgressMsg(`Error: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleTrendingNow = async () => {
    if (analyzing) return
    setAnalyzing(true)
    setTrends([])
    setProgressMsg('Scanning the internet for the biggest trends right now...')

    const msgs = [
      'Mining top Reddit communities...',
      'Checking Wikipedia for pageview spikes...',
      'Cross-correlating signals...',
      'Scoring and ranking...',
    ]
    let msgIdx = 0
    const interval = setInterval(() => {
      msgIdx = Math.min(msgIdx + 1, msgs.length - 1)
      setProgressMsg(msgs[msgIdx])
    }, 3000)

    try {
      const res = await fetch('http://localhost:8000/api/trending')
      clearInterval(interval)
      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()
      if (data.report && data.report.trends) {
        setTrends(data.report.trends)
        setProgressMsg(`Found ${data.report.trends.length} trending topics${data.cached ? ' (cached)' : ''}`)
      } else {
        setProgressMsg('Could not load trending topics.')
      }
    } catch (err) {
      clearInterval(interval)
      setProgressMsg(`Error: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  const handleMakeStickers = (trend) => {
    const parent = searchTopic.trim() || undefined
    setSelectedTrend(parent ? { ...trend, parent_topic: parent } : { ...trend })
    onNavigateStudio()
  }

  const handleMakeStickersMoment = (moment) => {
    const parent = searchTopic.trim() || undefined
    setSelectedTrend({
      name: moment.name,
      description: moment.description,
      ...(parent ? { parent_topic: parent } : {}),
    })
    onNavigateStudio()
  }

  return (
    <div className="trend-pulse">
      <div className="trend-search">
        <input
          type="text"
          className="trend-search-input"
          placeholder="Enter a topic to analyze (e.g. 'cats', 'AI memes', 'Minecraft')..."
          value={searchTopic}
          onChange={e => setSearchTopic(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleAnalyze()}
          disabled={analyzing}
        />
        <select
          className="lookback-select"
          value={lookback}
          onChange={e => setLookback(e.target.value)}
          disabled={analyzing}
        >
          <option value="day">Last 24 hours</option>
          <option value="3days">Last 3 days</option>
          <option value="week">Last week</option>
          <option value="month">Last month</option>
        </select>
        <button
          className="trend-search-btn"
          onClick={handleAnalyze}
          disabled={!searchTopic.trim() || analyzing}
        >
          {analyzing ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {trends.length === 0 && !analyzing && (
        <div className="trend-empty">
          <div className="trend-empty-icon">&#128200;</div>
          <h2>Trend Pulse</h2>
          <p>Search for a topic or see what's trending right now across the internet.</p>
          <button className="trending-now-btn" onClick={handleTrendingNow} disabled={analyzing}>
            🔥 What's Trending Right Now
          </button>
          <div className="trend-suggestions">
            {['viral memes', 'anime', 'gaming', 'cottagecore', 'Taylor Swift'].map(s => (
              <button key={s} className="suggestion" onClick={() => setSearchTopic(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {analyzing && (
        <div className="trend-loading">
          <div className="typing"><span></span><span></span><span></span></div>
          <p className="progress-msg">{progressMsg}</p>
          <div className="progress-bar-track">
            <div className="progress-bar-fill progress-bar-animated" />
          </div>
        </div>
      )}

      {!analyzing && progressMsg && trends.length > 0 && (
        <p className="progress-summary">{progressMsg}</p>
      )}

      {trends.length > 0 && (
        <div className="trend-grid">
          {trends.map((trend, i) => (
            <TrendCard
              key={i}
              trend={trend}
              expanded={expandedIdx === i}
              onExpand={() => setExpandedIdx(expandedIdx === i ? null : i)}
              onMakeStickers={handleMakeStickers}
            />
          ))}
        </div>
      )}

      {moments && moments.moments && moments.moments.length > 0 && (
        <section className="moments-section">
          <h2 className="section-title">Viral Moments</h2>
          <p className="section-subtitle">
            Specific scenes, quotes, and memes the community is buzzing about
            ({moments.total_comments_analyzed} comments analyzed)
          </p>
          {moments.community_vibe && (
            <p className="community-vibe">Community vibe: {moments.community_vibe}</p>
          )}
          <div className="moments-grid">
            {moments.moments.map((moment, i) => (
              <MomentCard key={i} moment={moment} onMakeStickers={() => handleMakeStickersMoment(moment)} />
            ))}
          </div>
        </section>
      )}
    </div>
  )
}

export default TrendPulse
