import { createContext, useState, useContext, useRef, useCallback, useEffect } from 'react'

const TrendContext = createContext()

const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const CHAT_URL = `${API_BASE}/api/chat`

// LocalStorage helpers — only used for activePackId now
function loadState(key, fallback) {
  try {
    const raw = localStorage.getItem(`stickerfuse_${key}`)
    return raw ? JSON.parse(raw) : fallback
  } catch { return fallback }
}

function saveState(key, value) {
  try { localStorage.setItem(`stickerfuse_${key}`, JSON.stringify(value)) } catch {}
}

export function TrendProvider({ children }) {
  // --- Pack state (source of truth is the API) ---
  const [packs, setPacks] = useState([])
  const [activePack, setActivePack] = useState(null)

  // Studio state (ephemeral per session)
  const [generatedStickers, setGeneratedStickers] = useState([])
  const [stickerIdeas, setStickerIdeas] = useState([])

  // AI brainstorm results (before adding to bank)
  const [brainstormResults, setBrainstormResults] = useState(null)

  // The idea currently being designed in Studio
  const [studioIdea, setStudioIdea] = useState(null)

  // Chat — ephemeral per session, no localStorage persistence
  const [messages, setMessages] = useState([])
  const [chatLoading, setChatLoading] = useState(false)

  // --- Pack API helpers ---
  const fetchPacks = useCallback(async () => {
    try {
      const res = await fetch(`${API_BASE}/api/packs`)
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setPacks(data.packs || data || [])
    } catch (e) {
      console.error('fetchPacks failed:', e)
    }
  }, [])

  const createPack = useCallback(async (name, topic) => {
    const res = await fetch(`${API_BASE}/api/packs`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, topic }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    const data = await res.json()
    const pack = data.pack || data
    setActivePack(pack)
    saveState('activePackId', pack.id)
    // Refresh packs list
    fetchPacks()
    return pack
  }, [fetchPacks])

  const selectPack = useCallback(async (packId) => {
    const res = await fetch(`${API_BASE}/api/packs/${packId}`)
    if (!res.ok) throw new Error(`${res.status}`)
    const data = await res.json()
    const pack = data.pack || data
    setActivePack(pack)
    saveState('activePackId', pack.id)
    // Reset studio state when switching packs
    setGeneratedStickers([])
    setStickerIdeas([])
    setBrainstormResults(null)
    setStudioIdea(null)
    return pack
  }, [])

  const refreshActivePack = useCallback(async () => {
    if (!activePack?.id) return
    try {
      const res = await fetch(`${API_BASE}/api/packs/${activePack.id}`)
      if (!res.ok) throw new Error(`${res.status}`)
      const data = await res.json()
      setActivePack(data.pack || data)
    } catch (e) {
      console.error('refreshActivePack failed:', e)
    }
  }, [activePack?.id])

  const addIdeaToPack = useCallback(async (idea) => {
    if (!activePack?.id) return
    const res = await fetch(`${API_BASE}/api/packs/${activePack.id}/ideas`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ idea }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await refreshActivePack()
  }, [activePack?.id, refreshActivePack])

  const addIdeasBatch = useCallback(async (ideas) => {
    if (!activePack?.id) return
    const res = await fetch(`${API_BASE}/api/packs/${activePack.id}/ideas/batch`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ideas }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await refreshActivePack()
  }, [activePack?.id, refreshActivePack])

  const removeIdeaFromPack = useCallback(async (ideaId) => {
    if (!activePack?.id) return
    const res = await fetch(`${API_BASE}/api/packs/${activePack.id}/ideas/${ideaId}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await refreshActivePack()
  }, [activePack?.id, refreshActivePack])

  const addStickerToPack = useCallback(async (filename, ideaRef) => {
    if (!activePack?.id) return
    const res = await fetch(`${API_BASE}/api/packs/${activePack.id}/stickers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ filename, idea_ref: ideaRef }),
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await refreshActivePack()
  }, [activePack?.id, refreshActivePack])

  const removeStickerFromPack = useCallback(async (filename) => {
    if (!activePack?.id) return
    const res = await fetch(`${API_BASE}/api/packs/${activePack.id}/stickers/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
    })
    if (!res.ok) throw new Error(`${res.status}`)
    await refreshActivePack()
  }, [activePack?.id, refreshActivePack])

  const clearActivePack = useCallback(() => {
    setActivePack(null)
    saveState('activePackId', null)
    setGeneratedStickers([])
    setStickerIdeas([])
    setBrainstormResults(null)
    setStudioIdea(null)
  }, [])

  // Restore active pack on mount
  useEffect(() => {
    const savedId = loadState('activePackId', null)
    if (savedId) {
      selectPack(savedId).catch(() => {
        // Pack may have been deleted; clear stale reference
        saveState('activePackId', null)
      })
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // --- Clear chat on pack switch ---
  const prevPackRef = useRef(activePack?.id)
  useEffect(() => {
    if (activePack?.id !== prevPackRef.current) {
      prevPackRef.current = activePack?.id
      setMessages([])  // clear chat on pack switch
    }
  }, [activePack?.id])

  // --- Build context for chat ---
  const buildChatContext = useCallback(() => ({
    active_pack: activePack?.name || '',
    pack_topic: activePack?.topic || '',
    current_view: '',  // will be set by ChatSidebar from App's view state
    current_idea: studioIdea?.text || '',
    current_sticker_prompt: '',  // will be set by Studio
    idea_bank: (activePack?.ideas || []).map(i => i.text).slice(0, 10),
    stickers_in_pack: activePack?.stickers?.length || 0,
  }), [activePack, studioIdea])

  // --- Chat ---
  const messagesRef = useRef(messages)
  messagesRef.current = messages

  const sendChatMessage = useCallback(async (text, { silent = false, context = null } = {}) => {
    if (!text.trim()) return null

    const userMsg = { role: 'user', content: text }
    const current = messagesRef.current
    // Keep last 4 messages for context, strip toolResults, cap at 50
    const trimmed = current.slice(-4).map(m => ({ role: m.role, content: m.content }))
    const nextMessages = [...current, userMsg]

    if (!silent) {
      setMessages(nextMessages)
    }
    setChatLoading(true)

    try {
      const res = await fetch(CHAT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: [...trimmed, { role: 'user', content: text }],
          context: context || buildChatContext(),
        }),
      })

      if (!res.ok) throw new Error(`Server error: ${res.status}`)

      const data = await res.json()
      const assistantMsg = {
        role: 'assistant',
        content: data.reply || data.response || '',
        toolResults: data.tool_results || [],
      }

      if (!silent) {
        setMessages(prev => [...prev, assistantMsg])
      }

      return { reply: assistantMsg.content, toolResults: assistantMsg.toolResults }
    } catch (err) {
      const errMsg = {
        role: 'assistant',
        content: `Connection error: ${err.message}. Make sure the backend is running on port 8000.`,
      }
      if (!silent) {
        setMessages(prev => [...prev, errMsg])
      }
      return null
    } finally {
      setChatLoading(false)
    }
  }, [buildChatContext])

  const value = {
    // Packs
    packs, fetchPacks, createPack, selectPack, activePack, clearActivePack,
    addIdeaToPack, addIdeasBatch, removeIdeaFromPack,
    addStickerToPack, removeStickerFromPack, refreshActivePack,
    // Studio
    generatedStickers, setGeneratedStickers,
    stickerIdeas, setStickerIdeas,
    studioIdea, setStudioIdea,
    // Brainstorm
    brainstormResults, setBrainstormResults,
    // Chat
    messages, setMessages,
    chatLoading,
    sendChatMessage,
    buildChatContext,
  }

  return <TrendContext.Provider value={value}>{children}</TrendContext.Provider>
}

export function useTrend() {
  const ctx = useContext(TrendContext)
  if (!ctx) throw new Error('useTrend must be used within TrendProvider')
  return ctx
}

export default TrendContext
