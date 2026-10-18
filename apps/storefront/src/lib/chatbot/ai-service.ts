import {
  RED_FLAG_SYMPTOMS,
  STORE_POLICIES_INFO,
  SYMPTOM_TRIAGE_GUIDELINES,
} from "./knowledge-base";
import { searchMedicines, formatProductsContext, removeVietnameseTones } from "./product-search";
import { classifyUserIntent, extractProductSearchQuery } from "./intent";
import { cleanMedicalText } from "./sanitizer";
import { buildConversationContext, extractActiveDrugFromHistory } from "./context-tracker";
import { handleSymptomTriage } from "./symptom-triage";
import {
  findDrugKnowledge,
  formatDrugInformationReply,
  formatDrugSideEffectsReply,
  formatDrugComparisonReply,
  DRUG_KNOWLEDGE_BASE,
} from "./drug-knowledge";
import {
  ChatAttachment,
  ChatProductItem,
  ChatResponse,
  ChatSafetyAlert,
  StandardIntent,
} from "./types";

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
  activeDrug?: string
): string {
  return `Bạn là Trợ lý AI của H4CARE, chuyên hỗ trợ người dùng tìm hiểu thông tin thuốc, sản phẩm y tế và giải đáp thắc mắc về sức khỏe một cách khách quan, ân cần, an toàn và chính xác. Tránh các ngôn từ quảng cáo bán hàng, phóng đại hoặc khẩu hiệu thương mại.
Tuyệt đối KHÔNG sử dụng cụm từ "Tra cứu thuốc chính hãng" hay bất kỳ khẩu hiệu tiếp thị nào.
Không lặp lại câu chào sau mỗi tin nhắn.

=== LỜI CHÀO MẶC ĐỊNH CHUẨN MỰC (CHỈ DÙNG KHI NGƯỜI DÙNG CHÀO HỎI BAN ĐẦU) ===
"Chào bạn! Mình là trợ lý AI của H4CARE. Mình có thể hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp các thắc mắc về sức khỏe.

Bạn cần mình hỗ trợ điều gì hôm nay?"

=== QUY TẮC Y TẾ VÀ AN TOÀN BẮT BUỘC ===
1. Khi người dùng mô tả triệu chứng sức khỏe:
   - ĐÂY LÀ TƯ VẤN SỨC KHỎE, TUYỆT ĐỐI KHÔNG TỰ ĐỘNG GỢI Ý DANH SÁCH THUỐC MUA SẮM.
   - CHỈ HỎI ĐÚNG MỘT CÂU TRỌNG TÂM mỗi lượt để làm rõ tình trạng (thời gian xuất hiện -> vị trí -> triệu chứng cảnh báo kèm theo).
   - Ghi nhớ câu trả lời trước đó, KHÔNG hỏi lại những thông tin người dùng đã nói (ví dụ đã nói "từ hôm qua" thì không hỏi lại thời gian).
   - Nếu phát hiện dấu hiệu nguy hiểm (ngất, khó thở, đau thắt ngực, sốt cao co giật, nôn ra máu, đau hố chậu phải kèm sốt nghi ruột thừa) -> Lập tức cảnh báo khẩn cấp và khuyên đi khám/gọi 115 ngay.
   - Không kết luận chắc chắn bệnh, không tự kê đơn thuốc điều trị.

2. Khi người dùng hỏi thông tin thuốc (Paracetamol, Ibuprofen, Vitamin C...):
   - Giải thích rõ hoạt chất, công dụng, chống chỉ định, cảnh báo quá liều (đặc biệt độc tính gan của Paracetamol khi dùng > 4g/ngày).
   - Trả lời trung thực, khách quan theo Dược thư Quốc gia. Không tự cá nhân hóa liều.

3. Khi người dùng hỏi đại từ ("thuốc đó", "loại này", "nó"):
   - Đang đề cập đến: ${activeDrug || "thuốc vừa được thảo luận trong lịch sử"}. Trả lời đúng trọng tâm về thuốc đó.

4. Khi người dùng muốn gặp Dược sĩ thật:
   - Thông báo rõ ràng kênh kết nối chính thức: Hotline Dược sĩ 1800 6828 (8:00 - 21:00, miễn phí) hoặc email duocsi@h4care.vn. Không giả mạo có người thật chat trực tiếp 24/7.

=== DỮ LIỆU SẢN PHẨM H4CARE ĐÃ XÁC MINH (CHỈ DÙNG KHI Ý ĐỊNH LÀ PRODUCT_SEARCH) ===
${productsContext}

=== NGÔN NGỮ ===
Tiếng Việt chuẩn y khoa, tự nhiên, ân cần, ngắn gọn, không sinh mã HTML thô hay ký tự u003c.`;
}

