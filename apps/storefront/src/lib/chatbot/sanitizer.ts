import { Product } from "@/types";
import { ChatProductItem } from "./types";

const HTML_ENTITY_MAP: Record<string, string> = {
  aacute: "á", Aacute: "Á",
  agrave: "à", Agrave: "À",
  atilde: "ã", Atilde: "Ã",
  acirc: "â", Acirc: "Â",
  eacute: "é", Eacute: "É",
  egrave: "è", Egrave: "È",
  ecirc: "ê", Ecirc: "Ê",
  iacute: "í", Iacute: "Í",
  igrave: "ì", Igrave: "Ì",
  oacute: "ó", Oacute: "Ó",
  ograve: "ò", Ograve: "Ò",
  otilde: "õ", Otilde: "Õ",
  ocirc: "ô", Ocirc: "Ô",
  uacute: "ú", Uacute: "Ú",
  ugrave: "ù", Ugrave: "Ù",
  yacute: "ý", Yacute: "Ý",
  deg: "°",
  ndash: "-",
  mdash: "—",
  hellip: "...",
  bull: "•",
  trade: "™",
  reg: "®",
  copy: "©",
  quot: '"',
  amp: "&",
  lt: "<",
  gt: ">",
  ge: "≥",
  le: "≤",
  nbsp: " ",
  beta: "beta",
  alpha: "alpha",
};

/**
 * Làm sạch và chuẩn hóa văn bản y tế / dược phẩm:
 * - Khử mã hóa Unicode escaping lỗi như u003c, u003e, u0026...
 * - Giải mã các HTML entities tiếng Việt (&ecirc;, &aacute;, &agrave;...)
 * - Tái ghép nối các âm tiết bị ngắt quãng do crawler entity (vi ê n -> viên, t á -> tá)
 * - Loại bỏ toàn bộ thẻ HTML thô (<h2\>, <strong\>, <p\>, <br\>...)
 * - Cắt bỏ rác dữ liệu cào (crawled attribute dumps, json metadata, seo title, leaflet dumps)
 * - Chuẩn hóa khoảng trắng và dấu câu
 */
