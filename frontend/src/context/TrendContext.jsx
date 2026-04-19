import { createContext, useState, useContext, useRef, useCallback } from 'react'

const TrendContext = createContext()

const API_URL = 'http://localhost:8000/api/chat'

export function TrendProvider({ children }) {
  const [trends, setTrends] = useState([])
  const [selectedTrend, setSelectedTrend] = useState(null)
  const [stickerIdeas, setStickerIdeas] = useState([])
  const [viralBites, setViralBites] = useState([])
  const [generatedStickers, setGeneratedStickers] = useState([])
  const [messages, setMessages] = useState([])
  const [chatLoading, setChatLoading] = useState(false)

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
