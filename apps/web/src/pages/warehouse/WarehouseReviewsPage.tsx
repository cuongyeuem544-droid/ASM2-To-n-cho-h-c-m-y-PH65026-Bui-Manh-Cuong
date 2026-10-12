import { useEffect, useState } from 'react'
import { MessageSquare, Star } from 'lucide-react'
import { api } from '../../services/api'

interface ReviewItem {
  id: number
  order_id: number | null
  product_name: string
  rating: number
  comment: string | null
  is_verified_purchase: boolean
  created_at: string | null
}

export function WarehouseReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    setLoading(true)
    api<{ items: ReviewItem[]; total: number }>('/warehouse-portal/reviews')
      .then((res) => setReviews(res.items || []))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', maxWidth: '1400px', margin: '0 auto' }}>
      {/* Header */}
      <div
        style={{
          background: 'white',
          borderRadius: '16px',
          border: '1px solid #e2e8f0',
          padding: '20px 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          flexWrap: 'wrap',
          gap: '16px',
          boxShadow: '0 1px 3px rgba(0,0,0,0.03)',
        }}
      >
        <div>
          <div style={{ fontSize: '11px', fontWeight: 800, color: '#047857', textTransform: 'uppercase', letterSpacing: '0.8px' }}>
            CHẤT LƯỢNG ĐÓNG GÓI & SỰ HÀI LÒNG KHÁCH HÀNG
          </div>
          <h1 style={{ margin: '4px 0 0', fontSize: '22px', fontWeight: 900, color: '#0f172a' }}>
            Đánh Giá & Phản Hồi Đơn Hàng
          </h1>
          <p style={{ margin: '4px 0 0', fontSize: '13px', color: '#64748b' }}>
            Lắng nghe ý kiến của người mua đối với các đơn hàng do chi nhánh kho của bạn xử lý
          </p>
        </div>

        <div
          style={{
            background: '#ecfdf5',
            border: '1px solid #a7f3d0',
            padding: '8px 16px',
            borderRadius: '12px',
            fontSize: '13px',
            fontWeight: 800,
            color: '#047857',
            display: 'flex',
            alignItems: 'center',
            gap: '8px',
          }}
        >
          <MessageSquare size={16} />
          <span>Tổng số: {reviews.length} đánh giá</span>
        </div>
      </div>

      {/* Reviews Grid */}
      {loading ? (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1px solid #e2e8f0',
            padding: '60px 20px',
            textAlign: 'center',
            color: '#94a3b8',
            fontWeight: 700,
          }}
        >
          Đang tải phản hồi từ khách hàng…
        </div>
      ) : reviews.length === 0 ? (
        <div
          style={{
            background: 'white',
            borderRadius: '16px',
            border: '1.5px dashed #cbd5e1',
            padding: '60px 20px',
            textAlign: 'center',
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#f1f5f9',
              color: '#64748b',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 16px',
            }}
          >
            <MessageSquare size={28} />
          </div>
          <h3 style={{ margin: 0, fontSize: '16px', fontWeight: 800, color: '#0f172a' }}>
            Chưa có phản hồi nào cho chi nhánh
          </h3>
          <p style={{ margin: '6px 0 0', fontSize: '13px', color: '#64748b' }}>
            Các phản hồi từ khách hàng sau khi nhận hàng thành công sẽ hiển thị tại đây.
          </p>
        </div>
      ) : (
        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fill, minmax(360px, 1fr))',
            gap: '18px',
          }}
        >
          {reviews.map((r) => (
            <div
              key={r.id}
              style={{
                background: 'white',
                borderRadius: '16px',
                border: '1px solid #e2e8f0',
                padding: '20px',
                boxShadow: '0 2px 6px rgba(0,0,0,0.03)',
                display: 'flex',
                flexDirection: 'column',
                justifyContent: 'space-between',
                gap: '14px',
                transition: 'transform 0.15s ease, box-shadow 0.15s ease',
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.transform = 'translateY(-2px)'
                e.currentTarget.style.boxShadow = '0 8px 16px rgba(0,0,0,0.06)'
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.transform = 'translateY(0)'
                e.currentTarget.style.boxShadow = '0 2px 6px rgba(0,0,0,0.03)'
              }}
            >
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '10px' }}>
                  <span style={{ fontWeight: 800, fontSize: '14px', color: '#0f172a' }}>
                    {r.product_name}
                  </span>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '2px', color: '#f59e0b' }}>
                    {Array.from({ length: 5 }).map((_, i) => (
                      <Star
                        key={i}
                        size={15}
                        fill={i < r.rating ? '#f59e0b' : 'none'}
                        color={i < r.rating ? '#f59e0b' : '#cbd5e1'}
                      />
                    ))}
                  </div>
                </div>

                <p
                  style={{
                    margin: '12px 0 0',
                    fontSize: '13px',
                    color: '#334155',
                    background: '#f8fafc',
                    padding: '12px 14px',
                    borderRadius: '10px',
                    border: '1px solid #e2e8f0',
                    fontStyle: 'italic',
                    lineHeight: 1.5,
                  }}
                >
                  "{r.comment || 'Khách hàng không để lại nhận xét văn bản.'}"
                </p>
              </div>

              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  fontSize: '11.5px',
                  color: '#64748b',
                  paddingTop: '6px',
                  borderTop: '1px solid #f1f5f9',
                }}
              >
                <span style={{ fontWeight: 700, color: '#047857' }}>
                  {r.order_id ? `Đơn hàng #${r.order_id}` : 'Đơn giao kho'}
                </span>
                <span>{r.created_at ? new Date(r.created_at).toLocaleDateString('vi-VN') : ''}</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
