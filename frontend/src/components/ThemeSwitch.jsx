import { Monitor, Moon, Sun } from 'lucide-react'

const OPTIONS = [
  { value: 'light', label: 'Light', Icon: Sun },
  { value: 'dark', label: 'Dark', Icon: Moon },
  { value: 'system', label: 'System', Icon: Monitor },
]

export default function ThemeSwitch({ theme, onChange }) {
  return (
    <div className="theme-switch" role="radiogroup" aria-label="Color theme">
      {OPTIONS.map(({ value, label, Icon }) => (
        <button
          key={value}
          type="button"
          role="radio"
          aria-checked={theme === value}
          className={theme === value ? 'active' : ''}
          onClick={() => onChange(value)}
          title={`${label} theme`}
        >
          <Icon size={15} aria-hidden="true" />
          <span>{label}</span>
        </button>
      ))}
    </div>
  )
}
