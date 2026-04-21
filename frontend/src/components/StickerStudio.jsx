import { useState, useEffect } from 'react'
import { useTrend } from '../context/TrendContext'

const API_BASE = 'http://localhost:8000'

async function studioPost(path, body) {
  const res = await fetch(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.status === 'error') {
    throw new Error(data.error || `Request failed (${res.status})`)
  }
  return data
}

function StickerStudio({ onNavigateTrends }) {
  const {
    selectedTrend,
    viralBites,
    stickerIdeas, setStickerIdeas,
    generatedStickers, setGeneratedStickers,
    chatLoading,
  } = useTrend()

  // If we arrived with pre-selected merch ideas (from TrendPulse), use them as sticker concepts
  const hasPreloadedIdeas = viralBites && viralBites.length > 0 && stickerIdeas.length === 0

  const [selectedConcept, setSelectedConcept] = useState(null)
  const [loadingConcepts, setLoadingConcepts] = useState(false)
  const [loadingPhrases, setLoadingPhrases] = useState(false)
  const [loadingImage, setLoadingImage] = useState(false)
  const [refinement, setRefinement] = useState('')
  const [conceptMode, setConceptMode] = useState('auto')
  const [studioNotice, setStudioNotice] = useState('')
  const [phraseOptions, setPhraseOptions] = useState([])
  const [selectedPhraseOption, setSelectedPhraseOption] = useState(null)

  const trendName = selectedTrend
    ? (selectedTrend.trend_name || selectedTrend.name || 'selected trend')
    : null

  const parentTopic = selectedTrend?.parent_topic || ''
  const studioBusy = loadingConcepts || loadingPhrases || loadingImage

  useEffect(() => {
    setPhraseOptions([])
    setSelectedPhraseOption(null)
    setStudioNotice('')
  }, [selectedTrend?.name, selectedTrend?.trend_name])

  // Auto-populate sticker concepts from merch ideation selections
  useEffect(() => {
    if (hasPreloadedIdeas) {
      const preloaded = viralBites.map(bite => ({
        concept_description: bite.text,
        visual_description: bite.visual_description || bite.text,
        art_style: '',
        layout_type: bite.visual_description ? 'text_and_image' : 'text_only',
        color_palette: [],
        text_content: bite.text,
        viral_bite_ref: bite.context || '',
      }))
      setStickerIdeas(preloaded)
      setStudioNotice(`${preloaded.length} concepts loaded from your selections. Click "Generate Image" to create stickers.`)
    }
  }, [hasPreloadedIdeas])

  useEffect(() => {
    if (conceptMode !== 'phrase') {
      setPhraseOptions([])
      setSelectedPhraseOption(null)
    }
  }, [conceptMode])

  const getTrendContextText = () => {
    if (!selectedTrend) return ''
    const desc = selectedTrend.description || ''
    const evidence = Array.isArray(selectedTrend.evidence) ? selectedTrend.evidence : []
    const evidenceTitles = evidence
      .slice(0, 5)
      .map((e) => e?.title || e?.text || '')
      .filter(Boolean)
    const bits = []
    if (parentTopic) bits.push(`User searched / parent topic: ${parentTopic}`)
    bits.push(desc, ...evidenceTitles)
    return bits.filter(Boolean).join(' | ')
  }

  const handleSuggestPhrases = async () => {
    if (!trendName || loadingPhrases) return
    setLoadingPhrases(true)
    setStudioNotice('')
    setPhraseOptions([])
    try {
      const data = await studioPost('/api/studio/suggest-phrases', {
        parent_topic: parentTopic,
        moment: trendName,
        trend_context: getTrendContextText(),
      })
      const phrases = data.phrases || []
      if (phrases.length > 0) {
        setPhraseOptions(phrases)
        setStudioNotice('Pick one phrase, then click “Brainstorm sticker concepts”.')
      } else {
        setStudioNotice('No phrases returned. Try again.')
      }
    } catch (e) {
      setStudioNotice(e.message || 'Could not load phrase options.')
    } finally {
      setLoadingPhrases(false)
    }
  }

  const runAutoImages = async (concepts, momentForContext) => {
    if (!Array.isArray(concepts) || concepts.length === 0) return 0
    let n = 0
    for (const concept of concepts.slice(0, 2)) {
      const prompt = concept.visual_description || concept.concept_description || concept.prompt || concept.description
      if (!prompt) continue
      try {
        const data = await studioPost('/api/studio/generate-image', {
          prompt,
          parent_topic: parentTopic,
          moment: momentForContext || trendName,
        })
        if (data.filename) {
          n += 1
          setGeneratedStickers(prev => [...prev, data.filename])
        }
      } catch {
        /* one image failure should not block the rest */
      }
    }
    return n
  }

  const handleGenerateConceptsFromTrend = async () => {
    if (!trendName || loadingConcepts) return
    if (conceptMode === 'phrase' && phraseOptions.length > 0 && !selectedPhraseOption) {
      setStudioNotice('Select one of the suggested phrases first, or clear phrase options by switching mode.')
      return
    }
    setStudioNotice('')
    setLoadingConcepts(true)
    setStickerIdeas([])
    const momentLabel = conceptMode === 'phrase' && selectedPhraseOption ? selectedPhraseOption : trendName
    try {
      const data = await studioPost('/api/studio/brainstorm', {
        parent_topic: parentTopic,
        moment: momentLabel,
        trend_context: getTrendContextText(),
        mode: conceptMode,
      })
      const ideas = data.data?.ideas ?? []
      if (ideas.length === 0) {
        setStudioNotice('No concepts returned. Check your API key and try again.')
        return
      }
      const modeFiltered = ideas.filter((idea) => {
        const layout = idea.layout_type || idea.layout || ''
        if (conceptMode === 'visual') return layout !== 'text_only'
        if (conceptMode === 'phrase') return layout !== 'image_only'
        return true
      })
      const finalIdeas = modeFiltered.length > 0 ? modeFiltered : ideas
      setStickerIdeas(finalIdeas)

      setLoadingImage(true)
      const created = await runAutoImages(finalIdeas, momentLabel)
      setLoadingImage(false)
      if (created > 0) {
        setStudioNotice(`Generated ${created} sticker preview${created > 1 ? 's' : ''} in step 3.`)
      }
    } catch (e) {
      setStudioNotice(e.message || 'Brainstorm failed.')
    } finally {
      setLoadingConcepts(false)
    }
  }

  const handleGenerateImage = async (concept) => {
    if (loadingImage) return
    setSelectedConcept(concept)
    setLoadingImage(true)
    const prompt = concept.visual_description || concept.concept_description || concept.prompt || concept.description || JSON.stringify(concept)
    try {
      const data = await studioPost('/api/studio/generate-image', {
        prompt,
        parent_topic: parentTopic,
        moment: trendName,
      })
      if (data.filename) {
        setGeneratedStickers(prev => [...prev, data.filename])
      }
    } catch (e) {
      setStudioNotice(e.message || 'Image generation failed.')
    } finally {
      setLoadingImage(false)
    }
  }

  const handleRefinement = async () => {
    if (!refinement.trim()) return
    setLoadingImage(true)
    const base = selectedConcept
      ? `${refinement}\n\nReference concept: ${selectedConcept.visual_description || selectedConcept.concept_description || ''}`
      : `${refinement}\n\nTopic: ${trendName}${parentTopic ? `; parent: ${parentTopic}` : ''}`
    try {
      const data = await studioPost('/api/studio/generate-image', {
        prompt: base,
        parent_topic: parentTopic,
        moment: trendName,
      })
      if (data.filename) {
        setGeneratedStickers(prev => [...prev, data.filename])
      }
    } catch (e) {
      setStudioNotice(e.message || 'Refinement failed.')
    } finally {
      setLoadingImage(false)
      setRefinement('')
    }
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
        {parentTopic && (
          <p className="studio-parent-topic">Parent topic: <strong>{parentTopic}</strong></p>
        )}
      </div>

      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">1</span> Sticker Direction</h3>
          <select
            value={conceptMode}
            onChange={(e) => setConceptMode(e.target.value)}
            disabled={studioBusy}
            className="studio-mode-select"
            aria-label="Concept mode"
          >
            <option value="auto">Auto (best fit)</option>
            <option value="phrase">Phrase-focused</option>
            <option value="visual">Visual-focused</option>
          </select>
        </div>

        {conceptMode === 'phrase' && (
          <div className="studio-phrase-step">
            <h4 className="studio-subheading">Phrase options</h4>
            <p className="studio-hint">Pick distinct wordings first, then brainstorm sticker art.</p>
            <button
              type="button"
              className="studio-action-btn secondary"
              onClick={handleSuggestPhrases}
              disabled={studioBusy}
            >
              {loadingPhrases ? 'Suggesting…' : 'Suggest phrase options'}
            </button>
            {phraseOptions.length > 0 && (
              <div className="phrase-chips">
                {phraseOptions.map((p, i) => (
                  <button
                    type="button"
                    key={i}
                    className={`phrase-chip ${selectedPhraseOption === p ? 'selected' : ''}`}
                    onClick={() => setSelectedPhraseOption(p)}
                  >
                    {p}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          className="studio-action-btn"
          onClick={handleGenerateConceptsFromTrend}
          disabled={loadingConcepts || (conceptMode === 'phrase' && phraseOptions.length > 0 && !selectedPhraseOption)}
        >
          {loadingConcepts ? 'Brainstorming...' : 'Brainstorm sticker concepts'}
        </button>
        {(loadingConcepts || loadingPhrases) && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>{loadingPhrases ? 'Generating phrase options…' : 'Generating sticker concepts…'}</span>
          </div>
        )}
        {studioNotice && <div className="studio-note">{studioNotice}</div>}
      </section>

      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">2</span> Sticker Concepts</h3>
        </div>
        {stickerIdeas.length > 0 ? (
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
                    disabled={studioBusy || chatLoading}
                  >
                    {loadingImage && selectedConcept === concept ? 'Generating...' : 'Generate Image'}
                  </button>
                </div>
              )
            })}
          </div>
        ) : (
          !loadingConcepts && (
            <p className="studio-hint">Concepts will appear here after you run “Brainstorm sticker concepts”.</p>
          )
        )}
      </section>

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
              <div key={`${filename}-${i}`} className="generated-sticker-card">
                <img
                  src={`${API_BASE}/stickers/${filename}`}
                  alt={`Sticker ${i + 1}`}
                  className="generated-sticker-img"
                  onError={(e) => { e.target.style.opacity = 0.3 }}
                />
                <div className="sticker-actions">
                  <a
                    href={`${API_BASE}/stickers/${filename}`}
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
                    disabled={studioBusy}
                  >
                    Regenerate
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="studio-refinement">
        <div className="input-wrap">
          <textarea
            className="chat-input"
            value={refinement}
            onChange={e => setRefinement(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRefinement() } }}
            placeholder="Refine your stickers... (e.g. 'make it more pastel', 'add sparkles')"
            rows={1}
            disabled={studioBusy}
          />
          <button
            className="send-btn"
            onClick={handleRefinement}
            disabled={!refinement.trim() || studioBusy}
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
