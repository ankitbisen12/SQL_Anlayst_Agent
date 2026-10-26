import { useCallback, useEffect, useRef, useState } from 'react'

const KEY = 'analyst.conversations.v1'
const MAX_CONVERSATIONS = 30

export const newId = () =>
  (crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random().toString(16).slice(2)}`)

function load() {
  try {
    const parsed = JSON.parse(localStorage.getItem(KEY) || '[]')
    if (!Array.isArray(parsed)) return []
    // Anything that was still streaming when the page closed is marked as interrupted.
    return parsed.map((c) => ({
      ...c,
      messages: c.messages.map((m) =>
        m.role === 'assistant' && !m.done && !m.error ? { ...m, done: true, interrupted: true } : m,
      ),
    }))
  } catch {
    return []
  }
}

// Conversations are kept in this browser only (localStorage). The backend is stateless.
export function useConversations() {
  const [conversations, setConversations] = useState(load)
  const [activeId, setActiveId] = useState(null)
  const saveTimer = useRef(null)

  useEffect(() => {
    // Debounced: streaming produces many small updates.
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(() => {
      try {
        localStorage.setItem(KEY, JSON.stringify(conversations.slice(0, MAX_CONVERSATIONS)))
      } catch {
        /* quota exceeded or storage blocked: history just isn't persisted */
      }
    }, 400)
    return () => clearTimeout(saveTimer.current)
  }, [conversations])

  const active = conversations.find((c) => c.id === activeId) || null

  const createConversation = useCallback((title) => {
    const conversation = { id: newId(), title, createdAt: Date.now(), updatedAt: Date.now(), messages: [] }
    setConversations((prev) => [conversation, ...prev])
    setActiveId(conversation.id)
    return conversation.id
  }, [])

  const updateConversation = useCallback((id, fn) => {
    setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, ...fn(c), updatedAt: Date.now() } : c)))
  }, [])

  const updateMessage = useCallback(
    (conversationId, messageId, patch) =>
      updateConversation(conversationId, (c) => ({
        messages: c.messages.map((m) => (m.id === messageId ? { ...m, ...patch(m) } : m)),
      })),
    [updateConversation],
  )

  const deleteConversation = useCallback((id) => {
    setConversations((prev) => prev.filter((c) => c.id !== id))
    setActiveId((current) => (current === id ? null : current))
  }, [])

  const clearAll = useCallback(() => {
    setConversations([])
    setActiveId(null)
  }, [])

  return {
    conversations, active, activeId, setActiveId,
    createConversation, updateConversation, updateMessage, deleteConversation, clearAll,
  }
}
