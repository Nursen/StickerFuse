import { useTrend } from '../context/TrendContext'

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'

export default function PackView() {
  const { activePack, removeStickerFromPack } = useTrend()

  if (!activePack) return null

  const stickers = activePack.stickers || []
  const ideas = activePack.ideas || []

  const handleExport = () => {
    window.open(`${API_BASE}/api/packs/${activePack.id}/export`, '_blank')
  }

  return (
    <div className="pack-view">
      <div className="pack-view-header">
        <h2>{activePack.name}</h2>
        <p className="pack-view-stats">
          {stickers.length} sticker{stickers.length !== 1 ? 's' : ''} &middot; {ideas.length} idea{ideas.length !== 1 ? 's' : ''}
        </p>
        {activePack.topic && (
          <p className="pack-view-topic">Topic: {activePack.topic}</p>
        )}
      </div>

      {stickers.length > 0 && (
        <button className="export-btn" onClick={handleExport}>
          Download Pack (ZIP)
        </button>
      )}

      {stickers.length === 0 ? (
        <div className="pack-view-empty">
          <p className="studio-hint">
            No stickers in this pack yet. Go to Studio to generate some, then save them here.
          </p>
        </div>
      ) : (
        <div className="pack-sticker-grid">
          {stickers.map(s => (
            <div key={s.filename} className="pack-sticker-card">
              <img
                src={`${API_BASE}/stickers/${s.filename}`}
                alt={s.idea_ref || 'Sticker'}
                className="pack-sticker-img"
                onError={e => { e.target.style.opacity = 0.3 }}
              />
              {s.idea_ref && <span className="sticker-ref">{s.idea_ref}</span>}
              <div className="pack-sticker-actions">
                <a
                  href={`${API_BASE}/stickers/${s.filename}`}
                  download={s.filename}
                  className="download-btn"
                >
                  Download
                </a>
                <button
                  className="delete-sticker-btn"
                  onClick={() => removeStickerFromPack(s.filename)}
                >
                  Remove
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
