export type UserRole = 'ADMIN' | 'WAREHOUSE_MANAGER' | 'WAREHOUSE_STAFF' | 'CUSTOMER'

export interface User {
  id: number
  email: string
  phone?: string | null
  full_name: string
  role: UserRole
  loyalty_points?: number
  is_active: boolean
  warehouse_id?: number | null
  warehouse_name?: string | null
  must_change_password?: boolean
  password_changed_at?: string | null
  created_by_user_id?: number | null
  created_by_name?: string | null
  created_at?: string
  last_login_at?: string | null
}

export interface UserActivityLog {
  id: number
  action: string
  created_at?: string
  user_name?: string | null
  ip_address?: string | null
  details?: any
}

export type ConfidenceLabel = 'HIGH_OFFICIAL_MATCH' | 'REVIEW_REQUIRED' | 'INSUFFICIENT_EVIDENCE' | 'BLOCKED'

export interface Product {
  id: number
  canonical_name: string
  registration_number: string | null
  manufacturer: string | null
  image_url?: string | null
  description?: string | null
  usage_instructions?: string | null
  indications?: string | null
  contraindications?: string | null
  side_effects?: string | null
  storage_conditions?: string | null
  dosage_form?: string | null
  route?: string | null
  package_description?: string | null
  manufacturing_country?: string | null
  price?: number | null
  total_stock?: number
  near_expiry_count?: number
  active_ingredient?: string | null
  rx_otc_status: 'OTC' | 'PRESCRIPTION' | 'UNKNOWN'
  product_type?: string | null
  prescription_status?: string | null
  category_slug?: string | null
  regulatory_status: string
  overall_score: number
  confidence_label: ConfidenceLabel
  publish_status: string
  is_demo: boolean
  updated_at: string
}

export interface ProductPage {
  items: Product[]
  total: number
  page: number
  page_size: number
  pages: number
}

export interface Source {
  id: number
  code: string
  name: string
  source_type: string
  base_url: string | null
  authority_level: number
  authority_weight: number
  enabled: boolean
  robots_status: string
  crawl_frequency: string
  last_success_at: string | null
}

export interface Conflict {
  id: number
  product_id: number
  conflict_type: string
  severity: 'LOW' | 'MEDIUM' | 'HIGH' | 'CRITICAL'
  field_name: string
  value_a: string | null
  value_b: string | null
  description: string
  status: string
  created_at: string
}

export interface WarehouseLocationItem {
  id: number
  code: string
  name: string | null
  aisle: string | null
  shelf: string | null
  bin: string | null
}

export interface WarehouseItem {
  id: number
  code: string
  name: string
  address: string
  ward?: string | null
  district?: string | null
  province?: string | null
  lat?: number | null
  lng?: number | null
  is_active: boolean
  is_central: boolean
  phone?: string | null
  locations_count: number
  locations: WarehouseLocationItem[]
  total_on_hand: number
  total_available: number
  created_at?: string
}

export interface BatchStockBreakdown {
  warehouse_id: number
  warehouse_name: string
  warehouse_code: string
  location_code?: string | null
  quantity_on_hand: number
  quantity_reserved: number
  quantity_available: number
}

export interface InventoryBatchItem {
  id: number
  batch_number: string
  sku_id: number
  sku_code: string
  uom: string
  product_id?: number | null
  product_name: string
  registration_number?: string | null
  manufacture_date?: string | null
  expiry_date: string
  days_remaining: number
  risk_level: 'SAFE' | 'WARNING' | 'CRITICAL'
  risk_label: string
  status: 'ACTIVE' | 'QUARANTINED' | 'RECALLED' | 'EXPIRED'
  certificate_url?: string | null
  supplier_name: string
  initial_quantity: number
  total_on_hand: number
  total_available: number
  stocks: BatchStockBreakdown[]
}

export interface StockReceiptLineItem {
  id: number
  sku_id: number
  sku_code: string
  batch_number: string
  manufacture_date?: string | null
  expiry_date: string
  quantity: number
  purchase_unit_price: number
  line_total: number
}

export interface StockReceiptItemType {
  id: number
  receipt_code: string
  warehouse_id: number
  warehouse_name: string
  supplier_id: number
  supplier_name: string
  status: string
  total_amount: number
  received_date?: string | null
  note?: string | null
  items_count: number
  items: StockReceiptLineItem[]
  created_at?: string
}

