import { createContext, useState, useContext, useRef, useCallback, useEffect } from 'react'

const TrendContext = createContext()

const API_URL = 'http://localhost:8000/api/chat'

// LocalStorage helpers
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
  const [trends, setTrendsRaw] = useState(() => loadState('trends', []))
  const [selectedTrend, setSelectedTrendRaw] = useState(() => loadState('selectedTrend', null))
  const [stickerIdeas, setStickerIdeasRaw] = useState(() => loadState('stickerIdeas', []))
  const [viralBites, setViralBitesRaw] = useState(() => loadState('viralBites', []))
  const [generatedStickers, setGeneratedStickersRaw] = useState(() => loadState('generatedStickers', []))
  const [messages, setMessages] = useState(() => loadState('messages', []))
  const [chatLoading, setChatLoading] = useState(false)

  // Persist to localStorage on change
  const setTrends = (v) => { const val = typeof v === 'function' ? v(trends) : v; setTrendsRaw(val); saveState('trends', val) }
  const setSelectedTrend = (v) => { setSelectedTrendRaw(v); saveState('selectedTrend', v) }
  const setStickerIdeas = (v) => { const val = typeof v === 'function' ? v(stickerIdeas) : v; setStickerIdeasRaw(val); saveState('stickerIdeas', val) }
  const setViralBites = (v) => { const val = typeof v === 'function' ? v(viralBites) : v; setViralBitesRaw(val); saveState('viralBites', val) }
  const setGeneratedStickers = (v) => { const val = typeof v === 'function' ? v(generatedStickers) : v; setGeneratedStickersRaw(val); saveState('generatedStickers', val) }

  // Also persist messages
  useEffect(() => { saveState('messages', messages) }, [messages])

  // Stable ref for messages to avoid stale closures
  const messagesRef = useRef(messages)
  messagesRef.current = messages

  const sendChatMessage = useCallback(async (text, { silent = false } = {}) => {
    if (!text.trim()) return null

    const userMsg = { role: 'user', content: text }
    const nextMessages = [...messagesRef.current, userMsg]

    if (!silent) {
      setMessages(nextMessages)
    }
    setChatLoading(true)

    try {
      const res = await fetch(API_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          history: nextMessages.map(m => ({ role: m.role, content: m.content })),
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
  }, [])

  const value = {
    trends, setTrends,
    selectedTrend, setSelectedTrend,
    stickerIdeas, setStickerIdeas,
    viralBites, setViralBites,
    generatedStickers, setGeneratedStickers,
    messages, setMessages,
    chatLoading,
    sendChatMessage,
  }

  return <TrendContext.Provider value={value}>{children}</TrendContext.Provider>
}

export function useTrend() {
  const ctx = useContext(TrendContext)
  if (!ctx) throw new Error('useTrend must be used within TrendProvider')
  return ctx
}

export default TrendContext
