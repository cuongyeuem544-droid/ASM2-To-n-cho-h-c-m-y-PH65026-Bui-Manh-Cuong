import {
  RED_FLAG_SYMPTOMS,
  STORE_POLICIES_INFO,
  SYMPTOM_TRIAGE_GUIDELINES,
} from "./knowledge-base";
import { searchMedicines, formatProductsContext, removeVietnameseTones } from "./product-search";
import { classifyUserIntent, extractProductSearchQuery } from "./intent";
import { cleanMedicalText } from "./sanitizer";
import {
  buildConversationContext,
  extractActiveDrugFromHistory,
  extractUserMemory,
  checkMemoryQuery,
  checkSelfIntroduction,
  detectNameAction,
  detectAgeAction,
  buildConversationSummary,
} from "./context-tracker";
import {
  normalizeVietnameseSlang,
  detectUserMood,
  detectSymptomEscalation,
  resolveAnaphoricDrugQuery,
} from "./vietnamese-nlp";
import { handleSymptomTriage } from "./symptom-triage";
import {
  findDrugKnowledge,
  formatDrugInformationReply,
  formatDrugSideEffectsReply,
  formatDrugComparisonReply,
  DRUG_KNOWLEDGE_BASE,
} from "./drug-knowledge";
import { ChatAttachment, ChatProductItem, ChatResponse, ChatSafetyAlert, ExtractedMemory, StandardIntent } from "./types";

interface MessageHistoryItem {
  role: "user" | "assistant";
  content: string;
}

/**
 * Kiểm tra xem tin nhắn có chứa triệu chứng nguy hiểm khẩn cấp (Red Flag) hay không
 */
export function detectRedFlag(text: string): ChatSafetyAlert | null {
  const norm = removeVietnameseTones(text);

  for (const item of RED_FLAG_SYMPTOMS) {
    for (const kw of item.keywords) {
      const normKw = removeVietnameseTones(kw);
      if (new RegExp(`\\b${normKw}\\b`, "i").test(norm)) {
        return {
          level: item.level,
          title: item.title,
          message: item.message,
          actionRequired: item.action,
          emergencyNumber: "115",
        };
      }
    }
  }

  return null;
}

/**
 * Xây dựng System Prompt chuẩn y tế H4CARE cho LLM khi có dữ liệu sản phẩm
 */
function buildSystemPrompt(
  productsContext: string,
  intent: StandardIntent,
  memory?: ExtractedMemory,
  activeDrug?: string,
  contextSummary?: string
): string {
  const memoryLines: string[] = [];
  if (memory?.userName) memoryLines.push(`- Tên khách hàng: ${memory.userName}`);
  if (memory?.age) memoryLines.push(`- Tuổi: ${memory.age} tuổi`);
  if (memory?.gender) memoryLines.push(`- Giới tính: ${memory.gender}`);
  if (memory?.symptoms && memory.symptoms.length > 0) memoryLines.push(`- Triệu chứng: ${memory.symptoms.join(", ")}`);
  if (memory?.symptomDuration) memoryLines.push(`- Thời gian xuất hiện: ${memory.symptomDuration}`);
  if (memory?.symptomLocation) memoryLines.push(`- Vị trí đau/khó chịu: ${memory.symptomLocation}`);
  if (memory?.symptomEscalated) memoryLines.push(`- Diễn tiến: ĐANG TĂNG NẶNG (Ưu tiên theo dõi sát/hướng dẫn đi khám)`);
  if (memory?.userMood) memoryLines.push(`- Tâm trạng chia sẻ: ${memory.userMood}`);
  if (memory?.currentMedicines && memory.currentMedicines.length > 0) memoryLines.push(`- Thuốc đang dùng: ${memory.currentMedicines.join(", ")}`);
  if (memory?.lastDiscussedProduct || activeDrug) memoryLines.push(`- Thuốc đang thảo luận: ${memory?.lastDiscussedProduct || activeDrug}`);

  const memoryBlock = memoryLines.length > 0
    ? `=== BỘ NHỚ THỰC THẾ ĐÃ XÁC NHẬN TỪ NGƯỜI DÙNG (SESSION MEMORY) ===\n${memoryLines.join("\n")}`
    : `=== BỘ NHỚ PHIÊN: Khách hàng chưa chia sẻ thông tin cá nhân cụ thể. ===`;

  return `Bạn là "Trợ lý AI H4CARE" - hệ thống tư vấn thông tin thuốc và chăm sóc sức khỏe thông minh chuẩn GPP H4CARE.
Mục tiêu của bạn là mang lại trải nghiệm hội thoại tự nhiên, thấu hiểu, ân cần như ChatGPT, đồng thời tuyệt đối tuân thủ quy chuẩn an toàn dược khoa và y tế.

${memoryBlock}

${contextSummary ? `=== TÓM TẮT NGỮ CẢNH HỘI THOẠI TRƯỚC ĐÓ ===\n${contextSummary}\n` : ""}
=== NGUYÊN TẮC HỘI THOẠI TỰ NHIÊN (CHATGPT-STYLE) ===
1. Trả lời đúng trọng tâm câu hỏi của người dùng, không né tránh, không máy móc.
2. Câu hỏi ngắn/đơn giản -> Trả lời súc tích, ngắn gọn. Câu hỏi chuyên sâu/triệu chứng -> Giải thích rõ ràng, có cấu trúc.
3. KHÔNG chào lại ("Xin chào...") ở mỗi tin nhắn. Chỉ chào ở lượt đầu tiên hoặc khi người dùng chào.
4. KHÔNG liên tục hỏi máy móc "Bạn muốn tìm thuốc hay tư vấn triệu chứng?". Hãy lắng nghe và tiếp nối dòng suy nghĩ của người dùng.
5. Khi người dùng chia sẻ tâm trạng (buồn, mệt mỏi, vui vẻ) -> Hãy đồng cảm, lắng nghe như một người bạn, TUYỆT ĐỐI KHÔNG ép chuyển sang mua thuốc.
6. Khi người dùng dùng đại từ ("nó", "loại đó", "thuốc này", "cái đó") -> Hãy hiểu đúng là đang nói về ${memory?.lastDiscussedProduct || activeDrug || "loại thuốc vừa thảo luận"}.
7. Khi người dùng hỏi lại thông tin đã nói ("tôi bao nhiêu tuổi", "tên tôi là gì", "tôi bị từ khi nào") -> Tra cứu đúng phần SESSION MEMORY ở trên để trả lời chính xác.

=== QUY TẮC Y TẾ VÀ AN TOÀN BẮT BUỘC ===
1. Khi người dùng mô tả triệu chứng sức khỏe:
   - ĐÂY LÀ TƯ VẤN SỨC KHỎE, TUYỆT ĐỐI KHÔNG TỰ ĐỘNG GỢI Ý DANH SÁCH THUỐC MUA SẮM.
   - CHỈ HỎI ĐÚNG MỘT CÂU TRỌNG TÂM mỗi lượt để làm rõ tình trạng (thời gian xuất hiện -> vị trí -> triệu chứng cảnh báo kèm theo).
   - Ghi nhớ câu trả lời trước đó, KHÔNG hỏi lại những thông tin người dùng đã nói.
   - Nếu phát hiện dấu hiệu nguy hiểm (ngất, khó thở, đau thắt ngực, sốt cao co giật, nôn ra máu, đau hố chậu phải kèm sốt nghi ruột thừa) -> Lập tức cảnh báo khẩn cấp và khuyên đi khám/gọi 115 ngay.
   - Không kết luận chắc chắn bệnh, không tự kê đơn thuốc điều trị.

2. Khi người dùng hỏi thông tin thuốc (Paracetamol, Ibuprofen, Vitamin C...):
   - Giải thích rõ hoạt chất, công dụng, chống chỉ định, cảnh báo quá liều (đặc biệt độc tính gan của Paracetamol khi dùng > 4g/ngày).
   - Trả lời trung thực, khách quan theo Dược thư Quốc gia. Không tự cá nhân hóa liều.

3. Khi người dùng muốn gặp Dược sĩ thật:
   - Thông báo rõ ràng kênh kết nối chính thức: Chuyển tab Tư vấn trực tiếp hoặc Hotline Dược sĩ 1800 6828 (8:00 - 21:00, miễn phí).

=== NGUYÊN TẮC PHÂN TÍCH HÌNH ẢNH Y TẾ & THỊ GIÁC (MULTIMODAL / VISION) ===
1. Đọc và nhận diện thông tin trên ảnh (nhãn thuốc, bao bì, vỉ thuốc, đơn thuốc):
   - Nhận diện tên thuốc, biệt dược, tên hoạt chất, hàm lượng, dạng bào chế, nhà sản xuất, hạn dùng nếu thấy rõ.
   - Đối với đơn thuốc: đọc các dòng thuốc, liều dùng ghi trong đơn, nhắc nhở mang đơn thuốc ra nhà thuốc để Dược sĩ đối soát.
2. Thận trọng y khoa tuyệt đối:
   - Ảnh chụp có thể bị mờ, lóa sáng, thiếu góc hoặc sai lệch màu sắc. Luôn thông báo rõ: "Kết quả nhận diện qua ảnh chỉ mang tính tham khảo, không đảm bảo chính xác tuyệt đối".
   - Tuyệt đối KHÔNG tự ý thay đổi liều dùng hoặc tự kê đơn mới cho người dùng.
   - Với ảnh triệu chứng ngoài da (mẩn ngứa, phát ban, vết thương): TUYỆT ĐỐI KHÔNG chẩn đoán bệnh chắc chắn chỉ qua ảnh chụp. Luôn khuyên người dùng nên đi khám bác sĩ da liễu hoặc cơ sở y tế để được thăm khám trực tiếp.
   - Nếu ảnh quá mờ, mất chữ, chụp thiếu góc: hãy ân cần đề nghị người dùng chụp lại ảnh rõ nét hơn, phẳng hơn và đủ ánh sáng.

=== DỮ LIỆU SẢN PHẨM H4CARE ĐÃ XÁC MINH (CHỈ DÙNG KHI Ý ĐỊNH LÀ PRODUCT_SEARCH) ===
${productsContext}

=== NGÔN NGỮ ===
Tiếng Việt chuẩn y khoa, tự nhiên, ân cần, ngắn gọn, không sinh mã HTML thô hay ký tự u003c.`;
}

