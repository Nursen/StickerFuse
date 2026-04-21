import { useState, useEffect } from 'react'
import { useTrend } from '../context/TrendContext'

export default function PackHome({ onPackSelected }) {
  const { packs, fetchPacks, createPack, selectPack } = useTrend()
  const [newPackName, setNewPackName] = useState('')
  const [newPackTopic, setNewPackTopic] = useState('')
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => { fetchPacks() }, [fetchPacks])

  const handleCreate = async () => {
    if (!newPackName.trim()) return
    setCreating(true)
    setError('')
    try {
      await createPack(newPackName.trim(), newPackTopic.trim())
      setNewPackName('')
      setNewPackTopic('')
      onPackSelected()
    } catch (e) {
      setError(e.message || 'Could not create pack')
    } finally {
      setCreating(false)
    }
  }

  const handleSelect = async (packId) => {
    try {
      await selectPack(packId)
      onPackSelected()
    } catch (e) {
      setError(e.message || 'Could not load pack')
    }
  }

  return (
    <div className="pack-home">
      <div className="create-pack-card">
        <h2>Start a new sticker pack</h2>
        <p className="create-pack-desc">
          A pack groups your ideas and generated stickers around a theme.
        </p>
        <input
          type="text"
          className="pack-input"
          placeholder="Pack name (e.g. 'Bridgerton Vibes')"
          value={newPackName}
          onChange={e => setNewPackName(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
          disabled={creating}
          maxLength={100}
        />
        <input
          type="text"
          className="pack-input"
          placeholder="Topic or fandom (optional)"
          value={newPackTopic}
          onChange={e => setNewPackTopic(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') handleCreate() }}
          disabled={creating}
          maxLength={100}
        />
        <button
          className="create-pack-btn"
          onClick={handleCreate}
          disabled={!newPackName.trim() || creating}
        >
          {creating ? 'Creating...' : 'Create Pack'}
        </button>
        {error && <div className="pack-error">{error}</div>}
      </div>

      {packs.length > 0 && (
        <div className="packs-section">
          <h3 className="packs-section-title">Your Packs</h3>
          <div className="packs-grid">
            {packs.map(p => (
              <div
                key={p.id}
                className="pack-card"
                onClick={() => handleSelect(p.id)}
              >
                <h4 className="pack-card-name">{p.name}</h4>
                {p.topic && <p className="pack-card-topic">{p.topic}</p>}
                <span className="pack-card-stats">
                  {p.idea_count || 0} ideas &middot; {p.sticker_count || 0} stickers
                </span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
