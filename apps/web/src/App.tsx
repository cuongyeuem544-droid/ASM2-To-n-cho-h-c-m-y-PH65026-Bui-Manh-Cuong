import { lazy, Suspense } from 'react'
import { Navigate, Outlet, Route, Routes } from 'react-router-dom'
import { Layout } from './components/Layout'
import { useAuth } from './services/auth'

const AuditPage = lazy(() => import('./pages/AuditPage').then(module => ({ default: module.AuditPage })))
const CandidatesPage = lazy(() => import('./pages/CandidatesPage').then(module => ({ default: module.CandidatesPage })))
const ConflictsPage = lazy(() => import('./pages/ConflictsPage').then(module => ({ default: module.ConflictsPage })))
const DashboardPage = lazy(() => import('./pages/DashboardPage').then(module => ({ default: module.DashboardPage })))
const ImportsPage = lazy(() => import('./pages/ImportsPage').then(module => ({ default: module.ImportsPage })))
const LoginPage = lazy(() => import('./pages/LoginPage').then(module => ({ default: module.LoginPage })))
const NotFoundPage = lazy(() => import('./pages/NotFoundPage').then(module => ({ default: module.NotFoundPage })))
const OrdersPage = lazy(() => import('./pages/OrdersPage').then(module => ({ default: module.OrdersPage })))
const PharmacyCrawlerPage = lazy(() => import('./pages/PharmacyCrawlerPage').then(module => ({ default: module.PharmacyCrawlerPage })))
const ProductDetailPage = lazy(() => import('./pages/ProductDetailPage').then(module => ({ default: module.ProductDetailPage })))
const ProductsPage = lazy(() => import('./pages/ProductsPage').then(module => ({ default: module.ProductsPage })))
const ReceiptsPage = lazy(() => import('./pages/ReceiptsPage').then(module => ({ default: module.ReceiptsPage })))
const RunsPage = lazy(() => import('./pages/RunsPage').then(module => ({ default: module.RunsPage })))
const SourcesPage = lazy(() => import('./pages/SourcesPage').then(module => ({ default: module.SourcesPage })))
const TransfersPage = lazy(() => import('./pages/TransfersPage').then(module => ({ default: module.TransfersPage })))
const UsersPage = lazy(() => import('./pages/UsersPage').then(module => ({ default: module.UsersPage })))
const WarehousesPage = lazy(() => import('./pages/WarehousesPage').then(module => ({ default: module.WarehousesPage })))
const BatchesPage = lazy(() => import('./pages/BatchesPage').then(module => ({ default: module.BatchesPage })))
const EmailsPage = lazy(() => import('./pages/EmailsPage').then(module => ({ default: module.EmailsPage })))
const ReviewsPage = lazy(() => import('./pages/ReviewsPage').then(module => ({ default: module.ReviewsPage })))
const CampaignsPage = lazy(() => import('./pages/CampaignsPage').then(module => ({ default: module.CampaignsPage })))
const CategoriesPage = lazy(() => import('./pages/CategoriesPage').then(module => ({ default: module.CategoriesPage })))
const ClassificationQueuePage = lazy(() => import('./pages/ClassificationQueuePage').then(module => ({ default: module.ClassificationQueuePage })))
const ReturnsPage = lazy(() => import('./pages/ReturnsPage').then(module => ({ default: module.ReturnsPage })))
const RefundsPage = lazy(() => import('./pages/RefundsPage').then(module => ({ default: module.RefundsPage })))
const ExchangesPage = lazy(() => import('./pages/ExchangesPage').then(module => ({ default: module.ExchangesPage })))

function ProtectedLayout() {
  const { user, loading } = useAuth()
  if (loading) return <div className="full-loading">Đang khởi tạo PharmaTrust…</div>
  if (!user) return <Navigate to="/login" replace />
  return <Layout><Outlet /></Layout>
}

function AdminOnly({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return user?.role === 'ADMIN' ? children : <Navigate to="/" replace />
}

export default function App() {
  return (
    <Suspense fallback={<div className="full-loading">Đang tải giao diện…</div>}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route element={<ProtectedLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="products/:id" element={<ProductDetailPage />} />
          <Route path="categories" element={<CategoriesPage />} />
          <Route path="classification/queue" element={<ClassificationQueuePage />} />
          <Route path="orders" element={<OrdersPage />} />
          <Route path="returns" element={<ReturnsPage />} />
          <Route path="refunds" element={<RefundsPage />} />
          <Route path="exchanges" element={<ExchangesPage />} />
          <Route path="reviews" element={<ReviewsPage />} />
          <Route path="campaigns" element={<CampaignsPage />} />
          <Route path="warehouses" element={<WarehousesPage />} />
          <Route path="inventory/batches" element={<BatchesPage />} />
          <Route path="inventory/receipts" element={<ReceiptsPage />} />
          <Route path="inventory/transfers" element={<TransfersPage />} />
          <Route path="pharmacy-crawler" element={<PharmacyCrawlerPage />} />
          <Route path="candidates" element={<CandidatesPage />} />
          <Route path="conflicts" element={<ConflictsPage />} />
          <Route path="sources" element={<SourcesPage />} />
          <Route path="imports" element={<ImportsPage />} />
          <Route path="runs" element={<RunsPage />} />
          <Route path="emails" element={<AdminOnly><EmailsPage /></AdminOnly>} />
          <Route path="users" element={<AdminOnly><UsersPage /></AdminOnly>} />
          <Route path="audit" element={<AdminOnly><AuditPage /></AdminOnly>} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Suspense>
  )
}
