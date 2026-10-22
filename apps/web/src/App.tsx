import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { ErrorBoundary } from './components/ErrorBoundary'
import { ForceChangePasswordModal } from './components/ForceChangePasswordModal'
import { useAuth } from './services/auth'

// Admin Pages
const AuditPage = lazy(() => import('./pages/AuditPage').then(module => ({ default: module.AuditPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const ImportsPage = lazy(() => import('./pages/ImportsPage').then(module => ({ default: module.ImportsPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(module => ({ default: module.LoginPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(module => ({ default: module.NotFoundPage })))
const OrdersPage = lazy(() => import('./pages/OrdersPage').then(module => ({ default: module.OrdersPage })))
const ProductDetailPage = lazy(() => import('./pages/ProductDetailPage').then(module => ({ default: module.ProductDetailPage })))
const ProductsPage = lazy(() => import('./pages/ProductsPage').then(module => ({ default: module.ProductsPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then(module => ({ default: module.RunsPage })))
const SourcesPage = lazy(() => import('./pages/SourcesPage').then(module => ({ default: module.SourcesPage })))
const UsersPage = lazy(() => import('./pages/UsersPage').then(module => ({ default: module.UsersPage })))
const WarehousesPage = lazy(() => import('./pages/WarehousesPage').then(module => ({ default: module.WarehousesPage })))
const BatchesPage = lazy(() => import('./pages/BatchesPage').then(module => ({ default: module.BatchesPage })))
const EmailsPage = lazy(() => import('./pages/EmailsPage').then(module => ({ default: module.EmailsPage })))
const ReviewsPage = lazy(() => import('./pages/ReviewsPage').then(module => ({ default: module.ReviewsPage })))
const CampaignsPage = lazy(() => import('./pages/CampaignsPage').then(module => ({ default: module.CampaignsPage })))
const CategoriesPage = lazy(() => import('./pages/CategoriesPage').then(module => ({ default: module.CategoriesPage })))
const ReturnsPage = lazy(() => import('./pages/ReturnsPage').then(module => ({ default: module.ReturnsPage })))
const RefundsPage = lazy(() => import('./pages/RefundsPage').then(module => ({ default: module.RefundsPage })))
const LiveChatPage = lazy(() => import('./pages/LiveChatPage').then(module => ({ default: module.LiveChatPage })))
const ChatbotAdminPage = lazy(() => import('./pages/admin/ChatbotAdminPage').then(module => ({ default: module.ChatbotAdminPage })))
const RevenuePage = lazy(() => import('./pages/RevenuePage').then(module => ({ default: module.RevenuePage })))

// Warehouse Manager Pages & Layout
const WarehouseManagerLayout = lazy(() =>
  import('./components/WarehouseManagerLayout').then(module => ({ default: module.WarehouseManagerLayout }))
)
const WarehouseOverviewPage = lazy(() =>
  import('./pages/warehouse/WarehouseOverviewPage').then(module => ({ default: module.WarehouseOverviewPage }))
)
const WarehouseProductsPage = lazy(() =>
  import('./pages/warehouse/WarehouseProductsPage').then(module => ({ default: module.WarehouseProductsPage }))
)
const WarehouseImportsPage = lazy(() =>
  import('./pages/warehouse/WarehouseImportsPage').then(module => ({ default: module.WarehouseImportsPage }))
)
const WarehouseAlertsPage = lazy(() =>
  import('./pages/warehouse/WarehouseAlertsPage').then(module => ({ default: module.WarehouseAlertsPage }))
)
const WarehouseOrdersPage = lazy(() =>
  import('./pages/warehouse/WarehouseOrdersPage').then(module => ({ default: module.WarehouseOrdersPage }))
)
const WarehouseReturnsPage = lazy(() =>
  import('./pages/warehouse/WarehouseReturnsPage').then(module => ({ default: module.WarehouseReturnsPage }))
)
const WarehouseBatchesPage = lazy(() =>
  import('./pages/warehouse/WarehouseBatchesPage').then(module => ({ default: module.WarehouseBatchesPage }))
)
const WarehouseStockPage = lazy(() =>
  import('./pages/warehouse/WarehouseStockPage').then(module => ({ default: module.WarehouseStockPage }))
)
const WarehouseAdjustmentsPage = lazy(() =>
  import('./pages/warehouse/WarehouseAdjustmentsPage').then(module => ({ default: module.WarehouseAdjustmentsPage }))
)
const WarehouseStaffPage = lazy(() =>
  import('./pages/warehouse/WarehouseStaffPage').then(module => ({ default: module.WarehouseStaffPage }))
)
const WarehouseAuditPage = lazy(() =>
  import('./pages/warehouse/WarehouseAuditPage').then(module => ({ default: module.WarehouseAuditPage }))
)
const WarehouseReviewsPage = lazy(() =>
  import('./pages/warehouse/WarehouseReviewsPage').then(module => ({ default: module.WarehouseReviewsPage }))
)

// Warehouse Staff Pages & Layout
const WarehouseStaffLayout = lazy(() =>
  import('./components/WarehouseStaffLayout').then(module => ({ default: module.WarehouseStaffLayout }))
)
const StaffTodayPage = lazy(() =>
  import('./pages/staff/StaffTodayPage').then(module => ({ default: module.StaffTodayPage }))
)
const StaffPickingPackingPage = lazy(() =>
  import('./pages/staff/StaffPickingPackingPage').then(module => ({ default: module.StaffPickingPackingPage }))
)
const StaffInventoryChecksPage = lazy(() =>
  import('./pages/staff/StaffInventoryChecksPage').then(module => ({ default: module.StaffInventoryChecksPage }))
)
const StaffStockPage = lazy(() =>
  import('./pages/staff/StaffStockPage').then(module => ({ default: module.StaffStockPage }))
)
const StaffHistoryPage = lazy(() =>
  import('./pages/staff/StaffHistoryPage').then(module => ({ default: module.StaffHistoryPage }))
)
const StaffReturnsPage = lazy(() =>
  import('./pages/staff/StaffReturnsPage').then(module => ({ default: module.StaffReturnsPage }))
)

function ProtectedAdminLayout() {
  const { user, loading } = useAuth()
  if (loading) return <div className="full-loading">Đang khởi tạo PharmaTrust…</div>
  if (!user) return <Navigate to="/login" replace />
  // Role redirection for warehouse managers and staff to their dedicated portals
  if (user.role === 'WAREHOUSE_MANAGER') return <Navigate to="/warehouse/overview" replace />
  if (user.role === 'WAREHOUSE_STAFF') return <Navigate to="/staff/today" replace />
  if (user.role !== 'ADMIN') return <Navigate to="/login" replace />
  return (
    <Layout>
      <Outlet />
    </Layout>
  )
}

function WarehouseManagerGuard() {
  const { user, loading } = useAuth()
  if (loading) return <div className="full-loading">Đang khởi tạo PharmaTrust…</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'WAREHOUSE_MANAGER' && user.role !== 'ADMIN') {
    if (user.role === 'WAREHOUSE_STAFF') return <Navigate to="/staff/today" replace />
    return <Navigate to="/" replace />
  }
  return <WarehouseManagerLayout />
}

function WarehouseStaffGuard() {
  const { user, loading } = useAuth()
  if (loading) return <div className="full-loading">Đang khởi tạo PharmaTrust…</div>
  if (!user) return <Navigate to="/login" replace />
  if (user.role !== 'WAREHOUSE_STAFF' && user.role !== 'WAREHOUSE_MANAGER' && user.role !== 'ADMIN') {
    return <Navigate to="/" replace />
  }
  return <WarehouseStaffLayout />
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return user?.role === 'ADMIN' ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <ErrorBoundary>
      <ForceChangePasswordModal />
      <Suspense fallback={<div className="full-loading">Đang tải giao diện…</div>}>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          {/* 1. Admin System Portal Routes */}
          <Route element={<ProtectedAdminLayout />}>
            <Route index element={<DashboardPage />} />
            <Route path="products" element={<ProductsPage />} />
            <Route path="products/:id" element={<ProductDetailPage />} />
            <Route path="categories" element={<CategoriesPage />} />
            <Route path="classification/queue" element={<Navigate to="/products" replace />} />
            <Route path="orders" element={<OrdersPage />} />
            <Route path="returns" element={<ReturnsPage />} />
            <Route path="refunds" element={<RefundsPage />} />
            <Route path="revenue" element={<AdminOnly><RevenuePage /></AdminOnly>} />
            <Route path="reviews" element={<ReviewsPage />} />
            <Route path="campaigns" element={<CampaignsPage />} />
            <Route path="warehouses" element={<WarehousesPage />} />
            <Route path="inventory/batches" element={<BatchesPage />} />
            <Route path="sources" element={<SourcesPage />} />
            <Route path="imports" element={<ImportsPage />} />
            <Route path="runs" element={<RunsPage />} />
            <Route path="emails" element={<AdminOnly><EmailsPage /></AdminOnly>} />
            <Route path="users" element={<AdminOnly><UsersPage /></AdminOnly>} />
            <Route path="audit" element={<AdminOnly><AuditPage /></AdminOnly>} />
            <Route path="live-chat" element={<LiveChatPage />} />
            <Route path="admin/chatbot" element={<ChatbotAdminPage />} />
            <Route path="chatbot" element={<ChatbotAdminPage />} />
          </Route>

          {/* 2. Warehouse Manager Dedicated Portal Routes */}
          <Route path="/warehouse" element={<WarehouseManagerGuard />}>
            <Route index element={<Navigate to="/warehouse/overview" replace />} />
            <Route path="overview" element={<WarehouseOverviewPage />} />
            <Route path="live-chat" element={<LiveChatPage />} />
            <Route path="products" element={<WarehouseProductsPage />} />
            <Route path="orders" element={<WarehouseOrdersPage />} />
            <Route path="returns" element={<WarehouseReturnsPage />} />
            <Route path="imports" element={<WarehouseImportsPage />} />
            <Route path="batches" element={<WarehouseBatchesPage />} />
            <Route path="stock" element={<WarehouseStockPage />} />
            <Route path="inventory-check" element={<WarehouseAdjustmentsPage />} />
            <Route path="alerts" element={<WarehouseAlertsPage />} />
            <Route path="staff" element={<WarehouseStaffPage />} />
            <Route path="audit" element={<WarehouseAuditPage />} />
            <Route path="reviews" element={<WarehouseReviewsPage />} />
          </Route>

          {/* 3. Warehouse Staff Dedicated Portal Routes */}
          <Route path="/staff" element={<WarehouseStaffGuard />}>
            <Route index element={<Navigate to="/staff/today" replace />} />
            <Route path="today" element={<StaffTodayPage />} />
            <Route path="picking-packing" element={<StaffPickingPackingPage />} />
            <Route path="inventory-checks" element={<StaffInventoryChecksPage />} />
            <Route path="stock" element={<StaffStockPage />} />
            <Route path="history" element={<StaffHistoryPage />} />
            <Route path="returns" element={<StaffReturnsPage />} />
          </Route>

          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </Suspense>
    </ErrorBoundary>
  )
}
