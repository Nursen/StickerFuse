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

function StickerStudio({ onGoToIdeas, onGoToPack }) {
  const {
    activePack,
    studioIdea,
    stickerIdeas, setStickerIdeas,
    generatedStickers, setGeneratedStickers,
    addStickerToPack,
  } = useTrend()

  const [selectedConcept, setSelectedConcept] = useState(null)
  const [loadingConcepts, setLoadingConcepts] = useState(false)
  const [loadingPhrases, setLoadingPhrases] = useState(false)
  const [loadingImage, setLoadingImage] = useState(false)
  const [refinement, setRefinement] = useState('')
  const [conceptMode, setConceptMode] = useState('auto')
  const [studioNotice, setStudioNotice] = useState('')
  const [phraseOptions, setPhraseOptions] = useState([])
  const [selectedPhraseOption, setSelectedPhraseOption] = useState(null)
  const [deletingFile, setDeletingFile] = useState(null)
  const [selectedRefineSticker, setSelectedRefineSticker] = useState(null)
  const [stickerPromptByFile, setStickerPromptByFile] = useState({})
  const [savingFile, setSavingFile] = useState(null)

  const ideaText = studioIdea?.text || studioIdea?.concept || ''
  const parentTopic = studioIdea?.topic || activePack?.topic || ''
  const studioBusy = loadingConcepts || loadingPhrases || loadingImage

  useEffect(() => {
    setPhraseOptions([])
    setSelectedPhraseOption(null)
    setStudioNotice('')
  }, [studioIdea?.id])

  useEffect(() => {
    if (conceptMode !== 'phrase') {
      setPhraseOptions([])
      setSelectedPhraseOption(null)
    }
  }, [conceptMode])

  useEffect(() => {
    if (generatedStickers.length === 0) {
      setSelectedRefineSticker(null)
      return
    }
    setSelectedRefineSticker(sel =>
      sel && generatedStickers.includes(sel) ? sel : generatedStickers[generatedStickers.length - 1],
    )
  }, [generatedStickers])

  const getTrendContextText = () => {
    const bits = []
    if (parentTopic) bits.push(`Topic: ${parentTopic}`)
    if (ideaText) bits.push(`Idea: ${ideaText}`)
    if (studioIdea?.visual_description) bits.push(`Visual: ${studioIdea.visual_description}`)
    if (studioIdea?.fandom_element) bits.push(`Fandom: ${studioIdea.fandom_element}`)
    if (studioIdea?.internet_element) bits.push(`Internet: ${studioIdea.internet_element}`)
    return bits.join(' | ')
  }

  const handleSuggestPhrases = async () => {
    if (!ideaText || loadingPhrases) return
    setLoadingPhrases(true)
    setStudioNotice('')
    setPhraseOptions([])
    try {
      const data = await studioPost('/api/studio/suggest-phrases', {
        parent_topic: parentTopic,
        moment: ideaText,
        trend_context: getTrendContextText(),
      })
      const phrases = data.phrases || []
      if (phrases.length > 0) {
        setPhraseOptions(phrases)
        setStudioNotice('Pick one phrase, then click "Brainstorm sticker concepts".')
      } else {
        setStudioNotice('No phrases returned. Try again.')
      }
    } catch (e) {
      setStudioNotice(e.message || 'Could not load phrase options.')
    } finally {
      setLoadingPhrases(false)
    }
  }

  const runAutoImages = async (concepts) => {
    if (!Array.isArray(concepts) || concepts.length === 0) return 0
    let n = 0
    for (const concept of concepts.slice(0, 2)) {
      const prompt = concept.visual_description || concept.concept_description || concept.prompt || concept.description
      if (!prompt) continue
      try {
        const data = await studioPost('/api/studio/generate-image', {
          prompt,
          parent_topic: parentTopic,
          moment: ideaText,
        })
        if (data.filename) {
          n += 1
          setGeneratedStickers(prev => [...prev, data.filename])
          setStickerPromptByFile(prev => ({ ...prev, [data.filename]: prompt }))
          setSelectedRefineSticker(data.filename)
        }
      } catch { /* one failure shouldn't block the rest */ }
    }
    return n
  }

  const handleGenerateConceptsFromIdea = async () => {
    if (!ideaText || loadingConcepts) return
    if (conceptMode === 'phrase' && phraseOptions.length > 0 && !selectedPhraseOption) {
      setStudioNotice('Select one of the suggested phrases first.')
      return
    }
    setStudioNotice('')
    setLoadingConcepts(true)
    setStickerIdeas([])
    const momentLabel = conceptMode === 'phrase' && selectedPhraseOption ? selectedPhraseOption : ideaText
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
      const modeFiltered = ideas.filter(idea => {
        const layout = idea.layout_type || idea.layout || ''
        if (conceptMode === 'visual') return layout !== 'text_only'
        if (conceptMode === 'phrase') return layout !== 'image_only'
        return true
      })
      const finalIdeas = modeFiltered.length > 0 ? modeFiltered : ideas
      setStickerIdeas(finalIdeas)

      setLoadingImage(true)
      const created = await runAutoImages(finalIdeas)
      setLoadingImage(false)
      if (created > 0) {
        setStudioNotice(`Generated ${created} sticker preview${created > 1 ? 's' : ''}.`)
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
        moment: ideaText,
      })
      if (data.filename) {
        setGeneratedStickers(prev => [...prev, data.filename])
        setStickerPromptByFile(prev => ({ ...prev, [data.filename]: prompt }))
        setSelectedRefineSticker(data.filename)
      }
    } catch (e) {
      setStudioNotice(e.message || 'Image generation failed.')
    } finally {
      setLoadingImage(false)
    }
  }

  const handleRegenerateSticker = async (filename) => {
    const prompt = stickerPromptByFile[filename]
    if (!prompt) {
      setStudioNotice('No saved prompt for this image.')
      return
    }
    if (loadingImage) return
    setLoadingImage(true)
    setStudioNotice('')
    try {
      const data = await studioPost('/api/studio/generate-image', {
        prompt,
        parent_topic: parentTopic,
        moment: ideaText,
      })
      if (data.filename) {
        setGeneratedStickers(prev => [...prev, data.filename])
        setStickerPromptByFile(prev => ({ ...prev, [data.filename]: prompt }))
        setSelectedRefineSticker(data.filename)
      }
    } catch (e) {
      setStudioNotice(e.message || 'Regenerate failed.')
    } finally {
      setLoadingImage(false)
    }
  }

  const handleRefinement = async () => {
    if (!refinement.trim()) return
    if (!selectedRefineSticker) {
      setStudioNotice('Click a sticker to choose which one to refine.')
      return
    }
    setLoadingImage(true)
    const prior = stickerPromptByFile[selectedRefineSticker] || ''
    const base = prior
      ? `${refinement}\n\nRevise this die-cut sticker design. The previous generation brief was:\n${prior}\n\nApply the refinement above. Keep print-ready edges and a clean sticker silhouette.`
      : `${refinement}\n\nTopic: ${ideaText}${parentTopic ? `; parent: ${parentTopic}` : ''}`
    try {
      const data = await studioPost('/api/studio/generate-image', {
        prompt: base,
        parent_topic: parentTopic,
        moment: ideaText,
      })
      if (data.filename) {
        setGeneratedStickers(prev => [...prev, data.filename])
        setStickerPromptByFile(prev => ({ ...prev, [data.filename]: base }))
        setSelectedRefineSticker(data.filename)
      }
    } catch (e) {
      setStudioNotice(e.message || 'Refinement failed.')
    } finally {
      setLoadingImage(false)
      setRefinement('')
    }
  }

  const handleDeleteSticker = async (filename) => {
    setDeletingFile(filename)
    setStudioNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/studio/sticker/${encodeURIComponent(filename)}`, { method: 'DELETE' })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.status === 'error') {
        throw new Error(data.error || `Delete failed (${res.status})`)
      }
      setGeneratedStickers(prev => {
        const next = prev.filter(f => f !== filename)
        setStickerPromptByFile(p => {
          const copy = { ...p }
          delete copy[filename]
          return copy
        })
        setSelectedRefineSticker(sel => {
          if (sel !== filename) return sel
          return next.length ? next[next.length - 1] : null
        })
        return next
      })
    } catch (e) {
      setStudioNotice(e.message || 'Could not delete sticker.')
    } finally {
      setDeletingFile(null)
    }
  }

  const handleSaveToPack = async (filename) => {
    setSavingFile(filename)
    try {
      await addStickerToPack(filename, ideaText || 'Studio sticker')
      setStudioNotice(`Saved ${filename} to pack.`)
    } catch (e) {
      setStudioNotice(e.message || 'Could not save to pack.')
    } finally {
      setSavingFile(null)
    }
  }

  const isStickerInPack = (filename) => {
    return (activePack?.stickers || []).some(s => s.filename === filename)
  }

  // Empty state — no idea selected
  if (!studioIdea) {
    return (
      <div className="studio-empty">
        <div className="studio-empty-icon">&#127912;</div>
        <h2>Sticker Studio</h2>
        <p>Pick an idea from the Idea Bank to start designing.</p>
        <button className="back-link" onClick={onGoToIdeas}>
          &larr; Go to Ideas
        </button>
      </div>
    )
  }

  return (
    <div className="sticker-studio">
      <div className="studio-header">
        <button className="back-link" onClick={onGoToIdeas}>&larr; Back to Ideas</button>
        <h2>Designing: <span className="studio-trend-name">{ideaText}</span></h2>
        {parentTopic && (
          <p className="studio-parent-topic">Topic: <strong>{parentTopic}</strong></p>
        )}
      </div>

      {/* Step 1: Sticker Direction */}
      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">1</span> Sticker Direction</h3>
          <select
            value={conceptMode}
            onChange={e => setConceptMode(e.target.value)}
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
              {loadingPhrases ? 'Suggesting...' : 'Suggest phrase options'}
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
          onClick={handleGenerateConceptsFromIdea}
          disabled={loadingConcepts || (conceptMode === 'phrase' && phraseOptions.length > 0 && !selectedPhraseOption)}
        >
          {loadingConcepts ? 'Brainstorming...' : 'Brainstorm sticker concepts'}
        </button>
        {(loadingConcepts || loadingPhrases) && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>{loadingPhrases ? 'Generating phrase options...' : 'Generating sticker concepts...'}</span>
          </div>
        )}
        {studioNotice && <div className="studio-note">{studioNotice}</div>}
      </section>

      {/* Step 2: Sticker Concepts */}
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
                    disabled={studioBusy}
                  >
                    {loadingImage && selectedConcept === concept ? 'Generating...' : 'Generate Image'}
                  </button>
                </div>
              )
            })}
          </div>
        ) : (
          !loadingConcepts && (
            <p className="studio-hint">Concepts will appear here after you run "Brainstorm sticker concepts".</p>
          )
        )}
      </section>

      {/* Step 3: Generated Stickers */}
      <section className="studio-section">
        <div className="studio-section-header">
          <h3><span className="step-num">3</span> Generated Stickers</h3>
          {generatedStickers.length > 0 && (
            <button className="studio-action-btn" onClick={onGoToPack}>
              View Pack
            </button>
          )}
        </div>
        {loadingImage && (
          <div className="studio-loading">
            <div className="typing"><span></span><span></span><span></span></div>
            <span>Generating sticker image...</span>
          </div>
        )}
        {generatedStickers.length > 0 && (
          <p className="studio-hint studio-refine-hint">
            Click a sticker to select it for refinement. Selected:{' '}
            <span className="studio-refine-filename">{selectedRefineSticker || '--'}</span>
          </p>
        )}
        {generatedStickers.length > 0 && (
          <div className="stickers-grid">
            {generatedStickers.map((filename, i) => {
              const isRefineSelected = selectedRefineSticker === filename
              const inPack = isStickerInPack(filename)
              return (
                <div
                  key={`${filename}-${i}`}
                  className={`generated-sticker-card ${isRefineSelected ? 'selected-sticker' : ''}`}
                  onClick={() => setSelectedRefineSticker(filename)}
                  role="group"
                  aria-label={
                    isRefineSelected
                      ? `Selected sticker ${i + 1}. Use Refine below.`
                      : `Sticker ${i + 1}. Click to select for refinement.`
                  }
                >
                  <div className="generated-sticker-preview">
                    <img
                      src={`${API_BASE}/stickers/${filename}`}
                      alt=""
                      className="generated-sticker-img"
                      onError={e => { e.target.style.opacity = 0.3 }}
                    />
                    {isRefineSelected ? (
                      <span className="sticker-selected-badge">Selected for refine</span>
                    ) : (
                      <span className="sticker-select-cta" aria-hidden="true">Click to select</span>
                    )}
                  </div>
                  <div className="sticker-actions" onClick={e => e.stopPropagation()}>
                    {inPack ? (
                      <span className="in-pack-badge">In pack</span>
                    ) : (
                      <button
                        className="save-to-pack-btn"
                        onClick={() => handleSaveToPack(filename)}
                        disabled={studioBusy || savingFile === filename}
                      >
                        {savingFile === filename ? 'Saving...' : 'Save to Pack'}
                      </button>
                    )}
                    <a
                      href={`${API_BASE}/stickers/${filename}`}
                      download={filename}
                      className="download-btn"
                    >
                      Download
                    </a>
                    <button
                      className="regenerate-btn"
                      type="button"
                      onClick={() => handleRegenerateSticker(filename)}
                      disabled={studioBusy || deletingFile}
                    >
                      Regenerate
                    </button>
                    <button
                      type="button"
                      className="delete-sticker-btn"
                      onClick={() => handleDeleteSticker(filename)}
                      disabled={studioBusy || deletingFile}
                    >
                      {deletingFile === filename ? '...' : 'Delete'}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </section>

      {/* Refinement */}
      <div className="studio-refinement">
        <p className="studio-refine-caption">
          Refine the <strong>selected</strong> sticker. Adds a new variation; original stays until you delete it.
        </p>
        <div className="input-wrap">
          <textarea
            className="chat-input"
            value={refinement}
            onChange={e => setRefinement(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleRefinement() } }}
            placeholder={selectedRefineSticker ? `Refine ${selectedRefineSticker}... (e.g. more pastel, bolder outline)` : 'Select a sticker first, then describe changes...'}
            rows={1}
            disabled={studioBusy || !selectedRefineSticker}
          />
          <button
            className="send-btn"
            onClick={handleRefinement}
            disabled={!refinement.trim() || studioBusy || !selectedRefineSticker}
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
