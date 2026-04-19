import { useState } from 'react'
import { useTrend } from '../context/TrendContext'

function extractViralBites(toolResults) {
  if (!toolResults) return []
  const bites = []
  for (const tr of toolResults) {
    let data = tr.result || tr.data || tr.output || tr
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch (_) { continue }
    }
    if (data && data.viral_bites && Array.isArray(data.viral_bites)) {
      bites.push(...data.viral_bites)
    } else if (data && data.bites && Array.isArray(data.bites)) {
      bites.push(...data.bites)
    } else if (Array.isArray(data)) {
      const biteLike = data.filter(d => d && (d.text || d.phrase || d.bite))
      bites.push(...biteLike)
    }
  }
  return bites
}

function extractStickerConcepts(toolResults) {
  if (!toolResults) return []
  const concepts = []
  for (const tr of toolResults) {
    let data = tr.result || tr.data || tr.output || tr
    if (typeof data === 'string') {
      try { data = JSON.parse(data) } catch (_) { continue }
    }
    if (data && data.sticker_ideas && Array.isArray(data.sticker_ideas)) {
      concepts.push(...data.sticker_ideas)
    } else if (data && data.ideas && Array.isArray(data.ideas)) {
      concepts.push(...data.ideas)
    } else if (data && data.concepts && Array.isArray(data.concepts)) {
      concepts.push(...data.concepts)
    } else if (Array.isArray(data)) {
      const conceptLike = data.filter(d => d && (d.art_style || d.style || d.prompt || d.description))
      concepts.push(...conceptLike)
    }
  }
  return concepts
}

function extractStickerImage(toolResults) {
  if (!toolResults) return []
  const images = []
  for (const tr of toolResults) {
    const raw = tr.result || tr.data || tr.output || ''
    if (typeof raw === 'string') {
      const match = raw.match(/Sticker image saved to:.*?([^/\\]+\.png)/i)
      if (match) images.push(match[1])
      // Also check for just a filename pattern
      const fnMatch = raw.match(/([a-zA-Z0-9_-]+\.png)/g)
      if (fnMatch) {
        for (const fn of fnMatch) {
          if (!images.includes(fn)) images.push(fn)
        }
      }
    }
  }
  return images
}