/**
 * Gọi Google Gemini API với luân phiên turn role chuẩn
 */
async function callGemini(
  apiKey: string,
  model: string,
  systemPrompt: string,
  history: MessageHistoryItem[],
  currentMessage: string,
  timeoutMs: number
): Promise<string> {
  let targetModel =
    model === "gemini-1.5-flash" || model === "gemini-2.0-flash" || model === "gemini-2.5-flash"
      ? "gemini-3.5-flash"
      : model;

  const rawContents = [
    ...history.slice(-8).map((m) => ({
      role: m.role === "assistant" ? "model" : "user",
      text: cleanMedicalText(m.content),
    })),
    {
      role: "user",
      text: cleanMedicalText(currentMessage),
    },
  ];

  const firstUserIdx = rawContents.findIndex((c) => c.role === "user");
  const validTurns =
    firstUserIdx >= 0
      ? rawContents.slice(firstUserIdx)
      : [{ role: "user", text: cleanMedicalText(currentMessage) }];

  const contents: Array<{ role: string; parts: Array<{ text: string }> }> = [];
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

  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const postPayload = {
      systemInstruction: {
        parts: [{ text: systemPrompt }],
      },
      contents,
      generationConfig: {
        temperature: 0.2,
        maxOutputTokens: 800,
      },
    };

    let res = await fetch(
      `https://generativelanguage.googleapis.com/v1beta/models/${targetModel}:generateContent?key=${apiKey}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(postPayload),
        signal: controller.signal,
      }
    );

    // Tự động thử fallback sang gemini-3.5-flash nếu model cũ bị 404 deprecated
    if (res.status === 404 && targetModel !== "gemini-3.5-flash") {
      targetModel = "gemini-3.5-flash";
      res = await fetch(
        `https://generativelanguage.googleapis.com/v1beta/models/${targetModel}:generateContent?key=${apiKey}`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(postPayload),
          signal: controller.signal,
        }
      );
    }

    clearTimeout(timer);

    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`Gemini API HTTP ${res.status}: ${errText}`);
    }

    const data = await res.json();
    const text = data.candidates?.[0]?.content?.parts?.[0]?.text;
    if (!text) {
      throw new Error("Phản hồi từ Gemini rỗng");
    }
    return cleanMedicalText(text);
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Gọi OpenAI API
 */
