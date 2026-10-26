import { MessageSquare, Plus, Trash2, X } from 'lucide-react'
import ThemeSwitch from './ThemeSwitch'

const STATUS_TEXT = {
  online: 'Database connected',
  offline: 'Backend unreachable',
  checking: 'Connecting…',
}

function groupByDate(conversations) {
  const startOfToday = new Date().setHours(0, 0, 0, 0)
  const week = startOfToday - 6 * 86400000
  const groups = [
    { label: 'Today', items: [] },
    { label: 'Previous 7 days', items: [] },
    { label: 'Older', items: [] },
  ]
  for (const c of conversations) {
    const t = c.updatedAt || c.createdAt
    groups[t >= startOfToday ? 0 : t >= week ? 1 : 2].items.push(c)
  }
  return groups.filter((g) => g.items.length)
}

export default function Sidebar({
  open, onClose, conversations, activeId, onSelect, onNew, onDelete, theme, onThemeChange, health, busy,
}) {
  return (
    <>
      <div className={`scrim${open ? ' visible' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`sidebar${open ? ' open' : ''}`} aria-label="Conversations">
        <div className="sidebar-top">
          <div className="brand">
            <img src="/favicon.svg" alt="" width="28" height="28" />
            <div>
              <div className="brand-name">SQL Analyst</div>
              <div className="brand-sub">Airbnb data</div>
            </div>
            <button type="button" className="icon-button only-mobile" onClick={onClose} aria-label="Close menu">
              <X size={18} />
            </button>
          </div>
          <button type="button" className="new-chat" onClick={onNew} disabled={busy}>
            <Plus size={16} aria-hidden="true" />
            New chat
          </button>
        </div>

        <nav className="history">
          {conversations.length === 0 ? (
            <p className="history-empty">Your conversations will appear here.</p>
          ) : (
            groupByDate(conversations).map((group) => (
              <div key={group.label} className="history-group">
                <div className="history-label">{group.label}</div>
                <ul>
                  {group.items.map((c) => (
                    <li key={c.id}>
                      <button
                        type="button"
                        className={`history-item${c.id === activeId ? ' active' : ''}`}
                        onClick={() => onSelect(c.id)}
                        aria-current={c.id === activeId ? 'page' : undefined}
                        disabled={busy && c.id !== activeId}
                      >
                        <MessageSquare size={15} aria-hidden="true" />
                        <span className="history-title">{c.title}</span>
                      </button>
                      <button
                        type="button"
                        className="history-delete"
                        onClick={() => onDelete(c.id)}
                        aria-label={`Delete conversation: ${c.title}`}
                        disabled={busy && c.id === activeId}
                      >
                        <Trash2 size={14} />
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            ))
          )}
        </nav>

        <div className="sidebar-bottom">
          <div className={`health health-${health}`} role="status">
            <span className="health-dot" aria-hidden="true" />
            {STATUS_TEXT[health]}
          </div>
          <ThemeSwitch theme={theme} onChange={onThemeChange} />
        </div>
      </aside>
    </>
  )
}
