import { ChartColumn, Download, Table2 } from 'lucide-react'
import { lazy, Suspense, useState } from 'react'
import { toCsv } from '../format'
import DataTable from './DataTable'
import MetricCard from './MetricCard'

// Recharts is large: load it only when the first chart is shown.
const ChartView = lazy(() => import('./ChartView'))

const CHART_TYPES = new Set(['bar', 'line', 'pie', 'scatter'])

function downloadCsv(result) {
  const blob = new Blob([toCsv(result.columns, result.rows)], { type: 'text/csv;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'query-result.csv'
  a.click()
  URL.revokeObjectURL(url)
}

export default function ResultCard({ result, chart }) {
  const hasChart = chart && CHART_TYPES.has(chart.type)
  const [view, setView] = useState('chart')

  if (!result.rows.length) {
    return <div className="result-empty">The query ran successfully but returned no rows.</div>
  }
  if (chart?.type === 'metric') return <MetricCard chart={chart} />

  const showChart = hasChart && view === 'chart'

  return (
    <section className="result-card" aria-label="Query result">
      <header className="result-header">
        <div className="result-title">
          Result
          <span className="pill">
            {result.row_count} row{result.row_count === 1 ? '' : 's'}
            {result.truncated ? ' · truncated' : ''}
          </span>
        </div>
        <div className="result-actions">
          {hasChart && (
            <div className="segmented" role="tablist" aria-label="Result view">
              <button type="button" role="tab" aria-selected={view === 'chart'} className={view === 'chart' ? 'active' : ''}
                onClick={() => setView('chart')}>
                <ChartColumn size={14} aria-hidden="true" /> Chart
              </button>
              <button type="button" role="tab" aria-selected={view === 'table'} className={view === 'table' ? 'active' : ''}
                onClick={() => setView('table')}>
                <Table2 size={14} aria-hidden="true" /> Table
              </button>
            </div>
          )}
          <button type="button" className="action-button" onClick={() => downloadCsv(result)}
            aria-label="Download CSV" title="Download CSV">
            <Download size={14} />
          </button>
        </div>
      </header>
      <div className="result-body">
        {showChart ? (
          <Suspense fallback={<div className="chart-loading">Loading chart…</div>}>
            <ChartView chart={chart} result={result} />
          </Suspense>
        ) : (
          <DataTable result={result} />
        )}
      </div>
    </section>
  )
}
