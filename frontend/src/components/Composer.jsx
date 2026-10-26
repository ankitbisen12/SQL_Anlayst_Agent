import { ArrowUp, Square } from 'lucide-react'
import { useEffect, useRef } from 'react'

const MAX_CHARS = 1000

export default function Composer({ value, onChange, onSubmit, onStop, busy, autoFocus }) {
  const ref = useRef(null)

  // Auto-grow up to the CSS max-height.
  useEffect(() => {
    const el = ref.current
    if (!el) return
    el.style.height = 'auto'
    el.style.height = `${el.scrollHeight}px`
  }, [value])

  useEffect(() => {
    if (autoFocus && !busy) ref.current?.focus()
  }, [autoFocus, busy])

  const submit = (e) => {
    e.preventDefault()
    if (!busy && value.trim()) onSubmit(value)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey && !e.nativeEvent.isComposing) submit(e)
  }

  const nearLimit = value.length > MAX_CHARS * 0.8

  return (
    <form className="composer" onSubmit={submit}>
      <div className="composer-box">
        <textarea
          ref={ref}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Ask about listings, prices, bookings, reviews…"
          rows={1}
          maxLength={MAX_CHARS}
          aria-label="Your question"
        />
        <div className="composer-row">
          <span className="composer-hint">
            <kbd>Enter</kbd> to send · <kbd>Shift</kbd>+<kbd>Enter</kbd> for a new line
          </span>
          {nearLimit && <span className="composer-count">{value.length}/{MAX_CHARS}</span>}
          {busy ? (
            <button type="button" className="send-button stop" onClick={onStop} aria-label="Stop generating" title="Stop">
              <Square size={14} fill="currentColor" />
            </button>
          ) : (
            <button type="submit" className="send-button" disabled={!value.trim()} aria-label="Send question" title="Send">
              <ArrowUp size={18} />
            </button>
          )}
        </div>
      </div>
      <p className="disclaimer">Read-only analyst. Answers can be wrong, so check the SQL for important decisions.</p>
    </form>
  )
}
