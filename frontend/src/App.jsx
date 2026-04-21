import { useState } from 'react'
import { TrendProvider } from './context/TrendContext'
import TrendPulse from './components/TrendPulse'
import StickerStudio from './components/StickerStudio'
import StickerViewer from './components/StickerViewer'
import CommunityView from './components/CommunityView'
import ChatSidebar from './components/ChatSidebar'

const TABS = [
  { id: 'trends', label: 'Trends' },
  { id: 'studio', label: 'Studio' },
  { id: 'library', label: 'Sticker Viewer' },
  { id: 'community', label: 'Community', badge: 'Beta' },
]

function AppInner() {
  const [activeTab, setActiveTab] = useState('trends')
  const [chatOpen, setChatOpen] = useState(false)

  return (
    <div className={`app-layout ${chatOpen ? 'chat-open' : ''}`}>
      <header className="top-nav">
        <h1 className="logo">StickerFuse</h1>
        <nav className="nav-tabs">
          {TABS.map(tab => (
            <button
              key={tab.id}
              className={`nav-tab ${activeTab === tab.id ? 'active' : ''}`}
              onClick={() => setActiveTab(tab.id)}
            >
              {tab.label}
              {tab.badge && <span className="tab-badge">{tab.badge}</span>}
            </button>
          ))}
        </nav>
        <button
          className={`chat-toggle ${chatOpen ? 'active' : ''}`}
          onClick={() => setChatOpen(!chatOpen)}
          aria-label="Toggle chat"
          title="Toggle chat"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
          </svg>
        </button>
      </header>

      <div className="main-area">
        <div className="content-panel">
          {activeTab === 'trends' && (
            <TrendPulse onNavigateStudio={() => setActiveTab('studio')} />
          )}
          {activeTab === 'studio' && (
            <StickerStudio onNavigateTrends={() => setActiveTab('trends')} />
          )}
          {activeTab === 'library' && (
            <StickerViewer />
          )}
          {activeTab === 'community' && (
            <CommunityView />
          )}
        </div>
        <ChatSidebar open={chatOpen} onClose={() => setChatOpen(false)} />
      </div>
    </div>
  )
}

function App() {
  return (
    <TrendProvider>
      <AppInner />
    </TrendProvider>
  )
}

export default App
