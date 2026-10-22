export interface OrderStatusAction {
  target_status: string
  label: string
  allowed: boolean
  reason: string | null
}

export interface OrderActionNotification {
  type: 'success' | 'error'
  message: string
}

interface Props {
  actions?: OrderStatusAction[]
  busy: boolean
  notification: OrderActionNotification | null
  onUpdate: (status: string) => void
  onRefresh: () => void
}

const buttons = [
  { status: 'CONFIRMED', label: 'Xác nhận đơn', background: '#2563eb', color: '#fff' },
  { status: 'SHIPPING', label: 'Đang giao hàng', background: '#0284c7', color: '#fff' },
  { status: 'COMPLETED', label: 'Hoàn thành', background: '#16a34a', color: '#fff' },
  { status: 'CANCELLED', label: 'Hủy đơn', background: '#fee2e2', color: '#dc2626' },
]

export function OrderStatusActions({ actions, busy, notification, onUpdate, onRefresh }: Props) {
  const unavailable = buttons.flatMap(button => {
    const action = actions?.find(item => item.target_status === button.status)
    return action && !action.allowed && action.reason ? [`${button.label}: ${action.reason}`] : []
  })

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0 }}>
      {notification && (
        <div
          role={notification.type === 'error' ? 'alert' : 'status'}
          className={`alert ${notification.type === 'success' ? 'alert-success' : 'alert-error'}`}
          style={{ margin: 0 }}
        >
          {notification.message}
        </div>
      )}
      {busy && <div role="status">Đang xử lý yêu cầu, vui lòng chờ…</div>}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {buttons.map(button => {
          const action = actions?.find(item => item.target_status === button.status)
          const disabled = busy || action?.allowed !== true
          return (
            <button
              key={button.status}
              type="button"
              disabled={disabled}
              title={action?.reason || (busy ? 'Đang xử lý yêu cầu' : undefined)}
              onClick={() => onUpdate(button.status)}
              style={{
                padding: '8px 14px', background: button.background, color: button.color,
                border: 'none', borderRadius: 6, fontSize: 12, fontWeight: 700,
                cursor: disabled ? 'not-allowed' : 'pointer', opacity: disabled ? 0.55 : 1,
              }}
            >
              {button.label}
            </button>
          )
        })}
        <button type="button" disabled={busy} onClick={onRefresh} className="admin-button button-secondary">
          Làm mới trạng thái
        </button>
      </div>
      {!actions && <div role="status">Chưa tải được điều kiện xử lý đơn. Bấm “Làm mới trạng thái” để thử lại.</div>}
      {unavailable.length > 0 && (
        <ul style={{ margin: 0, paddingLeft: 18, color: '#475569', fontSize: 12 }}>
          {unavailable.map(reason => <li key={reason}>{reason}</li>)}
        </ul>
      )}
    </div>
  )
}
