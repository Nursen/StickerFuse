import { useState } from 'react'
import { useTrend } from '../context/TrendContext'

const APPEAL_COLORS = { broad: '#22c55e', fandom: '#a855f7', deep_cut: '#ef4444' }
const APPEAL_LABELS = { broad: 'Broad Appeal', fandom: 'Fandom', deep_cut: 'Deep Cut' }
const CATEGORY_EMOJI = {
  quote_mashup: '💬', character_meme: '🎭', ship_name: '💕',
  visual_pun: '🎨', identity_statement: '✊', anachronism: '⏰', inside_joke: '🤫',
}

function StickerIdeaCard({ idea, selected, onSelect }) {
  const appeal = idea.estimated_appeal || 'fandom'
  const cat = idea.category || ''
  const emoji = CATEGORY_EMOJI[cat] || '✨'

  return (
    <div
      className={`idea-card ${selected ? 'idea-selected' : ''}`}
      onClick={onSelect}
    >
      <div className="idea-card-top">
        <span className="idea-emoji">{emoji}</span>
        <span
          className="appeal-badge"
          style={{
            background: `${APPEAL_COLORS[appeal] || '#6b7280'}18`,
            color: APPEAL_COLORS[appeal] || '#6b7280',
          }}
        >
          {APPEAL_LABELS[appeal] || appeal}
        </span>
      </div>

      {idea.text_on_sticker && (
        <div className="idea-sticker-text">"{idea.text_on_sticker}"</div>
      )}

      <p className="idea-concept">{idea.concept}</p>

      <div className="idea-collision">
        <span className="collision-tag fandom-tag">{idea.fandom_element}</span>
        <span className="collision-x">×</span>
        <span className="collision-tag internet-tag">{idea.internet_element}</span>
      </div>

      <p className="idea-why">{idea.why_its_funny}</p>

      {selected && <div className="idea-check">✓ Selected</div>}
    </div>
  )
}

function FandomDNAPanel({ dna }) {
  if (!dna) return null
  return (
    <details className="fandom-dna-panel">
      <summary className="fandom-dna-toggle">🧬 Fandom DNA</summary>
      <div className="fandom-dna-content">
        {dna.iconic_quotes?.length > 0 && (
          <div className="dna-section">
            <span className="dna-label">Quotes:</span>
            <div className="dna-tags">{dna.iconic_quotes.map((q, i) => <span key={i} className="dna-tag">"{q}"</span>)}</div>
          </div>
        )}
        {dna.ship_names?.length > 0 && (
          <div className="dna-section">
            <span className="dna-label">Ships:</span>
            <div className="dna-tags">{dna.ship_names.map((s, i) => <span key={i} className="dna-tag ship-tag">{s}</span>)}</div>
          </div>
        )}
        {dna.visual_icons?.length > 0 && (
          <div className="dna-section">
            <span className="dna-label">Icons:</span>
            <div className="dna-tags">{dna.visual_icons.map((v, i) => <span key={i} className="dna-tag">{v}</span>)}</div>
          </div>
        )}
      </div>
    </details>
  )
}

