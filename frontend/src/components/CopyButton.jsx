import { Check, Copy } from 'lucide-react'
import { useState } from 'react'

export default function CopyButton({ text, label = 'Copy', showLabel = false }) {
  const [copied, setCopied] = useState(false)

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setTimeout(() => setCopied(false), 1500)
    } catch {
      /* clipboard blocked (insecure context) */
    }
  }

  return (
    <button type="button" className={`action-button${showLabel ? ' with-label' : ''}`} onClick={copy}
      aria-label={copied ? 'Copied' : label} title={copied ? 'Copied' : label}>
      {copied ? <Check size={14} /> : <Copy size={14} />}
      {showLabel && <span>{copied ? 'Copied' : label}</span>}
    </button>
  )
}
