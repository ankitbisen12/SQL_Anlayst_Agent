import { useCallback, useEffect, useState } from 'react'

const KEY = 'analyst.theme'
const media = () => window.matchMedia('(prefers-color-scheme: dark)')

function readStored() {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : 'system'
  } catch {
    return 'system'
  }
}

// theme: 'light' | 'dark' | 'system'. resolved: the theme actually shown ('light' | 'dark').
export function useTheme() {
  const [theme, setThemeState] = useState(readStored)
  const [systemDark, setSystemDark] = useState(() => media().matches)

  useEffect(() => {
    const mq = media()
    const onChange = (e) => setSystemDark(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  useEffect(() => {
    const root = document.documentElement
    if (theme === 'system') root.removeAttribute('data-theme')
    else root.setAttribute('data-theme', theme)
    try {
      if (theme === 'system') localStorage.removeItem(KEY)
      else localStorage.setItem(KEY, theme)
    } catch {
      /* storage unavailable: theme still applies for this session */
    }
  }, [theme])

  const setTheme = useCallback((value) => setThemeState(value), [])
  const resolved = theme === 'system' ? (systemDark ? 'dark' : 'light') : theme
  return { theme, resolved, setTheme }
}
