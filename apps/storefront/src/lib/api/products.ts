import { Product, Category } from "@/types";
import { PRODUCTS_DATA } from "@/data/products";
import { CATEGORIES_DATA } from "@/data/mockData";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "";

export async function getStoreCategoriesTree(): Promise<Category[]> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/store/categories/tree`, {
      next: { revalidate: 60 },
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data) && data.length > 0) {
        return data;
      }
    }
  } catch (err) {
    console.warn("Backend API unavailable for categories tree, using local CATEGORIES_DATA:", err);
  }
  return CATEGORIES_DATA;
}

export async function getStoreProducts(params?: {
  category?: string;
  subCategory?: string;
  productType?: string;
  prescriptionStatus?: string;
  prescriptionType?: "all" | "otc" | "rx";
  search?: string;
  sort?: string;
  limit?: number;
  offset?: number;
}): Promise<{ items: Product[]; total: number }> {
  try {
    const query = new URLSearchParams();
    if (params?.category) query.set("category", params.category);
    if (params?.subCategory) query.set("subCategory", params.subCategory);
    if (params?.productType) query.set("product_type", params.productType);
    if (params?.prescriptionStatus) query.set("prescription_status", params.prescriptionStatus);
    if (params?.prescriptionType) query.set("prescriptionType", params.prescriptionType);
    if (params?.search) query.set("search", params.search);
    if (params?.sort) query.set("sort", params.sort);
    if (params?.limit) query.set("limit", String(params.limit));
    if (params?.offset) query.set("offset", String(params.offset));

    const res = await fetch(`${API_BASE}/api/v1/store/products?${query.toString()}`, {
      next: { revalidate: 60 },
    });

    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items) && data.items.length > 0) {
        return data;
      }
    }
  } catch (err) {
    console.warn("Backend API unavailable, using local product catalog:", err);
  }

  // Graceful fallback to static products
  let filtered = [...PRODUCTS_DATA];
  if (params?.category) {
    filtered = filtered.filter((p) => p.category === params.category);
  }
  if (params?.prescriptionType === "rx") {
    filtered = filtered.filter((p) => p.isPrescription);
  } else if (params?.prescriptionType === "otc") {
    filtered = filtered.filter((p) => !p.isPrescription);
  }
  if (params?.search) {
    const q = params.search.toLowerCase();
    filtered = filtered.filter(
      (p) =>
        p.name.toLowerCase().includes(q) ||
        p.brand.toLowerCase().includes(q) ||
        p.activeIngredient.toLowerCase().includes(q)
    );
  }

  return { items: filtered, total: filtered.length };
}

export async function getStoreProductBySlug(slug: string): Promise<Product | null> {
  try {
    const res = await fetch(`${API_BASE}/api/v1/store/products/${encodeURIComponent(slug)}`, {
      next: { revalidate: 60 },
    });
    if (res.ok) {
      return await res.json();
    }
  } catch (err) {
    console.warn("Backend API unavailable for product detail, using local product catalog:", err);
  }

  // Fallback to local catalog
  const found = PRODUCTS_DATA.find((p) => p.slug === slug || p.id === slug);
  return found || null;
}
