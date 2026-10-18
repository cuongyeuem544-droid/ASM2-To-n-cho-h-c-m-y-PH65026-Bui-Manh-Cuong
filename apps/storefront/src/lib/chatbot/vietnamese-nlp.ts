import { removeVietnameseTones } from "./product-search";

/**
 * Từ điển các từ viết tắt / tiếng lóng phổ biến trong giao tiếp mạng của người Việt
 * Được thiết kế để chuẩn hóa ngữ nghĩa một cách an toàn, có nhận thức ngữ cảnh (Context-aware).
 */

export interface NormalizedResult {
  normalized: string;
  raw: string;
  detectedSlang: string[];
}

/**
 * Chuẩn hóa các từ viết tắt và tiếng lóng tiếng Việt có xét theo ngữ cảnh
 */
export function normalizeVietnameseSlang(rawText: string): NormalizedResult {
  let text = rawText.trim();
  const detectedSlang: string[] = [];

  // 1. Chuẩn hóa viết tắt tuổi: "39t", "19t", "20t", "39 t", "19 tuổi r"
  text = text.replace(/\b(\d{1,3})\s*(?:t|tuoi)\s*(?:r|roi)?\b/gi, (match, p1) => {
    detectedSlang.push(match);
    return `${p1} tuổi`;
  });

  // 2. Chuẩn hóa ngữ cảnh hỏi thời gian: "từ qua h", "qua h", "hqua", "hqa"
  text = text.replace(/\b(tu qua h|qua h|tu hom qua den gio|hqua toi gio)\b/gi, () => {
    detectedSlang.push("qua h");
    return "từ hôm qua đến giờ";
  });
  text = text.replace(/\b(hqua|hqa|hom qua)\b/gi, () => {
    return "hôm qua";
  });
  text = text.replace(/(?:^|\s)(?:htrc|hôm\s+trc|hom\s+trc)(?=\s|[.,?!]|$)/gi, (match) => {
    detectedSlang.push("htrc");
    const prefix = match.startsWith(" ") ? " " : "";
    return `${prefix}hôm trước`;
  });

  // 3. Chuẩn hóa tác dụng phụ: "td phụ", "td phu"
  text = text.replace(/(?:^|\s)td\s+(?:phụ|phu)(?=\s|[.,?!]|$)/gi, (match) => {
    detectedSlang.push("td phụ");
    const prefix = match.startsWith(" ") ? " " : "";
    return `${prefix}tác dụng phụ`;
  });

  // 4. Chuẩn hóa từ ngữ cảnh "bn":
  // - Nếu đi với "tuổi", "tiền", "nhiêu" -> "bao nhiêu"
  // - Nếu đi ở vị trí đại từ xưng hô ("chào bn", "bn ơi", "bn có", "nhớ giùm bn") -> "bạn"
  text = text.replace(/\bbn\s+(tuổi|tuoi|tiền|tien|nhiêu|nhieu|k|nghìn|nghin|đ|vnd)\b/gi, "bao nhiêu $1");
  text = text.replace(/\b(giá|gia|hết|het)\s+bn\b/gi, "$1 bao nhiêu");
  text = text.replace(/\b(chào|chao|alo|hey|hi)\s+bn\b/gi, "$1 bạn");
  text = text.replace(/\bbn\s+(ơi|oi|có|co|cho|xem|biết|biet|nhớ|nho)\b/gi, "bạn $1");

  // 5. Chuẩn hóa từ ngữ cảnh "bh":
  // - "từ nãy tới bh", "đến bh" -> "bây giờ"
  // - "bh mới khỏi", "bh thì" -> "bao giờ"
  text = text.replace(/\b(tới|toi|đến|den|từ|tu)\s+bh\b/gi, "$1 bây giờ");
  text = text.replace(/\bbh\s+(mới|moi|thì|thi|xong|khỏi|khoi)\b/gi, "bao giờ $1");

  // 6. Danh sách các cặp từ viết tắt xác định (Boundary-safe token replacements)
  const exactTokenMap: Array<[RegExp, string, string]> = [
    [/\b(mk|mik)\b/gi, "mình", "mk"],
    [/\b(tui)\b/gi, "tôi", "tui"],
    [/\b(ko|kh|k|hok|hông|hong)\b/gi, "không", "ko"],
    [/\b(đc|dc)\b/gi, "được", "dc"],
    [/\b(ntn)\b/gi, "như thế nào", "ntn"],
    [/\b(lm)\b/gi, "làm", "lm"],
    [/\b(j|ji)\b/gi, "gì", "j"],
    [/\b(z|v)\b/gi, "vậy", "z"],
    [/\b(chx)\b/gi, "chưa", "chx"],
    [/\b(đg|dg)\b/gi, "đang", "đg"],
    [/\b(vs)\b/gi, "với", "vs"],
    [/\b(cx)\b/gi, "cũng", "cx"],
    [/\b(ib)\b/gi, "nhắn tin", "ib"],
    [/\b(rep)\b/gi, "trả lời", "rep"],
    [/\b(ns)\b/gi, "nói", "ns"],
  ];

  for (const [regex, replacement, tokenName] of exactTokenMap) {
    if (regex.test(text)) {
      detectedSlang.push(tokenName);
      text = text.replace(regex, replacement);
    }
  }

  // 7. Chuẩn hóa "r" ở cuối câu hoặc trước dấu câu: "xong r", "nặng hơn r", "20 r" -> "rồi"
  text = text.replace(/\b([a-zA-Zà-ỹ0-9]+)\s+r([\s.,!?]|$)/gi, (match, p1, p2) => {
    // Không thay thế nếu p1 là chữ đơn lẻ không rõ nghĩa
    detectedSlang.push("r");
    return `${p1} rồi${p2}`;
  });

  // 8. Chuẩn hóa "b" ở đầu hoặc giữa câu chỉ "bạn" (ví dụ: "b ơi", "chào b", "b nhớ", "đố b")
  text = text.replace(/(?:^|\s)(?:chào|chao|đố|do|ơi|oi|nhớ|nho|cho)\s+b(?=\s|[.,?!]|$)/gi, (match) => {
    return match.replace(/\bb\b/gi, "bạn");
  });
  text = text.replace(/(?:^|\s)b\s+(ơi|oi|nhớ|nho|biết|biet|có|co|thấy|thay)(?=\s|[.,?!]|$)/gi, (match, p1) => {
    const prefix = match.startsWith(" ") ? " " : "";
    return `${prefix}bạn ${p1}`;
  });

  // 9. Chuẩn hóa "t" ở đầu hoặc trước động từ chỉ "tôi" (ví dụ: "t tên", "t bị", "t 39t", "đầu t")
  text = text.replace(/\b(đầu|bung|người|ten|tên)\s+t\b/gi, "$1 tôi");
  text = text.replace(/\bt\s+(tên|ten|bị|bi|đau|dau|thấy|thay|uống|uong)\b/gi, "tôi $1");

  return {
    normalized: text.trim(),
    raw: rawText,
    detectedSlang,
  };
}

