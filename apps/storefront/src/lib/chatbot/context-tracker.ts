import { ConversationContext, ExtractedMemory, SymptomContext } from "./types";
import { removeVietnameseTones } from "./product-search";
import {
  normalizeVietnameseSlang,
  extractUserAge,
  isAgeQuery,
  detectUserMood,
  detectSymptomEscalation,
  resolveAnaphoricDrugQuery,
} from "./vietnamese-nlp";

const COMMON_DRUGS_LOOKUP = [
  { name: "Paracetamol", aliases: ["paracetamol", "panadol", "efferalgan", "hapacol", "acetaminophen"] },
  { name: "Ibuprofen", aliases: ["ibuprofen", "advil", "motrin", "gofen"] },
  { name: "Vitamin C", aliases: ["vitamin c", "acid ascorbic", "ascorbic acid", "berocca", "strepsils orange with vitamin c"] },
  { name: "Smecta", aliases: ["smecta", "diosmectite", "diosmectit"] },
  { name: "Gaviscon", aliases: ["gaviscon", "natri alginate", "alginat"] },
  { name: "Augmentin", aliases: ["augmentin", "amoxicillin", "clavulanic"] },
  { name: "Zinnat", aliases: ["zinnat", "cefuroxim", "cefuroxime"] },
  { name: "Ventolin", aliases: ["ventolin", "salbutamol"] },
  { name: "Mobic", aliases: ["mobic", "meloxicam"] },
  { name: "Amlor", aliases: ["amlor", "amlodipin", "amlodipine"] },
  { name: "Crestor", aliases: ["crestor", "rosuvastatin"] },
  { name: "Medrol", aliases: ["medrol", "methylprednisolon"] },
  { name: "Voltaren", aliases: ["voltaren", "diclofenac"] },
  { name: "Duphalac", aliases: ["duphalac", "lactulose"] },
  { name: "Phosphalugel", aliases: ["phosphalugel", "thuoc chu p", "chu p"] },
  { name: "Daflon", aliases: ["daflon", "diosmin", "hesperidin"] },
];

const ANAPHORIC_PRONOUNS_REGEX = /\b(thuoc do|thuoc nay|loai do|loai nay|loai vua noi|thuoc vua roi|san pham do|san pham nay|no)\b/i;

/**
 * Trích xuất thực thể thuốc đang được thảo luận (Active Drug Entity) từ hội thoại
 */
export function extractActiveDrugFromHistory(
  history: Array<{ role: string; content: string }>,
  currentMessage: string
): string | undefined {
  const normCurrent = removeVietnameseTones(currentMessage);

  // 1. Kiểm tra trực tiếp trong tin nhắn hiện tại
  for (const drug of COMMON_DRUGS_LOOKUP) {
    for (const alias of drug.aliases) {
      if (new RegExp(`\\b${alias}\\b`, "i").test(normCurrent)) {
        return drug.name;
      }
    }
  }

  // 2. Nếu người dùng dùng đại từ thay thế ("thuốc đó", "loại này", "nó"...), quét ngược lịch sử
  const hasPronoun = ANAPHORIC_PRONOUNS_REGEX.test(normCurrent);

  // Quét từ tin nhắn gần nhất trở về trước
  for (let i = history.length - 1; i >= 0; i--) {
    const item = history[i];
    const normContent = removeVietnameseTones(item.content);

    for (const drug of COMMON_DRUGS_LOOKUP) {
      for (const alias of drug.aliases) {
        if (new RegExp(`\\b${alias}\\b`, "i").test(normContent)) {
          return drug.name;
        }
      }
    }
  }

  return undefined;
}

/**
 * Kiểm tra xem tin nhắn hiện tại có chứa đại từ thay thế hướng về thuốc trước đó không
 */
export function hasDrugPronoun(message: string): boolean {
  const norm = removeVietnameseTones(message);
  return ANAPHORIC_PRONOUNS_REGEX.test(norm);
}

/**
 * Phân tích và xây dựng trạng thái triệu chứng (Symptom Context Tracker) qua các lượt hội thoại
 */
