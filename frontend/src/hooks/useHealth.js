import { useEffect, useState } from 'react'

const API_URL = import.meta.env.VITE_API_URL || ''

// 'checking' | 'online' | 'offline' - polls the readiness probe (API + database).
export function useHealth(intervalMs = 30000) {
  const [status, setStatus] = useState('checking')

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await fetch(`${API_URL}/api/health/ready`, { cache: 'no-store' })
        if (!cancelled) setStatus(res.ok ? 'online' : 'offline')
      } catch {
        if (!cancelled) setStatus('offline')
      }
    }
    check()
    const timer = setInterval(check, intervalMs)
    const onFocus = () => check()
    window.addEventListener('focus', onFocus)
    return () => {
      cancelled = true
      clearInterval(timer)
      window.removeEventListener('focus', onFocus)
    }
  }, [intervalMs])

  return status
}