/**
 * Trích xuất tuổi của chính người dùng một cách thông minh, không nhầm người khác
 */
export function extractUserAge(
  rawText: string,
  normalizedText?: string
): { hasAge: boolean; age?: number; isCorrection?: boolean; isOtherPerson?: boolean } {
  const norm = normalizedText || normalizeVietnameseSlang(rawText).normalized;
  const noTones = removeVietnameseTones(norm);

  // 1. Kiểm tra nếu câu nói về người khác (mẹ tôi 50 tuổi, con tôi 5 tuổi...)
  const isOther = /\b(me|bo|ba|ma|con|be|chau|vo|chong|ban|anh trai|em|ong|bac si)\b/i.test(noTones) &&
    /\b(50|60|70|80|\d{1,2})\s*tuoi\b/i.test(noTones) &&
    !/\b(toi|minh|em|anh|tui)\s*(\d{1,2})\s*tuoi\b/i.test(noTones);

  if (isOther) {
    return { hasAge: false, isOtherPerson: true };
  }

  // 2. Kiểm tra cờ sửa tuổi ("thực ra mk 20 r", "không, tôi 29 cơ", "sửa lại là 20")
  const isCorrection = /\b(thuc ra|thuc su|khong|nham|sua lai|chinh xac la|doi thanh|co)\b/i.test(noTones);

  // 3. Các mẫu câu diễn đạt tuổi tự nhiên phong phú của người Việt:
  // - "t 39t r", "mk 19 tuổi", "tôi 39 tuổi", "năm nay tui 39 cái xuân xanh"
  // - "mình vừa bước sang tuổi 40", "mình 20 rồi", "em 25"
  const agePatterns: RegExp[] = [
    /\b(?:tôi|toi|mình|minh|tui|em|anh|chị|chi|t|mk)\s*(?:năm nay|nam nay)?\s*(\d{1,3})\s*(?:cái xuân xanh|tuổi|tuoi|t)\b/i,
    /\b(?:năm nay|nam nay)\s*(?:tôi|toi|mình|minh|tui|em|anh)?\s*(\d{1,3})\s*(?:cái xuân xanh|tuổi|tuoi|t)\b/i,
    /\b(?:bước sang tuổi|buoc sang tuoi|sang tuổi|sang tuoi)\s*(\d{1,3})\b/i,
    /\b(?:thực ra|thuc ra|không|khong|nhầm|nham)?\s*(?:tôi|toi|mình|minh|mk|tui|em)\s*(\d{1,3})\s*(?:rồi|roi|r|tuổi|tuoi)\b/i,
    /^(?:tôi|toi|mình|minh|mk|tui|em)\s*(\d{1,3})$/i,
    /\b(?:được|duoc)\s*(\d{1,3})\s*tuổi\b/i,
  ];

  for (const regex of agePatterns) {
    const match = norm.match(regex);
    if (match && match[1]) {
      const parsed = parseInt(match[1], 10);
      if (parsed > 0 && parsed < 125) {
        return {
          hasAge: true,
          age: parsed,
          isCorrection,
          isOtherPerson: false,
        };
      }
    }
  }

  return { hasAge: false };
}