export function trackSymptomContext(
  history: Array<{ role: string; content: string }>,
  currentMessage: string
): SymptomContext {
  const normCurrent = removeVietnameseTones(currentMessage);

  // Gom toàn bộ lịch sử người dùng và tin nhắn hiện tại
  const allUserTexts = [
    ...history.filter((m) => m.role === "user").map((m) => m.content),
    currentMessage,
  ];
  const combinedUserNorm = allUserTexts.map(removeVietnameseTones).join(" | ");

  const ctx: SymptomContext = {
    step: 1,
    accompanying: [],
  };

  // 1. Xác định Triệu chứng chính
  if (combinedUserNorm.includes("dau bung duoi") || combinedUserNorm.includes("bung duoi") || (combinedUserNorm.includes("dau") && combinedUserNorm.includes("bung duoi"))) {
    ctx.primarySymptom = "đau bụng dưới";
  } else if (combinedUserNorm.includes("dau bung") || (combinedUserNorm.includes("dau") && combinedUserNorm.includes("bung")) || combinedUserNorm.includes("da day")) {
    ctx.primarySymptom = "đau bụng";
  } else if (combinedUserNorm.includes("dau dau")) {
    ctx.primarySymptom = "đau đầu";
  } else if (/\bsot\b/i.test(combinedUserNorm)) {
    ctx.primarySymptom = "sốt";
  } else if (/\b(viem hong|dau hong|rat hong)\b/i.test(combinedUserNorm)) {
    ctx.primarySymptom = "đau họng";
  } else if (/\bho\b/i.test(combinedUserNorm)) {
    ctx.primarySymptom = "ho";
  } else if (combinedUserNorm.includes("tieu chay") || combinedUserNorm.includes("di ngoai")) {
    ctx.primarySymptom = "tiêu chảy";
  }

  // 2. Tính chất / Mức độ đau
  if (combinedUserNorm.includes("am i")) {
    ctx.severity = "âm ỉ";
  } else if (combinedUserNorm.includes("du doi") || combinedUserNorm.includes("quan tung con")) {
    ctx.severity = "dữ dội / quặn từng cơn";
  }

  // 3. Thời gian xuất hiện (Duration)
  const durationPatterns = [
    { pattern: /\b(tu hom qua|hom qua)\b/i, value: "từ hôm qua" },
    { pattern: /\b(sang nay|tu sang nay)\b/i, value: "từ sáng nay" },
    { pattern: /\b(hom nay|moi bi|vua bi)\b/i, value: "mới bị hôm nay" },
    { pattern: /\b(1 ngay|mot ngay|duoc 1 ngay)\b/i, value: "1 ngày" },
    { pattern: /\b(2 ngay|hai ngay|2-3 ngay|duoc 2 ngay)\b/i, value: "2 ngày" },
    { pattern: /\b(3 ngay|ba ngay)\b/i, value: "3 ngày" },
    { pattern: /\b(vai ngay|may ngay nay)\b/i, value: "vài ngày nay" },
    { pattern: /\b(1 tuan|mot tuan|nhieu tuan)\b/i, value: "khoảng 1 tuần" },
  ];

  for (const dp of durationPatterns) {
    if (dp.pattern.test(combinedUserNorm)) {
      ctx.duration = dp.value;
      break;
    }
  }

  // 4. Vị trí cụ thể (Location)
  if (/\b(ben phai|lech phai|ho chau phai|ha vi phai)\b/i.test(combinedUserNorm)) {
    ctx.location = "bên phải";
  } else if (/\b(ben trai|lech trai)\b/i.test(combinedUserNorm)) {
    ctx.location = "bên trái";
  } else if (/\b(o giua|chinh giua|quanh ron|vung ron)\b/i.test(combinedUserNorm)) {
    ctx.location = "ở giữa bụng";
  } else if (/\b(vung tren ron|thuong vi)\b/i.test(combinedUserNorm)) {
    ctx.location = "vùng trên rốn (thượng vị)";
  }

  const accompanying: string[] = [];

  // 5. Triệu chứng kèm theo (Accompanying)
  if (/\b(sot|nhiet do cao)\b/i.test(combinedUserNorm)) accompanying.push("sốt");
  if (/\b(non|buon non|oi)\b/i.test(combinedUserNorm)) accompanying.push("nôn/buồn nôn");
  if (/\b(ngat|ngat xiu|bat tinh)\b/i.test(combinedUserNorm)) accompanying.push("ngất xỉu");
  if (/\b(dau tang khi di lai|di lai dau|nhac chan dau)\b/i.test(combinedUserNorm)) accompanying.push("đau tăng khi vận động");
  if (/\b(chong mat|hoa mat)\b/i.test(combinedUserNorm)) accompanying.push("chóng mặt");
  const hasEscalated = detectSymptomEscalation(combinedUserNorm);
  if (hasEscalated) accompanying.push("đau tăng nặng dần");

  ctx.accompanying = accompanying;

  // 6. Kiểm tra Dấu hiệu nguy hiểm (Red Flag)
  if (accompanying.includes("ngất xỉu")) {
    ctx.hasRedFlag = true;
    ctx.redFlagReason = "Cơn đau kèm ngất xỉu / mất ý thức là dấu hiệu cấp cứu tối khẩn cấp (P0).";
  } else if (
    ctx.primarySymptom?.includes("bụng") &&
    ctx.location === "bên phải" &&
    (accompanying.includes("sốt") ||
      accompanying.includes("nôn/buồn nôn") ||
      accompanying.includes("đau tăng khi vận động") ||
      accompanying.includes("đau tăng nặng dần") ||
      hasEscalated)
  ) {
    ctx.hasRedFlag = true;
    ctx.redFlagReason = "Đau hố chậu phải kèm triệu chứng tăng nặng hoặc sốt/nôn là dấu hiệu chỉ điểm kinh điển của Viêm ruột thừa cấp cần can thiệp ngoại khoa khẩn cấp.";
  }

  // 7. Xác định Bước (Step) hiện tại trong quy trình hỏi bệnh
  if (ctx.hasRedFlag) {
    ctx.step = 4; // Cảnh báo khẩn cấp ngay
  } else if (!ctx.duration) {
    ctx.step = 1; // Cần hỏi thời gian
  } else if (!ctx.location && (ctx.primarySymptom?.includes("bụng") || ctx.primarySymptom?.includes("đầu"))) {
    ctx.step = 2; // Cần hỏi vị trí
  } else if (accompanying.length === 0) {
    ctx.step = 3; // Cần hỏi triệu chứng cảnh báo kèm theo
  } else {
    ctx.step = 4; // Đã đủ thông tin tư vấn
  }

  return ctx;
}

