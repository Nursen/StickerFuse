import { useState, useRef } from 'react'
import { useTrend } from '../context/TrendContext'

const APPEAL_COLORS = { broad: '#22c55e', fandom: '#a855f7', deep_cut: '#ef4444' }
const APPEAL_LABELS = { broad: 'Broad Appeal', fandom: 'Fandom', deep_cut: 'Deep Cut' }

export default function IdeaBank({ onGoToStudio }) {
  const {
    activePack,
    addIdeaToPack,
    addIdeasBatch,
    removeIdeaFromPack,
    brainstormResults, setBrainstormResults,
    setStudioIdea,
    setStickerIdeas,
    setGeneratedStickers,
  } = useTrend()

  const [manualIdea, setManualIdea] = useState('')
  const [searchTopic, setSearchTopic] = useState('')
  const [analyzing, setAnalyzing] = useState(false)
  const [progressMsg, setProgressMsg] = useState('')
  const [addingAll, setAddingAll] = useState(false)
  const abortRef = useRef(null)

  const ideas = activePack?.ideas || []

  // --- Manual idea input ---
  const handleAddManual = async () => {
    const text = manualIdea.trim()
    if (!text) return
    try {
      await addIdeaToPack({ text, source: 'manual' })
      setManualIdea('')
    } catch (e) {
      console.error('addIdeaToPack failed:', e)
    }
  }

  // --- AI Brainstorm ---
  const handleBrainstorm = async () => {
    if (!searchTopic.trim()) return
    if (abortRef.current) abortRef.current.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setAnalyzing(true)
    setBrainstormResults(null)
    setProgressMsg('Mining fandom communities for what fans are saying right now...')

    const msgs = [
      'Scraping Reddit posts + top comments...',
      'Scanning YouTube for reaction videos...',
      'Checking Wikipedia pageview spikes...',
      'Synthesizing community pulse...',
      'Researching fandom DNA + current internet vernacular...',
      'Colliding fandom x internet culture...',
      'Generating sticker concepts grounded in real fan data...',
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
        signal: controller.signal,
      })
      clearInterval(interval)

      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()

      if (data.status === 'error' && data.error) {
        setProgressMsg(`Analysis failed: ${data.error}`)
      } else if (data.data) {
        const stickerIdeas = data.data.sticker_ideas || []
        setBrainstormResults(stickerIdeas)
        const syn = data.synthesis
        const sourceInfo = syn
          ? ` -- mined ${syn.post_count || 0} posts, ${syn.comment_count || 0} comments, ${syn.youtube_videos || 0} videos`
          : ''
        setProgressMsg(`${stickerIdeas.length} concepts for "${searchTopic}"${sourceInfo}`)
      } else {
        setProgressMsg('Unexpected response from server.')
      }
    } catch (err) {
      clearInterval(interval)
      if (err.name === 'AbortError') return
      setProgressMsg(`Error: ${err.message}`)
    } finally {
      if (!controller.signal.aborted) setAnalyzing(false)
    }
  }

  const isIdeaInBank = (aiIdea) => {
    const text = aiIdea.text_on_sticker || aiIdea.concept || ''
    return ideas.some(i => i.text === text)
  }

  const handleAddAiIdea = async (aiIdea) => {
    try {
      await addIdeaToPack({
        text: aiIdea.text_on_sticker || aiIdea.concept,
        source: 'ai',
        topic: searchTopic,
        concept: aiIdea.concept,
        visual_description: aiIdea.visual_description,
        fandom_element: aiIdea.fandom_element,
        internet_element: aiIdea.internet_element,
        category: aiIdea.category,
        estimated_appeal: aiIdea.estimated_appeal,
        why_its_funny: aiIdea.why_its_funny,
      })
    } catch (e) {
      console.error('addIdeaToPack failed:', e)
    }
  }

  const handleAddAll = async () => {
    if (!brainstormResults?.length) return
    setAddingAll(true)
    try {
      const batch = brainstormResults
        .filter(ai => !isIdeaInBank(ai))
        .map(ai => ({
          text: ai.text_on_sticker || ai.concept,
          source: 'ai',
          topic: searchTopic,
          concept: ai.concept,
          visual_description: ai.visual_description,
          fandom_element: ai.fandom_element,
          internet_element: ai.internet_element,
          category: ai.category,
          estimated_appeal: ai.estimated_appeal,
          why_its_funny: ai.why_its_funny,
        }))
      if (batch.length > 0) {
        await addIdeasBatch(batch)
      }
    } catch (e) {
      console.error('addIdeasBatch failed:', e)
    } finally {
      setAddingAll(false)
    }
  }

  const handleMakeSticker = (idea) => {
    setStudioIdea(idea)
    setStickerIdeas([])
    setGeneratedStickers([])
    onGoToStudio()
  }

  return (
    <div className="idea-bank-page">
      {/* Manual idea input */}
      <section className="idea-bank-section">
        <h3 className="idea-bank-section-title">Add your own idea</h3>
        <div className="manual-idea-input">
          <input
            type="text"
            className="trend-search-input"
            placeholder="Type your own sticker idea..."
            value={manualIdea}
            onChange={e => setManualIdea(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleAddManual() }}
          />
          <button
            className="trend-search-btn"
            onClick={handleAddManual}
            disabled={!manualIdea.trim()}
          >
            + Add
          </button>
        </div>
      </section>

      {/* AI Brainstorm */}
      <section className="idea-bank-section">
        <h3 className="idea-bank-section-title">AI Brainstorm</h3>
        <div className="ai-brainstorm">
          <input
            type="text"
            className="trend-search-input"
            placeholder="Search a fandom, show, or topic..."
            value={searchTopic}
            onChange={e => setSearchTopic(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') handleBrainstorm() }}
            disabled={analyzing}
          />
          <button
            className="trend-search-btn"
            onClick={handleBrainstorm}
            disabled={!searchTopic.trim() || analyzing}
          >
            {analyzing ? 'Brainstorming...' : 'Brainstorm with AI'}
          </button>
        </div>

        {analyzing && (
          <div className="trend-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <p className="progress-msg">{progressMsg}</p>
            <div className="progress-bar-track">
              <div className="progress-bar-fill progress-bar-animated" />
            </div>
          </div>
        )}

        {!analyzing && progressMsg && (
          <p className="progress-summary">{progressMsg}</p>
        )}

        {brainstormResults && brainstormResults.length > 0 && !analyzing && (
          <div className="brainstorm-results">
            <div className="brainstorm-results-header">
              <h4>AI Suggestions ({brainstormResults.length})</h4>
              <button
                className="studio-action-btn"
                onClick={handleAddAll}
                disabled={addingAll}
              >
                {addingAll ? 'Adding...' : 'Add All to Pack'}
              </button>
            </div>
            <div className="ideas-grid">
              {brainstormResults.map((idea, i) => {
                const inBank = isIdeaInBank(idea)
                const appeal = idea.estimated_appeal || 'fandom'
                return (
                  <div key={i} className={`idea-card ${inBank ? 'idea-in-bank' : ''}`}>
                    <div className="idea-card-top">
                      <span className="source-badge source-ai">AI</span>
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
                    {idea.fandom_element && idea.internet_element && (
                      <div className="idea-collision">
                        <span className="collision-tag fandom-tag">{idea.fandom_element}</span>
                        <span className="collision-x">x</span>
                        <span className="collision-tag internet-tag">{idea.internet_element}</span>
                      </div>
                    )}
                    {idea.why_its_funny && <p className="idea-why">{idea.why_its_funny}</p>}
                    {inBank ? (
                      <div className="idea-check">Already in bank</div>
                    ) : (
                      <button
                        className="add-to-bank-btn"
                        onClick={() => handleAddAiIdea(idea)}
                      >
                        + Add to Pack
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          </div>
        )}
      </section>

      {/* The Bank */}
      <section className="idea-bank-section">
        <h3 className="idea-bank-section-title">
          Idea Bank ({ideas.length})
        </h3>
        {ideas.length === 0 ? (
          <p className="studio-hint">
            No ideas yet. Add your own above or brainstorm with AI.
          </p>
        ) : (
          <div className="idea-bank-list">
            {ideas.map(idea => (
              <div key={idea.id} className="idea-bank-card">
                <div className="idea-bank-card-content">
                  <span className={`source-badge ${idea.source === 'ai' ? 'source-ai' : 'source-manual'}`}>
                    {idea.source === 'ai' ? 'AI' : 'Manual'}
                  </span>
                  <span className="idea-bank-text">{idea.text}</span>
                  {idea.topic && <span className="idea-bank-topic">{idea.topic}</span>}
                </div>
                <div className="idea-bank-card-actions">
                  <button
                    className="make-sticker-btn-small"
                    onClick={() => handleMakeSticker(idea)}
                  >
                    Make Sticker
                  </button>
                  <button
                    className="remove-idea-btn"
                    onClick={() => removeIdeaFromPack(idea.id)}
                  >
                    Remove
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  )
}
