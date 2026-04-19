import { useState } from 'react'
import { useTrend } from '../context/TrendContext'

function CommunityView() {
  const { sendChatMessage, chatLoading } = useTrend()
  const [pastedText, setPastedText] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [analysisResult, setAnalysisResult] = useState(null)

  const handleAnalyze = async () => {
    if (!pastedText.trim() || analyzing) return
    setAnalyzing(true)
    const result = await sendChatMessage(
      `analyze this community text for recurring phrases, in-jokes, and sticker-worthy moments: ${pastedText}`
    )
    if (result) {
      setAnalysisResult(result.reply)
    }
    setAnalyzing(false)
  }

  const connections = [
    {
      name: 'Discord',
      desc: 'Connect a Discord server',
      color: '#5865F2',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M20.317 4.37a19.791 19.791 0 00-4.885-1.515.074.074 0 00-.079.037c-.21.375-.444.864-.608 1.25a18.27 18.27 0 00-5.487 0 12.64 12.64 0 00-.617-1.25.077.077 0 00-.079-.037A19.736 19.736 0 003.677 4.37a.07.07 0 00-.032.027C.533 9.046-.32 13.58.099 18.057a.082.082 0 00.031.057 19.9 19.9 0 005.993 3.03.078.078 0 00.084-.028c.462-.63.874-1.295 1.226-1.994a.076.076 0 00-.041-.106 13.107 13.107 0 01-1.872-.892.077.077 0 01-.008-.128 10.2 10.2 0 00.372-.292.074.074 0 01.077-.01c3.928 1.793 8.18 1.793 12.062 0a.074.074 0 01.078.01c.12.098.246.198.373.292a.077.077 0 01-.006.127 12.299 12.299 0 01-1.873.892.077.077 0 00-.041.107c.36.698.772 1.362 1.225 1.993a.076.076 0 00.084.028 19.839 19.839 0 006.002-3.03.077.077 0 00.032-.054c.5-5.177-.838-9.674-3.549-13.66a.061.061 0 00-.031-.03z"/>
        </svg>
      ),
    },
    {
      name: 'Twitch',
      desc: 'Monitor a Twitch channel',
      color: '#9146FF',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M11.571 4.714h1.715v5.143H11.57zm4.715 0H18v5.143h-1.714zM6 0L1.714 4.286v15.428h5.143V24l4.286-4.286h3.428L22.286 12V0zm14.571 11.143l-3.428 3.428h-3.429l-3 3v-3H6.857V1.714h13.714z"/>
        </svg>
      ),
    },
    {
      name: 'Slack',
      desc: 'Connect a Slack workspace',
      color: '#4A154B',
      icon: (
        <svg width="24" height="24" viewBox="0 0 24 24" fill="currentColor">
          <path d="M5.042 15.165a2.528 2.528 0 01-2.52 2.523A2.528 2.528 0 010 15.165a2.527 2.527 0 012.522-2.52h2.52v2.52zm1.271 0a2.527 2.527 0 012.521-2.52 2.527 2.527 0 012.521 2.52v6.313A2.528 2.528 0 018.834 24a2.528 2.528 0 01-2.521-2.522v-6.313zM8.834 5.042a2.528 2.528 0 01-2.521-2.52A2.528 2.528 0 018.834 0a2.528 2.528 0 012.521 2.522v2.52H8.834zm0 1.271a2.528 2.528 0 012.521 2.521 2.528 2.528 0 01-2.521 2.521H2.522A2.528 2.528 0 010 8.834a2.528 2.528 0 012.522-2.521h6.312zm6.313 2.521a2.528 2.528 0 012.521-2.521A2.528 2.528 0 0124 8.834a2.528 2.528 0 01-2.332 2.521h-2.521V8.834zm-1.271 0a2.528 2.528 0 01-2.521 2.521 2.528 2.528 0 01-2.521-2.521V2.522A2.528 2.528 0 0111.355 0a2.528 2.528 0 012.521 2.522v6.312zm-2.521 6.313a2.528 2.528 0 012.521 2.521 2.528 2.528 0 01-2.521 2.522 2.528 2.528 0 01-2.521-2.522v-2.521h2.521zm0-1.271a2.528 2.528 0 01-2.521-2.521 2.528 2.528 0 012.521-2.522h6.313A2.528 2.528 0 0124 15.165a2.528 2.528 0 01-2.522 2.521h-6.312z"/>
        </svg>
      ),
    },
  ]

  return (
    <div className="community-view">
      <div className="community-header">
        <h2>Community Mining</h2>
        <span className="beta-badge">BETA</span>
      </div>
      <p className="community-desc">
        Connect your community to discover niche trends, in-jokes, and sticker opportunities.
      </p>

      <div className="connection-cards">
        {connections.map(c => (
          <div key={c.name} className="connection-card" style={{ borderColor: c.color + '44' }}>
            <div className="connection-icon" style={{ color: c.color }}>{c.icon}</div>
            <div className="connection-info">
              <h4>{c.desc}</h4>
            </div>
            <button className="coming-soon-btn" disabled>Coming Soon</button>
          </div>
        ))}
      </div>

      <div className="community-paste">
        <h3>Or paste community text</h3>
        <p className="paste-desc">Chat logs, forum posts, Discord exports, etc.</p>
        <textarea
          className="paste-textarea"
          value={pastedText}
          onChange={e => setPastedText(e.target.value)}
          placeholder="Paste chat logs, forum posts, or community text here..."
          rows={6}
          disabled={analyzing}
        />
        <button
          className="trend-search-btn"
          onClick={handleAnalyze}
          disabled={!pastedText.trim() || analyzing}
        >
          {analyzing ? 'Analyzing...' : 'Analyze'}
        </button>
      </div>

      {analysisResult && (
        <div className="community-result">
          <h3>Analysis</h3>
          <div className="community-result-text">{analysisResult}</div>
        </div>
      )}
    </div>
  )
}

export default CommunityView
