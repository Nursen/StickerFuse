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
  const [researchReport, setResearchReport] = useState(null)
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
    setResearchReport(null)
    setProgressMsg('Step 1/4: Mapping the cultural universe...')

    const msgs = [
      'Step 1/4: Mapping entities, moments, and communities...',
      'Step 2/4: Gathering evidence across Reddit, YouTube, web...',
      'Step 2/4: Researching what people are saying (parallel)...',
      'Step 3/4: Synthesizing cultural insights...',
      'Step 3/4: Drawing conclusions from evidence...',
      'Step 4/4: Generating sticker opportunities...',
      'Step 4/4: Colliding fandom × internet culture...',
    ]
    let msgIdx = 0
    const interval = setInterval(() => {
      msgIdx = Math.min(msgIdx + 1, msgs.length - 1)
      setProgressMsg(msgs[msgIdx])
    }, 8000)

    try {
      const res = await fetch('http://localhost:8000/api/research', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic: searchTopic, max_entities: 6 }),
        signal: controller.signal,
      })
      clearInterval(interval)

      if (!res.ok) throw new Error(`Server error: ${res.status}`)
      const data = await res.json()

      if (data.status === 'error' && data.error) {
        setProgressMsg(`Research failed: ${data.error}`)
      } else if (data.report) {
        const report = data.report
        setResearchReport(report)
        const opps = report.opportunities || []
        setBrainstormResults(opps)
        const nInsights = report.insights?.length || 0
        const nEvidence = report.evidence?.length || 0
        setProgressMsg(
          `${opps.length} sticker concepts from ${nInsights} insights, ` +
          `${nEvidence} entities researched`
        )
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
        visual_description: aiIdea.visual_sketch || aiIdea.visual_description,
        why_now: aiIdea.why_now,
        target_buyer: aiIdea.target_buyer,
        emotional_hook: aiIdea.emotional_hook,
        source_insight: aiIdea.source_insight,
        // Legacy fields for backward compat with merch ideation results
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
          visual_description: ai.visual_sketch || ai.visual_description,
          why_now: ai.why_now,
          target_buyer: ai.target_buyer,
          emotional_hook: ai.emotional_hook,
          source_insight: ai.source_insight,
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
                    {/* Research agent fields */}
                    {idea.why_now && <p className="idea-why">🕐 {idea.why_now}</p>}
                    {idea.emotional_hook && <p className="idea-hook">💡 {idea.emotional_hook}</p>}
                    {idea.target_buyer && <p className="idea-buyer">🎯 {idea.target_buyer}</p>}
                    {/* Legacy merch ideation fields */}
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

        {/* Research Report (collapsible) */}
        {researchReport && !analyzing && (
          <details className="research-report-panel">
            <summary className="research-report-toggle">
              📋 Research Report — {researchReport.insights?.length || 0} insights,{' '}
              {researchReport.evidence?.length || 0} entities researched
            </summary>
            <div className="research-report-content">
              <p className="research-summary">{researchReport.executive_summary}</p>

              {researchReport.insights?.length > 0 && (
                <div className="research-insights">
                  <h5>Cultural Insights</h5>
                  {researchReport.insights.map((ins, i) => (
                    <div key={i} className="insight-card">
                      <div className="insight-header">
                        <span className={`virality-badge virality-${ins.virality}`}>{ins.virality}</span>
                        <strong>{ins.moment}</strong>
                      </div>
                      <p>{ins.what_happened}</p>
                      <p className="insight-reaction">{ins.community_reaction}</p>
                      <p className="insight-angle">🎨 {ins.sticker_angle}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </details>
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
