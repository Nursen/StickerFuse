import { useRef, useEffect, useState } from 'react'
import { useTrend } from '../context/TrendContext'
import Message from './Message'

function ChatSidebar({ open, onClose, currentView }) {
  const { messages, setMessages, chatLoading, sendChatMessage, buildChatContext } = useTrend()
  const [input, setInput] = useState('')
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  useEffect(() => {
    if (open) inputRef.current?.focus()
  }, [open])

  const handleSend = async () => {
    const text = input.trim()
    if (!text || chatLoading) return
    setInput('')
    const ctx = { ...buildChatContext(), current_view: currentView || '' }
    await sendChatMessage(text, { context: ctx })
  }

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className={`chat-sidebar ${open ? 'open' : ''}`}>
      <div className="sidebar-header">
        <span className="sidebar-title">Chat</span>
        <div style={{ display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
          {messages.length > 0 && (
            <button
              className="clear-chat-btn"
              onClick={() => setMessages([])}
              title="Clear chat history"
              style={{ fontSize: '0.75rem', padding: '0.15rem 0.5rem', borderRadius: '4px', border: '1px solid var(--border, #444)', background: 'transparent', color: 'var(--text-muted, #999)', cursor: 'pointer' }}
            >
              Clear
            </button>
          )}
          <button className="sidebar-close" onClick={onClose} aria-label="Close chat">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>

      <div className="sidebar-messages">
        {messages.length === 0 && (
          <div className="sidebar-empty">
            <p>Ask me anything about trends, stickers, or design ideas.</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <Message key={i} message={msg} />
        ))}
        {chatLoading && (
          <div className="message assistant">
            <div className="bubble assistant-bubble">
              <div className="typing"><span></span><span></span><span></span></div>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="sidebar-input">
        <div className="input-wrap">
          <textarea
            ref={inputRef}
            className="chat-input"
            value={input}
            onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask about trends or stickers..."
            rows={1}
            disabled={chatLoading}
          />
          <button
            className="send-btn"
            onClick={handleSend}
            disabled={!input.trim() || chatLoading}
            aria-label="Send"
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

export default ChatSidebar