export interface StockTransferLineItem {
  id: number
  batch_id: number
  batch_number: string
  sku_code: string
  quantity: number
  received_quantity: number
}

export interface StockTransferItemType {
  id: number
  transfer_code: string
  from_warehouse_id: number
  from_warehouse_name: string
  to_warehouse_id: number
  to_warehouse_name: string
  status: string
  note?: string | null
  items_count: number
  items: StockTransferLineItem[]
  created_at?: string
}

export interface StockMovementItem {
  id: number
  movement_code: string
  movement_type: string
  warehouse_id: number
  warehouse_name: string
  batch_id: number
  batch_number: string
  sku_code: string
  quantity: number
  balance_after: number
  reference_type?: string | null
  reference_id?: string | null
  note?: string | null
  created_at?: string
}

export interface SupplierItem {
  id: number
  code: string
  name: string
  tax_code?: string | null
  phone?: string | null
  email?: string | null
  address?: string | null
  gsp_license_number?: string | null
}

export interface WarehouseProductItem {
  product_id: number
  product_name: string
  registration_number: string
  product_type: string
  image_url: string | null
  sku_id: number
  sku_code: string
  uom: string
  unit_name: string
  total_on_hand: number
  total_available: number
  total_reserved: number
  batches_count: number
  earliest_expiry: string | null
  stock_status: 'IN_STOCK' | 'LOW_STOCK' | 'OUT_OF_STOCK' | 'NEAR_EXPIRY'
}

export interface WarehouseProductDetail {
  sku_id: number
  product_id: number
  general_info: {
    canonical_name: string
    registration_number: string
    active_ingredients: string
    dosage_form: string
    route_of_administration: string
    manufacturer: string
    country_of_origin: string
    package_description: string
    is_prescription: boolean
    regulatory_status: string
    primary_image_url: string | null
    description: string
    sku_code: string
    uom: string
    base_price: number
  }
  stock_levels: {
    total_on_hand: number
    total_available: number
    total_reserved: number
    total_quarantined: number
    min_stock: number
    max_stock: number
    reorder_point: number
  }
  batches: Array<{
    batch_id: number
    batch_number: string
    manufacture_date: string | null
    expiry_date: string | null
    quantity_on_hand: number
    quantity_available: number
    quantity_reserved: number
    location_name: string
    status: string
    supplier_name: string
    days_left: number
    is_near_expiry: boolean
    is_expired: boolean
  }>
  movements: Array<{
    id: number
    movement_code: string
    movement_type: string
    batch_number: string
    quantity: number
    balance_after: number
    reference_type: string
    reference_id: string
    note: string | null
    created_at: string | null
  }>
  related_orders: Array<{
    order_id: number
    order_code: string
    customer_name: string
    allocated_quantity: number
    batch_number: string
    order_status: string
    fulfillment_status: string
    created_at: string | null
  }>
}

export interface WarehouseImportPreview {
  import_id: number
  import_code: string
  filename: string
  total_rows: number
  valid_count: number
  warning_count: number
  invalid_count: number
  candidate_count: number
  can_commit: boolean
  preview_rows: Array<any>
  invalid_rows: Array<any>
  candidate_rows: Array<any>
}

export interface WarehouseImportHistoryItem {
  id: number
  import_code: string
  filename: string
  total_rows: number
  valid_rows: number
  invalid_rows: number
  candidate_rows: number
  status: string
  created_at: string | null
  committed_at: string | null
  imported_by_name: string
}

export interface WarehouseAlertItem {
  id: number
  alert_type: string
  title: string
  message: string
  severity: 'CRITICAL' | 'WARNING' | 'INFO'
  reference_type: string
  reference_id: string
  is_read: boolean
  created_at: string | null
}

export interface WarehouseNotificationItem {
  id: number
  warehouse_id: number
  recipient_user_id: number | null
  notification_type: string
  title: string
  message: string
  severity: 'INFO' | 'WARNING' | 'HIGH' | 'CRITICAL' | 'EXPIRED' | string
  entity_type: string | null
  entity_id: string | null
  action_url: string | null
  is_read: boolean
  read_at: string | null
  created_at: string | null
}
