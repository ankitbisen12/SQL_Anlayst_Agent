import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { useMemo, useState } from 'react'
import { formatValue, humanize, isNumber } from '../format'

function compare(a, b) {
  if (a === b) return 0
  if (a === null || a === undefined) return 1 // nulls last
  if (b === null || b === undefined) return -1
  if (isNumber(a) && isNumber(b)) return a - b
  return String(a).localeCompare(String(b), undefined, { numeric: true, sensitivity: 'base' })
}

export default function DataTable({ result }) {
  const { columns, rows } = result
  const [sort, setSort] = useState({ index: null, dir: 'asc' })

  const numeric = useMemo(
    () => columns.map((_, i) => rows.length > 0 && rows.every((r) => r[i] === null || isNumber(r[i]))),
    [columns, rows],
  )

  const sorted = useMemo(() => {
    if (sort.index === null) return rows
    const factor = sort.dir === 'asc' ? 1 : -1
    return [...rows].sort((a, b) => factor * compare(a[sort.index], b[sort.index]))
  }, [rows, sort])

  const toggleSort = (index) =>
    setSort((s) => (s.index !== index ? { index, dir: 'asc' } : s.dir === 'asc' ? { index, dir: 'desc' } : { index: null, dir: 'asc' }))

  return (
    <div className="table-scroll">
      <table>
        <thead>
          <tr>
            {columns.map((c, i) => {
              const active = sort.index === i
              const Icon = !active ? ArrowUpDown : sort.dir === 'asc' ? ArrowUp : ArrowDown
              return (
                <th key={c + i} className={numeric[i] ? 'num' : ''}
                  aria-sort={active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                  <button type="button" className={`th-button${active ? ' active' : ''}`} onClick={() => toggleSort(i)}>
                    {humanize(c)}
                    <Icon size={12} aria-hidden="true" />
                  </button>
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row, ri) => (
            <tr key={ri}>
              {row.map((v, ci) => (
                <td key={ci} className={`${numeric[ci] ? 'num' : ''}${v === null ? ' null' : ''}`}>{formatValue(v)}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
