import { removeVietnameseTones } from "./product-search";
import { StandardIntent } from "./types";
import { extractActiveDrugFromHistory, hasDrugPronoun, trackSymptomContext } from "./context-tracker";
import { normalizeVietnameseSlang } from "./vietnamese-nlp";

export type UserIntent = StandardIntent;

export interface IntentClassificationResult {
  intent: StandardIntent;
  searchQuery?: string;
  drugQuery?: string;
  matchedKeywords: string[];
}

/**
 * Trích xuất từ khóa tìm kiếm thuốc thực tế bằng cách loại bỏ các từ phụ trợ tiếng Việt
 */
export function extractProductSearchQuery(rawMessage: string): string {
  const normalizedRaw = normalizeVietnameseSlang(rawMessage).normalized;
  let q = normalizedRaw.trim();

  // Loại bỏ các tiền tố câu hỏi thường gặp để lấy đúng tên thuốc / hoạt chất
  const stopPrefixes = [
    /^(tôi muốn mua|toi muon mua)\s+/i,
    /^(tôi cần mua|toi can mua)\s+/i,
    /^(h4care có|h4care co|bên mình có|ben minh co|shop có|shop co)\s+/i,
    /^(có bán|co ban|có thuốc|co thuoc|có|co)\s+/i,
    /^(mua|mua thuốc|mua thuoc)\s+/i,
    /^(tìm|tim|tìm kiếm|tim kiem|tìm thuốc|tim thuoc|cho tôi tìm|cho toi tim)\s+/i,
    /^(tra cứu|tra cuu|cho tôi hỏi về|cho toi hoi ve|hỏi về|hoi ve)\s+/i,
    /^(bán cho tôi|ban cho toi|lấy cho tôi|lay cho toi)\s+/i,
    /^(thuốc|thuoc)\s+/i,
    /^(cho tôi xem|cho toi xem)\s+/i,
  ];

  for (const regex of stopPrefixes) {
    q = q.replace(regex, "");
  }

  // Loại bỏ các hậu tố hỏi giá / tồn kho
  const stopSuffixes = [
    /\s+(bao nhiêu tiền|bao nhieu tien|giá bao nhiêu|gia bao nhieu|bao nhiêu|bao nhieu)[\s?]*$/i,
    /\s+(không shop|khong shop|không ạ|khong a|ko shop|không|khong|ko)[\s?]*$/i,
    /\s+(còn hàng không|con hang khong|còn không|con khong)[\s?]*$/i,
    /\s+(đang bán|dang ban)[\s?]*$/i,
    /[\s?]+$/,
  ];

  for (const regex of stopSuffixes) {
    q = q.replace(regex, "");
  }

  return q.trim();
}

/**
 * Danh sách từ khóa triệu chứng sức khỏe (Có phân tách cụm từ và từ đơn bằng boundary)
 */
const SYMPTOM_PHRASES = [
  "dau bung duoi",
  "dau bung",
  "dau dau",
  "dau nua dau",
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
  "dau lung",
  "dau rang",
  "dau co",
  "dau khop",
  "say tau xe",
];

const SINGLE_WORD_SYMPTOMS = ["sot", "ho", "ngua"];

/**
 * Nhận diện chính xác 10 Intent Router chuẩn của người dùng
 */
