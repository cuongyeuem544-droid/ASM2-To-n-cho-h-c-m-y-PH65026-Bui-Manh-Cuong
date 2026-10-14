import { SymptomContext, ChatSafetyAlert } from "./types";
import { removeVietnameseTones } from "./product-search";

export interface SymptomTriageResponse {
  reply: string;
  quickReplies: string[];
  safetyAlert?: ChatSafetyAlert;
  isEmergency: boolean;
}

/**
 * Động cơ Tư vấn Triệu chứng Sức khỏe Đa lượt (Multi-turn Clinical Symptom Triage)
 * - Tuân thủ nguyên tắc CHỈ HỎI ĐÚNG MỘT CÂU TRỌNG TÂM mỗi lượt
 * - Không hỏi lại thông tin người dùng đã cung cấp
 * - Phát hiện dấu hiệu nguy hiểm (cấp cứu P0: ngất, bụng ngoại khoa, viêm ruột thừa cấp)
 * - Hướng dẫn đi khám kịp thời, tuyệt đối không tự kê đơn thuốc che triệu chứng
 */
export function handleSymptomTriage(
  ctx: SymptomContext,
  rawMessage: string
): SymptomTriageResponse {
  const norm = removeVietnameseTones(rawMessage);

  // 1. KIỂM TRA TÌNH HUỐNG CẤP CỨU P0 (Ngất, mất ý thức, đau dữ dội kèm ngất)
  if (
    norm.includes("ngat") ||
    norm.includes("bat tinh") ||
    norm.includes("hon me") ||
    ctx.accompanying?.includes("ngất xỉu")
  ) {
    const alert: ChatSafetyAlert = {
      level: "emergency",
      title: "🚨 CẢNH BÁO CẤP CỨU KHẨN CẤP (P0): MẤT Ý THỨC / NGẤT XỈU",
      message: "Cơn đau kèm theo ngất xỉu hoặc mất ý thức là dấu hiệu cấp cứu y khoa tối khẩn cấp (nguy cơ sốc mất máu, vỡ tạng trong ổ bụng hoặc tai biến tim mạch nguy kịch).",
      actionRequired: "Gọi ngay 115 hoặc khẩn cấp đưa đến phòng Cấp cứu bệnh viện gần nhất!",
      emergencyNumber: "115",
    };

    return {
      reply: `🚨 **CẢNH BÁO CẤP CỨU Y KHOA KHẨN CẤP (P0)**\n\nBạn hoặc người thân bị ngất xỉu / mất ý thức kèm theo cơn đau là dấu hiệu nguy kịch đe dọa trực tiếp tính mạng (có thể do xuất huyết nội tạng, vỡ phình mạch hoặc trụy tuần hoàn).\n\n👉 **HÀNH ĐỘNG CẦN THỰC HIỆN NGAY LẬP TỨC:**\n1. **Gọi cấp cứu 115 ngay lập tức** hoặc nhờ người xung quanh hỗ trợ đưa đến khoa Cấp cứu bệnh viện gần nhất.\n2. Đặt người bệnh nằm nghiêng an toàn, nới lỏng cổ áo và thắt lưng để thông thoáng đường thở.\n3. **TUYỆT ĐỐI KHÔNG** cho ăn uống, không bấm huyệt tùy tiện và **KHÔNG** tự ý cho uống bất kỳ loại thuốc giảm đau nào.`,
      quickReplies: ["📞 Gọi cấp cứu 115", "🏥 Tìm bệnh viện gần nhất"],
      safetyAlert: alert,
      isEmergency: true,
    };
  }

  // 2. NẾU PHÁT HIỆN DẤU HIỆU VIÊM RUỘT THỪA CẤP (Đau bụng dưới bên phải + sốt/nôn/đau tăng khi đi lại)
  if (ctx.hasRedFlag && ctx.redFlagReason?.includes("ruột thừa")) {
    const alert: ChatSafetyAlert = {
      level: "emergency",
      title: "🚨 CẢNH BÁO NGUY CƠ VIÊM RUỘT THỪA CẤP",
      message: "Cơn đau vùng bụng dưới bên phải (hố chậu phải) kèm theo sốt, buồn nôn hoặc đau nhói tăng khi đi lại là các dấu hiệu kinh điển của Viêm ruột thừa cấp cần can thiệp ngoại khoa kịp thời.",
      actionRequired: "Cần đến ngay cơ sở y tế / bệnh viện gần nhất để siêu âm ổ bụng và xét nghiệm máu cấp cứu.",
      emergencyNumber: "115",
    };

    return {
      reply: `🚨 **CẢNH BÁO Y TẾ: NGUY CƠ VIÊM RUỘT THỪA CẤP CẦN ĐI KHÁM NGAY**\n\nCác thông tin bạn vừa chia sẻ (đau bụng dưới bên phải, kèm ${ctx.accompanying?.join(", ") || "dấu hiệu tăng nặng"}) rất điển hình cho **Viêm ruột thừa cấp** hoặc bệnh lý ngoại khoa ổ bụng.\n\n👉 **LỜI KHUYÊN DƯỢC SĨ:**\n- **Đến ngay bệnh viện hoặc cơ sở y tế có khoa Ngoại gần nhất** để bác sĩ thăm khám, siêu âm và làm xét nghiệm máu trước khi ruột thừa có nguy cơ vỡ mủ.\n- **TUYỆT ĐỐI KHÔNG** tự ý mua thuốc giảm đau, hạ sốt hay chườm nóng lên bụng vì sẽ làm mất triệu chứng cảnh báo của bác sĩ ngoại khoa.\n- Nhịn ăn uống tạm thời để chuẩn bị nếu cần can thiệp y tế.`,
      quickReplies: ["🏥 Tìm cơ sở y tế gần nhất", "📞 Gọi cấp cứu 115"],
      safetyAlert: alert,
      isEmergency: true,
    };
  }

  // 3. KỊCH BẢN ĐAU BỤNG / ĐAU BỤNG DƯỚI (THEO ĐÚNG VÍ DỤ BẮT BUỘC)
  if (ctx.primarySymptom?.includes("bụng")) {
    // Bước 1: Chưa biết thời gian xuất hiện
    if (!ctx.duration) {
      return {
        reply: `Mình có thể hỏi thêm vài thông tin để hỗ trợ bạn nhé. **Bạn ${ctx.primarySymptom} từ khi nào?**`,
        quickReplies: ["Từ hôm qua", "Mới bị từ sáng nay", "Đã bị 2-3 ngày nay", "Bị cả tuần nay"],
        isEmergency: false,
      };
    }

    // Bước 2: Đã biết thời gian, nhưng chưa biết vị trí cụ thể
    if (!ctx.location) {
      return {
        reply: `Dạ mình đã ghi nhận bạn bị ${ctx.duration}. **Cơn đau chủ yếu ở bên trái, bên phải hay giữa bụng dưới?**`,
        quickReplies: ["Bên phải", "Bên trái", "Ở giữa bụng dưới", "Đau lan tỏa khắp bụng"],
        isEmergency: false,
      };
    }

    // Bước 3: Đã biết vị trí bên phải -> Hỏi triệu chứng cảnh báo ngoại khoa
    if (ctx.location === "bên phải" && ctx.accompanying?.length === 0) {
      return {
        reply: `**Bạn có bị sốt, nôn hoặc đau tăng lên khi đi lại không?**`,
        quickReplies: ["Có sốt nhẹ và buồn nôn", "Có đau nhói khi đi lại", "Không sốt, không nôn", "Chỉ đau âm ỉ thôi"],
        isEmergency: false,
      };
    }

    // Bước 4: Vị trí khác (bên trái, giữa bụng) và không có red flag
    return {
      reply: `Dạ mình đã tổng hợp thông tin: bạn bị **${ctx.primarySymptom} ${ctx.location}**, tính chất **${ctx.severity || "đau"}**, xuất hiện **${ctx.duration}**.\n\n💡 **HƯỚNG DẪN CHĂM SÓC & THEO DÕI AN TOÀN:**\n- Nghỉ ngơi tại chỗ, uống từng ngụm nước ấm nhỏ, ăn thức ăn lỏng dễ tiêu (cháo loãng), tránh đồ cay nóng, dầu mỡ hay sữa chua/rượu bia.\n- Tránh tự ý uống các loại thuốc giảm đau mạnh khi chưa xác định rõ nguyên nhân (vì có thể che lấp dấu hiệu viêm ruột thừa hoặc thủng tạng).\n- **Cần đến bệnh viện khám ngay nếu:** Cơn đau chuyển sang quặn thắt dữ dội, bụng cứng, sốt cao trên 38.5°C, nôn liên tục hoặc đi ngoài ra máu.`,
      quickReplies: ["🔍 Kênh tư vấn Dược sĩ", "🏥 Khi nào cần đi viện?"],
      isEmergency: false,
    };
  }

  // 4. KỊCH BẢN ĐAU ĐẦU
  if (ctx.primarySymptom?.includes("đầu")) {
    if (!ctx.duration) {
      return {
        reply: `Mình có thể hỏi thêm thông tin để tư vấn an toàn cho bạn nhé. **Bạn bị đau đầu từ bao giờ (mới bị hôm nay hay đã kéo dài vài ngày)?**`,
        quickReplies: ["Mới bị hôm nay", "Đã đau 2 ngày", "Đau kéo dài hơn 1 tuần"],
        isEmergency: false,
      };
    }

    if (!ctx.location) {
      return {
        reply: `Dạ bạn bị đau ${ctx.duration}. **Cơn đau xuất hiện ở vị trí nào (đau nửa đầu nhức nhối, đau vùng trán hay đau căng cả hai bên đầu) và có kèm theo sốt hoặc buồn nôn không ạ?**`,
        quickReplies: ["Đau nửa đầu", "Đau căng cả hai bên đầu", "Có kèm sốt", "Không sốt"],
        isEmergency: false,
      };
    }

    return {
      reply: `Dạ mình đã ghi nhận bạn bị **đau đầu ${ctx.location}**, xuất hiện **${ctx.duration}**.\n\n💡 **HƯỚNG DẪN CHĂM SÓC:**\n- Nằm nghỉ ngơi ở phòng yên tĩnh, giảm ánh sáng và tiếng ồn. Uống đủ nước và chườm khăn mát lên trán.\n- Nếu người lớn đau đầu do căng thẳng có thể dùng Paracetamol 500mg (1 viên/lần khi đau, cách 4-6 giờ, tối đa không quá 4 viên/ngày).\n- ⚠️ **DẤU HIỆU CẦN ĐI KHÁM NGAY:** Đau đầu dữ dội như sét đánh, kèm sốt cao, cứng gáy, nhìn mờ hoặc yếu một bên tay chân.`,
      quickReplies: ["💊 Tra cứu liều Paracetamol", "📞 Tư vấn Dược sĩ"],
      isEmergency: false,
    };
  }

  // 5. CÁC TRIỆU CHỨNG KHÁC (Hô hấp, Tiêu hóa, Cảm cúm)
  if (!ctx.duration) {
    return {
      reply: `Chào bạn, mình đã ghi nhận bạn đang có triệu chứng ${ctx.primarySymptom || "sức khỏe"}. Để hỗ trợ tốt nhất, **triệu chứng này xuất hiện được bao lâu rồi ạ?**`,
      quickReplies: ["Mới bị từ hôm nay", "Đã bị 2-3 ngày nay", "Kéo dài trên 1 tuần"],
      isEmergency: false,
    };
  }

  return {
    reply: `Dạ mình ghi nhận bạn có triệu chứng **${ctx.primarySymptom || "khó chịu"}**, xuất hiện **${ctx.duration}**.\n\n💡 **LỜI KHUYÊN CHĂM SÓC:**\n- Uống nhiều nước ấm, nghỉ ngơi điều độ và theo dõi sát diễn biến thân nhiệt.\n- Không tự ý dùng thuốc kháng sinh khi chưa có chỉ định xét nghiệm của Bác sĩ.\n- Nếu triệu chứng tăng nặng hoặc kéo dài quá 3 ngày không thuyên giảm, bạn nên đến cơ sở y tế gần nhất để được thăm khám trực tiếp nhé!`,
    quickReplies: ["📞 Liên hệ Dược sĩ H4CARE", "🔍 Tìm thuốc OTC phù hợp"],
    isEmergency: false,
  };
}
