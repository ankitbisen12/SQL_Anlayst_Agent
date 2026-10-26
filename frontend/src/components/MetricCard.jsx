import { formatValue, humanize } from '../format'

export default function MetricCard({ chart }) {
  return (
    <div className="metric">
      <div className="metric-label">{humanize(chart.label)}</div>
      <div className="metric-value">{formatValue(chart.value)}</div>
    </div>
  )
}