async function callOpenAiCompatible(
  apiKey: string,
  baseUrl: string,
  model: string,
  systemPrompt: string,
  history: MessageHistoryItem[],
  currentMessage: string,
  timeoutMs: number
): Promise<string> {
  const url = `${baseUrl.replace(/\/+$/, "")}/chat/completions`;

  const messages = [
    { role: "system", content: systemPrompt },
    ...history.slice(-6).map((m) => ({
      role: m.role,
      content: cleanMedicalText(m.content),
    })),
    { role: "user", content: cleanMedicalText(currentMessage) },
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
      throw new Error(`OpenAI API HTTP ${res.status}: ${errText}`);
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
  currentUser?: any
): { reply: string; quickReplies: string[]; attachProducts: boolean; safetyAlert?: ChatSafetyAlert; isHumanSupport?: boolean } {
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
    return {
      reply: `Dạ hiện tại em là **Trợ lý Dược sĩ AI H4CARE**, không thể chuyển máy nói chuyện trực tiếp với nhân sự thật qua cửa sổ chat này.\n\nĐể được kết nối và nhận tư vấn chuyên môn trực tiếp từ **Dược sĩ Đại học H4CARE**, quý khách vui lòng liên hệ qua các kênh chính thức:\n- 📞 **Hotline Dược sĩ tư vấn:** **1800 6828** (Miễn phí cước gọi, làm việc từ 8:00 - 21:00 hàng ngày).\n- 📧 **Hòm thư Dược sĩ thẩm định:** **duocsi@h4care.vn** (phản hồi trong vòng 30 - 60 phút).\n- 🏥 **Tư vấn trực tiếp tại quầy:** Tại tất cả các cơ sở Nhà thuốc H4CARE chuẩn GPP trên toàn quốc.\n\n💡 *Nếu quý khách có thắc mắc về liều dùng, thành phần hoặc thông tin thuốc cần tra cứu nhanh, quý khách cứ nhắn tại đây để em hỗ trợ giải đáp tức thì nhé ạ!*`,
      quickReplies: ["📞 Gọi hotline 1800 6828", "📤 Gửi ảnh đơn thuốc", "💬 Tôi có câu hỏi khác"],
      attachProducts: false,
      isHumanSupport: true,
    };
  }

  // 3. TƯ VẤN TRIỆU CHỨNG SỨC KHỎE (HEALTH_SYMPTOM - Single Question Triage)
  if (intent === "HEALTH_SYMPTOM") {
    const convContext = buildConversationContext(history, rawMessage);
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
    return {
      reply: `Chào bạn! Mình là trợ lý AI của H4CARE. Mình có thể hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp các thắc mắc về sức khỏe.\n\nBạn cần mình hỗ trợ điều gì hôm nay?`,
      quickReplies: [],
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

  // 9. CÁC HỘI THOẠI KHÁC (GENERAL_CHAT / IDENTITY / GRATITUDE / CHITCHAT)
  if (norm.includes("ban la ai") || norm.includes("ban ten gi")) {
    return {
      reply: `Mình là **Trợ lý AI H4CARE**. Mình có thể hỗ trợ bạn tìm hiểu thông tin thuốc, sản phẩm và giải đáp các thắc mắc về sức khỏe. Bạn cần mình hỗ trợ điều gì hôm nay?`,
      quickReplies: [],
      attachProducts: false,
    };
  }

  if (norm.includes("cam on") || norm.includes("thank you")) {
    return {
      reply: `Dạ không có gì ạ! Rất vui được hỗ trợ bạn. Nếu bạn cần tìm hiểu thêm về bất kỳ loại thuốc hay sản phẩm chăm sóc sức khỏe nào, cứ nhắn cho mình nhé. Chúc bạn và gia đình luôn dồi dào sức khỏe!`,
      quickReplies: [],
      attachProducts: false,
    };
  }

  return {
    reply: `Dạ mình chưa hiểu rõ câu hỏi của bạn. Bạn có thể diễn đạt lại hoặc cho mình biết bạn đang cần tìm thuốc hay tư vấn triệu chứng gì không ạ?`,
    quickReplies: [],
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
    attachments?: ChatAttachment[];
    conversationId?: string;
    sessionId?: string;
    extractedMemory?: any;
  }
): Promise<ChatResponse> {
  const cleanInput = cleanMedicalText(message).trim();
  const attachments = options?.attachments || [];

  // 1. Phân tích ngữ cảnh đa lượt
  const convContext = buildConversationContext(history, cleanInput);
  const activeDrug = convContext.activeDrug || (options?.contextProduct ? options.contextProduct.name : undefined);

  // 2. Phân loại ý định của người dùng TRƯỚC TIÊN
  const intentResult = classifyUserIntent(cleanInput, history);
  const { intent, searchQuery, drugQuery } = intentResult;

  // 3. Kiểm tra Red Flag cấp cứu
  const safetyAlert = detectRedFlag(cleanInput);

  // 4. CHỈ tìm kiếm sản phẩm khi câu hỏi thực sự là tìm thuốc / mua thuốc
  let recommendedProducts: ChatProductItem[] = [];
  if (intent === "PRODUCT_SEARCH") {
    const q = searchQuery || extractProductSearchQuery(cleanInput);
    recommendedProducts = await searchMedicines(q, 4);
  }

  // 5. Kiểm tra cấu hình AI Provider
  const provider = (process.env.AI_PROVIDER || "").toLowerCase().trim();
  const geminiKey = process.env.GEMINI_API_KEY || (provider === "gemini" ? process.env.AI_API_KEY : "");
  const openAiKey = process.env.OPENAI_API_KEY || (provider === "openai" ? process.env.AI_API_KEY : "");
  const genericKey = process.env.AI_API_KEY || "";
  const timeoutMs = Number(process.env.AI_TIMEOUT_MS) || 25000;

  const hasRealAiConfigured = Boolean(geminiKey || openAiKey || (genericKey && provider !== "mock"));

  // 6. Xử lý trực tiếp các intent chuyên biệt để đảm bảo tuân thủ nghiêm ngặt chuẩn y khoa
  const isDirectDeterministicIntent =
    intent === "EMERGENCY" ||
    intent === "HUMAN_SUPPORT" ||
    intent === "GREETING" ||
    intent === "ORDER_SUPPORT" ||
    intent === "PRESCRIPTION_SUPPORT" ||
    intent === "GENERAL_CHAT" ||
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
      options?.currentUser
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
    };
  }

  // 7. Nếu có AI Provider thực sự cho DRUG_INFORMATION, HEALTH_SYMPTOM hoặc PRODUCT_SEARCH
  const productsContext = formatProductsContext(recommendedProducts);
  const systemPrompt = buildSystemPrompt(productsContext, intent, activeDrug);

  // TH1: Gọi Google Gemini API
  if (geminiKey || (provider === "gemini" && genericKey)) {
    const key = geminiKey || genericKey;
    const model = process.env.AI_MODEL || "gemini-3.5-flash";
    try {
      const reply = await callGemini(key, model, systemPrompt, history, cleanInput, timeoutMs);
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
      };
    } catch (err: any) {
      console.warn("[Chatbot AI] Gemini API lỗi, chuyển mạch sang H4CARE Fallback:", err.message);
    }
  }

  // TH2: Gọi OpenAI API
  if (openAiKey || (provider === "openai" && genericKey) || provider === "ollama") {
    const key = openAiKey || genericKey;
    const model = process.env.AI_MODEL || (provider === "ollama" ? "qwen2.5:3b" : "gpt-4o-mini");
    const baseUrl =
      process.env.AI_BASE_URL ||
      (provider === "ollama" ? "http://localhost:11434/v1" : "https://api.openai.com/v1");

    try {
      const reply = await callOpenAiCompatible(key, baseUrl, model, systemPrompt, history, cleanInput, timeoutMs);
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
      };
    } catch (err: any) {
      console.warn("[Chatbot AI] OpenAI API lỗi, chuyển mạch sang H4CARE Fallback:", err.message);
    }
  }

  // Chuyển mạch an toàn sang H4CARE Expert System nếu các Provider ngoài gặp sự cố
  const fallbackOutput = handleIntentDeterministically(
    intent,
    cleanInput,
    searchQuery,
    recommendedProducts,
    safetyAlert,
    activeDrug,
    history,
    options?.currentUser
  );

  return {
    reply: fallbackOutput.reply,
    recommendedProducts: fallbackOutput.attachProducts ? recommendedProducts : [],
    safetyAlert: fallbackOutput.safetyAlert || safetyAlert || undefined,
    quickReplies: fallbackOutput.quickReplies,
    providerUsed: "h4care_expert_system",
    modelUsed: "fallback-v2",
    intentDetected: intent,
    isHumanSupport: fallbackOutput.isHumanSupport,
  };
}