function TrendPulse({ onNavigateStudio }) {
  const { setSelectedTrend, setViralBites } = useTrend()
  const [searchTopic, setSearchTopic] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [progressMsg, setProgressMsg] = useState('')
  const [merchResult, setMerchResult] = useState(null)
  const [selectedIdeas, setSelectedIdeas] = useState(new Set())

  const handleSearch = async () => {
    if (!searchTopic.trim() || analyzing) return
    setAnalyzing(true)
    setMerchResult(null)
    setSelectedIdeas(new Set())
    setProgressMsg('Researching fandom DNA + current internet culture...')

    const msgs = [
      'Searching web for fandom quotes, ships, and icons...',
      'Finding trending internet phrases and meme formats...',
      'Colliding fandom × internet culture...',
      'Generating sticker concepts...',
      'Ranking by appeal and creativity...',
    ]
    let msgIdx = 0
    const interval = setInterval(() => {
      msgIdx = Math.min(msgIdx + 1, msgs.length - 1)
      setProgressMsg(msgs[msgIdx])
    }, 4000)

    try {
      const res = await fetch('http://localhost:8000/api/ideate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: searchTopic }),
      })
      clearInterval(interval)

      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()

      if (data.data) {
        setMerchResult(data.data)
        const count = data.data.sticker_ideas?.length || 0
        setProgressMsg(`${count} sticker concepts generated for "${searchTopic}"`)
      } else if (data.error) {
        setProgressMsg(`Error: ${data.error}`)
      }
    } catch (err) {
      clearInterval(interval)
      setProgressMsg(`Error: ${err.message}`)
    } finally {
      setAnalyzing(false)
    }
  }

  const toggleIdeaSelection = (idx) => {
    setSelectedIdeas(prev => {
      const next = new Set(prev)
      if (next.has(idx)) next.delete(idx)
      else next.add(idx)
      return next
    })
  }

  const handleCreateSelected = () => {
    if (selectedIdeas.size === 0 || !merchResult) return
    const ideas = merchResult.sticker_ideas.filter((_, i) => selectedIdeas.has(i))
    // Pass selected ideas to Studio as viral bites (they have text + visual descriptions)
    setViralBites(ideas.map(idea => ({
      text: idea.text_on_sticker || idea.concept,
      context: `${idea.fandom_element} × ${idea.internet_element}`,
      source_type: idea.category,
      visual_description: idea.visual_description,
      monetization_potential: idea.estimated_appeal === 'broad' ? 'high' : 'medium',
    })))
    setSelectedTrend({
      name: searchTopic,
      description: `Merch concepts for ${searchTopic}`,
      parent_topic: searchTopic,
    })
    onNavigateStudio()
  }

  const ideas = merchResult?.sticker_ideas || []
  const recommended = merchResult?.recommended_pack || []

  return (
    <div className="trend-pulse">
      <div className="trend-search">
        <input
          type="text"
          className="trend-search-input"
          placeholder="Enter a fandom, show, game, artist, or cultural moment..."
          value={searchTopic}
          onChange={e => setSearchTopic(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && handleSearch()}
          disabled={analyzing}
        />
        <button
          className="trend-search-btn"
          onClick={handleSearch}
          disabled={!searchTopic.trim() || analyzing}
        >
          {analyzing ? 'Generating...' : 'Generate Ideas'}
        </button>
      </div>

      {/* Empty state */}
      {!merchResult && !analyzing && (
        <div className="trend-empty">
          <div className="trend-empty-icon">✨</div>
          <h2>What stickers should we make?</h2>
          <p>
            Enter any fandom, show, game, artist, or cultural moment. We'll find the clever
            intersections between fandom culture and internet vernacular — the stickers fans
            actually want on their laptops.
          </p>
          <div className="trend-suggestions">
            {['Bridgerton', 'Minecraft', 'Taylor Swift', 'The Bear', 'Dune', 'Animal Crossing'].map(s => (
              <button key={s} className="suggestion" onClick={() => setSearchTopic(s)}>{s}</button>
            ))}
          </div>
        </div>
      )}

      {/* Loading */}
      {analyzing && (
        <div className="trend-loading">
          <div className="typing"><span></span><span></span><span></span></div>
          <p className="progress-msg">{progressMsg}</p>
          <div className="progress-bar-track">
            <div className="progress-bar-fill progress-bar-animated" />
          </div>
        </div>
      )}

      {/* Results */}
      {merchResult && !analyzing && (
        <>
          {/* Summary */}
          <div className="results-header">
            <p className="progress-summary">{progressMsg}</p>
            {selectedIdeas.size > 0 && (
              <button className="create-selected-btn" onClick={handleCreateSelected}>
                Create {selectedIdeas.size} Sticker{selectedIdeas.size > 1 ? 's' : ''} →
              </button>
            )}
          </div>

          {/* Fandom DNA (collapsible) */}
          <FandomDNAPanel dna={merchResult.fandom_dna} />

          {/* Recommended Pack */}
          {recommended.length > 0 && (
            <div className="recommended-pack">
              <h3 className="pack-title">⭐ Recommended Pack</h3>
              <div className="pack-items">
                {recommended.map((r, i) => <span key={i} className="pack-item">{r}</span>)}
              </div>
            </div>
          )}

          {/* All Ideas */}
          <div className="ideas-grid">
            {ideas.map((idea, i) => (
              <StickerIdeaCard
                key={i}
                idea={idea}
                selected={selectedIdeas.has(i)}
                onSelect={() => toggleIdeaSelection(i)}
              />
            ))}
          </div>

          {/* Internet vernacular used */}
          {merchResult.current_internet_vernacular?.length > 0 && (
            <details className="vernacular-panel">
              <summary className="vernacular-toggle">🌐 Internet vernacular used</summary>
              <div className="vernacular-tags">
                {merchResult.current_internet_vernacular.map((v, i) => (
                  <span key={i} className="vernacular-tag">{v}</span>
                ))}
              </div>
            </details>
          )}
        </>
      )}
    </div>
  )
}

export default TrendPulse
