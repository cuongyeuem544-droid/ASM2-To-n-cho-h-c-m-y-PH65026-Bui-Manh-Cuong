import { PRODUCTS_DATA } from "@/data/products";
import { Product } from "@/types";
import { ChatProductItem } from "./types";
import { sanitizeProduct, cleanMedicalText } from "./sanitizer";

/**
 * Loại bỏ dấu tiếng Việt để tìm kiếm không dấu / viết tắt
 */
export function removeVietnameseTones(str: string): string {
  if (!str) return "";
  let s = str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
  s = s.replace(/[đĐ]/g, (m) => (m === "đ" ? "d" : "D"));
  return s.toLowerCase().trim();
}

/**
 * Danh sách các từ dừng (stop-words) phổ biến trong tìm kiếm y tế không dùng để chấm điểm riêng lẻ
 */
const SEARCH_STOP_WORDS = new Set([
  "thuoc",
  "san",
  "pham",
  "vien",
  "hop",
  "goi",
  "chai",
  "lo",
  "tuyp",
  "la",
  "gi",
  "co",
  "ban",
  "mua",
  "tim",
  "cho",
  "toi",
  "minh",
  "em",
  "shop",
  "khong",
  "a",
  "va",
  "voi",
  "o",
  "duoc",
  "cai",
  "nay",
  "do",
]);

/**
 * Tìm kiếm sản phẩm thông minh trong danh mục thuốc H4CARE
 * Áp dụng lọc stop words và đối soát từ khóa an toàn
 */