function StickerStudio({ onNavigateTrends }) {
  const {
    selectedTrend, setSelectedTrend,
    viralBites, setViralBites,
    stickerIdeas, setStickerIdeas,
    generatedStickers, setGeneratedStickers,
    sendChatMessage, chatLoading,
  } = useTrend()

  const [selectedBite, setSelectedBite] = useState(null)
  const [selectedConcept, setSelectedConcept] = useState(null)
  const [loadingBites, setLoadingBites] = useState(false)
  const [loadingConcepts, setLoadingConcepts] = useState(false)
  const [loadingImage, setLoadingImage] = useState(false)
  const [refinement, setRefinement] = useState('')

  const trendName = selectedTrend
    ? (selectedTrend.trend_name || selectedTrend.name || 'selected trend')
    : null

  const handleExtractBites = async () => {
    if (!trendName || loadingBites) return
    setLoadingBites(true)
    const result = await sendChatMessage(`extract viral bites from '${trendName}'`)
    if (result && result.toolResults) {
      const parsed = extractViralBites(result.toolResults)
      if (parsed.length > 0) setViralBites(parsed)
    }
    setLoadingBites(false)
  }

  const handleGenerateConcepts = async (bite) => {
    if (loadingConcepts) return
    setSelectedBite(bite)
    setLoadingConcepts(true)
    const biteText = bite.text || bite.phrase || bite.bite || JSON.stringify(bite)
    const result = await sendChatMessage(`generate sticker ideas for '${biteText}'`)
    if (result && result.toolResults) {
      const parsed = extractStickerConcepts(result.toolResults)
      if (parsed.length > 0) setStickerIdeas(parsed)
    }
    setLoadingConcepts(false)
  }

  const handleGenerateImage = async (concept) => {
    if (loadingImage) return
    setSelectedConcept(concept)
    setLoadingImage(true)
    const prompt = concept.visual_description || concept.concept_description || concept.prompt || concept.description || JSON.stringify(concept)
    const result = await sendChatMessage(`generate a sticker image for: ${prompt}`)
    if (result && result.toolResults) {
      const images = extractStickerImage(result.toolResults)
      if (images.length > 0) {
        setGeneratedStickers(prev => [...prev, ...images])
      }
    }
    setLoadingImage(false)
  }

  const handleRefinement = async () => {
    if (!refinement.trim()) return
    const result = await sendChatMessage(refinement)
    if (result && result.toolResults) {
      const images = extractStickerImage(result.toolResults)
      if (images.length > 0) {
        setGeneratedStickers(prev => [...prev, ...images])
      }
    }
    setRefinement('')
  }

  if (!selectedTrend) {
    return (
      <div className="studio-empty">
        <div className="studio-empty-icon">&#127912;</div>
        <h2>Sticker Studio</h2>
        <p>Select a trend from Trend Pulse to start creating stickers.</p>
        <button className="back-link" onClick={onNavigateTrends}>&larr; Go to Trends</button>
      </div>
    )
  }

  return (
    <div className="sticker-studio">
      <div className="studio-header">
        <button className="back-link" onClick={onNavigateTrends}>&larr; Back to Trends</button>
        <h2>Creating stickers for: <span className="studio-trend-name">{trendName}</span></h2>
      </div>

      {/* Step 1: Viral Bites */}
      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">1</span> Viral Bites</h3>
          {viralBites.length === 0 && (
            <button className="studio-action-btn" onClick={handleExtractBites} disabled={loadingBites}>
              {loadingBites ? 'Extracting...' : 'Extract Viral Bites'}
            </button>
          )}
        </div>
        {loadingBites && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>Finding viral phrases...</span>
          </div>
        )}
        {viralBites.length > 0 && (
          <div className="bites-scroll">
            {viralBites.map((bite, i) => {
              const text = bite.text || bite.phrase || bite.bite || JSON.stringify(bite)
              const source = bite.source_type || bite.source || bite.type || ''
              const potential = bite.monetization_potential || bite.potential || ''
              const isSelected = selectedBite === bite
              return (
                <div
                  key={i}
                  className={`bite-card ${isSelected ? 'selected' : ''}`}
                  onClick={() => handleGenerateConcepts(bite)}
                >
                  <div className="bite-text">"{text}"</div>
                  <div className="bite-meta">
                    {source && <span className="bite-source">{source}</span>}
                    {potential && <span className="bite-potential">{potential}</span>}
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Step 2: Sticker Concepts */}
      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">2</span> Sticker Concepts</h3>
        </div>
        {loadingConcepts && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>Generating concepts...</span>
          </div>
        )}
        {stickerIdeas.length > 0 && (
          <div className="concepts-grid">
            {stickerIdeas.map((concept, i) => {
              const style = concept.art_style || concept.style || ''
              const layout = concept.layout_type || concept.layout || ''
              const desc = concept.concept_description || concept.visual_description || concept.description || concept.prompt || ''
              const colors = concept.colors || concept.color_palette || []
              return (
                <div key={i} className="concept-card">
                  {style && <div className="concept-style">{style}</div>}
                  {layout && <div className="concept-layout">{layout}</div>}
                  <div className="concept-desc">{desc}</div>
                  {colors.length > 0 && (
                    <div className="concept-colors">
                      {(Array.isArray(colors) ? colors : []).slice(0, 5).map((c, j) => (
                        <span key={j} className="color-swatch" style={{ background: c }} title={c} />
                      ))}
                    </div>
                  )}
                  <button
                    className="generate-image-btn"
                    onClick={() => handleGenerateImage(concept)}
                    disabled={loadingImage}
                  >
                    {loadingImage && selectedConcept === concept ? 'Generating...' : 'Generate Image'}
                  </button>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Step 3: Generated Stickers */}
      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">3</span> Generated Stickers</h3>
        </div>
        {loadingImage && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>Generating sticker image...</span>
          </div>
        )}
        {generatedStickers.length > 0 && (
          <div className="stickers-grid">
            {generatedStickers.map((filename, i) => (
              <div key={i} className="generated-sticker-card">
                <img
                  src={`http://localhost:8000/stickers/${filename}`}
                  alt={`Sticker ${i + 1}`}
                  className="generated-sticker-img"
                />
                <div className="sticker-actions">
                  <a
                    href={`http://localhost:8000/stickers/${filename}`}
                    download={filename}
                    className="download-btn"
                  >
                    Download
                  </a>
                  <button
                    className="regenerate-btn"
                    onClick={() => {
                      if (selectedConcept) handleGenerateImage(selectedConcept)
                    }}
                    disabled={loadingImage}
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Refinement input */}
      <div className="studio-refinement">
        <div className="input-wrap">
          <textarea
            className="chat-input"
            value={refinement}
            onChange={e => setRefinement(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRefinement() } }}
            placeholder="Refine your stickers... (e.g. 'make it more pastel', 'add sparkles')"
            rows={1}
            disabled={chatLoading}
          />
          <button
            className="send-btn"
            onClick={handleRefinement}
            disabled={!refinement.trim() || chatLoading}
            aria-label="Send refinement"
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  )
}

export default StickerStudio
