import { useState } from 'react'

const TOOL_COLORS = {
  mining: '#3b82f6',
  reddit: '#3b82f6',
  search: '#3b82f6',
  discovery: '#22c55e',
  trend: '#22c55e',
  explore: '#22c55e',
  design: '#a855f7',
  sticker: '#a855f7',
  generate: '#a855f7',
  image: '#a855f7',
}

function getToolColor(name) {
  const lower = (name || '').toLowerCase()
  for (const [key, color] of Object.entries(TOOL_COLORS)) {
    if (lower.includes(key)) return color
  }
  return '#6b7280'
}

function formatValue(val, depth = 0) {
  if (val === null || val === undefined) return <span className="json-null">null</span>
  if (typeof val === 'boolean') return <span className="json-bool">{String(val)}</span>
  if (typeof val === 'number') return <span className="json-num">{val}</span>
  if (typeof val === 'string') {
    // Truncate very long strings
    const display = val.length > 300 ? val.slice(0, 300) + '...' : val
    return <span className="json-str">"{display}"</span>
  }
  if (Array.isArray(val)) {
    if (val.length === 0) return <span className="json-bracket">[]</span>
    return (
      <div className="json-indent">
        {val.map((item, i) => (
          <div key={i} className="json-entry">
            <span className="json-index">{i}: </span>
            {formatValue(item, depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  if (typeof val === 'object') {
    const keys = Object.keys(val)
    if (keys.length === 0) return <span className="json-bracket">{'{}'}</span>
    return (
      <div className="json-indent">
        {keys.map(k => (
          <div key={k} className="json-entry">
            <span className="json-key">{k}: </span>
            {formatValue(val[k], depth + 1)}
          </div>
        ))}
      </div>
    )
  }
  return String(val)
}

function ToolResult({ result }) {
  const [open, setOpen] = useState(false)
  const name = result.tool_name || result.name || 'Tool Result'
  const raw = result.result || result.data || result.output || result
  let data = raw
  if (typeof raw === 'string') {
    try { data = JSON.parse(raw) } catch (_) { data = raw }
  }
  const color = getToolColor(name)

  return (
    <div className="tool-card" style={{ borderLeftColor: color }}>
      <button className="tool-header" onClick={() => setOpen(!open)}>
        <span className="tool-dot" style={{ background: color }} />
        <span className="tool-name">{name}</span>
        <span className={`chevron ${open ? 'open' : ''}`}>&#9654;</span>
      </button>
      {open && (
        <div className="tool-body">
          {typeof data === 'string' ? (
            <pre className="tool-text">{data}</pre>
          ) : (
            <div className="tool-json">{formatValue(data)}</div>
          )}
        </div>
      )}
    </div>
  )
}

export default ToolResult
