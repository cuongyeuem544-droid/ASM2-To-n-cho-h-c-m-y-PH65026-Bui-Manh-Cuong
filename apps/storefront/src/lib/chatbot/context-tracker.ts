import { ConversationContext, SymptomContext } from "./types";
import { removeVietnameseTones } from "./product-search";

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

  ctx.accompanying = accompanying;

  // 6. Kiểm tra Dấu hiệu nguy hiểm (Red Flag)
  if (accompanying.includes("ngất xỉu")) {
    ctx.hasRedFlag = true;
    ctx.redFlagReason = "Cơn đau kèm ngất xỉu / mất ý thức là dấu hiệu cấp cứu tối khẩn cấp (P0).";
  } else if (ctx.primarySymptom?.includes("bụng") && ctx.location === "bên phải" && (accompanying.includes("sốt") || accompanying.includes("nôn/buồn nôn") || accompanying.includes("đau tăng khi vận động"))) {
    ctx.hasRedFlag = true;
    ctx.redFlagReason = "Đau hố chậu phải kèm sốt/buồn nôn hoặc đau tăng khi đi lại là dấu hiệu chỉ điểm kinh điển của Viêm ruột thừa cấp cần can thiệp ngoại khoa khẩn cấp.";
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
 * Xây dựng toàn diện ConversationContext
 */
export function buildConversationContext(
  history: Array<{ role: string; content: string }>,
  currentMessage: string
): ConversationContext {
  const activeDrug = extractActiveDrugFromHistory(history, currentMessage);
  const symptomContext = trackSymptomContext(history, currentMessage);

  return {
    activeDrug,
    symptomContext,
  };
}
