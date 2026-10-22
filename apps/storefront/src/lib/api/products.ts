import { Product, Category } from "@/types";
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

export interface StoreProductsResponse {
  items: Product[];
  total: number;
  page?: number;
  pageSize?: number;
  totalPages?: number;
  availableBrands?: string[];
  availableOrigins?: string[];
  availableDosageForms?: string[];
}

export interface GetStoreProductsParams {
  category?: string;
  subCategory?: string;
  productType?: string;
  prescriptionStatus?: string;
  prescriptionType?: "all" | "otc" | "rx";
  search?: string;
  sort?: string;
  limit?: number;
  offset?: number;
  page?: number;
  pageSize?: number;
  brand?: string | string[];
  origin?: string | string[];
  dosageForm?: string | string[];
  priceRange?: string;
  minPrice?: number;
  maxPrice?: number;
}

export async function getStoreProducts(params?: GetStoreProductsParams): Promise<StoreProductsResponse> {
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
    if (params?.page) query.set("page", String(params.page));
    if (params?.pageSize) query.set("pageSize", String(params.pageSize));
    if (params?.priceRange) query.set("priceRange", params.priceRange);
    if (params?.minPrice !== undefined) query.set("minPrice", String(params.minPrice));
    if (params?.maxPrice !== undefined) query.set("maxPrice", String(params.maxPrice));

    if (params?.brand) {
      const brands = Array.isArray(params.brand) ? params.brand.join(",") : params.brand;
      if (brands) query.set("brand", brands);
    }
    if (params?.origin) {
      const origins = Array.isArray(params.origin) ? params.origin.join(",") : params.origin;
      if (origins) query.set("origin", origins);
    }
    if (params?.dosageForm) {
      const dosageForms = Array.isArray(params.dosageForm) ? params.dosageForm.join(",") : params.dosageForm;
      if (dosageForms) query.set("dosageForm", dosageForms);
    }

    const res = await fetch(`${API_BASE}/api/v1/store/products?${query.toString()}`, {
      next: { revalidate: 60 },
    });

    if (res.ok) {
      const data = await res.json();
      if (data && Array.isArray(data.items)) {
        return {
          items: data.items,
          total: typeof data.total === "number" ? data.total : data.items.length,
          page: data.page,
          pageSize: data.pageSize,
          totalPages: data.totalPages,
          availableBrands: data.availableBrands || [],
          availableOrigins: data.availableOrigins || [],
          availableDosageForms: data.availableDosageForms || [],
        };
      }
    }
  } catch (err) {
    console.warn("Backend API unavailable for getStoreProducts:", err);
  }

  return {
    items: [],
    total: 0,
    availableBrands: [],
    availableOrigins: [],
    availableDosageForms: [],
  };
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
    console.warn("Backend API unavailable for product detail:", err);
  }
  return null;
}
