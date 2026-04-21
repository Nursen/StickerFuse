import { useState, useEffect } from 'react'

const API_BASE = 'http://localhost:8000'

async function fetchLibrary() {
  const res = await fetch(`${API_BASE}/api/sticker-library`)
  const data = await res.json().catch(() => ({}))
  if (!res.ok || data.status === 'error') {
    throw new Error(data.error || `Request failed (${res.status})`)
  }
  return data
}

/**
 * Copy a sticker from `/stickers/{sourceFilename}` into the user's library (server-side copy).
 */
export default function SaveToLibraryButton({ sourceFilename, disabled = false, onSaved }) {
  const [open, setOpen] = useState(false)
  const [folders, setFolders] = useState([])
  const [folderId, setFolderId] = useState('')
  const [newFolderName, setNewFolderName] = useState('')
  const [loading, setLoading] = useState(false)
  const [notice, setNotice] = useState('')

  const loadFolders = async () => {
    try {
      const data = await fetchLibrary()
      const list = data.folders || []
      setFolders(list)
      setFolderId((prev) => {
        if (prev && list.some((f) => f.id === prev)) return prev
        return list[0]?.id || ''
      })
    } catch (e) {
      setNotice(e.message || 'Could not load folders')
    }
  }

  useEffect(() => {
    if (open) {
      setNotice('')
      loadFolders()
    }
  }, [open])

  const createFolder = async () => {
    const name = newFolderName.trim()
    if (!name) return
    setLoading(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/folders`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.status === 'error') throw new Error(data.error || 'Could not create folder')
      setNewFolderName('')
      await loadFolders()
      if (data.folder?.id) setFolderId(data.folder.id)
    } catch (e) {
      setNotice(e.message || 'Create folder failed')
    } finally {
      setLoading(false)
    }
  }

  const save = async () => {
    if (!folderId || !sourceFilename) return
    setLoading(true)
    setNotice('')
    try {
      const res = await fetch(`${API_BASE}/api/sticker-library/items`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ folder_id: folderId, source_filename: sourceFilename }),
      })
      const data = await res.json().catch(() => ({}))
      if (!res.ok || data.status === 'error') throw new Error(data.error || 'Save failed')
      setNotice('Saved.')
      onSaved?.()
      setTimeout(() => setOpen(false), 600)
    } catch (e) {
      setNotice(e.message || 'Save failed')
    } finally {
      setLoading(false)
    }
  }

  if (!sourceFilename) return null

  return (
    <div className="save-to-library-wrap">
      <button
        type="button"
        className="save-to-library-btn"
        onClick={() => setOpen((o) => !o)}
        disabled={disabled}
      >
        Save to library
      </button>
      {open && (
        <div className="save-to-library-popover" role="dialog" aria-label="Save to sticker library">
          <p className="save-to-library-title">Save a copy to Sticker Viewer</p>
          <p className="save-to-library-note">
            Copies are stored separately—deleting this image in Studio will not remove the saved copy.
          </p>
          {folders.length === 0 ? (
            <p className="save-to-library-empty">Create a folder first (name below).</p>
          ) : (
            <label className="save-to-library-field">
              <span>Folder</span>
              <select
                value={folderId}
                onChange={(e) => setFolderId(e.target.value)}
                disabled={loading}
              >
                {folders.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}</option>
                ))}
              </select>
            </label>
          )}
          <div className="save-to-library-new-folder">
            <input
              type="text"
              value={newFolderName}
              onChange={(e) => setNewFolderName(e.target.value)}
              placeholder="New folder name"
              maxLength={80}
              disabled={loading}
            />
            <button type="button" onClick={createFolder} disabled={loading || !newFolderName.trim()}>
              Create
            </button>
          </div>
          {notice && <div className="save-to-library-notice">{notice}</div>}
          <div className="save-to-library-actions">
            <button type="button" className="secondary" onClick={() => setOpen(false)}>Cancel</button>
            <button
              type="button"
              onClick={save}
              disabled={loading || !folderId}
            >
              {loading ? 'Saving…' : 'Save'}
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