/**
 * Làm sạch chuỗi thông điệp lỗi, tuyệt đối không để lộ API Key, Secret hay Token
 */
function sanitizeError(msg: string): string {
  if (!msg) return "";
  return msg
    .replace(/key=[A-Za-z0-9_\-\.]+/gi, "key=[REDACTED]")
    .replace(/AIzaSy[A-Za-z0-9_\-\.]+/gi, "[REDACTED_API_KEY]")
    .replace(/sk-[A-Za-z0-9_\-\.]+/gi, "[REDACTED_API_KEY]")
    .replace(/Bearer\s+[A-Za-z0-9_\-\.]+/gi, "Bearer [REDACTED]");
}

/**
 * Gọi Google Gemini API với luân phiên turn role chuẩn và hỗ trợ Multimodal Vision
 */
async function callGemini(
  apiKey: string,
  model: string,
  systemPrompt: string,
  history: MessageHistoryItem[],
  currentMessage: string,
  timeoutMs: number,
  attachments?: ChatAttachment[]
): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const rawContents = [
    ...history.slice(-8).map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      text: cleanMedicalText(m.content),
    })),
  ];

  const firstUserIdx = rawContents.findIndex((c) => c.role === "user");
  const validTurns = firstUserIdx >= 0 ? rawContents.slice(firstUserIdx) : [];

  const contents: Array<{ role: string; parts: Array<any> }> = [];
  for (const turn of validTurns) {
    if (!turn.text.trim()) continue;
    if (contents.length > 0 && contents[contents.length - 1].role === turn.role) {
      contents[contents.length - 1].parts[0].text += "\n\n" + turn.text;
    } else {
      contents.push({
        role: turn.role,
        parts: [{ text: turn.text }],
      });
    }
  }

  // Lượt người dùng hiện tại (kèm ảnh inlineData nếu có)
  const currentParts: Array<any> = [];
  if (attachments && attachments.length > 0) {
    for (const att of attachments) {
      if (att.base64Data) {
        currentParts.push({
          inlineData: {
            mimeType: att.mimeType || "image/jpeg",
            data: att.base64Data,
          },
        });
      }
    }
  }
  const cleanCurrent = cleanMedicalText(currentMessage).trim();
  currentParts.push({
    text: cleanCurrent || "Vui lòng xem và đọc thông tin trên hình ảnh đính kèm giúp tôi.",
  });

  contents.push({
    role: "user",
    parts: currentParts,
  });

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        systemInstruction: {
          parts: [{ text: systemPrompt }],
        },
        contents,
        generationConfig: {
          temperature: 0.2,
          maxOutputTokens: 800,
        },
      }),
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Gemini API HTTP ${res.status}: ${sanitizeError(errText)}`);
    }

    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) {
      if (data.candidates?.[0]?.finishReason) {
        throw new Error(`Gemini kết thúc với lý do: ${data.candidates[0].finishReason}`);
      }
      if (data.promptFeedback?.blockReason) {
        throw new Error(`Gemini chặn với lý do: ${data.promptFeedback.blockReason}`);
      }
      throw new Error("Phản hồi từ Gemini rỗng");
    }
    return cleanMedicalText(text);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Gọi OpenAI API hỗ trợ Vision
 */
async function callOpenAiCompatible(
  apiKey: string,
  baseUrl: string,
  model: string,
  systemPrompt: string,
  history: MessageHistoryItem[],
  currentMessage: string,
  timeoutMs: number,
  attachments?: ChatAttachment[]
): Promise<string> {
  const url = `${baseUrl.replace(/\/+$/, "")}/chat/completions`;

  const userContent: Array<any> = [];
  if (attachments && attachments.length > 0) {
    for (const att of attachments) {
      if (att.base64Data) {
        userContent.push({
          type: "image_url",
          image_url: {
            url: `data:${att.mimeType || "image/jpeg"};base64,${att.base64Data}`,
          },
        });
      }
    }
  }
  const cleanCurrent = cleanMedicalText(currentMessage).trim();
  userContent.push({
    type: "text",
    text: cleanCurrent || "Vui lòng xem và đọc thông tin trên hình ảnh đính kèm giúp tôi.",
  });

  const messages = [
    { role: "system", content: systemPrompt },
    ...history.slice(-6).map((m) => ({
      role: m.role,
      content: cleanMedicalText(m.content),
    })),
    { role: "user", content: userContent },
  ];

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const res = await fetch(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      body: JSON.stringify({
        model,
        messages,
        temperature: 0.2,
        max_tokens: 800,
      }),
      signal: controller.signal,
    });

    clearTimeout(timer);

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`OpenAI API HTTP ${res.status}: ${sanitizeError(errText)}`);
    }

    const data = await res.json();
    const content = data.choices?.[0]?.message?.content;
    if (!content) {
      throw new Error("Phản hồi từ OpenAI API rỗng");
    }
    return cleanMedicalText(content);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Động cơ Xử lý Ý định Chuyên gia H4CARE (Expert Decision Engine)
 * Xử lý chính xác từng nhóm ý định theo đúng tiêu chuẩn thực tế
 */
function handleIntentDeterministically(
  intent: StandardIntent,
  rawMessage: string,
  searchQuery: string | undefined,
  products: ChatProductItem[],
  safetyAlert: ChatSafetyAlert | null,
  activeDrug?: string,
  history: MessageHistoryItem[] = [],
  currentUser?: any,
  extractedMemory?: ExtractedMemory
): { reply: string; quickReplies: string[]; attachProducts: boolean; safetyAlert?: ChatSafetyAlert; isHumanSupport?: boolean; handoffRequested?: boolean } {
  const norm = removeVietnameseTones(rawMessage);

  // 1. TÌNH HUỐNG KHẨN CẤP (EMERGENCY / P0)
  if (intent === "EMERGENCY") {
    const alert = safetyAlert || {
      level: "emergency" as const,
      title: "🚨 CẢNH BÁO Y TẾ KHẨN CẤP (P0)",
      message: "Dấu hiệu mất ý thức, ngất xỉu, khó thở hoặc đau dữ dội đột ngột là tình huống cấp cứu y tế tối khẩn cấp.",
      actionRequired: "Gọi ngay 115 hoặc đưa người bệnh đến khoa Cấp cứu bệnh viện gần nhất lập tức!",
      emergencyNumber: "115",
    };

    return {
      reply: `🚨 **${alert.title}**\n\n${alert.message}\n\n👉 **HÀNH ĐỘNG CẦN THỰC HIỆN NGAY LẬP TỨC:**\n1. **Gọi cấp cứu 115 ngay lập tức** hoặc nhờ người xung quanh hỗ trợ đưa đến cơ sở y tế gần nhất.\n2. Đặt người bệnh nằm nghiêng an toàn, nới lỏng trang phục.\n3. **TUYỆT ĐỐI KHÔNG** tự ý cho uống thuốc giảm đau hay ăn uống bất cứ thứ gì.\n\n*H4CARE khuyến cáo: Tuyệt đối không trì hoãn cấp cứu để tìm kiếm thông tin thuốc.*`,
      quickReplies: ["📞 Gọi cấp cứu 115", "🏥 Tìm bệnh viện gần nhất"],
      attachProducts: false,
      safetyAlert: alert,
    };
  }

  // 2. KẾT NỐI DƯỢC SĨ / NHÂN VIÊN THẬT (HUMAN_SUPPORT)
  if (intent === "HUMAN_SUPPORT") {
    const namePrefix = extractedMemory?.userName ? ` bạn **${extractedMemory.userName}**` : "";
    return {
      reply: `Dạ vâng${namePrefix}! Mình đang kích hoạt kết nối để chuyển cuộc trò chuyện sang **Dược sĩ / Nhân viên tư vấn trực tiếp của H4CARE** qua tab **"Tư vấn trực tiếp"** ngay bây giờ ạ.\n\nNhân viên hỗ trợ sẽ tiếp nhận và trò chuyện cùng bạn trong giây lát.\n\n*(Trường hợp cần tư vấn khẩn cấp về đơn thuốc, bạn cũng có thể gọi hotline Dược sĩ miễn cước: **1800 6828** từ 8:00 - 21:00 hàng ngày).*`,
      quickReplies: ["🎧 Chuyển sang tư vấn trực tiếp", "📞 Gọi hotline 1800 6828"],
      attachProducts: false,
      isHumanSupport: true,
      handoffRequested: true,
    };
  }

  // 3. TƯ VẤN TRIỆU CHỨNG SỨC KHỎE (HEALTH_SYMPTOM - Single Question Triage)
  if (intent === "HEALTH_SYMPTOM") {
    const convContext = buildConversationContext(history, rawMessage, extractedMemory);
    const triageRes = handleSymptomTriage(convContext.symptomContext!, rawMessage);

    return {
      reply: triageRes.reply,
      quickReplies: triageRes.quickReplies,
      attachProducts: false,
      safetyAlert: triageRes.safetyAlert,
    };
  }

  // 4. THÔNG TIN DƯỢC LÝ & HOẠT CHẤT (DRUG_INFORMATION)
  if (intent === "DRUG_INFORMATION") {
    // Trường hợp so sánh hai thuốc (Paracetamol vs Ibuprofen)
    const mentionsParacetamol = norm.includes("paracetamol") || norm.includes("panadol");
    const mentionsIbuprofen = norm.includes("ibuprofen");

    if ((mentionsParacetamol && mentionsIbuprofen) || (norm.includes("so sanh") || norm.includes("giong nhau") || norm.includes("khac nhau") || norm.includes("uong chung"))) {
      const drugPara = findDrugKnowledge("paracetamol")!;
      const drugIbu = findDrugKnowledge("ibuprofen")!;
      return {
        reply: formatDrugComparisonReply(drugPara, drugIbu),
        quickReplies: ["💊 Tra cứu Paracetamol", "💊 Tra cứu Ibuprofen", "🔍 Tìm thuốc tại H4CARE"],
        attachProducts: false,
      };
    }

    // Tra cứu hoạt chất chính
    const targetDrugName = activeDrug || rawMessage;
    const drugInfo = findDrugKnowledge(targetDrugName) || findDrugKnowledge("paracetamol");

    if (drugInfo) {
      // Nếu hỏi riêng về tác dụng phụ
      if (norm.includes("tac dung phu") || norm.includes("tac dung khong mong muon") || norm.includes("uong vao bi gi")) {
        return {
          reply: formatDrugSideEffectsReply(drugInfo),
          quickReplies: ["📖 Liều dùng an toàn", "⚖️ So sánh với thuốc khác", "🔍 Xem sản phẩm có bán"],
          attachProducts: false,
        };
      }

      // Giải thích tổng quan về hoạt chất
      return {
        reply: formatDrugInformationReply(drugInfo),
        quickReplies: [
          `⚠️ Tác dụng phụ của ${drugInfo.name}`,
          `🔍 Tìm mua ${drugInfo.name} tại H4CARE`,
          "⚖️ So sánh Paracetamol và Ibuprofen",
        ],
        attachProducts: false,
      };
    }

    // Trường hợp không tìm thấy dữ liệu dược thư cho hoạt chất lạ
    return {
      reply: `Dạ hiện tại thông tin về dược chất **"${cleanMedicalText(rawMessage)}"** chưa có trong Dược thư thu gọn của H4CARE. Để đảm bảo an toàn, quý khách vui lòng đọc kỹ tờ hướng dẫn sử dụng đi kèm sản phẩm hoặc liên hệ Dược sĩ qua email: **duocsi@h4care.vn** nhé!`,
      quickReplies: ["💊 Tra cứu Paracetamol", "💊 Tra cứu Ibuprofen", "📞 Hotline Dược sĩ"],
      attachProducts: false,
    };
  }

  // 5. CHÀO HỎI (GREETING)
  if (intent === "GREETING") {
    const greetingName = extractedMemory?.userName ? ` bạn **${extractedMemory.userName}**` : "";
    return {
      reply: `Xin chào${greetingName}! Mình là **Trợ lý AI H4CARE** 🩺. Mình luôn sẵn sàng hỗ trợ bạn tư vấn sức khỏe ban đầu, tra cứu thông tin thuốc và giải đáp các thắc mắc về nhà thuốc. Bạn cần mình hỗ trợ gì hôm nay ạ?`,
      quickReplies: [
        "🔍 Tra cứu thông tin thuốc",
        "🤒 Tư vấn triệu chứng sức khỏe",
        "📦 Chính sách đổi trả thuốc",
        "🎧 Tư vấn trực tiếp với nhân viên",
      ],
      attachProducts: false,
    };
  }

  // 6. HƯỚNG DẪN MUA THUỐC KÊ ĐƠN (PRESCRIPTION_SUPPORT)
  if (intent === "PRESCRIPTION_SUPPORT") {
    return {
      reply: `Dạ đối với **Thuốc kê đơn (có ký hiệu Rx)**, theo quy định của Bộ Y Tế, H4CARE thực hiện quy trình bán thuốc có kiểm soát như sau:\n\n1. Quý khách vào trang sản phẩm hoặc mục **Gửi đơn thuốc** trên website.\n2. Chụp ảnh đơn thuốc rõ nét do Bác sĩ chỉ định (còn trong thời hạn hiệu lực) và tải lên hệ thống.\n3. Dược sĩ chuyên môn H4CARE sẽ liên hệ xác nhận liều dùng, tiền sử dị ứng và thẩm định chuyên môn.\n4. Sau khi đơn được Dược sĩ duyệt, đơn hàng sẽ được xuất kho và giao tận nơi.`,
      quickReplies: [
        "📤 Cổng tải đơn thuốc trực tuyến",
        "📞 Kênh tư vấn Dược sĩ",
        "🔍 Tìm thuốc không kê đơn (OTC)",
      ],
      attachProducts: false,
    };
  }

  // 7. HỖ TRỢ ĐƠN HÀNG & CHÍNH SÁCH (ORDER_SUPPORT)
  if (intent === "ORDER_SUPPORT") {
    // Chính sách ship
    if (norm.includes("phi ship") || norm.includes("phi giao hang") || norm.includes("van chuyen")) {
      return {
        reply: `Dạ về **Chính sách giao hàng và Phí ship tại H4CARE**:\n\n- **Thời gian giao hàng:** 1 - 3 ngày làm việc trên toàn quốc (có hỗ trợ hỏa tốc trong ngày tại khu vực nội thành).\n- **Phí giao hàng:**\n  + Nội tỉnh: Đồng giá **25.000 đ**\n  + Liên tỉnh: Đồng giá **35.000 đ**\n  + **Miễn phí giao hàng:** Áp dụng cho các đơn hàng từ 300.000 đ trở lên.\n- **Đổi trả hàng do lỗi vận chuyển / nhà thuốc:** H4CARE miễn phí 100% phí bưu tá thu hồi bưu phẩm.`,
        quickReplies: ["💳 Các phương thức thanh toán", "📦 Chính sách đổi trả 7 ngày", "🔍 Tra cứu đơn hàng của tôi"],
        attachProducts: false,
      };
    }

    // Tra cứu đơn hàng
    if (currentUser?.phone) {
      return {
        reply: `Dạ quý khách đang đăng nhập với số điện thoại **${currentUser.phone}** (${currentUser.fullName || "Khách hàng"}).\n\nQuý khách có thể xem toàn bộ lịch sử đơn hàng, hành trình vận chuyển và trạng thái thanh toán trực tiếp tại trang [Quản lý đơn hàng của tôi](/account).\n\n*Nếu cần hỗ trợ sửa địa chỉ hoặc hủy đơn trước khi xuất kho, quý khách vui lòng liên hệ hotline Dược sĩ: 1800 6828 để được xử lý kịp thời ạ.*`,
        quickReplies: ["📦 Xem lịch sử đơn hàng", "🚚 Khi nào đơn được giao?", "📞 Hotline Dược sĩ"],
        attachProducts: false,
      };
    }

    return {
      reply: `Dạ em xin giải thích các trạng thái đơn hàng trên hệ thống H4CARE:\n\n- **PENDING (Chờ xử lý):** Đơn hàng vừa đặt thành công, đang chờ hệ thống tiếp nhận.\n- **CONFIRMED (Đã xác nhận):** Đơn hàng hợp lệ, đã được nhân sự nhà thuốc xác nhận.\n- **PROCESSING (Đang chuẩn bị):** Dược sĩ đang kiểm tra hạn dùng và đóng gói bưu phẩm tại kho chuẩn GPP.\n- **SHIPPING (Đang giao hàng):** Đơn thuốc đang trên đường vận chuyển tới bạn.\n- **COMPLETED (Hoàn thành):** Đã nhận hàng thành công.\n\n💡 *Để tra cứu chính xác đơn hàng của mình, quý khách vui lòng [Đăng nhập](/login) hoặc cung cấp Mã đơn hàng ạ.*`,
      quickReplies: ["🔐 Đăng nhập tra cứu", "🚚 Phí giao hàng bao nhiêu?", "📦 Chính sách đổi trả 7 ngày"],
      attachProducts: false,
    };
  }

  // 8. TÌM KIẾM SẢN PHẨM / THUỐC CỤ THỂ (PRODUCT_SEARCH)
  if (intent === "PRODUCT_SEARCH") {
    if (products.length > 0) {
      return {
        reply: `Dạ H4CARE tìm thấy các sản phẩm phù hợp trong hệ thống:\n\n${products
          .map(
            (p) =>
              `• **[${p.name}](/product/${p.slug})**\n  - Phân loại: ${p.isPrescription ? "🔴 Thuốc kê đơn (Rx)" : "🟢 Thuốc không kê đơn (OTC) / TPCN"}\n  - Hoạt chất: \`${p.activeIngredient || "Theo công bố"}\`\n  - Giá bán: **${(p.salePrice || p.price).toLocaleString("vi-VN")} đ** (${p.stock > 0 ? "Còn hàng" : "Hết hàng"})\n  - Tóm tắt: ${p.shortDescription}`
          )
          .join("\n\n")}\n\nBạn có thể nhấp vào sản phẩm để xem chi tiết liều dùng hoặc thêm vào giỏ hàng nhé!`,
        quickReplies: [
          "📖 Cách dùng & Liều lượng",
          "💊 Thuốc có tác dụng phụ gì?",
          "🚚 Phí giao hàng bao nhiêu?",
        ],
        attachProducts: true,
      };
    }

    // Không tìm thấy sản phẩm
    const displayQ = searchQuery || cleanMedicalText(rawMessage);
    return {
      reply: `Dạ hiện tại H4CARE chưa tìm thấy sản phẩm nào trùng khớp với tên **"${displayQ}"** trong danh mục của nhà thuốc.\n\nNhằm đảm bảo an toàn tuyệt đối, hệ thống không tự tạo thông tin chưa qua kiểm chứng. Bạn có thể:\n- Thử tìm theo tên hoạt chất chính (ví dụ: *Paracetamol, Ibuprofen, Vitamin C...*)\n- Kiểm tra lại chính tả tên thuốc\n- Hoặc gửi yêu cầu đến email Dược sĩ: **duocsi@h4care.vn** để được hỗ trợ kiểm tra kho nhé!`,
      quickReplies: [
        "🔍 Tìm thuốc hạ sốt Paracetamol",
        "🔍 Tìm Vitamin C DHC",
        "🔍 Tìm men vi sinh tiêu hóa",
        "📞 Kênh tư vấn Dược sĩ",
      ],
      attachProducts: false,
    };
  }

  // 9. CÁC HỘI THOẠI KHÁC (GENERAL_CHAT / IDENTITY / GRATITUDE / CHITCHAT / MOOD / CLARIFICATION)
  const moodResult = detectUserMood(rawMessage);
  if (moodResult.hasMood && moodResult.replyHint) {
    return {
      reply: `${moodResult.replyHint}\n\nNếu bạn cảm thấy mệt mỏi trong người hoặc cần tư vấn về dinh dưỡng, sức khỏe, bạn cứ chia sẻ thêm với mình nhé!`,
      quickReplies: ["🤒 Tư vấn sức khỏe", "💊 Vitamin & Tăng đề kháng", "🎧 Trò chuyện với nhân viên"],
      attachProducts: false,
    };
  }

  // Khách hàng đính chính hoặc báo hiểu lầm
  if (/\b(khong phai y do|ko phai y do|khong phai the|ko phai the|y toi la|y minh la|y mk la|toi dang hoi|minh dang hoi|hieu nham roi|hieu sai roi)\b/i.test(norm)) {
    return {
      reply: `Dạ mình xin lỗi vì đã chưa nắm bắt đúng ý bạn! Bạn có thể nói rõ hơn một chút để mình hiểu đúng và hỗ trợ bạn chu đáo nhất được không ạ?`,
      quickReplies: ["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng bệnh", "🎧 Gặp nhân viên tư vấn"],
      attachProducts: false,
    };
  }

  if (norm.includes("ban la ai") || norm.includes("ban ten gi")) {
    return {
      reply: `Mình là **Trợ lý Dược sĩ AI H4CARE** – hệ thống tư vấn thông tin thuốc và hỗ trợ khách hàng của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE. Mình luôn sẵn sàng hỗ trợ bạn tra cứu thuốc chính hãng, tìm hiểu triệu chứng và hướng dẫn mua hàng 24/7.`,
      quickReplies: ["🔍 Tra cứu thông tin thuốc", "🚚 Chính sách giao hàng", "💬 Tư vấn triệu chứng sức khỏe"],
      attachProducts: false,
    };
  }

  if (norm.includes("cam on") || norm.includes("thank you")) {
    return {
      reply: `Dạ không có gì ạ! Rất vui được hỗ trợ bạn. Nếu bạn cần tìm hiểu thêm về bất kỳ loại thuốc hay sản phẩm chăm sóc sức khỏe nào, cứ nhắn cho mình nhé. Chúc bạn và gia đình luôn dồi dào sức khỏe!`,
      quickReplies: ["🔍 Tra cứu sản phẩm khác", "📦 Hướng dẫn đặt hàng", "💬 Kênh tư vấn Dược sĩ"],
      attachProducts: false,
    };
  }

  if (/\b(ban co khoe khong|co khoe khong|khoe khong|hom nay the nao)\b/i.test(norm)) {
    return {
      reply: `Cảm ơn bạn đã hỏi thăm! Mình là Trợ lý AI nên luôn tràn đầy năng lượng và sẵn sàng hỗ trợ bạn bất kỳ lúc nào. Hôm nay bạn cảm thấy thế nào, có cần mình giúp gì về sức khỏe hoặc tra cứu thuốc không ạ?`,
      quickReplies: ["🔍 Tra cứu thông tin thuốc", "🤒 Tư vấn triệu chứng sức khỏe", "🎧 Gặp nhân viên tư vấn"],
      attachProducts: false,
    };
  }

  const friendlyName = extractedMemory?.userName ? ` bạn **${extractedMemory.userName}**` : "";
  return {
    reply: `Dạ${friendlyName}, mình đang lắng nghe bạn đây ạ. Bạn có thể chia sẻ thêm câu hỏi hoặc vấn đề sức khỏe bạn đang quan tâm để mình hỗ trợ bạn được chu đáo nhất nhé!`,
    quickReplies: [
      "🔍 Tra cứu thông tin thuốc",
      "🤒 Tư vấn triệu chứng sức khỏe",
      "📦 Chính sách đổi trả & Giao hàng",
      "🎧 Gặp nhân viên tư vấn",
    ],
    attachProducts: false,
  };
}

/**
 * Hàm điều phối AI chính:
 * 1. Phân tích ngữ cảnh đàm thoại & Active Drug Entity.
 * 2. Nhận diện ý định (Intent) người dùng TRƯỚC TIÊN.
 * 3. CHỈ tìm kiếm dữ liệu sản phẩm khi ý định là PRODUCT_SEARCH.
 * 4. Gọi Gemini / OpenAI nếu có cấu hình; Fallback sang H4CARE Expert System an toàn 100%.
 */
export async function getAiChatResponse(
  message: string,
  history: MessageHistoryItem[] = [],
  options?: {
    currentUser?: any;
    contextProduct?: any;
    sessionId?: string;
    conversationId?: string;
    extractedMemory?: ExtractedMemory;
    attachments?: ChatAttachment[];
  }
): Promise<ChatResponse> {
  const cleanInput = cleanMedicalText(message).trim();

  // 1. Trích xuất và cập nhật Session Memory (Slot Extraction)
  const updatedMemory = extractUserMemory(cleanInput, options?.extractedMemory, history);
  if (options?.currentUser?.fullName && !updatedMemory.userName) {
    updatedMemory.userName = options.currentUser.fullName;
  }

  // Ghi nhận hình ảnh đính kèm vào memory phiên nếu có
  if (options?.attachments && options.attachments.length > 0) {
    const firstAtt = options.attachments[0];
    updatedMemory.lastAttachedImage = {
      fileName: firstAtt.fileName,
      url: firstAtt.url,
      description: cleanInput || "Ảnh đính kèm từ người dùng",
    };
  }

  // 2. Phân tích ngữ cảnh đàm thoại & Active Drug
  const convContext = buildConversationContext(history, cleanInput, updatedMemory);
  let activeDrug =
    updatedMemory.lastDiscussedProduct ||
    convContext.activeDrug ||
    (options?.contextProduct ? options.contextProduct.name : undefined);

  // Nhận diện câu hỏi quy chiếu hình ảnh ("thuốc trong ảnh", "ảnh lúc nãy", "ảnh vừa gửi")
  const normClean = removeVietnameseTones(cleanInput);
  if (
    /\b(trong anh|trong hinh|anh luc nay|anh vua gui|hinh luc nay|thuoc trong anh|thuoc trong hinh)\b/i.test(normClean)
  ) {
    if (updatedMemory.lastAttachedImage?.activeDrug) {
      activeDrug = updatedMemory.lastAttachedImage.activeDrug;
      updatedMemory.lastDiscussedProduct = updatedMemory.lastAttachedImage.activeDrug;
    } else if (updatedMemory.lastDiscussedProduct) {
      activeDrug = updatedMemory.lastDiscussedProduct;
    }
  }

  // Nhận diện câu hỏi quy chiếu đại từ về thuốc ("nó là gì", "thuốc này có tác dụng phụ không", "loại đầu tiên")
  const anaphoricDrug = resolveAnaphoricDrugQuery(
    cleanInput,
    updatedMemory.lastDiscussedProduct,
    updatedMemory.firstDiscussedProduct
  );
  if (anaphoricDrug.isAnaphoric && anaphoricDrug.targetDrug) {
    activeDrug = anaphoricDrug.targetDrug;
    updatedMemory.lastDiscussedProduct = anaphoricDrug.targetDrug;
  }

  // 3. KIỂM TRA RED FLAG NGUY HIỂM CẤP CỨU (P0 - EMERGENCY)
  const safetyAlert = detectRedFlag(cleanInput);
  if (safetyAlert) {
    const alertOutput = handleIntentDeterministically(
      "EMERGENCY",
      cleanInput,
      undefined,
      [],
      safetyAlert,
      activeDrug,
      history,
      options?.currentUser,
      updatedMemory
    );
    return {
      reply: alertOutput.reply,
      recommendedProducts: [],
      safetyAlert,
      quickReplies: alertOutput.quickReplies,
      providerUsed: "h4care_expert_system",
      modelUsed: "emergency-triage-v2",
      intentDetected: "EMERGENCY",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 4. KIỂM TRA CÂU HỎI TRUY VẤN MEMORY ("Tên tôi là gì?", "Bạn nhớ tên tôi không?", "Tôi bị gì nhỉ?", "Tôi nói tôi đau từ khi nào?", "Tôi bao nhiêu tuổi?")
  // NOTE: Bắt buộc kiểm tra truy vấn trước để các câu hỏi tên không bao giờ bị nhầm là câu xưng tên!
  const memoryAnswer = checkMemoryQuery(cleanInput, updatedMemory);
  if (memoryAnswer) {
    return {
      reply: memoryAnswer,
      quickReplies: [
        "🔍 Tra cứu thông tin thuốc",
        "🤒 Tôi muốn tư vấn triệu chứng",
        "🎧 Gặp nhân viên tư vấn",
      ],
      providerUsed: "h4care_memory_engine",
      intentDetected: "GENERAL_CHAT",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 5. KIỂM TRA NGƯỜI DÙNG GIỚI THIỆU HOẶC ĐỔI TÊN ("Tên tôi là Cường", "Giờ gọi tôi là Hùng nhé", "Không, tôi tên Hoàn cơ")
  const nameAction = detectNameAction(cleanInput, options?.extractedMemory);
  if (nameAction.hasName && nameAction.name) {
    updatedMemory.userName = nameAction.name;
    const replyText = nameAction.isRename
      ? `Dạ vâng! Mình đã cập nhật lại tên của bạn rồi nhé. Từ giờ mình sẽ gọi bạn là **${nameAction.name}**! Rất vui được tiếp tục hỗ trợ bạn, bạn đang cần mình tư vấn thêm vấn đề gì ạ?`
      : `Chào bạn **${nameAction.name}**! Rất vui được đồng hành và hỗ trợ bạn hôm nay. Bạn cần mình tư vấn về vấn đề sức khỏe hay tra cứu loại thuốc nào ạ?`;

    return {
      reply: replyText,
      quickReplies: [
        "🔍 Tra cứu thông tin thuốc",
        "🤒 Tư vấn triệu chứng sức khỏe",
        "🎧 Tư vấn trực tiếp với nhân viên",
      ],
      providerUsed: "h4care_memory_engine",
      intentDetected: "GENERAL_CHAT",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 5.1 KIỂM TRA NGƯỜI DÙNG CUNG CẤP HOẶC ĐIỀU CHỈNH TUỔI ("Tôi 39 tuổi", "mk 19t", "thực ra mk 20 r")
  const ageAction = detectAgeAction(cleanInput, options?.extractedMemory);
  if (ageAction.hasAge && ageAction.age) {
    updatedMemory.age = String(ageAction.age);
    const replyText = ageAction.isCorrection
      ? `Dạ vâng! Mình đã cập nhật lại tuổi của bạn là **${ageAction.age} tuổi** rồi nhé. Thông tin tuổi này rất hữu ích để mình đưa ra tư vấn liều dùng và giải pháp phù hợp nhất. Bạn đang cần mình hỗ trợ gì thêm không ạ?`
      : `Dạ mình đã ghi nhớ bạn **${ageAction.age} tuổi** rồi nhé. Bạn đang có triệu chứng khó chịu nào hoặc cần tra cứu loại thuốc gì không ạ?`;

    return {
      reply: replyText,
      quickReplies: [
        "🔍 Tra cứu thông tin thuốc",
        "🤒 Tư vấn triệu chứng sức khỏe",
        "🎧 Gặp nhân viên tư vấn",
      ],
      providerUsed: "h4care_memory_engine",
      intentDetected: "GENERAL_CHAT",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 5.2 KIỂM TRA CHIA SẺ TÂM TRẠNG / CẢM XÚC ("nay mk hơi buồn", "thấy lo quá")
  const moodAction = detectUserMood(cleanInput);
  if (moodAction.hasMood && moodAction.replyHint) {
    updatedMemory.userMood = moodAction.moodType;
    return {
      reply: `${moodAction.replyHint}\n\nNếu bạn cảm thấy mệt mỏi trong người hoặc cần tư vấn về dinh dưỡng, sức khỏe, bạn cứ chia sẻ thêm với mình nhé!`,
      quickReplies: [
        "🤒 Tư vấn sức khỏe",
        "💊 Vitamin & Tăng đề kháng",
        "🎧 Trò chuyện với nhân viên",
      ],
      providerUsed: "h4care_conversational_engine",
      intentDetected: "GENERAL_CHAT",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 6. Phân loại ý định của người dùng
  const intentResult = classifyUserIntent(cleanInput, history);
  const { intent, searchQuery } = intentResult;

  // 7. YÊU CẦU KẾT NỐI DƯỢC SĨ / NHÂN VIÊN THẬT (HUMAN_SUPPORT)
  if (intent === "HUMAN_SUPPORT" || updatedMemory.requestedRealPharmacist) {
    const expertOutput = handleIntentDeterministically(
      "HUMAN_SUPPORT",
      cleanInput,
      searchQuery,
      [],
      null,
      activeDrug,
      history,
      options?.currentUser,
      updatedMemory
    );
    const summaryParts: string[] = [];
    if (updatedMemory.userName) summaryParts.push(`Khách hàng: ${updatedMemory.userName}`);
    if (updatedMemory.symptoms && updatedMemory.symptoms.length > 0) {
      summaryParts.push(`Triệu chứng: ${updatedMemory.symptoms.join(", ")}`);
    }
    if (updatedMemory.symptomDuration) summaryParts.push(`Thời gian: ${updatedMemory.symptomDuration}`);
    if (updatedMemory.lastDiscussedProduct) summaryParts.push(`Thuốc quan tâm: ${updatedMemory.lastDiscussedProduct}`);
    summaryParts.push(`Yêu cầu: "${cleanInput}"`);

    return {
      reply: expertOutput.reply,
      recommendedProducts: [],
      quickReplies: expertOutput.quickReplies,
      providerUsed: "h4care_expert_system",
      intentDetected: "HUMAN_SUPPORT",
      isHumanSupport: true,
      handoffRequested: true,
      contextSummary: summaryParts.join(" | "),
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 8. TÌM KIẾM SẢN PHẨM (CHỈ KHI Ý ĐỊNH LÀ PRODUCT_SEARCH)
  let recommendedProducts: ChatProductItem[] = [];
  if (intent === "PRODUCT_SEARCH") {
    const q = searchQuery || extractProductSearchQuery(cleanInput);
    recommendedProducts = await searchMedicines(q, 4);
    if (q) {
      updatedMemory.lastDiscussedProduct = q;
    }
  }

  // 9. Cấu hình AI Provider ngoài (nếu có)
  const provider = (process.env.AI_PROVIDER || "").toLowerCase().trim();
  const geminiKey = process.env.GEMINI_API_KEY || (provider === "gemini" ? process.env.AI_API_KEY : "");
  const openAiKey = process.env.OPENAI_API_KEY || (provider === "openai" ? process.env.AI_API_KEY : "");
  const genericKey = process.env.AI_API_KEY || "";
  const timeoutMs = Number(process.env.AI_TIMEOUT_MS) || 25000;
  const hasRealAiConfigured = Boolean(geminiKey || openAiKey || (genericKey && provider !== "mock"));

  // 9.1 Nếu có tệp ảnh đính kèm nhưng chưa có Vision API Key -> Báo rõ trung thực, không giả vờ đã xem ảnh
  if (options?.attachments && options.attachments.length > 0 && !hasRealAiConfigured) {
    const att = options.attachments[0];
    const fileNameNotice = att.fileName ? `**"${att.fileName}"**` : "hình ảnh";
    return {
      reply: `Dạ em đã nhận được tệp ${fileNameNotice} của bạn.\n\n⚠️ **Thông báo hệ thống:** Hiện tại máy chủ H4CARE chưa kết nối mô hình Trí tuệ Thị giác AI (Vision AI) do chưa cấu hình khóa API. Do đó, Trợ lý AI tự động chưa thể quét và đọc trực tiếp nhãn thuốc/đơn thuốc từ hình ảnh lúc này.\n\n👉 **Giải pháp hỗ trợ:**\n- Bạn có thể gõ trực tiếp tên thuốc hoặc các thành phần nhìn thấy trên vỏ hộp vào ô chat để em tra cứu thông tin dược thư ngay.\n- Hoặc nhấp vào nút **"Tư vấn trực tiếp"** bên trên để gặp Dược sĩ chuyên môn H4CARE trực tiếp kiểm tra và tư vấn đơn thuốc giúp bạn nhé!`,
      recommendedProducts: [],
      quickReplies: [
        "🎧 Tư vấn trực tiếp với Dược sĩ",
        "🔍 Tra cứu Paracetamol",
        "🔍 Tra cứu Vitamin C",
      ],
      providerUsed: "h4care_expert_system",
      modelUsed: "vision-offline-notice",
      intentDetected: "GENERAL_CHAT",
      apiStatus: "offline_expert_system",
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 10. Xử lý trực tiếp các intent chuyên biệt để đảm bảo tuân thủ nghiêm ngặt chuẩn y khoa
  const isDirectDeterministicIntent =
    intent === "ORDER_SUPPORT" ||
    intent === "PRESCRIPTION_SUPPORT" ||
    !hasRealAiConfigured;

  if (isDirectDeterministicIntent) {
    const expertOutput = handleIntentDeterministically(
      intent,
      cleanInput,
      searchQuery,
      recommendedProducts,
      safetyAlert,
      activeDrug,
      history,
      options?.currentUser,
      updatedMemory
    );

    return {
      reply: expertOutput.reply,
      recommendedProducts: expertOutput.attachProducts ? recommendedProducts : [],
      safetyAlert: expertOutput.safetyAlert || safetyAlert || undefined,
      quickReplies: expertOutput.quickReplies,
      providerUsed: "h4care_expert_system",
      modelUsed: "gpp-rules-v2",
      intentDetected: intent,
      isHumanSupport: expertOutput.isHumanSupport,
      handoffRequested: expertOutput.handoffRequested,
      sessionId: options?.sessionId,
      extractedMemory: updatedMemory,
    };
  }

  // 11. Nếu có AI Provider thực sự cho DRUG_INFORMATION, HEALTH_SYMPTOM, PRODUCT_SEARCH, GENERAL_CHAT hoặc GREETING
  const productsContext = formatProductsContext(recommendedProducts);
  const contextSummary = buildConversationSummary(history, updatedMemory);
  const systemPrompt = buildSystemPrompt(productsContext, intent, updatedMemory, activeDrug, contextSummary);

  let lastApiError: { provider: string; message: string; isQuota: boolean; isAuth: boolean } | null = null;

  // TH1: Gọi Google Gemini API
  if (geminiKey || (provider === "gemini" && genericKey)) {
    const key = geminiKey || genericKey;
    const model = process.env.AI_MODEL || "gemini-1.5-flash";
    const startTime = Date.now();
    try {
      const reply = await callGemini(key, model, systemPrompt, history, cleanInput, timeoutMs, options?.attachments);
      const latencyMs = Date.now() - startTime;
      return {
        reply,
        recommendedProducts: intent === "PRODUCT_SEARCH" && recommendedProducts.length > 0 ? recommendedProducts : [],
        safetyAlert: safetyAlert || undefined,
        quickReplies: [
          "📖 Xem chi tiết sản phẩm",
          "📦 Hướng dẫn đặt mua",
          "💬 Tôi có câu hỏi khác",
        ],
        providerUsed: "google_gemini",
        modelUsed: model,
        intentDetected: intent,
        apiStatus: "real_llm_success",
        latencyMs,
        sessionId: options?.sessionId,
        extractedMemory: updatedMemory,
      };
    } catch (err: any) {
      const errMsg = sanitizeError(err?.message || String(err));
      const isQuota = errMsg.includes("429") || errMsg.includes("quota") || errMsg.includes("RESOURCE_EXHAUSTED") || errMsg.includes("rate_limit");
      const isAuth = errMsg.includes("401") || errMsg.includes("403") || errMsg.includes("API_KEY_INVALID") || errMsg.includes("not valid");
      lastApiError = { provider: "Google Gemini", message: errMsg, isQuota, isAuth };
      console.warn("[Chatbot AI] Gemini API lỗi, chuyển mạch sang H4CARE Fallback:", errMsg);
    }
  }

  // TH2: Gọi OpenAI API
  if (openAiKey || (provider === "openai" && genericKey) || provider === "ollama") {
    const key = openAiKey || genericKey;
    const model = process.env.AI_MODEL || (provider === "ollama" ? "qwen2.5:3b" : "gpt-4o-mini");
    const baseUrl =
      process.env.AI_BASE_URL ||
      (provider === "ollama" ? "http://localhost:11434/v1" : "https://api.openai.com/v1");
    const startTime = Date.now();

    try {
      const reply = await callOpenAiCompatible(key, baseUrl, model, systemPrompt, history, cleanInput, timeoutMs, options?.attachments);
      const latencyMs = Date.now() - startTime;
      return {
        reply,
        recommendedProducts: intent === "PRODUCT_SEARCH" && recommendedProducts.length > 0 ? recommendedProducts : [],
        safetyAlert: safetyAlert || undefined,
        quickReplies: [
          "📖 Xem chi tiết sản phẩm",
          "📦 Hướng dẫn đặt mua",
          "💬 Tôi có câu hỏi khác",
        ],
        providerUsed: "openai",
        modelUsed: model,
        intentDetected: intent,
        apiStatus: "real_llm_success",
        latencyMs,
        sessionId: options?.sessionId,
        extractedMemory: updatedMemory,
      };
    } catch (err: any) {
      const errMsg = sanitizeError(err?.message || String(err));
      const isQuota = errMsg.includes("429") || errMsg.includes("quota") || errMsg.includes("insufficient_quota") || errMsg.includes("rate_limit");
      const isAuth = errMsg.includes("401") || errMsg.includes("403") || errMsg.includes("Incorrect API key");
      lastApiError = { provider: "OpenAI", message: errMsg, isQuota, isAuth };
      console.warn("[Chatbot AI] OpenAI API lỗi, chuyển mạch sang H4CARE Fallback:", errMsg);
    }
  }

  // Chuyển mạch an toàn sang H4CARE Expert System nếu các Provider ngoài gặp sự cố hoặc chưa cấu hình
  const fallbackOutput = handleIntentDeterministically(
    intent,
    cleanInput,
    searchQuery,
    recommendedProducts,
    safetyAlert,
    activeDrug,
    history,
    options?.currentUser,
    updatedMemory
  );

  let statusNotice = "";
  let apiStatus: "offline_expert_system" | "quota_exceeded" | "api_error" = "offline_expert_system";

  if (lastApiError) {
    if (lastApiError.isQuota) {
      apiStatus = "quota_exceeded";
      statusNotice = `\n\n> ⚠️ **Thông báo hệ thống:** Mô hình AI ngoài (${lastApiError.provider}) đang tạm thời hết hạn mức sử dụng (Quota / Rate Limit). Hệ thống đã chuyển mạch sang Trợ lý Dược khoa H4CARE dự phòng để duy trì hỗ trợ cho bạn.`;
    } else if (lastApiError.isAuth) {
      apiStatus = "api_error";
      statusNotice = `\n\n> ⚠️ **Thông báo hệ thống:** API Key của mô hình AI (${lastApiError.provider}) chưa hợp lệ hoặc đã hết hạn. Hệ thống đang phản hồi bằng Trợ lý Dược khoa H4CARE dự phòng.`;
    } else {
      apiStatus = "api_error";
      statusNotice = `\n\n> ℹ️ **Thông báo hệ thống:** Kết nối tới mô hình AI ngoài (${lastApiError.provider}) bị gián đoạn. Câu trả lời này được cung cấp bởi Trợ lý Dược khoa H4CARE dự phòng.`;
    }
  }

  return {
    reply: statusNotice ? `${fallbackOutput.reply}${statusNotice}` : fallbackOutput.reply,
    recommendedProducts: fallbackOutput.attachProducts ? recommendedProducts : [],
    safetyAlert: fallbackOutput.safetyAlert || safetyAlert || undefined,
    quickReplies: fallbackOutput.quickReplies,
    providerUsed: lastApiError ? `${lastApiError.provider.toLowerCase().replace(/\s+/g, "_")}_fallback` : "h4care_expert_system",
    modelUsed: lastApiError ? "fallback-on-api-error" : "fallback-v2",
    intentDetected: intent,
    apiStatus,
    apiErrorDetail: lastApiError
      ? lastApiError.isQuota
        ? "Quota Exceeded (HTTP 429)"
        : lastApiError.isAuth
        ? "Invalid/Unauthorized API Key (HTTP 401/403)"
        : "API Connection Error"
      : undefined,
    isHumanSupport: fallbackOutput.isHumanSupport,
    handoffRequested: fallbackOutput.handoffRequested,
    sessionId: options?.sessionId,
    extractedMemory: updatedMemory,
  };
}