export function classifyUserIntent(
  rawMessage: string,
  history: Array<{ role: string; content: string }> = []
): IntentClassificationResult {
  const normalizedRaw = normalizeVietnameseSlang(rawMessage).normalized;
  const trimmed = normalizedRaw.trim();
  const norm = removeVietnameseTones(trimmed);

  // 1. DẤU HIỆU CẤP CỨU / RED FLAGS (P0 - EMERGENCY)
  const redFlagKeywords = [
    "ngat",
    "ngat xiu",
    "ngat di",
    "bat tinh",
    "hon me",
    "choang ngat",
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
    "sot cao co giat",
    "co giat",
    "non ra mau",
    "di ngoai ra mau",
    "phan den nhu ba ca phe",
    "meo mieng",
    "liet nua nguoi",
    "yeu tay chan",
    "noi ngong dot ngot",
    "dot quy",
    "soc phan ve",
    "bung cung nhu go",
    "dau du doi va ngat",
    "dau bung du doi va ngat",
    "dau bung va ngat",
  ];

  for (const kw of redFlagKeywords) {
    if (new RegExp(`\\b${kw}\\b`, "i").test(norm)) {
      return { intent: "EMERGENCY", matchedKeywords: [kw] };
    }
  }

  // 2. KẾT NỐI HỖ TRỢ NGƯỜI THẬT (HUMAN_SUPPORT)
  const humanSupportRegex = /\b(gap duoc si|gap nhan vien|gap nguoi that|duoc si that|nhan vien that|can gap duoc si|ho tro truc tiep|chuyen sang nguoi that|tu van truc tiep|cho toi gap duoc si|lien he duoc si|gui cau hoi cho nhan vien|toi can gap duoc si|toi muon gap duoc si)\b/i;
  if (humanSupportRegex.test(norm)) {
    return { intent: "HUMAN_SUPPORT", matchedKeywords: ["human_support"] };
  }

  // 3. THÔNG TIN DƯỢC LÝ & HOẠT CHẤT (DRUG_INFORMATION)
  // Ví dụ: "Paracetamol là thuốc gì?", "Thuốc đó có tác dụng phụ gì?", "Ibuprofen là gì?", "Còn Ibuprofen thì sao?", "Hai loại này có giống nhau không?"
  const isAskingWhatIsDrug = /\b(la thuoc gi|la gi|la thuoc nao|cong dung la gi|dung de lam gi|thanh phan la gi)\b/i.test(norm);
  const isAskingSideEffects = /\b(tac dung phu|co tac dung phu gi|uong vao bi gi|tac dung khong mong muon)\b/i.test(norm);
  const isAskingComparison = /\b(co giong nhau khong|khac nhau the nao|so sanh|uong chung duoc khong|uong cung luc duoc khong|con (.+?) thi sao)\b/i.test(norm);
  const isPronounDrugQuestion = hasDrugPronoun(norm) && (isAskingSideEffects || isAskingWhatIsDrug || norm.includes("tac dung") || norm.includes("dung nhu the nao"));

  const knownDrugNames = ["paracetamol", "panadol", "efferalgan", "ibuprofen", "vitamin c", "smecta", "gaviscon", "augmentin", "zinnat", "ventolin", "mobic", "amlor", "crestor", "medrol", "voltaren", "daflon"];
  const mentionsKnownDrug = knownDrugNames.some((d) => norm.includes(d));

  if (isAskingWhatIsDrug || isAskingSideEffects || isAskingComparison || (mentionsKnownDrug && (norm.includes("tac dung") || norm.includes("uong the nao") || norm.includes("co dung duoc khong"))) || isPronounDrugQuestion) {
    const activeDrug = extractActiveDrugFromHistory(history, trimmed);
    return {
      intent: "DRUG_INFORMATION",
      drugQuery: activeDrug || trimmed,
      matchedKeywords: ["drug_information"],
    };
  }

  // 4. KIỂM TRA ĐANG TRONG TIẾN TRÌNH HỎI BỆNH ĐA LƯỢT (MULTI-TURN SYMPTOM TRIAGE CONTINUATION)
  // Nếu câu hỏi hiện tại là tìm kiếm sản phẩm rõ ràng, hoặc hỏi thuốc cụ thể thì không gán nhầm sang triệu chứng!
  const isAskingProductExplicitly = /\b(vitamin|thuoc|co ban|co khong|h4care co|gia bao nhieu|bao nhieu tien|mua|tim|shop co)\b/i.test(norm);

  const lastAssistant = [...history].reverse().find((m) => m.role === "assistant");
  const isAssistantAskingSymptom = lastAssistant && (
    lastAssistant.content.includes("từ khi nào") ||
    lastAssistant.content.includes("bao lâu") ||
    lastAssistant.content.includes("ở vị trí nào") ||
    lastAssistant.content.includes("bên phải hay giữa") ||
    lastAssistant.content.includes("bên trái, bên phải hay giữa") ||
    lastAssistant.content.includes("có bị sốt") ||
    lastAssistant.content.includes("sốt, nôn hoặc đau tăng")
  );

  const isAnsweringSymptom = /\b(tu hom qua|hom qua|sang nay|moi bi|vua bi|2 ngay|3 ngay|ben phai|ben trai|o giua|giua bung|quanh ron|khong sot|co sot|co non|khong non|dau am i|chi dau am i|co dau|khong dau|co|khong)\b/i.test(norm);

  if (!isAskingProductExplicitly && isAssistantAskingSymptom && (isAnsweringSymptom || (norm.length < 35 && !norm.includes("vitamin") && !norm.includes("thuoc") && !norm.includes("mua")))) {
    return {
      intent: "HEALTH_SYMPTOM",
      matchedKeywords: ["symptom_continuation"],
    };
  }

  // Dự phòng an toàn: nếu lịch sử đã có triệu chứng chính và tin nhắn hiện tại là câu trả lời triệu chứng
  if (isAnsweringSymptom && !isAskingProductExplicitly && !/\b(mua|gia bao nhieu|bao nhieu tien|phi ship|don hang)\b/i.test(norm)) {
    const prevContext = trackSymptomContext(history, trimmed);
    if (prevContext.primarySymptom) {
      return {
        intent: "HEALTH_SYMPTOM",
        matchedKeywords: ["symptom_continuation_fallback"],
      };
    }
  }

  // 5. MÔ TẢ TRIỆU CHỨNG SỨC KHỎE BAN ĐẦU (HEALTH_SYMPTOM)
  const hasSymptomPattern = /\b(toi bi|em bi|be bi|con toi bi|nguoi nha bi|bi dau|dang bi|bi sot|bi ho|bi cum)\b/i.test(norm);
  const matchedPhrase = SYMPTOM_PHRASES.find((p) => norm.includes(p));
  const matchedSingle = SINGLE_WORD_SYMPTOMS.find((w) => new RegExp(`\\b${w}\\b`, "i").test(norm));
  const matchedSymptom = matchedPhrase || matchedSingle;

  if (hasSymptomPattern || matchedSymptom) {
    // Nếu có triệu chứng nhưng người dùng nói rõ "mua thuốc..." / "tìm thuốc..." thì ưu tiên PRODUCT_SEARCH
    if (/\b(mua thuoc|tim thuoc|co thuoc gi|thuoc gi|uong thuoc gi)\b/i.test(norm)) {
      const cleanQ = extractProductSearchQuery(trimmed);
      return {
        intent: "PRODUCT_SEARCH",
        searchQuery: cleanQ || matchedSymptom || trimmed,
        matchedKeywords: [matchedSymptom || "symptom_search"],
      };
    }

    return {
      intent: "HEALTH_SYMPTOM",
      matchedKeywords: [matchedSymptom || "symptom"],
    };
  }

  // 6. KIỂM TRA MÃ HTML THÔ KHÔNG AN TOÀN
  if (/^(?:u003[ce]|\\u003[ce]|<[a-z0-9\/]|<\/[a-z0-9]|<[a-z0-9])/i.test(trimmed) || trimmed.startsWith("<") || /u003c|\\u003c|<[^>]+>/i.test(trimmed)) {
    return { intent: "GENERAL_CHAT", matchedKeywords: ["html_raw"] };
  }

  // 7. CHÀO HỎI (GREETING)
  const greetingExactRegex = /^(hi|hello|hey|alo|halo|xin chao|chao ban|chao shop|chao duoc si|chao em|chao anh|chao chi|chao|good morning|good afternoon|good evening)(\s+(ban|shop|duoc si|em|anh|chi|bot|nha|oi|a|nhe))*[\s!.,?~]*$/i;
  if (greetingExactRegex.test(norm)) {
    return { intent: "GREETING", matchedKeywords: [norm] };
  }

  // 8. ĐỊNH DANH (GENERAL_CHAT / IDENTITY)
  const identityRegex = /\b(ban la ai|ban ten gi|ten ban la gi|ai tao ra ban|ban la con gi|ban la nguoi hay bot|who are you|ban la bot ha|gioi thieu ban|gioi thieu ve ban)\b/i;
  if (identityRegex.test(norm)) {
    return { intent: "GENERAL_CHAT", matchedKeywords: [norm] };
  }

  // 9. CẢM ƠN (GENERAL_CHAT / GRATITUDE)
  const gratitudeRegex = /\b(cam on|thank you|thanks|tks|cam on ban|cam on shop|cam on duoc si|da cam on|ok cam on)\b/i;
  if (gratitudeRegex.test(norm)) {
    return { intent: "GENERAL_CHAT", matchedKeywords: [norm] };
  }

  // 10. TÁN GẪU (GENERAL_CHAT / CHITCHAT)
  const chitchatExactRegex = /^(ok|oke|okie|vang|da|da vang|duoc roi|tam biet|bye|bye bye|hen gap lai|good|tuyet voi|hay qua)[\s!.,?~]*$/i;
  if (chitchatExactRegex.test(norm)) {
    return { intent: "GENERAL_CHAT", matchedKeywords: [norm] };
  }

  // 11. HƯỚNG DẪN MUA THUỐC KÊ ĐƠN (PRESCRIPTION_SUPPORT)
  const rxRegex = /\b(thuoc ke don|thuoc rx|huong dan mua thuoc ke don|can don thuoc khong|gui don thuoc|tai don thuoc|don thuoc bac si|toi co don thuoc|co don thuoc)\b/i;
  if (rxRegex.test(norm)) {
    return { intent: "PRESCRIPTION_SUPPORT", matchedKeywords: [norm] };
  }

  // 12. HỖ TRỢ ĐƠN HÀNG & CHÍNH SÁCH (ORDER_SUPPORT)
  const orderSupportRegex = /\b(don hang|trang thai don|kiem tra don|tra cuu don|pending la gi|shipping la gi|huy don hang|huy don|don hang cua toi|phi giao hang|phi ship|tien ship|phi van chuyen|thanh toan|chinh sach doi tra|doi tra thuoc|doi thuoc|hoan tien)\b/i;
  if (orderSupportRegex.test(norm)) {
    return { intent: "ORDER_SUPPORT", matchedKeywords: [norm] };
  }

  // 13. TÌM KIẾM SẢN PHẨM / THUỐC TRÊN HỆ THỐNG H4CARE (PRODUCT_SEARCH)
  const productTriggers = [
    "mua", "tim", "gia", "thuoc", "vitamin", "panadol", "efferalgan", "berocca",
    "smecta", "strepsils", "amoxicillin", "nexium", "gaviscon", "crestor",
    "amlor", "medrol", "paracetamol", "dau ca", "glucosamine", "khau trang",
    "nhiet ke", "loai nao dang ban", "san pham do", "ban", "co khong", "co vitamin c khong",
  ];

  const isExplicitSearch = productTriggers.some((t) => norm.includes(removeVietnameseTones(t)));
  const cleanQuery = extractProductSearchQuery(trimmed);

  // Xử lý đại từ: "loại nào đang bán", "cho tôi xem sản phẩm đó"
  let finalQuery = cleanQuery;
  if ((norm.includes("loai nao") || norm.includes("san pham do") || norm.includes("cho toi xem")) && !finalQuery) {
    const activeDrug = extractActiveDrugFromHistory(history, trimmed);
    if (activeDrug) finalQuery = activeDrug;
  }

  const hasSearchPrefix = cleanQuery !== trimmed;
  if (isExplicitSearch || hasSearchPrefix) {
    return {
      intent: "PRODUCT_SEARCH",
      searchQuery: finalQuery || trimmed,
      matchedKeywords: ["product_search"],
    };
  }

  // 14. Mặc định là câu hỏi thông thường
  return {
    intent: "GENERAL_CHAT",
    matchedKeywords: [],
  };
}
