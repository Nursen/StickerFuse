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
  const name = trend.trend_name || trend.name || 'Unknown Trend'
  const spike = trend.spike_score || trend.spike || 0
  const velocity = trend.velocity || trend.growth_rate || 0
  const comments = trend.comment_count || trend.comments || trend.engagement || 0
  const platforms = trend.platforms || trend.sources || []
  const confidence = trend.confidence || trend.confidence_level || ''
  const sentiment = trend.sentiment || trend.sentiment_label || ''
  const trajectory = trend.trajectory || ''
  const longevity = trend.longevity || trend.still_trending || ''
  const evidence = trend.evidence || trend.data_points || []
  const evidenceCount = Array.isArray(evidence) ? evidence.length : (trend.evidence_count || 0)

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
          <span>spike: {spike.toFixed ? spike.toFixed(1) : spike}x</span>
          <span>velocity: {velocity.toFixed ? velocity.toFixed(1) : velocity}/hr</span>
          <span>{comments} comments</span>
        </div>

        <div className="trend-indicators">
          <SentimentDisplay sentiment={sentiment} />
          <TrajectoryBadge trajectory={trajectory} />
          {longevity && (
            <span className="trend-longevity">
              3-day: <LongevityBadge prediction={longevity} />
            </span>
          )}
        </div>

        {evidenceCount > 0 && (
          <div className="trend-evidence-count">Backed by {evidenceCount} data points</div>
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

function TrendPulse({ onNavigateStudio }) {
  const { trends, setTrends, setSelectedTrend, sendChatMessage, chatLoading } = useTrend()
  const [searchTopic, setSearchTopic] = useState('')
  const [expandedIdx, setExpandedIdx] = useState(null)
  const [analyzing, setAnalyzing] = useState(false)

  const handleAnalyze = async () => {
    if (!searchTopic.trim() || analyzing) return
    setAnalyzing(true)
    const result = await sendChatMessage(
      `analyze trends for ${searchTopic} on subreddits ${searchTopic}`,
      { silent: false }
    )
    if (result && result.toolResults) {
      const parsed = extractTrends(result.toolResults)
      if (parsed.length > 0) {
        setTrends(parsed)
      }
    }
    setAnalyzing(false)
  }

  const handleMakeStickers = (trend) => {
    setSelectedTrend(trend)
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
          <p>Search for a topic to discover what's trending across Reddit, Google, YouTube, and more. We'll find the hottest sticker opportunities.</p>
          <div className="trend-suggestions">
            {['viral memes', 'anime', 'gaming', 'cottagecore'].map(s => (
              <button key={s} className="suggestion" onClick={() => setSearchTopic(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {analyzing && trends.length === 0 && (
        <div className="trend-loading">
          <div className="typing"><span></span><span></span><span></span></div>
          <p>Mining trends for "{searchTopic}"...</p>
        </div>
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
    </div>
  )
}

export default TrendPulse
