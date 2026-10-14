export const RED_FLAG_SYMPTOMS = [
  {
    keywords: ["khó thở", "suy hô hấp", "thở dốc", "thở rít", "tím tái", "ngạt thở", "không thở được"],
    title: "CẢNH BÁO NGUY HIỂM: DẤU HIỆU SUY HÔ HẤP",
    message: "Triệu chứng khó thở, thở rít hoặc tím tái là dấu hiệu cấp cứu y khoa khẩn cấp. Người bệnh có thể gặp nguy cơ thiếu oxy não và trụy hô hấp.",
    action: "Hãy gọi ngay cấp cứu 115 hoặc đưa người bệnh đến bệnh viện/cơ sở y tế gần nhất lập tức!",
    level: "emergency" as const,
  },
  {
    keywords: ["đau thắt ngực", "đau tim", "ép ngực", "lan ra cánh tay", "lan lên hàm", "đau nhói ngực trái"],
    title: "CẢNH BÁO KHẨN CẤP: NGUY CƠ NHỒI MÁU CƠ TIM",
    message: "Cơn đau thắt ngực dữ dội, cảm giác đè nặng hoặc lan ra vai, cánh tay trái, hàm là dấu hiệu cảnh báo hội chứng mạch vành cấp / nhồi máu cơ tim.",
    action: "Cần gọi 115 ngay. Để bệnh nhân ngồi nghỉ ở tư thế nửa nằm nửa ngồi, nới lỏng trang phục, tuyệt đối không tự lái xe.",
    level: "emergency" as const,
  },
  {
    keywords: ["sốt cao co giật", "co giật", "sốt trên 39", "sốt trên 40", "sốt li bì", "co giật ở trẻ"],
    title: "CẢNH BÁO Y TẾ: SỐT CAO CO GIẬT",
    message: "Sốt cao trên 39.5°C kèm co giật, mê sảng hoặc li bì ở trẻ em cần được can thiệp y tế khẩn trương để tránh tổn thương thần kinh.",
    action: "Đặt người bệnh nằm nghiêng an toàn, chườm ấm các vùng bẹn/nách, không nhét vật cứng vào miệng và chuyển ngay tới viện.",
    level: "emergency" as const,
  },
  {
    keywords: ["nôn ra máu", "đi ngoài ra máu", "phân đen như bã cà phê", "phân bã cà phê", "chảy máu dạ dày"],
    title: "CẢNH BÁO: XUẤT HUYẾT TIÊU HÓA",
    message: "Nôn ra máu tươi hoặc dịch nâu đen bã cà phê, đại tiện phân đen sệt là biểu hiện xuất huyết đường tiêu hóa nặng.",
    action: "Cần đến ngay khoa cấp cứu bệnh viện. Không ăn uống thêm bất kỳ thứ gì.",
    level: "emergency" as const,
  },
  {
    keywords: ["méo miệng", "liệt nửa người", "yếu tay chân", "nói ngọng đột ngột", "mờ mắt đột ngột", "tai biến", "đột quỵ"],
    title: "CẢNH BÁO ĐỘT QUỴ NÃO CẤP (FAST)",
    message: "Các dấu hiệu méo mặt, yếu liệt tay chân hoặc rối loạn ngôn ngữ đột ngột là triệu chứng điển hình của đột quỵ não.",
    action: "Thời gian vàng là dưới 3 - 4.5 giờ. Gọi ngay 115 hoặc đưa bệnh nhân đến trung tâm đột quỵ gần nhất.",
    level: "emergency" as const,
  },
  {
    keywords: ["dị ứng thuốc", "sốc phản vệ", "phù môi", "phù mắt", "ngứa rát toàn thân", "nghẹt thở sau uống thuốc"],
    title: "CẢNH BÁO: DỊ ỨNG THUỐC / NGUY CƠ PHẢN VỆ",
    message: "Dấu hiệu phù môi, sưng mí mắt, ngứa nổi mày đay rầm rộ hoặc tức ngực sau khi dùng thuốc có thể tiến triển thành sốc phản vệ đe dọa tính mạng.",
    action: "Ngừng ngay thuốc đang dùng, mang theo mẫu thuốc và đến cơ sở y tế gần nhất để tiêm thuốc chống sốc.",
    level: "emergency" as const,
  },
];