/**
 * Kiểm tra xem tin nhắn có đang nhắc đến bên thứ 3 (người khác) hay không
 * Ví dụ: "Mẹ tôi tên là Lan", "Bé nhà tôi tên Bống", "Bác sĩ Hùng..."
 * Tuyệt đối KHÔNG gán tên bên thứ 3 vào userName của khách hàng!
 */
export function isThirdPartyReference(rawMessage: string): boolean {
  const norm = removeVietnameseTones(rawMessage);
  const thirdPartyRegex =
    /\b(me toi|bo toi|ba toi|ma toi|con toi|con cua toi|con gai toi|con trai toi|be nha toi|be nha minh|chau nha toi|chau nha minh|chau toi|vo toi|chong toi|ban toi|nguoi yeu|anh trai|em trai|em gai|chi gai|ong toi|ba noi|ba ngoai|ong noi|ong ngoai|bac si|duoc si|dong nghiep|hang xom)\b/i;
  return thirdPartyRegex.test(norm);
}

/**
 * Kiểm tra xem người dùng có đang hỏi/truy vấn tên của mình không
 * Ví dụ: "Tên tôi là gì?", "Tôi tên gì?", "Bạn nhớ tên tôi không?", "Bạn có nhớ tên tôi không?"
 */
export function isNameQuery(rawMessage: string): boolean {
  const norm = removeVietnameseTones(rawMessage);
  return (
    /\b(ten toi la gi|toi ten gi|toi ten la gi|ten minh la gi|ban biet toi ten gi khong|ban co nho ten toi khong|ban nho ten toi khong|ban nho ten toi ko|nho ten toi khong|nho ten toi ko|co nho ten toi khong|toi ten la gi nhi|toi ten gi nhi|htrc.*ns ten j|ns ten j|minh ten j|ten mk la gi|mk ten gi|do ban.*ten gi|do b.*ten gi|nho ten mk ko|nho ten toi ko)\b/i.test(
      norm
    ) || /^(ten toi la gi|toi ten gi|ten toi|ten minh|ten mk)[\s?]*$/i.test(norm)
  );
}

/**
 * Trích xuất tên của chính người dùng một cách linh hoạt, tự nhiên
 * Hỗ trợ:
 * - "Tôi tên là Cường"
 * - "Tôi tên Hùng"
 * - "Mình tên Hoàn"
 * - "Gọi tôi là Đức Anh"
 * - "Từ giờ gọi tôi là Hùng"
 * - "Giờ tôi lại thành tên Hùng"
 * - "Không, tên tôi là Hoàn cơ"
 * - "Không, tôi tên Hoàn cơ"
 * - "Bạn cứ gọi mình là An nhé"
 * - "toi ten hung", "gio goi toi la hoan", "m ten hung", "mk ten hoan"
 */
