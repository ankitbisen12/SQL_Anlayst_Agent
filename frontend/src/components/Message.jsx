import { ChevronDown, CircleAlert, CircleCheck, LoaderCircle, RotateCcw, Sparkles } from 'lucide-react'
import { useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import CopyButton from './CopyButton'
import ResultCard from './ResultCard'
import SqlPanel from './SqlPanel'

function Progress({ steps, running, latencyMs }) {
  const [open, setOpen] = useState(false)
  if (!steps.length) return null

  const list = (
    <ol className="steps">
      {steps.map((s, i) => {
        const active = running && i === steps.length - 1
        return (
          <li key={s.step + i} className={active ? 'active' : 'complete'}>
            {active ? <LoaderCircle size={14} className="spin" aria-hidden="true" /> : <CircleCheck size={14} aria-hidden="true" />}
            {s.message}
          </li>
        )
      })}
    </ol>
  )

  if (running) return <div className="progress">{list}</div>

  return (
    <div className={`progress collapsed${open ? ' open' : ''}`}>
      <button type="button" className="progress-toggle" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <CircleCheck size={14} aria-hidden="true" />
        {steps.length} step{steps.length === 1 ? '' : 's'}
        {latencyMs !== undefined && ` · ${(latencyMs / 1000).toFixed(1)}s`}
        <ChevronDown size={14} className="chevron" aria-hidden="true" />
      </button>
      {open && list}
    </div>
  )
}

function UserMessage({ message }) {
  return (
    <div className="message user">
      <div className="user-bubble">{message.content}</div>
    </div>
  )
}

function AssistantMessage({ message, onRetry, canRetry }) {
  const running = !message.done && !message.error
  const waiting = running && message.steps.length === 0 && !message.content

  return (
    <div className="message assistant">
      <div className="assistant-avatar" aria-hidden="true"><Sparkles size={15} /></div>
      <div className="assistant-body">
        <div className="assistant-name">Analyst</div>

        {waiting && (
          <div className="typing" aria-label="Thinking"><span /><span /><span /></div>
        )}
        <Progress steps={message.steps} running={running && !message.content} latencyMs={message.latencyMs} />

        {message.result && <ResultCard result={message.result} chart={message.chart} />}

        {message.content && (
          <div className={`answer markdown${running ? ' streaming' : ''}`}>
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
          </div>
        )}

        {message.sql && <SqlPanel sql={message.sql} />}

        {message.interrupted && <div className="note">This response was interrupted.</div>}

        {message.error && (
          <div className="alert" role="alert">
            <CircleAlert size={16} aria-hidden="true" />
            <span>{message.error}</span>
            {canRetry && (
              <button type="button" className="alert-action" onClick={onRetry}>
                <RotateCcw size={14} aria-hidden="true" /> Retry
              </button>
            )}
          </div>
        )}

        {message.done && message.content && (
          <div className="message-actions">
            <CopyButton text={message.content} label="Copy answer" />
            {canRetry && (
              <button type="button" className="action-button" onClick={onRetry} aria-label="Regenerate answer" title="Regenerate">
                <RotateCcw size={14} />
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

export default function Message({ message, onRetry, canRetry }) {
  return message.role === 'user'
    ? <UserMessage message={message} />
    : <AssistantMessage message={message} onRetry={onRetry} canRetry={canRetry} />
}
