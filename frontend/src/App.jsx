import { ArrowDown, Menu, Plus } from 'lucide-react'
import { useCallback, useEffect, useRef, useState } from 'react'
import { streamChat } from './api/streamChat'
import Composer from './components/Composer'
import Message from './components/Message'
import Sidebar from './components/Sidebar'
import Welcome from './components/Welcome'
import { newId, useConversations } from './hooks/useConversations'
import { useHealth } from './hooks/useHealth'
import { useTheme } from './hooks/useTheme'

const HISTORY_TURNS = 6
const titleFrom = (text) => (text.length > 60 ? `${text.slice(0, 57)}…` : text)

export default function App() {
  const { theme, setTheme } = useTheme()
  const health = useHealth()
  const {
    conversations, active, activeId, setActiveId,
    createConversation, updateConversation, updateMessage, deleteConversation,
  } = useConversations()

  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [atBottom, setAtBottom] = useState(true)
  const abortRef = useRef(null)
  const scrollRef = useRef(null)

  const messages = active?.messages ?? []

  useEffect(() => {
    document.title = active ? `${active.title} · SQL Analyst` : 'Airbnb SQL Analyst'
  }, [active])

  // Follow the stream only while the user is at the bottom (don't fight manual scrolling).
  useEffect(() => {
    if (atBottom) scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight })
  }, [messages, atBottom])

  const onScroll = () => {
    const el = scrollRef.current
    setAtBottom(el.scrollHeight - el.scrollTop - el.clientHeight < 80)
  }

  const scrollToBottom = () => scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' })

  const run = useCallback(async (question, baseMessages, conversationId) => {
    const history = baseMessages
      .filter((m) => m.content && !m.error && !m.interrupted)
      .slice(-HISTORY_TURNS)
      .map((m) => ({ role: m.role, content: m.content.slice(0, 4000) }))

    const assistantId = newId()
    updateConversation(conversationId, () => ({
      messages: [
        ...baseMessages,
        { id: newId(), role: 'user', content: question },
        { id: assistantId, role: 'assistant', content: '', steps: [], sql: '', result: null, chart: null, error: '', done: false },
      ],
    }))
    setBusy(true)
    setAtBottom(true)

    const patch = (fn) => updateMessage(conversationId, assistantId, fn)
    const controller = new AbortController()
    abortRef.current = controller

    try {
      await streamChat({
        question,
        history,
        signal: controller.signal,
        onEvent: (event) => {
          switch (event.type) {
            case 'status': patch((m) => ({ steps: [...m.steps, event] })); break
            case 'sql': patch(() => ({ sql: event.sql })); break
            case 'result': patch(() => ({ result: event })); break
            case 'chart': patch(() => ({ chart: event.chart })); break
            case 'token': patch((m) => ({ content: m.content + event.content })); break
            case 'error': patch(() => ({ error: event.message })); break
            case 'done': patch((m) => ({ done: true, latencyMs: event.latency_ms, content: event.answer || m.content })); break
            default: break
          }
        },
      })
      patch((m) => (m.done || m.error ? {} : { error: 'The connection closed before the answer finished.' }))
    } catch (err) {
      if (err.name === 'AbortError') patch((m) => ({ done: true, interrupted: true, content: m.content }))
      else patch(() => ({ error: err.message === 'Failed to fetch' ? 'Cannot reach the backend. Is it running?' : err.message }))
    } finally {
      abortRef.current = null
      setBusy(false)
    }
  }, [updateConversation, updateMessage])

  const ask = (text) => {
    const question = text.trim()
    if (!question || busy) return
    setInput('')
    const conversationId = activeId ?? createConversation(titleFrom(question))
    run(question, active?.messages ?? [], conversationId)
  }

  // Re-run the last question, replacing its answer.
  const retry = () => {
    const lastUser = messages.findLastIndex((m) => m.role === 'user')
    if (lastUser < 0 || busy) return
    run(messages[lastUser].content, messages.slice(0, lastUser), activeId)
  }

  const newChat = () => {
    setActiveId(null)
    setInput('')
    setSidebarOpen(false)
  }

  const lastAssistantId = [...messages].reverse().find((m) => m.role === 'assistant')?.id

  return (
    <div className="layout">
      <Sidebar
        open={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
        conversations={conversations}
        activeId={activeId}
        onSelect={(id) => { setActiveId(id); setSidebarOpen(false) }}
        onNew={newChat}
        onDelete={deleteConversation}
        theme={theme}
        onThemeChange={setTheme}
        health={health}
        busy={busy}
      />

      <main className="main">
        <header className="topbar">
          <button type="button" className="icon-button only-mobile" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu size={18} />
          </button>
          <h2 className="topbar-title">{active ? active.title : 'New chat'}</h2>
          <button type="button" className="icon-button only-mobile" onClick={newChat} disabled={busy} aria-label="New chat">
            <Plus size={18} />
          </button>
        </header>

        <div className="scroll-area" ref={scrollRef} onScroll={onScroll}>
          <div className="thread">
            {messages.length === 0 ? (
              <Welcome onAsk={ask} disabled={busy} />
            ) : (
              messages.map((m) => (
                <Message key={m.id} message={m} onRetry={retry} canRetry={!busy && m.id === lastAssistantId} />
              ))
            )}
          </div>
        </div>

        <div className="composer-wrap">
          {!atBottom && messages.length > 0 && (
            <button type="button" className="scroll-bottom" onClick={scrollToBottom} aria-label="Scroll to latest">
              <ArrowDown size={16} />
            </button>
          )}
          <Composer
            value={input}
            onChange={setInput}
            onSubmit={ask}
            onStop={() => abortRef.current?.abort()}
            busy={busy}
            autoFocus
          />
        </div>
      </main>
    </div>
  )
}