export function parseUserSelfName(rawMessage: string): string | null {
  // 1. Nếu là câu hỏi truy vấn tên -> không phải câu đặt tên
  if (isNameQuery(rawMessage)) {
    return null;
  }

  // 2. Nếu nhắc đến bên thứ 3 (mẹ tôi, bé nhà tôi, bác sĩ...) -> không lấy làm tên mình
  if (isThirdPartyReference(rawMessage)) {
    return null;
  }

  // 3. Chuẩn bị chuỗi xử lý
  let cleaned = rawMessage.trim();

  // Bỏ tiền tố phủ định / phản bác nếu có: "Không, ", "Không phải, ", "K, "
  cleaned = cleaned.replace(/^(?:không|khong|không phải|khong phai|k|ko|hông)\s*[,.:;!-]?\s*/i, "");

  // Bỏ tiền tố đại từ xưng hô với bot: "Bạn ", "Shop ", "Bot ", "Ad "
  cleaned = cleaned.replace(/^(?:bạn|ban|shop|bot|ad)\s+/i, "");

  // Bỏ tiền tố thời gian / đổi tên ở đầu câu: "Từ giờ ", "Từ nay ", "Giờ ", "Bây giờ "
  cleaned = cleaned.replace(/^(?:từ giờ|tu gio|từ nay|tu nay|giờ|gio|bây giờ|bay gio)\s+/i, "");

  // Danh sách các mẫu nhận diện tên người dùng linh hoạt
  const namePatterns: RegExp[] = [
    // Mẫu đổi tên: "lại thành tên Hùng", "đổi tên thành Hùng", "thành tên Hùng"
    /(?:lại thành tên|lai thanh ten|lại là tên|lai la ten|đổi tên thành|doi ten thanh|đổi thành tên|doi thanh ten|thành tên|thanh ten)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})/i,

    // Mẫu yêu cầu cách gọi: "cứ gọi tôi là An", "gọi mình là An", "gọi tôi là An", "cứ gọi em là An"
    /(?:cứ gọi tôi là|cu goi toi la|cứ gọi mình là|cu goi minh la|cứ gọi em là|cu goi em la|gọi tôi là|goi toi la|gọi mình là|goi minh la|gọi em là|goi em la|gọi là|goi la)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})/i,

    // Mẫu giới thiệu tự nhiên: "tôi tên là", "tôi tên", "mình tên là", "mình tên", "m tên", "mk tên", "em tên", "anh tên"
    /(?:tôi tên là|toi ten la|tôi tên|toi ten|tên tôi là|ten toi la|tên tôi|ten toi|mình tên là|minh ten la|mình tên|minh ten|tên mình là|ten minh la|tên mình|ten minh|em tên là|em ten la|em tên|em ten|tên em là|ten em la|anh tên là|anh ten la|anh tên|anh ten|chị tên là|chi ten la|chị tên|chi ten|m tên là|m ten la|m tên|m ten|mk tên là|mk ten la|mk tên|mk ten)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,40})/i,

    // Mẫu đại từ trực tiếp ở đầu câu: "Tôi là Hùng", "Mình là Lan", "Em là Mai"
    /^(?:tôi là|toi la|mình là|minh la|em là|em la|anh là|anh la|chị là|chi la)\s+([A-ZÀ-Ỹa-zà-ỹ\s]{2,30})$/i,
  ];

  for (const regex of namePatterns) {
    const match = cleaned.match(regex);
    if (match && match[1]) {
      let extracted = match[1].trim();

      // Cắt bớt phần sau dấu phẩy / dấu chấm nếu có (ví dụ: "Lan, 25 tuổi" -> "Lan")
      extracted = extracted.split(/[,.;!\n]/)[0].trim();

      // Cắt bỏ các hậu tố khẩu ngữ tiếng Việt: cơ, nhé, nha, ạ, đi, thôi, ơi, nè, đây, đó...
      extracted = extracted
        .replace(
          /\s+(cơ|co|nhé|nhe|nha|ạ|a|nè|ne|đây|day|đó|do|ơi|oi|đi|di|thôi|thoi|nhé shop|nha shop|ạ shop|nha bot|nhé bot|nhé bạn|nha bạn)$/i,
          ""
        )
        .trim();

      if (extracted.length < 2) continue;

      const normExtracted = removeVietnameseTones(extracted);

      // Loại bỏ các từ cấm / từ nghi vấn / từ chỉ thuốc / vai trò hệ thống
      const bannedWords = [
        "la ai",
        "la gi",
        "bot",
        "duoc si",
        "nhan vien",
        "bac si",
        "thuoc",
        "mua",
        "ban",
        "gi",
        "ai",
        "sot",
        "dau",
        "cam on",
        "chao",
        "alo",
        "suy nghi",
        "tu van",
      ];

      const isBanned = bannedWords.some((w) => new RegExp(`\\b${w}\\b`, "i").test(normExtracted));
      if (isBanned) continue;

      // Chuẩn hóa viết hoa chữ cái đầu mỗi từ
      const formattedName = extracted
        .split(/\s+/)
        .map((w) => w.charAt(0).toUpperCase() + w.slice(1).toLowerCase())
        .join(" ");

      return formattedName;
    }
  }

  return null;
}

