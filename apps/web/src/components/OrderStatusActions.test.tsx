import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import { OrderStatusActions, type OrderStatusAction } from './OrderStatusActions'

const actions: OrderStatusAction[] = [
  { target_status: 'CONFIRMED', label: 'Xác nhận đơn', allowed: true, reason: null },
  { target_status: 'SHIPPING', label: 'Đang giao hàng', allowed: false, reason: 'Chưa có kiện xuất kho.' },
  { target_status: 'COMPLETED', label: 'Hoàn thành', allowed: false, reason: 'Chưa giao thành công.' },
  { target_status: 'CANCELLED', label: 'Hủy đơn', allowed: true, reason: null },
]

const render = (overrides: Partial<Parameters<typeof OrderStatusActions>[0]> = {}) => renderToStaticMarkup(
  <OrderStatusActions actions={actions} busy={false} notification={null} onUpdate={() => {}} onRefresh={() => {}} {...overrides} />,
)

describe('admin order actions', () => {
  it('enables valid actions and explains blocked actions without requiring hover', () => {
    const html = render()
    const buttons = [...html.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)]
    expect(buttons.find(button => button[2] === 'Xác nhận đơn')?.[1]).not.toContain('disabled')
    expect(buttons.find(button => button[2] === 'Hủy đơn')?.[1]).not.toContain('disabled')
    expect(buttons.find(button => button[2] === 'Đang giao hàng')?.[1]).toContain('disabled')
    expect(html).toContain('<li>Đang giao hàng: Chưa có kiện xuất kho.</li>')
  })

  it('renders an API permission error in the action panel', () => {
    const html = render({ notification: { type: 'error', message: 'Lỗi quyền truy cập (403)' } })
    expect(html).toContain('role="alert"')
    expect(html).toContain('Lỗi quyền truy cập (403)')
  })

  it('keeps the completion message visible when no actions remain available', () => {
    const html = render({
      actions: actions.map(action => ({ ...action, allowed: false, reason: 'Đơn đã hoàn thành.' })),
      notification: { type: 'success', message: 'Đã hoàn thành đơn hàng.' },
    })
    expect(html).toContain('role="status"')
    expect(html).toContain('Đã hoàn thành đơn hàng.')
  })

  it('blocks every action while a request is running', () => {
    const html = render({ busy: true })
    const buttons = [...html.matchAll(/<button\b([^>]*)>/g)]
    expect(buttons).toHaveLength(5)
    expect(buttons.every(button => button[1].includes('disabled'))).toBe(true)
    expect(html).toContain('Đang xử lý yêu cầu')
  })

  it('shows recovery instructions and does not guess permissions when metadata is missing', () => {
    const html = render({ actions: undefined })
    expect(html).toContain('Chưa tải được điều kiện xử lý đơn')
    const buttons = [...html.matchAll(/<button\b([^>]*)>([^<]*)<\/button>/g)]
    expect(buttons.filter(button => button[1].includes('disabled'))).toHaveLength(4)
    expect(buttons.find(button => button[2] === 'Làm mới trạng thái')?.[1]).not.toContain('disabled')
  })
})
