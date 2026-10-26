import { ChevronRight, CodeXml } from 'lucide-react'
import { useState } from 'react'
import CopyButton from './CopyButton'

const TOKEN_RE =
  /(--[^\n]*)|('(?:[^']|'')*')|(\b\d+(?:\.\d+)?\b)|(\b(?:SELECT|FROM|WHERE|GROUP|BY|ORDER|LIMIT|JOIN|LEFT|RIGHT|INNER|OUTER|FULL|ON|AS|AND|OR|NOT|IN|IS|NULL|WITH|DISTINCT|HAVING|UNION|ALL|CASE|WHEN|THEN|ELSE|END|DESC|ASC|BETWEEN|LIKE|ILIKE|OVER|PARTITION|FILTER|USING|EXTRACT|INTERVAL|TRUE|FALSE)\b)|(\b[a-z_]+(?=\())/gi

// Tiny SQL highlighter: keywords, functions, strings, numbers, comments.
function highlight(sql) {
  const parts = []
  let last = 0
  for (const m of sql.matchAll(TOKEN_RE)) {
    if (m.index > last) parts.push(sql.slice(last, m.index))
    const cls = m[1] ? 'tk-comment' : m[2] ? 'tk-string' : m[3] ? 'tk-number' : m[4] ? 'tk-keyword' : 'tk-func'
    parts.push(<span key={m.index} className={cls}>{m[0]}</span>)
    last = m.index + m[0].length
  }
  parts.push(sql.slice(last))
  return parts
}

export default function SqlPanel({ sql }) {
  const [open, setOpen] = useState(false)
  return (
    <div className={`sql-panel${open ? ' open' : ''}`}>
      <div className="sql-header">
        <button type="button" className="sql-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <ChevronRight size={14} className="chevron" aria-hidden="true" />
          <CodeXml size={14} aria-hidden="true" />
          SQL query
        </button>
        <CopyButton text={sql} label="Copy SQL" />
      </div>
      {open && (
        <pre className="sql-code"><code>{highlight(sql)}</code></pre>
      )}
    </div>
  )
}