export const STORE_POLICIES_INFO = {
  orderingGuide: `
**Quy trình đặt mua hàng trên website H4CARE:**
1. **Tìm kiếm sản phẩm:** Tìm thuốc hoặc vật tư qua thanh tìm kiếm hoặc danh mục OTC / Kê đơn.
2. **Thêm vào giỏ hàng:**
   - Với **Thuốc không kê đơn (OTC)** & Thực phẩm chức năng: Quý khách nhấn "Thêm vào giỏ" hoặc "Mua ngay".
   - Với **Thuốc kê đơn (Rx)**: Theo Luật Dược, quý khách cần bấm "Tư vấn & Gửi đơn thuốc", tải ảnh chụp đơn thuốc của bác sĩ lên hệ thống để Dược sĩ H4CARE thẩm định chuyên môn trước khi xuất kho.
3. **Thanh toán & Giao nhận:** Nhập địa chỉ nhận hàng, chọn phương thức thanh toán (COD hoặc Ví MoMo Sandbox, Chuyển khoản VietQR).
4. **Xác nhận đơn hàng:** Hệ thống gửi mã tra cứu đơn hàng và nhân sự dược sĩ sẽ liên hệ hỗ trợ nếu cần thiết.
`,

  orderStatuses: `
**Ý nghĩa các trạng thái đơn hàng tại H4CARE:**
- **Chờ xử lý (PENDING):** Đơn hàng vừa được tạo trên hệ thống, đang chờ tiếp nhận.
- **Đã xác nhận (CONFIRMED):** Đơn hàng hợp lệ, thông tin người nhận đã được ghi nhận.
- **Đang chuẩn bị hàng (PROCESSING / PREPARING):** Dược sĩ đang kiểm tra hạn dùng, đóng gói theo chuẩn GPP tại kho dược.
- **Đang giao hàng (SHIPPING / DISPATCHED):** Bưu tá đang vận chuyển đơn thuốc tới địa chỉ của quý khách.
- **Giao thành công (COMPLETED / DELIVERED):** Quý khách đã nhận hàng và thanh toán (nếu chọn COD).
- **Đã hủy (CANCELLED):** Đơn hàng bị hủy theo yêu cầu của khách hàng hoặc do không liên lạc được để xác nhận đơn.
`,

  returnPolicy: `
**Chính sách đổi trả & hoàn tiền H4CARE (Chuẩn GPP Bộ Y Tế):**
- **Thời hạn áp dụng:** Trong vòng **07 ngày** kể từ khi nhận hàng thành công.
- **Sản phẩm áp dụng:** Thuốc không kê đơn (OTC), Thực phẩm chức năng, Mỹ phẩm dược liệu, Dụng cụ y tế còn nguyên tem niêm phong (seal).
- **Sản phẩm KHÔNG nhận đổi trả:**
  + **Thuốc kê đơn (Rx):** Theo quy định Luật Dược, không nhận đổi trả sau khi đã giao thành công nhằm tránh rủi ro bảo quản và nhiễm khuẩn.
  + **Vaccine và Sinh phẩm lạnh (2°C - 8°C):** Không đổi trả do yêu cầu dây chuyền bảo quản nhiệt độ nghiêm ngặt.
  + Hàng đã bị bóc tem, vỡ vỏ hộp hoặc sử dụng sai hướng dẫn.
- **Chi phí vận chuyển:**
  + **100% Miễn phí:** Nếu giao sai thuốc, hàng móp méo bể vỡ do vận chuyển, hoặc hạn sử dụng còn dưới 6 tháng.
  + Khách hàng chi trả: Trường hợp quý khách đổi ý hoặc đặt nhầm quy cách mà sản phẩm vẫn nguyên seal.
- **Thời gian hoàn tiền:** Trong vòng **24 giờ** qua MoMo hoặc chuyển khoản ngân hàng sau khi kho tiếp nhận và thẩm định.
`,

  paymentMethods: `
**Các phương thức thanh toán tại H4CARE:**
1. **COD (Thanh toán khi nhận hàng):** Kiểm tra kiện hàng bưu phẩm và thanh toán tiền mặt trực tiếp cho nhân viên giao hàng.
2. **Ví điện tử MoMo Sandbox:** Thanh toán an toàn, xác nhận giao dịch tự động tức thì.
3. **Chuyển khoản VietQR:** Quét mã QR thanh toán qua ứng dụng ngân hàng nhanh chóng.
`,

  contactChannels: `
**Kênh hỗ trợ & Tư vấn Dược sĩ H4CARE:**
- **Thời gian làm việc:** 8:00 - 21:00 hàng ngày (kể cả Thứ 7, Chủ Nhật).
- **Email Dược sĩ chuyên môn:** duocsi@h4care.vn
- **Kênh trực tuyến:** Cửa sổ chat AI & cổng gửi đơn thuốc trực tuyến trên website h4care.vn.
- **Lưu ý y tế:** Kênh tư vấn chuyên môn không thay thế dịch vụ cấp cứu y tế 115.
`,
};

export const SYMPTOM_TRIAGE_GUIDELINES = `
KHI NGƯỜI DÙNG HỎI VỀ TRIỆU CHỨNG SỨC KHỎE, BẠN PHẢI TUÂN THỦ NGHIÊM NGẶT CÁC NGUYÊN TẮC SAU:
1. KHÔNG KẾT LUẬN BỆNH NGAY khi người dùng chỉ nêu một vài triệu chứng ban đầu.
2. HỎI TỪNG CÂU NGẮN, mỗi lần chỉ hỏi đúng MỘT câu để làm rõ:
   - Độ tuổi của người bệnh (trẻ em, người lớn hay người cao tuổi?)
   - Thời gian xuất hiện triệu chứng (kéo dài bao nhiêu ngày?)
   - Mức độ nghiêm trọng (ví dụ: sốt bao nhiêu độ, đau mức độ nào?)
   - Có bệnh lý nền (gan, thận, dạ dày, huyết áp...) hoặc phụ nữ đang mang thai/cho con bú hay không?
3. NẾU PHÁT HIỆN DẤU HIỆU NGUY HIỂM (khó thở, đau thắt ngực, sốt cao co giật, nôn ra máu, đột quỵ, dị ứng phản vệ):
   - Ngay lập tức cảnh báo nguy hiểm và hướng dẫn gọi cấp cứu 115 hoặc đến cơ sở y tế gần nhất.
4. TUYỆT ĐỐI KHÔNG TỰ KÊ ĐƠN THUỐC KÊ ĐƠN (Rx), không tự ý chỉ định liều dùng đặc trị thay thế bác sĩ.
5. ĐỐI VỚI THUỐC KHÔNG KÊ ĐƠN (OTC): Chỉ gợi ý thông tin thành phần, công dụng và cách dùng tham khảo của các sản phẩm có thực trong hệ thống H4CARE, kèm khuyến nghị đọc kỹ hướng dẫn trước khi dùng.
6. LUÔN CÓ LỜI DẶN: "Thông tin tư vấn mang tính chất tham khảo. Quý khách vui lòng tham vấn ý kiến Bác sĩ hoặc Dược sĩ chuyên môn trước khi sử dụng thuốc."
`;