export async function searchMedicines(
  query: string,
  limit: number = 4
): Promise<ChatProductItem[]> {
  const cleanQ = cleanMedicalText(query).trim();
  if (!cleanQ || cleanQ.length < 2) {
    return [];
  }

  const rawQ = cleanQ.toLowerCase();
  const normQ = removeVietnameseTones(cleanQ);

  // Lọc ra các từ khóa có nghĩa thực sự (loại bỏ từ dừng như "thuốc", "cho", "tôi")
  const allWords = normQ.split(/\s+/).filter((w) => w.length >= 1);
  const meaningfulKeywords = allWords.filter((w) => !SEARCH_STOP_WORDS.has(w) && w.length >= 2);

  // Nếu người dùng chỉ gõ toàn từ dừng (ví dụ: "thuốc", "thuốc có bán không"), không tìm bừa bãi
  if (meaningfulKeywords.length === 0 && SEARCH_STOP_WORDS.has(normQ)) {
    return [];
  }

  // 1. Thử lấy từ Backend API nếu đang hoạt động
  try {
    const apiBase = (process.env.NEXT_PUBLIC_API_URL || "").replace(/\/+$/, "");
    const res = await fetch(`${apiBase}/api/v1/store/products?search=${encodeURIComponent(cleanQ)}&limit=${limit}`, {
      next: { revalidate: 30 },
      signal: AbortSignal.timeout(1500),
    });
    if (res.ok) {
      const data = await res.json();
      if (Array.isArray(data.items) && data.items.length > 0) {
        return data.items.slice(0, limit).map((p: any) => sanitizeProduct(p));
      }
    }
  } catch {
    // Tự động chuyển sang danh mục thuốc cục bộ H4CARE
  }

  // 2. Tra cứu trên danh mục PRODUCTS_DATA
  const scoredProducts: Array<{ product: Product; score: number }> = [];

  for (const p of PRODUCTS_DATA) {
    let score = 0;
    const pName = cleanMedicalText(p.name).toLowerCase();
    const pNameNorm = removeVietnameseTones(pName);
    const pActive = cleanMedicalText(p.activeIngredient).toLowerCase();
    const pActiveNorm = removeVietnameseTones(pActive);
    const pInd = cleanMedicalText(p.indications).toLowerCase();
    const pIndNorm = removeVietnameseTones(pInd);
    const pBrand = cleanMedicalText(p.brand).toLowerCase();
    const pBrandNorm = removeVietnameseTones(pBrand);

    // 1. Khớp chính xác cả cụm từ (chỉ áp dụng khi cụm từ không phải là từ dừng đơn thuần)
    const hasExactPhraseMatch =
      !SEARCH_STOP_WORDS.has(normQ) &&
      (pNameNorm.includes(normQ) || pActiveNorm.includes(normQ) || pBrandNorm.includes(normQ));

    if (hasExactPhraseMatch) {
      if (pNameNorm.includes(normQ)) score += 60;
      if (pActiveNorm.includes(normQ)) score += 45;
      if (pBrandNorm.includes(normQ)) score += 30;
    }

    // 2. Khớp từng từ khóa có nghĩa (có ranh giới từ để không ăn xén substring)
    let matchedNameCount = 0;
    let matchedActiveCount = 0;
    let matchedBrandCount = 0;
    let matchedIndCount = 0;
    let matchedKeywordsCount = 0;

    for (const kw of meaningfulKeywords) {
      const wordRegex = new RegExp(`\\b${kw}\\b`, "i");
      let matchedThisKw = false;

      if (wordRegex.test(pNameNorm)) {
        score += 35;
        matchedThisKw = true;
        matchedNameCount++;
      }
      if (wordRegex.test(pActiveNorm)) {
        score += 30;
        matchedThisKw = true;
        matchedActiveCount++;
      }
      if (wordRegex.test(pBrandNorm)) {
        score += 20;
        matchedThisKw = true;
        matchedBrandCount++;
      }
      if (wordRegex.test(pIndNorm)) {
        score += 10;
        matchedThisKw = true;
        matchedIndCount++;
      }

      if (matchedThisKw) {
        matchedKeywordsCount++;
      }
    }

    const matchesNameOrActive = matchedNameCount > 0 || matchedActiveCount > 0;

    // Tiêu chuẩn khớp nghiêm ngặt bảo đảm độ chính xác Dược khoa:
    // - Khớp cụm từ chính xác -> Hợp lệ
    // - Khớp từ khóa rời rạc: Bắt buộc phải khớp Tên thuốc hoặc Hoạt chất chính, VÀ:
    //   + Với 1 từ: Đã khớp tên/hoạt chất
    //   + Với >= 2 từ: Phải khớp ít nhất 2 từ VÀ đạt độ phủ >= 60%
    let satisfiesCoverage = false;
    if (hasExactPhraseMatch) {
      satisfiesCoverage = true;
    } else if (matchesNameOrActive) {
      if (meaningfulKeywords.length === 1) {
        satisfiesCoverage = matchedKeywordsCount >= 1;
      } else {
        const coverageRatio = matchedKeywordsCount / meaningfulKeywords.length;
        satisfiesCoverage = matchedKeywordsCount >= 2 && coverageRatio >= 0.6;
      }
    }

    // Ưu tiên sản phẩm bán chạy / nổi bật nếu cùng điểm
    if (p.isBestSeller) score += 2;
    if (p.isFeatured) score += 1;

    // Ngưỡng điểm tối thiểu hợp lệ và phải thỏa mãn độ phủ từ khóa
    if (satisfiesCoverage && score >= 35) {
      scoredProducts.push({ product: p, score });
    }
  }

  // Sắp xếp theo điểm tương đồng giảm dần
  scoredProducts.sort((a, b) => b.score - a.score);

  return scoredProducts.slice(0, limit).map((sp) => sanitizeProduct(sp.product));
}

/**
 * Trích xuất tóm tắt thông tin sản phẩm để truyền vào ngữ cảnh AI Prompt
 */
export function formatProductsContext(items: ChatProductItem[]): string {
  if (items.length === 0) return "Không có dữ liệu sản phẩm tương ứng.";

  return items
    .map(
      (item, idx) => `
[Sản phẩm ${idx + 1}]
- Tên: ${item.name}
- Phân loại: ${item.isPrescription ? "Thuốc kê đơn (Rx - Yêu cầu đơn bác sĩ)" : "Thuốc không kê đơn (OTC) / TPCN"}
- Hoạt chất chính: ${item.activeIngredient || "Theo công bố nhà sản xuất"}
- Giá bán thực tế: ${item.salePrice ? item.salePrice.toLocaleString("vi-VN") : item.price.toLocaleString("vi-VN")} đ
- Tình trạng: ${item.stock > 0 ? "Còn hàng" : "Tạm hết hàng"}
- Link chi tiết: /product/${item.slug}
- Công dụng tóm tắt: ${item.shortDescription}
`
    )
    .join("\n");
}
