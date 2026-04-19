import { useState, useRef, useEffect } from 'react'
import Message from './components/Message'

const API_URL = 'http://localhost:8000/api/chat'

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(scrollToBottom, [messages])

  // Focus input on mount
  useEffect(() => { inputRef.current?.focus() }, [])

  const sendMessage = async () => {
    const text = input.trim()
    if (!text || loading) return

    const userMsg = { role: 'user', content: text }
    const nextMessages = [...messages, userMsg]
    setMessages(nextMessages)
    setInput('')
    setLoading(true)

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
      setMessages(prev => [...prev, assistantMsg])
    } catch (err) {
      setMessages(prev => [
        ...prev,
        { role: 'assistant', content: `Connection error: ${err.message}. Make sure the backend is running on port 8000.` },
      ])
    } finally {
      setLoading(false)
      inputRef.current?.focus()
    }
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  return (
    <div className="app">
      <header className="header">
        <h1 className="logo">StickerFuse</h1>
        <span className="tagline">Viral Moments &rarr; Sticker Designs</span>
      </header>

      <main className="messages">
        {messages.length === 0 && (
          <div className="empty-state">
            <div className="empty-icon">&#127912;</div>
            <h2>What sticker should we make?</h2>
            <p>I can mine Reddit for viral trends, brainstorm sticker ideas, and generate designs. Just tell me a topic or mood.</p>
            <div className="suggestions">
              {['Find trending memes on Reddit', 'Sticker ideas about cats', 'What is going viral right now?'].map(s => (
                <button key={s} className="suggestion" onClick={() => { setInput(s); inputRef.current?.focus() }}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <Message key={i} message={msg} />
        ))}

        {loading && (
          <div className="message assistant">
            <div className="bubble assistant-bubble">
              <div className="typing">
                <span></span><span></span><span></span>
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </main>

      <footer className="input-bar">
        <div className="input-wrap">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe a sticker idea or ask about trends..."
            rows={1}
            disabled={loading}
          />
          <button
            className="send-btn"
            onClick={sendMessage}
            disabled={!input.trim() || loading}
            aria-label="Send"
          >
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="22" y1="2" x2="11" y2="13" />
              <polygon points="22 2 15 22 11 13 2 9 22 2" />
            </svg>
          </button>
        </div>
      </footer>
    </div>
  )
}

export default App
