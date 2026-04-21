import { useState, useEffect, useCallback } from 'react'
import { useTrend } from '../context/TrendContext'

const API_BASE = 'http://localhost:8000'

const ART_STYLES = [
  { id: 'kawaii', label: 'Kawaii', emoji: '\u{1F380}' },
  { id: 'retro', label: 'Retro', emoji: '\u{1F57A}' },
  { id: 'minimalist', label: 'Minimal', emoji: '\u25FB\uFE0F' },
  { id: 'hand-lettered', label: 'Lettering', emoji: '\u270D\uFE0F' },
  { id: 'pop-art', label: 'Pop Art', emoji: '\u{1F4A5}' },
  { id: 'grunge', label: 'Grunge', emoji: '\u{1F3B8}' },
  { id: 'watercolor', label: 'Watercolor', emoji: '\u{1F3A8}' },
  { id: 'pixel-art', label: 'Pixel', emoji: '\u{1F47E}' },
]

const LAYOUTS = [
  { id: 'text_only', label: 'Text Only', icon: 'Aa' },
  { id: 'image_only', label: 'Image Only', icon: '\u{1F5BC}' },
  { id: 'text_and_image', label: 'Both', icon: '\u{1F4DD}\u{1F5BC}' },
]

const COLOR_MOODS = ['pastels', 'bold & bright', 'earth tones', 'monochrome', 'neon', 'muted vintage']