/**
 * Nhận diện hành động xử lý tên (giới thiệu lần đầu vs. cập nhật / đổi tên)
 */
export function detectNameAction(
  rawMessage: string,
  prevMemory?: ExtractedMemory
): { hasName: boolean; name?: string; isRename?: boolean } {
  const extractedName = parseUserSelfName(rawMessage);
  if (!extractedName) {
    return { hasName: false };
  }

  const norm = removeVietnameseTones(rawMessage);
  const hasRenameKeyword = /\b(gio|tu gio|tu nay|lai thanh|lai la|doi ten|thanh ten|khong|co|nhung|thay vi)\b/i.test(
    norm
  );
  const hadPreviousName = Boolean(
    prevMemory?.userName && prevMemory.userName.toLowerCase() !== extractedName.toLowerCase()
  );

  const isRename = hadPreviousName || hasRenameKeyword;

  return {
    hasName: true,
    name: extractedName,
    isRename,
  };
}

/**
 * Nhận diện hành động cung cấp hoặc sửa tuổi
 */
export function detectAgeAction(
  rawMessage: string,
  prevMemory?: ExtractedMemory
): { hasAge: boolean; age?: number; isCorrection?: boolean; replyText?: string } {
  if (isAgeQuery(rawMessage)) {
    return { hasAge: false };
  }

  const ageRes = extractUserAge(rawMessage);
  if (!ageRes.hasAge || !ageRes.age) {
    return { hasAge: false };
  }

  const prevAge = prevMemory?.age ? parseInt(prevMemory.age, 10) : undefined;
  const isCorrection = ageRes.isCorrection || (prevAge !== undefined && prevAge !== ageRes.age);

  let replyText = `Mình ghi nhận bạn ${ageRes.age} tuổi nhé.`;
  if (isCorrection) {
    replyText = `À, vậy mình cập nhật lại là bạn ${ageRes.age} tuổi nhé.`;
  }

  return {
    hasAge: true,
    age: ageRes.age,
    isCorrection,
    replyText,
  };
}

/**
 * Xây dựng tóm tắt ngắn gọn trạng thái đàm thoại (Context Summary)
 */
export function buildConversationSummary(
  history: Array<{ role: string; content: string }>,
  memory: ExtractedMemory
): string {
  const parts: string[] = [];
  if (memory.userName) parts.push(`Khách: ${memory.userName}`);
  if (memory.age) parts.push(`Tuổi: ${memory.age}`);
  if (memory.symptoms && memory.symptoms.length > 0) parts.push(`Triệu chứng: ${memory.symptoms.join(", ")}`);
  if (memory.symptomDuration) parts.push(`Thời gian: ${memory.symptomDuration}`);
  if (memory.symptomLocation) parts.push(`Vị trí: ${memory.symptomLocation}`);
  if (memory.symptomEscalated) parts.push(`Diễn tiến: ĐANG TĂNG NẶNG`);
  if (memory.userMood) parts.push(`Tâm trạng: ${memory.userMood}`);
  if (memory.lastDiscussedProduct) parts.push(`Thuốc quan tâm: ${memory.lastDiscussedProduct}`);
  return parts.join(" | ");
}

/**
 * Trích xuất toàn diện Memory cho phiên chat (Session Memory & Slot Extraction)
 */
