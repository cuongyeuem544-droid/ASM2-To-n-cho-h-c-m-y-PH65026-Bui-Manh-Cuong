import {
  RED_FLAG_SYMPTOMS,
  STORE_POLICIES_INFO,
  SYMPTOM_TRIAGE_GUIDELINES,
} from "./knowledge-base";
import { searchMedicines, formatProductsContext, removeVietnameseTones } from "./product-search";
import { classifyUserIntent, extractProductSearchQuery, UserIntent } from "./intent";
import { cleanMedicalText } from "./sanitizer";
import { ChatProductItem, ChatResponse, ChatSafetyAlert } from "./types";

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
      if (norm.includes(normKw)) {
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
function buildSystemPrompt(productsContext: string, intent: UserIntent): string {
  return `Bạn là "Trợ lý Dược sĩ AI H4CARE" - hệ thống tư vấn thông tin thuốc và chăm sóc khách hàng của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE.

=== THÔNG TIN NHÀ THUỐC H4CARE ===
- Kênh Dược sĩ: duocsi@h4care.vn (8:00 - 21:00 hàng ngày).
- Chính sách giao hàng: 1-3 ngày toàn quốc. Phí ship 25.000đ nội tỉnh, 35.000đ liên tỉnh. Đơn từ 300.000đ được hỗ trợ phí giao.
- Chính sách đổi trả: 07 ngày đổi trả thuốc OTC nguyên seal, TPCN, thiết bị y tế. Thuốc kê đơn (Rx) và hàng lạnh (2-8°C) KHÔNG nhận đổi trả theo Luật Dược. Miễn phí thu hồi nếu lỗi giao sai, bể vỡ hoặc hạn dùng < 6 tháng.
- Thanh toán: COD (tiền mặt khi nhận), Ví MoMo Sandbox, Chuyển khoản VietQR.
- Đặt thuốc kê đơn: Bắt buộc gửi đơn thuốc của bác sĩ qua cổng trực tuyến để Dược sĩ H4CARE thẩm định trước khi xuất kho.

=== DỮ LIỆU SẢN PHẨM H4CARE ĐÃ XÁC MINH (CHỈ SỬ DỤNG KHI CÂU HỎI HỎI VỀ THUỐC) ===
${productsContext}

=== NGUYÊN TẮC BẮT BUỘC ===
1. Khi người dùng chào hỏi ("hi", "xin chào") -> CHỈ chào lại ngắn gọn, giới thiệu bản thân và hỏi người dùng cần hỗ trợ gì. TUYỆT ĐỐI KHÔNG tự động liệt kê danh sách thuốc khi người dùng chỉ chào hỏi.
2. Khi người dùng hỏi tên bạn ("bạn là ai", "bạn tên gì") -> Giới thiệu là Trợ lý Dược sĩ H4CARE, KHÔNG đưa sản phẩm vào.
3. Khi người dùng cảm ơn -> Đáp lại lịch sự, chúc sức khỏe.
4. Khi người dùng hỏi triệu chứng ("đau đầu", "đau bụng", "sốt") -> KHÔNG chẩn đoán bệnh vội vàng, KHÔNG tự kê đơn. Hỏi ĐÚNG MỘT câu ngắn phù hợp để tìm hiểu thêm (độ tuổi, mức độ, thời gian bị). Nếu có dấu hiệu nguy hiểm khẩn cấp, nhắc nhở đi khám ngay.
5. Khi người dùng hỏi về thuốc cụ thể -> CHỈ sử dụng thông tin từ danh mục H4CARE đã xác minh ở trên. Không bịa đặt tên thuốc, giá hoặc tồn kho.
6. Ngôn ngữ: Tiếng Việt tự nhiên, chuẩn mực y khoa, không dùng từ ngữ thô tục, không sinh mã HTML thô hay ký tự u003c. Trả lời ngắn gọn, đúng trọng tâm câu hỏi.`;
}

/**
 * Gọi Google Gemini API
 */
async function callGemini(
  apiKey: string,
  model: string,
  systemPrompt: string,
  history: MessageHistoryItem[],
  currentMessage: string,
  timeoutMs: number
): Promise<string> {
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  // Chuẩn bị các lượt hội thoại, khử rác u003c/u0026
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

  // Gemini REST API bắt buộc contents[0].role phải là 'user'
  const firstUserIdx = rawContents.findIndex((c) => c.role === "user");
  const validTurns =
    firstUserIdx >= 0
      ? rawContents.slice(firstUserIdx)
      : [{ role: "user", text: cleanMedicalText(currentMessage) }];

  // Gộp các lượt cùng role liên tiếp để đảm bảo luân phiên user / model hợp lệ
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
  intent: UserIntent,
  rawMessage: string,
  searchQuery: string | undefined,
  products: ChatProductItem[],
  safetyAlert: ChatSafetyAlert | null
): { reply: string; quickReplies: string[]; attachProducts: boolean } {
  const norm = removeVietnameseTones(rawMessage);

  // 1. Dấu hiệu nguy hiểm (Red Flags)
  if (intent === "EMERGENCY_RED_FLAG" && safetyAlert) {
    return {
      reply: `🚨 **${safetyAlert.title}**\n\n${safetyAlert.message}\n\n👉 **HÀNH ĐỘNG CẦN THỰC HIỆN NGAY LẬP TỨC:**\n${safetyAlert.actionRequired}\n\n*H4CARE khuyến cáo: Tuyệt đối không tự ý mua hoặc uống thêm thuốc tại nhà khi xuất hiện dấu hiệu khẩn cấp này.*`,
      quickReplies: ["📞 Gọi cấp cứu 115", "🏥 Tìm bệnh viện gần nhất", "💬 Tôi cần hỏi vấn đề khác"],
      attachProducts: false,
    };
  }

  // 2. Chào hỏi (Greeting) - Đúng câu ví dụ yêu cầu:
  // "Xin chào! Mình là trợ lý H4CARE. Mình có thể giúp bạn tìm kiếm sản phẩm, tra cứu thông tin thuốc hoặc hướng dẫn mua hàng. Bạn cần hỗ trợ gì ạ?"
  if (intent === "GREETING") {
    return {
      reply: `Xin chào! Mình là trợ lý H4CARE. Mình có thể giúp bạn tìm kiếm sản phẩm, tra cứu thông tin thuốc hoặc hướng dẫn mua hàng. Bạn cần hỗ trợ gì ạ?`,
      quickReplies: [
        "🔍 Tra cứu Vitamin C",
        "💊 Tìm thuốc hạ sốt Panadol",
        "📦 Phí giao hàng bao nhiêu?",
        "📋 Chính sách đổi trả thuốc",
      ],
      attachProducts: false,
    };
  }

  // 3. Giới thiệu bản thân (Identity)
  if (intent === "IDENTITY") {
    return {
      reply: `Mình là **Trợ lý Dược sĩ AI H4CARE** – hệ thống tư vấn thông tin thuốc và hỗ trợ khách hàng của Hệ thống Nhà thuốc trực tuyến chuẩn GPP H4CARE. Mình luôn sẵn sàng hỗ trợ bạn tra cứu thuốc chính hãng, tìm hiểu triệu chứng và hướng dẫn mua hàng 24/7.`,
      quickReplies: [
        "🔍 Tra cứu thông tin thuốc",
        "🚚 Chính sách giao hàng",
        "💬 Tư vấn triệu chứng sức khỏe",
      ],
      attachProducts: false,
    };
  }

  // 4. Lời cảm ơn (Gratitude)
  if (intent === "GRATITUDE") {
    return {
      reply: `Dạ không có gì ạ! Rất vui được hỗ trợ bạn. Nếu bạn cần tìm hiểu thêm về bất kỳ loại thuốc hay sản phẩm chăm sóc sức khỏe nào, cứ nhắn cho mình nhé. Chúc bạn và gia đình luôn dồi dào sức khỏe!`,
      quickReplies: [
        "🔍 Tra cứu sản phẩm khác",
        "📦 Hướng dẫn đặt hàng",
        "💬 Kênh tư vấn Dược sĩ",
      ],
      attachProducts: false,
    };
  }

  // 5. Giao tiếp thông thường (Chitchat)
  if (intent === "CHITCHAT") {
    return {
      reply: `Dạ vâng! Nếu bạn có bất kỳ câu hỏi nào về thuốc, triệu chứng hoặc dịch vụ tại H4CARE, mình luôn sẵn sàng hỗ trợ bạn bất kỳ lúc nào nhé.`,
      quickReplies: ["🔍 Tìm thuốc", "📦 Kiểm tra đơn hàng", "🚚 Phí ship bao nhiêu"],
      attachProducts: false,
    };
  }

  // 6. Hỏi giá không rõ sản phẩm (Unclear Pricing)
  if (intent === "UNCLEAR_PRICING") {
    return {
      reply: `Bạn đang muốn hỏi giá của loại thuốc hay sản phẩm nào ạ? Bạn hãy cho mình xin tên thuốc hoặc hoạt chất cụ thể (ví dụ: *Panadol Extra, Efferalgan 500mg, Vitamin C DHC, Berocca...*) để mình tra cứu giá niêm yết chính xác trong hệ thống H4CARE nhé!`,
      quickReplies: [
        "💊 Giá Panadol Extra",
        "💊 Giá Efferalgan 500mg",
        "🍊 Giá Vitamin C DHC",
        "🔍 Tìm theo nhóm thuốc",
      ],
      attachProducts: false,
    };
  }

  // 7. Chính sách Giao hàng & Phí ship (Shipping Policy)
  if (intent === "SHIPPING_POLICY") {
    return {
      reply: `Dạ về **Chính sách giao hàng và Phí ship tại H4CARE**:\n\n- **Thời gian giao hàng:** 1 - 3 ngày làm việc trên toàn quốc (có hỗ trợ hỏa tốc trong ngày tại khu vực nội thành).\n- **Phí giao hàng:**\n  + Nội tỉnh: Đồng giá **25.000 đ**\n  + Liên tỉnh: Đồng giá **35.000 đ**\n  + **Miễn phí giao hàng:** Áp dụng cho các đơn hàng từ 300.000 đ trở lên.\n- **Đổi trả hàng do lỗi vận chuyển / nhà thuốc:** H4CARE miễn phí 100% phí bưu tá thu hồi bưu phẩm.`,
      quickReplies: [
        "💳 Các phương thức thanh toán",
        "📦 Chính sách đổi trả 7 ngày",
        "🔍 Tra cứu đơn hàng của tôi",
      ],
      attachProducts: false,
    };
  }

  // 8. Phương thức Thanh toán (Payment Policy)
  if (intent === "PAYMENT_POLICY") {
    return {
      reply: `Dạ tại H4CARE, quý khách có thể lựa chọn các phương thức thanh toán tiện lợi sau:\n\n1. **COD (Thanh toán khi nhận hàng):** Kiểm tra kiện hàng bưu phẩm và thanh toán tiền mặt trực tiếp cho nhân viên giao hàng.\n2. **Ví điện tử MoMo Sandbox:** Thanh toán số trực tuyến nhanh chóng, an toàn và tự động cập nhật trạng thái đơn.\n3. **Chuyển khoản VietQR:** Quét mã QR thanh toán qua ứng dụng mọi ngân hàng tại Việt Nam không mất phí.`,
      quickReplies: [
        "🚚 Phí giao hàng bao nhiêu?",
        "📦 Chính sách đổi trả thuốc",
        "💊 Hướng dẫn mua thuốc kê đơn",
      ],
      attachProducts: false,
    };
  }

  // 9. Chính sách Đổi trả & Hoàn tiền (Return Policy)
  if (intent === "RETURN_POLICY") {
    return {
      reply: `Dạ về **Chính sách đổi trả & hoàn tiền tại H4CARE (Chuẩn GPP Bộ Y Tế)**:\n\n- **Thời hạn đổi trả:** Trong vòng **07 ngày** kể từ ngày nhận hàng thành công.\n- **Sản phẩm áp dụng:** Thuốc không kê đơn (OTC), Thực phẩm chức năng, Thiết bị y tế còn nguyên tem niêm phong (seal).\n- **Sản phẩm KHÔNG nhận đổi trả:** Thuốc kê đơn (Rx) và Vaccine / Sinh phẩm lạnh (2°C - 8°C) theo quy định nghiêm ngặt của Luật Dược nhằm bảo đảm chất lượng.\n- **Thời gian hoàn tiền:** Trong vòng **24 giờ** qua MoMo hoặc chuyển khoản ngân hàng sau khi bưu phẩm được kho dược thẩm định.`,
      quickReplies: [
        "📦 Chi phí đổi trả ai chịu?",
        "💬 Gửi yêu cầu đổi trả",
        "🚚 Chính sách giao hàng",
      ],
      attachProducts: false,
    };
  }

  // 10. Hướng dẫn Mua thuốc kê đơn (Prescription Guide)
  if (intent === "PRESCRIPTION_GUIDE") {
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

  // 11. Trạng thái Đơn hàng (Order Status)
  if (intent === "ORDER_STATUS") {
    return {
      reply: `Dạ em xin giải thích các trạng thái đơn hàng trên hệ thống H4CARE:\n\n- **PENDING (Chờ xử lý):** Đơn hàng vừa đặt thành công, đang chờ hệ thống tiếp nhận.\n- **CONFIRMED (Đã xác nhận):** Đơn hàng hợp lệ, đã được nhân sự nhà thuốc xác nhận.\n- **PROCESSING (Đang chuẩn bị):** Dược sĩ đang kiểm tra hạn dùng và đóng gói bưu phẩm tại kho chuẩn GPP.\n- **SHIPPING (Đang giao hàng):** Đơn thuốc đang trên đường vận chuyển tới địa chỉ nhận của bạn.\n- **COMPLETED (Hoàn thành):** Bạn đã nhận hàng và hoàn tất đơn.\n- **CANCELLED (Đã hủy):** Đơn hàng đã bị hủy theo yêu cầu.\n\nQuý khách có thể kiểm tra chi tiết tại mục **Tài khoản > Lịch sử đơn hàng** ạ.`,
      quickReplies: [
        "🚚 Khi nào đơn hàng được giao?",
        "❌ Cách hủy đơn hàng",
        "💬 Hỗ trợ trực tiếp từ Dược sĩ",
      ],
      attachProducts: false,
    };
  }

  // 12. Hỗ trợ Tài khoản (Account Help)
  if (intent === "ACCOUNT_HELP") {
    return {
      reply: `Dạ để quản lý tài khoản hoặc đổi mật khẩu, bạn có thể thực hiện:\n\n- **Đăng nhập:** Vào mục [Đăng nhập](/login) bằng số điện thoại hoặc email đã đăng ký.\n- **Quên mật khẩu:** Chọn [Quên mật khẩu](/forgot-password) để nhận mã đặt lại mật khẩu an toàn.\n- **Xem thông tin cá nhân:** Vào mục [Tài khoản của tôi](/account) để cập nhật sổ địa chỉ và xem lịch sử đơn hàng.`,
      quickReplies: ["🔐 Đăng nhập", "📝 Đăng ký tài khoản", "📦 Xem lịch sử đơn hàng"],
      attachProducts: false,
    };
  }

  // 13. Tư vấn Triệu chứng sức khỏe (Symptom Consultation)
  if (intent === "SYMPTOM_CONSULTATION") {
    // Trường hợp hỏi về đau bụng
    if (norm.includes("dau bung")) {
      return {
        reply: `Chào bạn, tình trạng đau bụng có thể do nhiều nguyên nhân khác nhau (như rối loạn tiêu hóa, viêm dạ dày hoặc đại tràng). Bạn cho mình hỏi: **Cơn đau xuất hiện ở vị trí nào (vùng trên rốn, quanh rốn hay bụng dưới) và đau âm ỉ hay quặn từng cơn ạ?**\n\n*(Lưu ý: Nếu bạn bị đau dữ dội đột ngột, bụng cứng hoặc kèm sốt, nôn ra máu, bạn cần đến bệnh viện cấp cứu ngay nhé).*`,
        quickReplies: [
          "Đau vùng trên rốn (dạ dày)",
          "Đau quặn quanh rốn",
          "Đau âm ỉ bụng dưới",
          "Đau kèm tiêu chảy",
        ],
        attachProducts: false,
      };
    }

    // Trường hợp hỏi về đau đầu (như ví dụ "Tôi đau đầu 2 ngày")
    if (norm.includes("dau dau")) {
      return {
        reply: `Chào bạn, tình trạng đau đầu kéo dài cần được theo dõi cẩn thận. Bạn cho mình hỏi thêm: **Bạn đau ở mức độ nào (đau âm ỉ cả đầu hay đau nhói nửa đầu) và có kèm theo sốt, chóng mặt hay buồn nôn không ạ?** Người bệnh là người lớn hay trẻ em vậy ạ?`,
        quickReplies: [
          "Đau âm ỉ, không sốt (người lớn)",
          "Đau nửa đầu nhức nhối",
          "Đau đầu có kèm sốt",
          "Dành cho trẻ em",
        ],
        attachProducts: false,
      };
    }

    // Triệu chứng chung khác (sốt, ho, cảm cúm...)
    return {
      reply: `Chào bạn, mình đã ghi nhận triệu chứng của bạn. Để tư vấn chính xác và an toàn nhất, bạn cho mình hỏi: **Triệu chứng này xuất hiện được bao lâu rồi, và người bệnh bao nhiêu tuổi (người lớn hay trẻ nhỏ) ạ?**`,
      quickReplies: [
        "Mới bị từ hôm nay (người lớn)",
        "Đã bị 2-3 ngày nay",
        "Dành cho trẻ nhỏ",
        "Có kèm sốt cao",
      ],
      attachProducts: false,
    };
  }

  // 14. Tìm kiếm Sản phẩm / Thuốc cụ thể (Product Search)
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

    // Khi không tìm thấy sản phẩm trùng khớp
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

  // 15. Câu hỏi không rõ nghĩa hoặc mã HTML thô (Unclear Question)
  return {
    reply: `Dạ mình chưa hiểu rõ câu hỏi của bạn. Bạn có thể diễn đạt lại hoặc cho mình biết bạn đang cần tìm thuốc hay tư vấn triệu chứng gì không ạ?`,
    quickReplies: [
      "🔍 Tra cứu thông tin thuốc",
      "🤒 Tư vấn triệu chứng bệnh",
      "📦 Chính sách đổi trả",
      "🚚 Phí ship bao nhiêu",
    ],
    attachProducts: false,
  };
}

/**
 * Hàm điều phối AI chính:
 * 1. Nhận diện ý định (Intent) người dùng TRƯỚC TIÊN.
 * 2. CHỈ tìm kiếm dữ liệu sản phẩm khi ý định là PRODUCT_SEARCH.
 * 3. Nếu có cấu hình AI Provider (Gemini/OpenAI), gọi mô hình với prompt sạch, không rác HTML.
 * 4. Nếu không có key hoặc xảy ra sự cố, sử dụng Động cơ Chuyên gia H4CARE chính xác, an toàn 100%.
 */
export async function getAiChatResponse(
  message: string,
  history: MessageHistoryItem[] = []
): Promise<ChatResponse> {
  const cleanInput = cleanMedicalText(message).trim();

  // 1. Phân loại ý định của người dùng TRƯỚC TIÊN
  const intentResult = classifyUserIntent(cleanInput, history);
  const { intent, searchQuery } = intentResult;

  // 2. Kiểm tra Red Flag cấp cứu
  const safetyAlert = detectRedFlag(cleanInput);

  // 3. CHỈ tìm kiếm sản phẩm khi câu hỏi thực sự là tìm thuốc / mua thuốc
  let recommendedProducts: ChatProductItem[] = [];
  if (intent === "PRODUCT_SEARCH") {
    const q = searchQuery || extractProductSearchQuery(cleanInput);
    recommendedProducts = await searchMedicines(q, 4);
  }

  // 4. Kiểm tra cấu hình AI Provider
  const provider = (process.env.AI_PROVIDER || "").toLowerCase().trim();
  const geminiKey = process.env.GEMINI_API_KEY || (provider === "gemini" ? process.env.AI_API_KEY : "");
  const openAiKey = process.env.OPENAI_API_KEY || (provider === "openai" ? process.env.AI_API_KEY : "");
  const genericKey = process.env.AI_API_KEY || "";
  const timeoutMs = Number(process.env.AI_TIMEOUT_MS) || 25000;

  const hasRealAiConfigured = Boolean(geminiKey || openAiKey || (genericKey && provider !== "mock"));

  // 5. Nếu câu hỏi là giao tiếp cơ bản (GREETING, IDENTITY, GRATITUDE, CHITCHAT, UNCLEAR_PRICING, EMERGENCY_RED_FLAG, POLICIES)
  // Xử lý trực tiếp và nhanh chóng, bảo đảm câu trả lời chuẩn xác 100%, không bị ảo giác hoặc rò rỉ dữ liệu ngoài ngữ cảnh
  const isDirectDeterministicIntent =
    intent === "GREETING" ||
    intent === "IDENTITY" ||
    intent === "GRATITUDE" ||
    intent === "CHITCHAT" ||
    intent === "UNCLEAR_PRICING" ||
    intent === "SHIPPING_POLICY" ||
    intent === "PAYMENT_POLICY" ||
    intent === "RETURN_POLICY" ||
    intent === "ORDER_STATUS" ||
    intent === "PRESCRIPTION_GUIDE" ||
    intent === "ACCOUNT_HELP" ||
    intent === "UNCLEAR_QUESTION" ||
    intent === "EMERGENCY_RED_FLAG";

  if (isDirectDeterministicIntent || !hasRealAiConfigured) {
    const expertOutput = handleIntentDeterministically(
      intent,
      cleanInput,
      searchQuery,
      recommendedProducts,
      safetyAlert
    );

    return {
      reply: expertOutput.reply,
      recommendedProducts: expertOutput.attachProducts ? recommendedProducts : [],
      safetyAlert: safetyAlert || undefined,
      quickReplies: expertOutput.quickReplies,
      providerUsed: "h4care_expert_system",
      modelUsed: "gpp-rules-v2",
    };
  }

  // 6. Nếu ý định là PRODUCT_SEARCH hoặc SYMPTOM_CONSULTATION VÀ có AI Provider thực sự
  const productsContext = formatProductsContext(recommendedProducts);
  const systemPrompt = buildSystemPrompt(productsContext, intent);

  // TH1: Gọi Google Gemini API
  if (geminiKey || (provider === "gemini" && genericKey)) {
    const key = geminiKey || genericKey;
    const model = process.env.AI_MODEL || "gemini-1.5-flash";
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
    safetyAlert
  );

  return {
    reply: fallbackOutput.reply,
    recommendedProducts: fallbackOutput.attachProducts ? recommendedProducts : [],
    safetyAlert: safetyAlert || undefined,
    quickReplies: fallbackOutput.quickReplies,
    providerUsed: "h4care_expert_system",
    modelUsed: "fallback-v2",
  };
}
