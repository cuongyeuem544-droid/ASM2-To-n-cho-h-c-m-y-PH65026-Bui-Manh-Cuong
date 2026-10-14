import { removeVietnameseTones } from "./product-search";

export type UserIntent =
  | "GREETING"
  | "IDENTITY"
  | "GRATITUDE"
  | "CHITCHAT"
  | "SHIPPING_POLICY"
  | "PAYMENT_POLICY"
  | "RETURN_POLICY"
  | "ORDER_STATUS"
  | "ORDER_GUIDE"
  | "PRESCRIPTION_GUIDE"
  | "ACCOUNT_HELP"
  | "EMERGENCY_RED_FLAG"
  | "UNCLEAR_PRICING"
  | "SYMPTOM_CONSULTATION"
  | "PRODUCT_SEARCH"
  | "UNCLEAR_QUESTION";

export interface IntentClassificationResult {
  intent: UserIntent;
  searchQuery?: string;
  contextProductSlug?: string;
  matchedKeywords: string[];
}

/**
 * Trích xuất từ khóa tìm kiếm thuốc thực tế bằng cách loại bỏ các từ phụ trợ tiếng Việt
 */
export function extractProductSearchQuery(rawMessage: string): string {
  let q = rawMessage.trim();

  // Loại bỏ các mẫu câu hỏi thường gặp để lấy đúng tên thuốc / hoạt chất
  const stopPrefixes = [
    /^(tôi muốn mua|toi muon mua)\s+/i,
    /^(tôi cần mua|toi can mua)\s+/i,
    /^(mua|mua thuốc|mua thuoc)\s+/i,
    /^(tìm|tim|tìm kiếm|tim kiem|tìm thuốc|tim thuoc|cho tôi tìm|cho toi tim)\s+/i,
    /^(tra cứu|tra cuu|cho tôi hỏi về|cho toi hoi ve|hỏi về|hoi ve)\s+/i,
    /^(bên mình có bán|ben minh co ban|shop có bán|shop co ban|có bán|co ban)\s+/i,
    /^(bán cho tôi|ban cho toi|lấy cho tôi|lay cho toi)\s+/i,
    /^(có thuốc|co thuoc|có|co)\s+/i,
    /^(thuốc|thuoc)\s+/i,
  ];

  for (const regex of stopPrefixes) {
    q = q.replace(regex, "");
  }

  // Loại bỏ các hậu tố hỏi giá / tồn kho
  const stopSuffixes = [
    /\s+(bao nhiêu tiền|bao nhieu tien|giá bao nhiêu|gia bao nhieu|bao nhiêu|bao nhieu)$/i,
    /\s+(không shop|khong shop|không ạ|khong a|ko shop|không|khong)$/i,
    /\s+(còn hàng không|con hang khong|còn không|con khong)$/i,
  ];

  for (const regex of stopSuffixes) {
    q = q.replace(regex, "");
  }

  return q.trim();
}

/**
 * Nhận diện chính xác ý định (Intent) của người dùng
 */