export function extractUserMemory(
  currentMessage: string,
  prevMemory?: ExtractedMemory,
  history: Array<{ role: string; content: string }> = []
): ExtractedMemory {
  const slangRes = normalizeVietnameseSlang(currentMessage);
  const normalized = slangRes.normalized;
  const normCurrent = removeVietnameseTones(normalized);

  const memory: ExtractedMemory = {
    ...prevMemory,
    symptoms: prevMemory?.symptoms ? [...prevMemory.symptoms] : [],
    currentMedicines: prevMemory?.currentMedicines ? [...prevMemory.currentMedicines] : [],
    correctedFacts: prevMemory?.correctedFacts ? { ...prevMemory.correctedFacts } : {},
  };

  // 1. Trích xuất Tên người dùng (user_name) - hỗ trợ cập nhật đè giá trị mới
  const extractedName = parseUserSelfName(currentMessage);
  if (extractedName) {
    if (memory.userName && memory.userName.toLowerCase() !== extractedName.toLowerCase()) {
      memory.correctedFacts = memory.correctedFacts || {};
      memory.correctedFacts["userName"] = {
        previous: memory.userName,
        current: extractedName,
        timestamp: new Date().toISOString(),
      };
    }
    memory.userName = extractedName;
  }

  // 2. Trích xuất Tuổi (age) - thông minh, không nhầm người khác
  const ageAction = detectAgeAction(currentMessage, prevMemory);
  if (ageAction.hasAge && ageAction.age) {
    if (memory.age && memory.age !== `${ageAction.age}`) {
      memory.correctedFacts = memory.correctedFacts || {};
      memory.correctedFacts["age"] = {
        previous: memory.age,
        current: `${ageAction.age}`,
        timestamp: new Date().toISOString(),
      };
    }
    memory.age = `${ageAction.age}`;
  }

  // 3. Trích xuất Giới tính (gender)
  if (/\b(nam|trai|đàn ông|dan ong)\b/i.test(normalized)) {
    memory.gender = "Nam";
  } else if (/\b(nữ|nu|gái|phụ nữ|phu nu)\b/i.test(normalized)) {
    memory.gender = "Nữ";
  }

  // 4. Trích xuất Triệu chứng (symptoms)
  const symptomKeywords = [
    { norm: "dau bung duoi", label: "đau bụng dưới" },
    { norm: "dau bung", label: "đau bụng" },
    { norm: "nhuc dau", label: "đau đầu" },
    { norm: "dau dau", label: "đau đầu" },
    { norm: "dau nua dau", label: "đau nửa đầu" },
    { norm: "viem hong", label: "viêm họng" },
    { norm: "dau hong", label: "đau họng" },
    { norm: "rat hong", label: "rát họng" },
    { norm: "sot", label: "sốt" },
    { norm: "ho", label: "ho" },
    { norm: "cam cum", label: "cảm cúm" },
    { norm: "tieu chay", label: "tiêu chảy" },
    { norm: "di ngoai", label: "đi ngoài" },
    { norm: "dau da day", label: "đau dạ dày" },
    { norm: "buon non", label: "buồn nôn" },
    { norm: "chong mat", label: "chóng mặt" },
    { norm: "ngat", label: "ngất xỉu" },
    { norm: "di ung", label: "dị ứng" },
  ];

  for (const sk of symptomKeywords) {
    if (new RegExp(`\\b${sk.norm}\\b`, "i").test(normCurrent)) {
      if (!memory.symptoms!.includes(sk.label)) {
        memory.symptoms!.push(sk.label);
      }
    }
  }

  // 5. Trích xuất Thời gian xuất hiện (symptomDuration)
  const durationPatterns = [
    { regex: /\b(tu hom qua den gio|qua h|tu hom qua|hom qua)\b/i, val: "từ hôm qua" },
    { regex: /\b(tu sang nay|sang nay)\b/i, val: "từ sáng nay" },
    { regex: /\b(moi bi|vua bi|hom nay)\b/i, val: "mới bị hôm nay" },
    { regex: /\b(duoc 1 ngay|1 ngay)\b/i, val: "1 ngày" },
    { regex: /\b(duoc 2 ngay|2 ngay|hai ngay)\b/i, val: "2 ngày" },
    { regex: /\b(duoc 3 ngay|3 ngay|ba ngay)\b/i, val: "3 ngày" },
    { regex: /\b(vai ngay|may ngay nay)\b/i, val: "vài ngày nay" },
    { regex: /\b(1 tuan|mot tuan)\b/i, val: "khoảng 1 tuần" },
  ];

  for (const dp of durationPatterns) {
    if (dp.regex.test(normCurrent)) {
      memory.symptomDuration = dp.val;
      break;
    }
  }

  // 6. Trích xuất Vị trí (symptomLocation)
  if (/\b(ben phai|lech phai|ho chau phai|ha vi phai)\b/i.test(normCurrent)) {
    memory.symptomLocation = "bên phải";
  } else if (/\b(ben trai|lech trai)\b/i.test(normCurrent)) {
    memory.symptomLocation = "bên trái";
  } else if (/\b(o giua|chinh giua|quanh ron|vung ron)\b/i.test(normCurrent)) {
    memory.symptomLocation = "ở giữa bụng";
  } else if (/\b(vung tren ron|thuong vi)\b/i.test(normCurrent)) {
    memory.symptomLocation = "vùng trên rốn (thượng vị)";
  }

  // 7. Trích xuất Mức độ & Tăng nặng (symptomSeverity & symptomEscalated)
  if (detectSymptomEscalation(currentMessage, normalized)) {
    memory.symptomEscalated = true;
    memory.symptomSeverity = "đang tăng nặng / đau nhiều hơn";
  } else if (normCurrent.includes("am i")) {
    memory.symptomSeverity = "âm ỉ";
  } else if (normCurrent.includes("du doi") || normCurrent.includes("quan tung con")) {
    memory.symptomSeverity = "dữ dội / quặn từng cơn";
  }

  // 8. Trích xuất Tâm trạng (userMood)
  const moodRes = detectUserMood(currentMessage, normalized);
  if (moodRes.hasMood && moodRes.moodType) {
    memory.userMood = moodRes.moodType;
  }

  // 9. Trích xuất Thuốc đang uống (currentMedicines)
  const medicineMatch = currentMessage.match(/(?:đang uống|đang dùng|đã uống|đã dùng)\s+([a-zA-Z0-9\s]{2,30})/i);
  if (medicineMatch && medicineMatch[1]) {
    const medName = medicineMatch[1].trim();
    if (medName.length >= 3 && !memory.currentMedicines!.includes(medName)) {
      memory.currentMedicines!.push(medName);
    }
  }

  // 10. Trích xuất Yêu cầu gặp Dược sĩ thật (requestedRealPharmacist)
  if (
    /\b(gap duoc si that|gap nguoi that|gap nhan vien|duoc si that|nguoi that|tu van truc tiep|nhan vien that|can gap duoc si|toi muon gap duoc si)\b/i.test(
      normCurrent
    )
  ) {
    memory.requestedRealPharmacist = true;
  }

  // 11. Cập nhật Thuốc đang thảo luận gần nhất & firstDiscussedProduct
  for (const drug of COMMON_DRUGS_LOOKUP) {
    for (const alias of drug.aliases) {
      if (new RegExp(`\\b${alias}\\b`, "i").test(normCurrent)) {
        if (!memory.firstDiscussedProduct) {
          memory.firstDiscussedProduct = drug.name;
        }
        memory.lastDiscussedProduct = drug.name;
        break;
      }
    }
  }

  // 12. Cập nhật contextSummary
  memory.contextSummary = buildConversationSummary(history, memory);

  return memory;
}

