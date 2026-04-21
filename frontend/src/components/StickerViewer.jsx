import { useState, useEffect, useCallback } from 'react'

const API_BASE = 'http://localhost:8000'

async function parseJson(res) {
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.status === 'error') {
    throw new Error(data.error || `Request failed (${res.status})`)
  }
  return data
}

export default function StickerViewer() {
  const [folders, setFolders] = useState([])
  const [items, setItems] = useState([])
  const [selectedFolderId, setSelectedFolderId] = useState('')
  const [newFolderName, setNewFolderName] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [notice, setNotice] = useState('')

  const load = useCallback(async () => {
    setLoading(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library`)
      const data = await parseJson(res)
      const f = data.folders || []
      const it = data.items || []
      setFolders(f)
      setItems(it)
      setSelectedFolderId((prev) => {
        if (prev && f.some((x) => x.id === prev)) return prev
        return f[0]?.id || ''
      })
    } catch (e) {
      setNotice(e.message || 'Could not load library')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
  }, [load])

  const createFolder = async () => {
    const name = newFolderName.trim()
    if (!name) return
    setBusy(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await parseJson(res)
      setNewFolderName('')
      await load()
      if (data.folder?.id) setSelectedFolderId(data.folder.id)
    } catch (e) {
      setNotice(e.message || 'Could not create folder')
    } finally {
      setBusy(false)
    }
  }

  const deleteFolder = async (folderId) => {
    const f = folders.find((x) => x.id === folderId)
    if (!f) return
    if (!window.confirm(`Delete folder “${f.name}” and all stickers inside it?`)) return
    setBusy(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/folders/${encodeURIComponent(folderId)}`, {
        method: 'DELETE',
      })
      await parseJson(res)
      await load()
    } catch (e) {
      setNotice(e.message || 'Could not delete folder')
    } finally {
      setBusy(false)
    }
  }

  const moveItem = async (itemId, folderId) => {
    if (!folderId) return
    setBusy(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/items/${encodeURIComponent(itemId)}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_id: folderId }),
      })
      await parseJson(res)
      await load()
    } catch (e) {
      setNotice(e.message || 'Could not move sticker')
    } finally {
      setBusy(false)
    }
  }

  const deleteItem = async (itemId) => {
    if (!window.confirm('Remove this sticker from your library? (The file in Studio is not affected.)')) return
    setBusy(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/items/${encodeURIComponent(itemId)}`, {
        method: 'DELETE',
      })
      await parseJson(res)
      await load()
    } catch (e) {
      setNotice(e.message || 'Could not delete sticker')
    } finally {
      setBusy(false)
    }
  }

  const folderItems = items.filter((it) => it.folder_id === selectedFolderId)
  const selectedFolder = folders.find((f) => f.id === selectedFolderId)

  return (
    <div className="sticker-viewer">
      <header className="sticker-viewer-header">
        <div>
          <h2>Sticker Viewer</h2>
          <p className="sticker-viewer-lede">
            Organize copies of stickers you saved from Studio or chat. Library files live on the server and stay
            available after you close the app. Removing a sticker here does not affect the Studio gallery.
          </p>
        </div>
        <button type="button" className="studio-action-btn secondary" onClick={load} disabled={loading || busy}>
          {loading ? 'Loading…' : 'Refresh'}
        </button>
      </header>

      {notice && <div className="studio-note sticker-viewer-notice">{notice}</div>}

      <div className="sticker-viewer-layout">
        <aside className="sticker-viewer-sidebar">
          <h3 className="sticker-viewer-sidebar-title">Folders</h3>
          <div className="sticker-viewer-new-folder">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="New folder name"
              maxLength={80}
              disabled={busy}
            />
            <button type="button" className="studio-action-btn" onClick={createFolder} disabled={busy || !newFolderName.trim()}>
              Add folder
            </button>
          </div>
          <ul className="sticker-viewer-folder-list">
            {folders.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className={`sticker-viewer-folder-btn ${selectedFolderId === f.id ? 'active' : ''}`}
                  onClick={() => setSelectedFolderId(f.id)}
                >
                  <span className="sticker-viewer-folder-name">{f.name}</span>
                  <span className="sticker-viewer-folder-count">
                    {items.filter((it) => it.folder_id === f.id).length}
                  </span>
                </button>
              </li>
            ))}
          </ul>
          {selectedFolderId && (
            <button
              type="button"
              className="sticker-viewer-delete-folder"
              onClick={() => deleteFolder(selectedFolderId)}
              disabled={busy}
            >
              Delete current folder
            </button>
          )}
        </aside>

        <section className="sticker-viewer-main">
          {loading ? (
            <div className="studio-loading">
              <div className="typing"><span /><span /><span /></div>
              <span>Loading library…</span>
            </div>
          ) : !selectedFolder ? (
            <p className="studio-hint">Create a folder to start collecting stickers.</p>
          ) : folderItems.length === 0 ? (
            <p className="studio-hint">
              No stickers in “{selectedFolder.name}” yet. Use <strong>Save to library</strong> in Studio or chat.
            </p>
          ) : (
            <div className="sticker-viewer-grid">
              {folderItems.map((it) => (
                <div key={it.id} className="sticker-viewer-card">
                  <img
                    src={`${API_BASE}/library/${it.folder_id}/${it.filename}`}
                    alt="Saved sticker"
                    className="sticker-viewer-img"
                  />
                  <div className="sticker-viewer-meta">
                    {it.source_label && (
                      <span className="sticker-viewer-source" title={it.source_label}>
                        From: {it.source_label}
                      </span>
                    )}
                  </div>
                  <div className="sticker-viewer-card-actions">
                    <label className="sticker-viewer-move">
                      <span>Move to</span>
                      <select
                        value={it.folder_id}
                        onChange={(e) => moveItem(it.id, e.target.value)}
                        disabled={busy}
                      >
                        {folders.map((f) => (
                          <option key={f.id} value={f.id}>{f.name}</option>
                        ))}
                      </select>
                    </label>
                    <a
                      className="download-btn"
                      href={`${API_BASE}/library/${it.folder_id}/${it.filename}`}
                      download={it.filename}
                    >
                      Download
                    </a>
                    <button
                      type="button"
                      className="delete-sticker-btn"
                      onClick={() => deleteItem(it.id)}
                      disabled={busy}
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
    </div>
  )
}