export function classifyUserIntent(
  rawMessage: string,
  history: Array<{ role: string; content: string }> = []
): IntentClassificationResult {
  const trimmed = rawMessage.trim();
  const norm = removeVietnameseTones(trimmed);

  // 1. Kiểm tra Dấu hiệu nguy hiểm (Red Flags) trước tiên
  const redFlagKeywords = [
    "kho tho",
    "suy ho hap",
    "tho doc",
    "tho rit",
    "tim tai",
    "ngat tho",
    "dau that nguc",
    "dau tim",
    "ep nguc",
    "lan ra canh tay",
    "lan len ham",
    "sot cao co giat",
    "co giat",
    "non ra mau",
    "di ngoai ra mau",
    "phan den nhu ba ca phe",
    "phan ba ca phe",
    "chay mau da day",
    "meo mieng",
    "liet nua nguoi",
    "yeu tay chan",
    "noi ngong dot ngot",
    "dot quy",
    "tai bien",
    "soc phan ve",
    "phu moi",
    "phu mat",
  ];

  for (const kw of redFlagKeywords) {
    if (norm.includes(kw)) {
      return { intent: "EMERGENCY_RED_FLAG", matchedKeywords: [kw] };
    }
  }

  // 2. Kiểm tra câu lệnh test HTML thô không an toàn (ví dụ: u003ch2, <h2, <strong...)
  if (
    /^(?:u003[ce]|\\u003[ce]|<[a-z0-9\/]|<\/[a-z0-9]|<[a-z0-9])/i.test(trimmed) ||
    trimmed.startsWith("<") ||
    /u003c|\\u003c|<[^>]+>/i.test(trimmed)
  ) {
    return { intent: "UNCLEAR_QUESTION", matchedKeywords: ["html_raw"] };
  }

  // 3. Chào hỏi (Greeting)
  // Các câu ngắn: hi, hello, hey, xin chào, chào bạn, chào shop, alo, hi bot, chào bạn ơi...
  const greetingExactRegex = /^(hi|hello|hey|alo|halo|xin chao|chao ban|chao shop|chao duoc si|chao em|chao anh|chao chi|chao|good morning|good afternoon|good evening)(\s+(ban|shop|duoc si|em|anh|chi|bot|nha|oi|a|nhe))*[\s!.,?~]*$/i;
  if (greetingExactRegex.test(norm)) {
    return { intent: "GREETING", matchedKeywords: [norm] };
  }

  // 4. Định danh (Identity): bạn tên gì, bạn là ai...
  const identityRegex = /\b(ban la ai|ban ten gi|ten ban la gi|ai tao ra ban|ban la con gi|ban la nguoi hay bot|who are you|ban la bot ha|gioi thieu ban|gioi thieu ve ban)\b/i;
  if (identityRegex.test(norm)) {
    return { intent: "IDENTITY", matchedKeywords: [norm] };
  }

  // 5. Cảm ơn (Gratitude)
  const gratitudeRegex = /\b(cam on|thank you|thanks|tks|cam on ban|cam on shop|cam on duoc si|da cam on|ok cam on)\b/i;
  if (gratitudeRegex.test(norm)) {
    return { intent: "GRATITUDE", matchedKeywords: [norm] };
  }

  // 6. Tán gẫu / Giao tiếp ngắn (Chitchat)
  const chitchatExactRegex = /^(ok|oke|okie|vang|da|da vang|duoc roi|tam biet|bye|bye bye|hen gap lai|good|tuyet voi|hay qua)[\s!.,?~]*$/i;
  if (chitchatExactRegex.test(norm)) {
    return { intent: "CHITCHAT", matchedKeywords: [norm] };
  }

  // 7. Hỏi về Giá nhưng không rõ thuốc nào (Unclear Pricing)
  // Ví dụ: "thuốc này bao nhiêu tiền", "cái này bao nhiêu", "giá bao nhiêu", "bao nhiêu tiền"...
  const unclearPriceRegex = /^(thuoc nay|san pham nay|cai nay|cai do|mon nay|no)\s+(bao nhieu tien|gia bao nhieu|gia the nao|bao nhieu)[\s?]*$/i;
  const barePriceRegex = /^(gia bao nhieu|bao nhieu tien|bao nhieu|gia the nao)[\s?]*$/i;
  if (unclearPriceRegex.test(norm) || barePriceRegex.test(norm)) {
    return { intent: "UNCLEAR_PRICING", matchedKeywords: [norm] };
  }

  // 8. Chính sách Giao hàng & Phí ship (Shipping Policy)
  const shippingRegex = /\b(phi giao hang|phi ship|tien ship|phi van chuyen|giao hang bao lau|bao lau thi nhan duoc|thoi gian giao hang|co freeship khong|mien phi van chuyen|chinh sach giao hang)\b/i;
  if (shippingRegex.test(norm)) {
    return { intent: "SHIPPING_POLICY", matchedKeywords: [norm] };
  }

  // 9. Chính sách Thanh toán (Payment Policy)
  const paymentRegex = /\b(thanh toan|phuong thuc thanh toan|tra tien mat|thanh toan momo|vi momo|tra qua momo|cod la gi|co tra gop khong|chuyen khoan|quet ma vietqr)\b/i;
  if (paymentRegex.test(norm)) {
    return { intent: "PAYMENT_POLICY", matchedKeywords: [norm] };
  }

  // 10. Chính sách Đổi trả & Hoàn tiền (Return Policy)
  const returnRegex = /\b(chinh sach doi tra|doi tra thuoc|doi thuoc|tra thuoc|hoan tien|tra hang|doi hang|quy dinh doi tra)\b/i;
  if (returnRegex.test(norm)) {
    return { intent: "RETURN_POLICY", matchedKeywords: [norm] };
  }

  // 11. Hướng dẫn Mua thuốc kê đơn (Prescription Guide)
  const rxRegex = /\b(thuoc ke don|thuoc rx|huong dan mua thuoc ke don|can don thuoc khong|gui don thuoc|tai don thuoc|don thuoc bac si)\b/i;
  if (rxRegex.test(norm)) {
    return { intent: "PRESCRIPTION_GUIDE", matchedKeywords: [norm] };
  }

  // 12. Trạng thái & Quản lý đơn hàng (Order Status)
  const orderStatusRegex = /\b(trang thai don|kiem tra don|tra cuu don|pending la gi|shipping la gi|huy don hang|huy don|don hang cua toi)\b/i;
  if (orderStatusRegex.test(norm)) {
    return { intent: "ORDER_STATUS", matchedKeywords: [norm] };
  }

  // 13. Hỗ trợ Tài khoản / Đăng nhập (Account Help)
  const accountRegex = /\b(tai khoan|dang nhap|dang ky|quen mat khau|lay lai mat khau|doi mat khau)\b/i;
  if (accountRegex.test(norm)) {
    return { intent: "ACCOUNT_HELP", matchedKeywords: [norm] };
  }

  // 14. Tư vấn Triệu chứng sức khỏe (Symptom Consultation)
  // Các từ khóa triệu chứng: tôi đau đầu 2 ngày, tôi bị sốt, đau bụng, ho có đờm, tiêu chảy...
  const symptomKeywords = [
    "dau bung",
    "dau dau",
    "dau nua dau",
    "sot",
    "ho",
    "viem hong",
    "dau hong",
    "rat hong",
    "nghet mui",
    "so mui",
    "chay nuoc mui",
    "cam cum",
    "cam lanh",
    "viem xoang",
    "tieu chay",
    "di ngoai",
    "tao bon",
    "dau da day",
    "trao nguoc",
    "o nong",
    "chong mat",
    "buon non",
    "hoa mat",
    "mat ngu",
    "kho ngu",
    "di ung",
    "noi me day",
    "ngua",
    "dau lung",
    "dau rang",
    "dau co",
    "dau khop",
    "say tau xe",
  ];

  // Nếu người dùng nói "tôi bị...", "em bị...", "bị đau...", hoặc chứa từ khóa triệu chứng
  const hasSymptomPattern =
    /\b(toi bi|em bi|be bi|con toi bi|nguoi nha bi|bi dau|dang bi|bi sot|bi ho|bi cum)\b/i.test(norm);

  const matchedSymptom = symptomKeywords.find((s) => norm.includes(s));

  if (hasSymptomPattern || matchedSymptom) {
    // Nếu có từ khóa triệu chứng nhưng người dùng nói rõ "mua thuốc..." / "tìm thuốc..." thì vẫn xếp vào PRODUCT_SEARCH
    if (/\b(mua thuoc|tim thuoc|co thuoc gi|thuoc gi|uong thuoc gi)\b/i.test(norm)) {
      const cleanQ = extractProductSearchQuery(trimmed);
      return {
        intent: "PRODUCT_SEARCH",
        searchQuery: cleanQ || matchedSymptom || trimmed,
        matchedKeywords: [matchedSymptom || "symptom_search"],
      };
    }

    return {
      intent: "SYMPTOM_CONSULTATION",
      matchedKeywords: [matchedSymptom || "symptom"],
    };
  }

  // 15. Tìm kiếm Sản phẩm / Thuốc cụ thể (Product Search)
  // Ví dụ: vitamin c, panadol, efferalgan, berocca, zinnat, thuốc hạ sốt, tìm thuốc...
  const productSearchTriggers = [
    "mua",
    "tim",
    "gia",
    "thuoc",
    "vitamin",
    "panadol",
    "efferalgan",
    "berocca",
    "smecta",
    "strepsils",
    "amoxicillin",
    "nexium",
    "gaviscon",
    "crestor",
    "amlor",
    "medrol",
    "paracetamol",
    "dầu cá",
    "dau ca",
    "glucosamine",
    "khau trang",
    "nhiet ke",
  ];

  const cleanQuery = extractProductSearchQuery(trimmed);
  const isExplicitSearch = productSearchTriggers.some((t) => norm.includes(removeVietnameseTones(t)));

  if (isExplicitSearch || cleanQuery.length >= 2) {
    return {
      intent: "PRODUCT_SEARCH",
      searchQuery: cleanQuery,
      matchedKeywords: ["product_search"],
    };
  }

  // 16. Mặc định là câu hỏi không rõ nghĩa
  return {
    intent: "UNCLEAR_QUESTION",
    matchedKeywords: [],
  };
}
