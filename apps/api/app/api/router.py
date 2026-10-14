from fastapi import APIRouter
from app.api import (
    admin_classification,
    admin_exchanges,
    admin_refunds,
    admin_returns,
    addresses,
    auth,
    campaigns,
    crawler,
    dashboard,
    emails,
    exports,
    health,
    imports,
    inventory,
    locations,
    me,
    orders,
    payments,
    products,
    returns,
    reviews,
    sources,
    storefront,
    warehouse_orders_returns,
    warehouse_portal,
)


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(auth.users_router)
api_router.include_router(sources.router)
api_router.include_router(crawler.router)
api_router.include_router(products.router)
api_router.include_router(products.public_router)
api_router.include_router(storefront.router)
api_router.include_router(orders.store_order_router)
api_router.include_router(orders.admin_order_router)
api_router.include_router(payments.payments_router)
api_router.include_router(emails.emails_router)
api_router.include_router(reviews.store_review_router)
api_router.include_router(reviews.admin_review_router)
api_router.include_router(campaigns.store_campaign_router)
api_router.include_router(campaigns.admin_campaign_router)
api_router.include_router(addresses.addresses_router)
api_router.include_router(addresses.customer_address_router)
api_router.include_router(inventory.router)
api_router.include_router(inventory.warehouses_router)
api_router.include_router(inventory.admin_units_router)
api_router.include_router(imports.router)
api_router.include_router(exports.router)
api_router.include_router(locations.locations_router)
api_router.include_router(dashboard.router)
api_router.include_router(returns.router)
api_router.include_router(admin_returns.router)
api_router.include_router(admin_refunds.router)
api_router.include_router(admin_exchanges.router)
api_router.include_router(admin_classification.router)
api_router.include_router(me.me_router)
api_router.include_router(warehouse_portal.router)
api_router.include_router(warehouse_orders_returns.manager_router)
api_router.include_router(warehouse_orders_returns.staff_router)
api_router.include_router(warehouse_orders_returns.compat_portal_router)