/**
 * Nhận diện câu hỏi truy vấn về tuổi: "b nhớ mk bn tuổi ko", "giờ mình bao nhiêu tuổi ấy nhỉ"
 */
export function isAgeQuery(rawText: string, normalizedText?: string): boolean {
  const norm = normalizedText || normalizeVietnameseSlang(rawText).normalized;
  const noTones = removeVietnameseTones(norm);

  return (
    /\b(nho.*(bn|bao nhieu).*tuoi|nho toi.*tuoi|nho minh.*tuoi|nho mk.*tuoi|nho t.*tuoi)\b/i.test(noTones) ||
    /\b(toi|minh|mk|tui)\s*(bao nhieu|bn|may)\s*tuoi\b/i.test(noTones) ||
    /\b(tuoi cua toi|tuoi cua minh|tuoi cua mk|toi may tuoi|minh may tuoi)\b/i.test(noTones) ||
    /\b(gio|bay gio|hien tai)\s*(minh|toi|mk)\s*(bao nhieu|bn)\s*tuoi\b/i.test(noTones)
  );
}

/**
 * Nhận diện câu chia sẻ tâm trạng / cảm xúc (để trò chuyện tự nhiên, không ép tìm thuốc)
 */
export function detectUserMood(rawText: string, normalizedText?: string): { hasMood: boolean; moodType?: string; replyHint?: string } {
  const norm = normalizedText || normalizeVietnameseSlang(rawText).normalized;
  const noTones = removeVietnameseTones(norm);

  if (/\b(buon|hoi buon|buon qua|chan qua|tam trang khong tot|met moi trong long|tieu cuc)\b/i.test(noTones)) {
    return {
      hasMood: true,
      moodType: "sad",
      replyHint: "Có chuyện gì khiến bạn buồn vậy? Nếu muốn, bạn có thể tâm sự cùng mình nhé. Mình luôn sẵn sàng lắng nghe.",
    };
  }

  if (/\b(lo lang|lo qua|bat an|so qua|hoang mang)\b/i.test(noTones) && !/\b(dau|sot|ngat|cap cuu)\b/i.test(noTones)) {
    return {
      hasMood: true,
      moodType: "anxious",
      replyHint: "Bạn đang cảm thấy lo lắng về điều gì vậy? Hãy hít thở thật sâu nhé, mình ở đây để cùng bạn tìm hiểu và tháo gỡ từng vấn đề.",
    };
  }

  if (/\b(vui|vui qua|hom nay vui|yeu doi|happy)\b/i.test(noTones)) {
    return {
      hasMood: true,
      moodType: "happy",
      replyHint: "Nghe thật tuyệt vời! Rất vui khi thấy bạn có một ngày tràn đầy năng lượng tích cực như vậy.",
    };
  }

  return { hasMood: false };
}

/**
 * Nhận diện tình trạng triệu chứng tăng nặng / leo thang (Escalated symptoms)
 * Ví dụ: "đau bụng dưới bên phải, giờ đau hơn r", "giờ nó nặng hơn r", "càng lúc càng đau"
 */
export function detectSymptomEscalation(rawText: string, normalizedText?: string): boolean {
  const norm = normalizedText || normalizeVietnameseSlang(rawText).normalized;
  const noTones = removeVietnameseTones(norm);

  return (
    /\b(dau hon|dau hon roi|dau nhieu hon|nang hon|nang hon roi|nang len|tang len|dau tang|cang luc cang dau|du doi hon|khong chiu noi)\b/i.test(noTones) ||
    /\b(gio dau hon|bh dau hon|gio nang hon|bh nang hon)\b/i.test(noTones)
  );
}

/**
 * Nhận diện các đại từ thay thế vị trí thuốc (Anaphoric drug pronouns)
 * Ví dụ: "nó là gì?", "thuốc này có tác dụng phụ không?", "loại lúc nãy có tốt không?"
 */
export function resolveAnaphoricDrugQuery(
  rawText: string,
  lastDrug?: string,
  firstDrug?: string
): { isAnaphoric: boolean; targetDrug?: string; isFirstDrug?: boolean } {
  const norm = removeVietnameseTones(rawText);

  // Kiểm tra nếu hỏi về "loại đầu tiên"
  if (/\b(loai dau tien|thuoc dau tien|thuoc ban dau|cai dau tien)\b/i.test(norm)) {
    return {
      isAnaphoric: true,
      targetDrug: firstDrug || lastDrug,
      isFirstDrug: true,
    };
  }

  // Kiểm tra đại từ thông thường: "nó", "loại đó", "thuốc này", "loại lúc nãy", "cái đó"
  const pronounRegex = /\b(no|loai do|thuoc nay|loai nay|thuoc do|loai luc nay|thuoc luc nay|cai do|cai nay|san pham do|san pham nay)\b/i;
  if (pronounRegex.test(norm) && lastDrug) {
    return {
      isAnaphoric: true,
      targetDrug: lastDrug,
    };
  }

  return { isAnaphoric: false };
}
