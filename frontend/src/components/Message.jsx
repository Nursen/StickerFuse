import ToolResult from './ToolResult'
import SaveToLibraryButton from './SaveToLibraryButton'

// Minimal markdown: **bold**, `code`, ```code blocks```
function renderContent(text) {
  if (!text) return null

  // Split on code blocks first
  const parts = text.split(/(```[\s\S]*?```)/g)

  return parts.map((part, i) => {
    // Fenced code block
    if (part.startsWith('```') && part.endsWith('```')) {
      const inner = part.slice(3, -3)
      // Strip optional language identifier on first line
      const newlineIdx = inner.indexOf('\n')
      const code = newlineIdx > -1 ? inner.slice(newlineIdx + 1) : inner
      return <pre key={i} className="code-block"><code>{code}</code></pre>
    }

    // Inline formatting: split on inline code first, then bold within non-code segments
    const inlineParts = part.split(/(`[^`]+`)/g)
    return (
      <span key={i}>
        {inlineParts.map((seg, j) => {
          if (seg.startsWith('`') && seg.endsWith('`')) {
            return <code key={j} className="inline-code">{seg.slice(1, -1)}</code>
          }
          // Bold
          const boldParts = seg.split(/(\*\*[^*]+\*\*)/g)
          return boldParts.map((bp, k) => {
            if (bp.startsWith('**') && bp.endsWith('**')) {
              return <strong key={`${j}-${k}`}>{bp.slice(2, -2)}</strong>
            }
            return bp
          })
        })}
      </span>
    )
  })
}

// Extract sticker image filenames from tool results
function getStickerImages(toolResults) {
  if (!toolResults) return []
  const images = []
  for (const tr of toolResults) {
    const raw = tr.result || tr.data || ''
    const match = typeof raw === 'string' && raw.match(/Sticker image saved to:.*?([^/\\]+\.png)/i)
    if (match) images.push(match[1])
  }
  return images
}

function Message({ message }) {
  const { role, content, toolResults } = message
  const isUser = role === 'user'
  const stickerImages = getStickerImages(toolResults)

  return (
    <div className={`message ${role}`}>
      <div className={`bubble ${role}-bubble`}>
        <div className="bubble-content">{renderContent(content)}</div>

        {stickerImages.length > 0 && (
          <div className="sticker-gallery">
            {stickerImages.map((filename, i) => (
              <div key={i} className="sticker-preview">
                <img
                  src={`http://localhost:8000/stickers/${filename}`}
                  alt="Generated sticker"
                  className="sticker-img"
                />
                <a
                  href={`http://localhost:8000/stickers/${filename}`}
                  download={filename}
                  className="download-btn"
                >
                  Download
                </a>
                <SaveToLibraryButton sourceFilename={filename} />
              </div>
            ))}
          </div>
        )}

        {toolResults && toolResults.length > 0 && (
          <div className="tool-results">
            {toolResults.map((tr, i) => (
              <ToolResult key={i} result={tr} />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

export default Message
