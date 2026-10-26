const compact = new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 })
const full = new Intl.NumberFormat('en-US', { maximumFractionDigits: 2 })

export const isNumber = (v) => typeof v === 'number' && Number.isFinite(v)

export function formatValue(value) {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'boolean') return value ? 'Yes' : 'No'
  if (isNumber(value)) return full.format(value)
  return String(value)
}

export const formatCompact = (value) => (isNumber(value) ? compact.format(value) : String(value))

// "avg_price" -> "Avg price"
export function humanize(column) {
  const text = String(column).replace(/_/g, ' ').trim()
  return text.charAt(0).toUpperCase() + text.slice(1)
}

export function toCsv(columns, rows) {
  const escape = (v) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s
  }
  return [columns, ...rows].map((r) => r.map(escape).join(',')).join('\n')
}
