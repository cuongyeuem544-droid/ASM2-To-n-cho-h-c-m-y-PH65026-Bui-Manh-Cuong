import { Clock } from 'lucide-react'
import { useEffect, useState } from 'react'
import { getCurrentVietnamTimeParts } from '../utils/dateUtils'

export function LiveClock() {
  const [timeParts, setTimeParts] = useState(getCurrentVietnamTimeParts)

  useEffect(() => {
    const timer = setInterval(() => {
      setTimeParts(getCurrentVietnamTimeParts())
    }, 1000)
    return () => clearInterval(timer)
  }, [])

  return (
    <div
      className="system-live-clock"
      title={`Bộ giờ chuẩn thời gian thực Việt Nam (Asia/Ho_Chi_Minh - GMT+7)\nCập nhật thời gian thực từng giây`}
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: '8px',
        padding: '5px 12px',
        borderRadius: '9999px',
        background: 'rgba(241, 245, 249, 0.85)',
        border: '1px solid #cbd5e1',
        fontSize: '12px',
        color: '#0f172a',
        fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace',
        userSelect: 'none',
        boxShadow: '0 1px 2px 0 rgba(0, 0, 0, 0.05)',
      }}
    >
      <div style={{ position: 'relative', display: 'flex', alignItems: 'center' }}>
        <Clock size={14} style={{ color: '#0284c7' }} />
        <span
          style={{
            position: 'absolute',
            top: -2,
            right: -2,
            width: '6px',
            height: '6px',
            borderRadius: '50%',
            backgroundColor: '#16a34a',
            boxShadow: '0 0 0 2px #fff',
          }}
        />
      </div>

      <div style={{ display: 'flex', alignItems: 'baseline', gap: '6px' }}>
        <span style={{ fontWeight: 800, fontSize: '13px', color: '#0f172a', letterSpacing: '0.02em' }}>
          {timeParts.timeStr}
        </span>
        <span style={{ color: '#64748b', fontSize: '11px', display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
          <span>•</span>
          <span style={{ textTransform: 'capitalize' }}>{timeParts.dayOfWeek}</span>,
          <span>{timeParts.dateStr}</span>
        </span>
      </div>

      <span
        style={{
          padding: '1px 5px',
          borderRadius: '4px',
          fontSize: '9.5px',
          fontWeight: 700,
          background: '#e0f2fe',
          color: '#0369a1',
          border: '1px solid #bae6fd',
          letterSpacing: '0.04em',
        }}
      >
        GMT+7
      </span>
    </div>
  )
}