/**
 * Kiểm tra xem người dùng có đang hỏi trực tiếp để tra cứu Memory hay không
 * Ví dụ: "Tên tôi là gì?", "Tôi bị gì nhỉ?", "Tôi nói tôi đau từ khi nào?"
 */
export function checkMemoryQuery(
  rawMessage: string,
  memory?: ExtractedMemory
): string | null {
  const norm = removeVietnameseTones(rawMessage);

  // 1. Hỏi về Tên ("Tên tôi là gì?", "Tôi tên gì?", "Bạn nhớ tên tôi không?", "htrc mk ns tên j ấy nhỉ")
  if (isNameQuery(rawMessage)) {
    if (memory?.userName) {
      return `Tên bạn là ${memory.userName}.`;
    }
    return `Dạ bạn chưa chia sẻ tên với mình. Bạn có thể cho mình biết tên để tiện xưng hô và hỗ trợ nhé!`;
  }

  // 2. Hỏi về Tuổi ("b nhớ mk bn tuổi ko", "giờ mình bao nhiêu tuổi ấy nhỉ", "Tôi bao nhiêu tuổi?")
  if (isAgeQuery(rawMessage)) {
    if (memory?.age) {
      return `Bạn vừa nói mình ${memory.age} tuổi.`;
    }
    return `Dạ bạn chưa cho mình biết số tuổi của mình ạ.`;
  }

  // 3. Hỏi về Triệu chứng / Bệnh ("Tôi bị gì nhỉ?", "Bạn còn nhớ bệnh tôi đang hỏi không?")
  const isAskingSymptoms =
    /\b(toi bi gi|toi bi gi nhi|toi vua noi toi bi gi|toi dang bi gi|toi bi benh gi|toi dang bi benh gi|con nho benh|nho benh toi dang hoi|benh toi dang hoi)\b/i.test(
      norm
    );

  if (isAskingSymptoms) {
    if (memory?.symptoms && memory.symptoms.length > 0) {
      const symptomList = memory.symptoms.join(", ");
      const durationText = memory.symptomDuration ? ` (xuất hiện ${memory.symptomDuration})` : "";
      const locText = memory.symptomLocation ? `, vị trí ${memory.symptomLocation}` : "";
      return `Bạn vừa chia sẻ là đang bị **${symptomList}**${locText}${durationText} ạ. Tình trạng hiện tại của bạn thế nào rồi?`;
    }
    return `Dạ trước đó bạn chưa chia sẻ triệu chứng sức khỏe nào với mình. Bạn đang cảm thấy không khỏe hay có dấu hiệu gì cần tư vấn ạ?`;
  }

  // 4. Hỏi về Thời gian đau ("Tôi nói tôi đau từ khi nào?", "Tôi bị đau từ bao giờ?", "Tôi đau từ lúc nào?")
  const isAskingDuration =
    /\b(toi noi toi dau tu khi nao|toi dau tu khi nao|toi bi dau tu bao gio|toi dau tu luc nao|toi dau bao lau roi)\b/i.test(
      norm
    );

  if (isAskingDuration) {
    if (memory?.symptomDuration) {
      return `Bạn đã chia sẻ là bị đau **${memory.symptomDuration}** ạ.`;
    }
    return `Dạ bạn chưa chia sẻ thời gian cơn đau bắt đầu. Bạn bị đau từ khi nào ạ?`;
  }

  // 5. Hỏi về Thuốc đang thảo luận ("Thuốc tôi đang hỏi là thuốc nào?", "Thuốc hồi nãy có td phụ ko?", "Loại đầu tiên có tác dụng gì?")
  if (/\b(loai dau tien|thuoc dau tien|thuoc ban dau)\b/i.test(norm)) {
    if (memory?.firstDiscussedProduct) {
      return `Thuốc đầu tiên bạn tìm hiểu trong cuộc trò chuyện này là **${memory.firstDiscussedProduct}** ạ.`;
    }
  }

  const isAskingDrug =
    /\b(thuoc toi dang hoi la thuoc nao|thuoc toi vua hoi la gi|thuoc toi dang hoi|thuoc vua roi la thuoc gi|thuoc hoi nay|thuoc luc nay)\b/i.test(
      norm
    );

  if (isAskingDrug) {
    if (memory?.lastDiscussedProduct) {
      return `Thuốc bạn đang tìm hiểu là **${memory.lastDiscussedProduct}** ạ.`;
    }
    return `Dạ trong cuộc trò chuyện này bạn chưa nhắc đến tên loại thuốc cụ thể nào. Bạn đang cần tìm hiểu thông tin về thuốc gì ạ?`;
  }

  return null;
}

/**
 * Kiểm tra xem người dùng có vừa giới thiệu tên mới không ("Tên tôi là Nguyễn Đức Anh", "Tôi tên là...")
 */
export function checkSelfIntroduction(rawMessage: string): { isIntro: boolean; name?: string } {
  const name = parseUserSelfName(rawMessage);
  if (name) {
    return { isIntro: true, name };
  }
  return { isIntro: false };
}

/**
 * Xây dựng toàn diện ConversationContext
 */
export function buildConversationContext(
  history: Array<{ role: string; content: string }>,
  currentMessage: string,
  prevMemory?: ExtractedMemory
): ConversationContext {
  const extractedMemory = extractUserMemory(currentMessage, prevMemory, history);
  const activeDrug = extractedMemory.lastDiscussedProduct || extractActiveDrugFromHistory(history, currentMessage);
  const symptomContext = trackSymptomContext(history, currentMessage);

  return {
    activeDrug,
    symptomContext,
    extractedMemory,
  };
}