export function cleanMedicalText(rawText: string | null | undefined): string {
  if (!rawText) return "";

  let text = String(rawText);

  // 1. Khử các chuỗi unicode escaping phổ biến từ JSON / crawler
  text = text
    .replace(/\\?u003c/gi, "<")
    .replace(/\\?u003e/gi, ">")
    .replace(/\\?u0022/gi, '"')
    .replace(/\\?u0027/gi, "'")
    .replace(/\\?u002f/gi, "/");

  // 2. Giải mã các ký tự tiếng Việt dạng HTML entities (với & hoặc u0026, có hoặc không có dấu chấm phẩy)
  text = text.replace(/(?:\\?u0026|&)(?:amp;)?([a-z0-9#]+);?/gi, (match, entity) => {
    const lower = entity.toLowerCase();
    if (HTML_ENTITY_MAP[entity]) return HTML_ENTITY_MAP[entity];
    if (HTML_ENTITY_MAP[lower]) return HTML_ENTITY_MAP[lower];
    if (lower.startsWith("#x")) {
      const code = parseInt(lower.slice(2), 16);
      if (!isNaN(code)) return String.fromCharCode(code);
    } else if (lower.startsWith("#")) {
      const code = parseInt(lower.slice(1), 10);
      if (!isNaN(code)) return String.fromCharCode(code);
    }
    return match;
  });

  // 3. Tái ghép nối các âm tiết tiếng Việt bị tách rời do crawler entity (ví dụ: vi ê n -> viên, t á -> tá, d ù ng -> dùng)
  text = text.replace(
    /([a-zA-ZđĐ]{1,2})\s+([áàảãạăắằẳẵặâấầẩẫậéèẻẽẹêếềểễệíìỉĩịóòỏõọôốồổỗộơớờởỡợúùủũụưứừửữựýỳỷỹỵ])(?:\s+([cmnptiy]|ch|ng|nh))?(?=\s|[.,;:!?\-]|$)/gi,
    (m, c1, v, c2) => c1 + v + (c2 || "")
  );

  // 4. Loại bỏ thẻ HTML và khoảng trắng thừa (bao gồm các biến thể < strong >)
  text = text.replace(/<[^>]+>/g, " ");

  // 5. Loại bỏ các đoạn rác do crawler cào nguyên khối JSON/HTML
  text = text.replace(/attributes\s+code\b[\s\S]*$/gi, "");
  text = text.replace(/filters\s+root\b[\s\S]*$/gi, "");
  text = text.replace(/thumbnail\s+image\s+url\b[\s\S]*$/gi, "");
  text = text.replace(/long\s+description\b[\s\S]*$/gi, "");
  text = text.replace(/seo\s+title\b[\s\S]*$/gi, "");
  text = text.replace(/registration\s+is\s+enable\b[\s\S]*$/gi, "");
  text = text.replace(/code\s+mo\s+ta\b[\s\S]*$/gi, "");

  // 6. Cắt bỏ các đoạn chỉ dẫn / quy cách / tá dược thừa trong hoạt chất hoặc mô tả
  text = text.replace(
    /\s*(?:t\s*[aá]\s*d[uư][oợ]c|tá\s+dược|ta\s+duoc|công\s+dụng|cong\s+dung|chỉ\s+định|chi\s+dinh|hướng\s+dẫn|huong\s+dan|liều\s+dùng|lieu\s+dung|đối\s+tượng|oi\s+tuong|thận\s+trọng|than\s+trong|chống\s+chỉ\s+định|chong\s+chi\s+dinh|tác\s+dụng\s+phụ|tac\s+dung\s+phu|bảo\s+quản|bao\s+quan|hạn\s+dùng|han\s+dung|quy\s+cách|quy\s+cach|xuất\s+xứ|xuat\s+xu|nhà\s+sản\s+xuất|nha\s+san\s+xuat|tiêu\s+chuẩn|tieu\s+chuan|thành\s+phần|thanh\s+phan|đặc\s+tính\s+dược\s+lực|đặc\s+tính\s+dược\s+động|pharmacity\s+cam\s+k[eê]t|h4care\s+cam\s+k[eê]t|n[eế]u\s+c[aà]n\s+th[eê]m\s+th[oô]ng\s+tin|[đd][oọ]c\s+k[yỹ]\s+h[uư][oớ]ng\s+d[aẫ]n|[đd][eể]\s+xa\s+t[aà]m\s+tay)\b[\s\S]*$/gi,
    ""
  );

  // 7. Gom khoảng trắng
  text = text.replace(/\s+/g, " ").trim();

  return text;
}

/**
 * Chuẩn hóa một Product thành ChatProductItem sạch sẽ, không chứa ký tự escape hay rác cào
 */
export function sanitizeProduct(p: Product): ChatProductItem {
  let cleanName = cleanMedicalText(p.name);
  let cleanActive = cleanMedicalText(p.activeIngredient);
  let cleanDesc = cleanMedicalText(p.shortDescription || p.description);

  // Giới hạn độ dài hoạt chất tối đa 120 ký tự để không tràn UI
  if (cleanActive.length > 120) {
    cleanActive = cleanActive.slice(0, 120).trim() + "...";
  }

  // Giới hạn mô tả tóm tắt tối đa 160 ký tự
  if (cleanDesc.length > 160) {
    cleanDesc = cleanDesc.slice(0, 160).trim() + "...";
  }

  return {
    id: p.id,
    name: cleanName || "Dược phẩm H4CARE",
    slug: p.slug || p.id,
    brand: cleanMedicalText(p.brand) || "H4CARE",
    categoryName: cleanMedicalText(p.categoryName) || "Dược phẩm",
    price: typeof p.price === "number" ? p.price : 0,
    salePrice: typeof p.salePrice === "number" ? p.salePrice : null,
    image: p.images && p.images.length > 0 ? p.images[0] : "/images/placeholder-medicine.svg",
    activeIngredient: cleanActive,
    dosageForm: cleanMedicalText(p.dosageForm) || "Viên nén",
    stock: typeof p.stock === "number" ? p.stock : 0,
    isPrescription: !!p.isPrescription,
    shortDescription: cleanDesc || "Sản phẩm chăm sóc sức khỏe chính hãng tại H4CARE.",
  };
}