function StickerStudio({ onGoToIdeas, onGoToPack }) {
  const { activePack, studioIdea, setStudioIdea, addStickerToPack } = useTrend()

  // All local state -- resets per idea
  const [stickerText, setStickerText] = useState('')
  const [selectedStyle, setSelectedStyle] = useState('')
  const [selectedLayout, setSelectedLayout] = useState('text_and_image')
  const [selectedColorMood, setSelectedColorMood] = useState('')
  const [visualDirection, setVisualDirection] = useState('')
  const [allVersions, setAllVersions] = useState([]) // {filename, prompt, timestamp}[]
  const [selectedVersion, setSelectedVersion] = useState(null)
  const [refinement, setRefinement] = useState('')
  const [generating, setGenerating] = useState(false)
  const [notice, setNotice] = useState('')
  const [savingFile, setSavingFile] = useState(null)

  // Reset all state when idea changes
  useEffect(() => {
    if (!studioIdea) return
    setStickerText(studioIdea.text || studioIdea.concept || '')
    setVisualDirection(studioIdea.visual_description || '')
    setSelectedStyle('')
    setSelectedLayout('text_and_image')
    setSelectedColorMood('')
    setAllVersions([])
    setSelectedVersion(null)
    setRefinement('')
    setNotice('')
  }, [studioIdea?.id, studioIdea?.text]) // eslint-disable-line react-hooks/exhaustive-deps

  const ideaText = studioIdea?.text || studioIdea?.concept || ''
  const parentTopic = studioIdea?.topic || activePack?.topic || ''

  const buildPrompt = useCallback(() => {
    const parts = []
    if (stickerText) parts.push(`Sticker text: "${stickerText}"`)
    if (visualDirection) parts.push(`Visual: ${visualDirection}`)
    if (selectedStyle) parts.push(`Art style: ${selectedStyle}`)
    if (selectedLayout) parts.push(`Layout: ${selectedLayout.replace(/_/g, ' ')}`)
    if (selectedColorMood) parts.push(`Color mood: ${selectedColorMood}`)
    parts.push('Clean die-cut sticker design, strong edges, print-ready')
    return parts.join('. ')
  }, [stickerText, visualDirection, selectedStyle, selectedLayout, selectedColorMood])

  const handleGenerate = async () => {
    setGenerating(true)
    setNotice('')
    const prompt = buildPrompt()
    const requests = [1, 2, 3].map(() =>
      fetch(`${API_BASE}/api/studio/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt, parent_topic: parentTopic, moment: stickerText }),
      }).then(r => r.json()).catch(() => null)
    )
    const results = await Promise.all(requests)
    const prevLen = allVersions.length
    const newVersions = results
      .filter(r => r?.filename)
      .map(r => ({ filename: r.filename, prompt, timestamp: new Date().toISOString() }))
    setAllVersions(prev => [...prev, ...newVersions])
    if (newVersions.length > 0) {
      setSelectedVersion(prevLen) // select first of the new batch
      setNotice(`Generated ${newVersions.length} variation${newVersions.length > 1 ? 's' : ''}.`)
    } else {
      setNotice('Generation failed. Check your API key and try again.')
    }
    setGenerating(false)
  }

  const handleRefine = async () => {
    if (!refinement.trim() || selectedVersion === null) return
    setGenerating(true)
    setNotice('')
    const base = allVersions[selectedVersion].prompt
    const newPrompt = `${refinement.trim()}. Based on: ${base}`
    try {
      const res = await fetch(`${API_BASE}/api/studio/generate-image`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ prompt: newPrompt, parent_topic: parentTopic, moment: stickerText }),
      })
      const data = await res.json()
      if (data?.filename) {
        const newVersion = { filename: data.filename, prompt: newPrompt, timestamp: new Date().toISOString() }
        setAllVersions(prev => {
          const next = [...prev, newVersion]
          setSelectedVersion(next.length - 1)
          return next
        })
        setNotice('Refinement added as new version.')
      }
    } catch {
      setNotice('Refinement failed.')
    }
    setGenerating(false)
    setRefinement('')
  }

  const handleSaveToPack = async (versionIdx) => {
    const v = allVersions[versionIdx]
    if (!v) return
    setSavingFile(v.filename)
    try {
      await addStickerToPack(v.filename, ideaText || 'Studio sticker')
      setNotice(`Saved ${v.filename} to pack.`)
    } catch (e) {
      setNotice(e.message || 'Could not save to pack.')
    } finally {
      setSavingFile(null)
    }
  }

  const isStickerInPack = (filename) => {
    return (activePack?.stickers || []).some(s => s.filename === filename)
  }

  // Navigate to next unfinished idea in the bank
  const handleNextIdea = () => {
    const ideas = activePack?.ideas || []
    if (ideas.length === 0) return
    const currentIdx = ideas.findIndex(i => (i.id || i.text) === (studioIdea?.id || studioIdea?.text))
    // Find next idea after current (wraps around)
    for (let offset = 1; offset <= ideas.length; offset++) {
      const nextIdx = (currentIdx + offset) % ideas.length
      const candidate = ideas[nextIdx]
      if ((candidate.id || candidate.text) !== (studioIdea?.id || studioIdea?.text)) {
        setStudioIdea(candidate)
        return
      }
    }
  }

  // Empty state
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
    <div className="studio-workspace">
      {/* Header */}
      <div className="studio-ws-header">
        <button className="back-link" onClick={onGoToIdeas}>&larr; Back to Ideas</button>
        <h2 className="studio-ws-title">Studio: <span className="studio-trend-name">{ideaText}</span></h2>
        <button className="back-link studio-next-btn" onClick={handleNextIdea}>
          Next Idea &rarr;
        </button>
      </div>

      {notice && <div className="studio-note">{notice}</div>}

      <div className="studio-panels">
        {/* LEFT PANEL -- Creative Brief */}
        <div className="studio-left-panel">
          {/* Context Card */}
          <div className="studio-context-card">
            <h3>{ideaText}</h3>
            {studioIdea.concept && <p className="studio-concept">{studioIdea.concept}</p>}
            {studioIdea.fandom_element && studioIdea.internet_element && (
              <div className="idea-collision">
                <span className="collision-tag fandom-tag">{studioIdea.fandom_element}</span>
                <span className="collision-x">&times;</span>
                <span className="collision-tag internet-tag">{studioIdea.internet_element}</span>
              </div>
            )}
            {studioIdea.why_its_funny && <p className="studio-why">{studioIdea.why_its_funny}</p>}
            {parentTopic && <p className="studio-topic-tag">Topic: {parentTopic}</p>}
          </div>

          {/* Sticker Text */}
          <div className="studio-field">
            <label>Sticker Text</label>
            <input
              value={stickerText}
              onChange={e => setStickerText(e.target.value)}
              placeholder="The text on your sticker..."
            />
          </div>

          {/* Art Style Picker */}
          <div className="studio-field">
            <label>Art Style</label>
            <div className="studio-style-grid">
              {ART_STYLES.map(s => (
                <button
                  key={s.id}
                  className={`style-tile ${selectedStyle === s.id ? 'style-selected' : ''}`}
                  onClick={() => setSelectedStyle(prev => prev === s.id ? '' : s.id)}
                >
                  <span className="style-emoji">{s.emoji}</span>
                  <span className="style-label">{s.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Layout Picker */}
          <div className="studio-field">
            <label>Layout</label>
            <div className="studio-layout-row">
              {LAYOUTS.map(l => (
                <button
                  key={l.id}
                  className={`layout-tile ${selectedLayout === l.id ? 'layout-selected' : ''}`}
                  onClick={() => setSelectedLayout(l.id)}
                >
                  <span className="layout-icon">{l.icon}</span>
                  <span className="layout-label">{l.label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Visual Direction */}
          <div className="studio-field">
            <label>Visual Direction</label>
            <textarea
              value={visualDirection}
              onChange={e => setVisualDirection(e.target.value)}
              rows={3}
              placeholder="Describe the visual... e.g. 'chibi character with a top hat holding a teacup'"
            />
          </div>

          {/* Color Mood */}
          <div className="studio-field">
            <label>Colors</label>
            <div className="studio-color-tags">
              {COLOR_MOODS.map(c => (
                <button
                  key={c}
                  className={`color-mood-tag ${selectedColorMood === c ? 'color-mood-selected' : ''}`}
                  onClick={() => setSelectedColorMood(prev => prev === c ? '' : c)}
                >
                  {c}
                </button>
              ))}
            </div>
          </div>

          {/* Generate Button */}
          <button className="generate-btn" onClick={handleGenerate} disabled={generating}>
            {generating ? 'Generating...' : 'Generate 3 Variations'}
          </button>
        </div>

        {/* RIGHT PANEL -- Generation Gallery */}
        <div className="studio-right-panel">
          {allVersions.length === 0 && !generating && (
            <div className="gallery-empty">
              <div className="gallery-empty-icon">{'\u{1F3A8}'}</div>
              <p>Your generated stickers will appear here.</p>
              <p className="studio-hint">Configure the creative brief on the left, then hit Generate.</p>
            </div>
          )}

          {generating && allVersions.length === 0 && (
            <div className="studio-loading">
              <div className="typing"><span></span><span></span><span></span></div>
              <span>Generating sticker variations...</span>
            </div>
          )}

          {/* Variation Grid */}
          {allVersions.length > 0 && (
            <>
              <div className="gallery-grid">
                {allVersions.map((v, i) => (
                  <div
                    key={`${v.filename}-${i}`}
                    className={`gallery-card ${selectedVersion === i ? 'gallery-selected' : ''}`}
                    onClick={() => setSelectedVersion(i)}
                  >
                    <img
                      src={`${API_BASE}/stickers/${v.filename}`}
                      alt={`v${i + 1}`}
                      onError={e => { e.target.style.opacity = 0.3 }}
                    />
                    <span className="version-label">v{i + 1}</span>
                  </div>
                ))}
              </div>

              {/* Selected Preview */}
              {selectedVersion !== null && allVersions[selectedVersion] && (
                <div className="gallery-preview">
                  <img
                    src={`${API_BASE}/stickers/${allVersions[selectedVersion].filename}`}
                    alt="Selected sticker preview"
                  />
                </div>
              )}

              {/* Refine Input */}
              <div className="refine-input">
                <input
                  placeholder="Refine: 'more pastel', 'bigger text', 'add sparkles'..."
                  value={refinement}
                  onChange={e => setRefinement(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleRefine()}
                  disabled={generating || selectedVersion === null}
                />
                <button onClick={handleRefine} disabled={generating || !refinement.trim() || selectedVersion === null}>
                  Refine &rarr;
                </button>
              </div>

              {/* Actions */}
              {selectedVersion !== null && allVersions[selectedVersion] && (
                <div className="gallery-actions">
                  {isStickerInPack(allVersions[selectedVersion].filename) ? (
                    <span className="in-pack-badge">In pack</span>
                  ) : (
                    <button
                      className="save-to-pack-btn-lg"
                      onClick={() => handleSaveToPack(selectedVersion)}
                      disabled={savingFile === allVersions[selectedVersion].filename}
                    >
                      {savingFile === allVersions[selectedVersion].filename ? 'Saving...' : 'Save to Pack'}
                    </button>
                  )}
                  <a
                    href={`${API_BASE}/stickers/${allVersions[selectedVersion].filename}`}
                    download={allVersions[selectedVersion].filename}
                    className="download-btn"
                  >
                    Download
                  </a>
                  {onGoToPack && (
                    <button className="view-pack-link" onClick={onGoToPack}>View Pack</button>
                  )}
                </div>
              )}

              {/* Version History Strip */}
              <div className="version-strip">
                <span className="version-strip-label">History</span>
                <div className="version-strip-scroll">
                  {allVersions.map((v, i) => (
                    <button
                      key={`strip-${v.filename}-${i}`}
                      className={`version-strip-thumb ${selectedVersion === i ? 'version-strip-active' : ''}`}
                      onClick={() => setSelectedVersion(i)}
                    >
                      <img src={`${API_BASE}/stickers/${v.filename}`} alt={`v${i + 1}`} />
                      <span>v{i + 1}</span>
                    </button>
                  ))}
                </div>
              </div>
            </>
          )}

          {generating && allVersions.length > 0 && (
            <div className="studio-loading studio-loading-inline">
              <div className="typing"><span></span><span></span><span></span></div>
              <span>Generating...</span>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default StickerStudio
