import { useState } from 'react'
import { TrendProvider, useTrend } from './context/TrendContext'
import PackHome from './components/PackHome'
import IdeaBank from './components/IdeaBank'
import StickerStudio from './components/StickerStudio'
import PackView from './components/PackView'
import CommunityView from './components/CommunityView'
import ChatSidebar from './components/ChatSidebar'

function AppInner() {
  const { activePack, clearActivePack } = useTrend()
  const [chatOpen, setChatOpen] = useState(false)
  const [view, setView] = useState('home') // 'home' | 'ideas' | 'studio' | 'pack-view' | 'community'

  // If no active pack and not on home, redirect to home
  // Community works without a pack; everything else needs one
  const currentView = (!activePack && view !== 'home' && view !== 'community') ? 'home' : view

  return (
    <div className={`app-layout ${chatOpen ? 'chat-open' : ''}`}>
      <header className="top-nav">
        <h1
          className="logo"
          onClick={() => { clearActivePack(); setView('home') }}
          style={{ cursor: 'pointer' }}
        >
          StickerFuse
        </h1>

        {activePack && (
          <nav className="nav-tabs">
            <button
              className={`nav-tab ${currentView === 'ideas' ? 'active' : ''}`}
              onClick={() => setView('ideas')}
            >
              Ideas ({activePack.ideas?.length || 0})
            </button>
            <button
              className={`nav-tab ${currentView === 'studio' ? 'active' : ''}`}
              onClick={() => setView('studio')}
            >
              Studio
            </button>
            <button
              className={`nav-tab ${currentView === 'pack-view' ? 'active' : ''}`}
              onClick={() => setView('pack-view')}
            >
              Pack ({activePack.stickers?.length || 0})
            </button>
          </nav>
        )}

        <button
          className={`nav-tab ${currentView === 'community' ? 'active' : ''}`}
          onClick={() => setView('community')}
        >
          Community <span className="tab-badge">Beta</span>
        </button>

        {activePack && (
          <span className="active-pack-indicator">
            {activePack.name}
          </span>
        )}

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
          {currentView === 'home' && (
            <PackHome onPackSelected={() => setView('ideas')} />
          )}
          {currentView === 'ideas' && (
            <IdeaBank onGoToStudio={() => setView('studio')} />
          )}
          {currentView === 'studio' && (
            <StickerStudio
              onGoToIdeas={() => setView('ideas')}
              onGoToPack={() => setView('pack-view')}
            />
          )}
          {currentView === 'pack-view' && (
            <PackView />
          )}
          {currentView === 'community' && (
            <CommunityView />
          )}
        </div>
        <ChatSidebar open={chatOpen} onClose={() => setChatOpen(false)} currentView={currentView} />
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
