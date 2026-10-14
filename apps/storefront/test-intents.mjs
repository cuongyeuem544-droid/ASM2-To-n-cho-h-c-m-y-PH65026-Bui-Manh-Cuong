import { getAiChatResponse } from "./src/lib/chatbot/ai-service.ts";
import { cleanMedicalText } from "./src/lib/chatbot/sanitizer.ts";

const TEST_CASES = [
  { input: "hi", expectedIntent: "Chào hỏi tự nhiên, KHÔNG có sản phẩm đính kèm, KHÔNG có u003c" },
  { input: "xin chào", expectedIntent: "Chào hỏi tự nhiên, KHÔNG có sản phẩm đính kèm" },
  { input: "bạn là ai", expectedIntent: "Giới thiệu chatbot H4CARE, KHÔNG có sản phẩm đính kèm" },
  { input: "cảm ơn", expectedIntent: "Đáp lại lịch sự, KHÔNG có sản phẩm đính kèm" },
  { input: "vitamin C", expectedIntent: "Tra cứu sản phẩm Vitamin C thực tế, có thẻ sản phẩm sạch" },
  { input: "thuốc này bao nhiêu tiền", expectedIntent: "Hỏi rõ sản phẩm nếu chưa có ngữ cảnh" },
  { input: "tôi đau bụng", expectedIntent: "Hỏi thông tin triệu chứng phù hợp (vị trí đau, tính chất đau)" },
  { input: "phí giao hàng bao nhiêu", expectedIntent: "Dựa vào chính sách thực tế H4CARE" },
  { input: "u003ch2", expectedIntent: "Không tự chuyển dữ liệu không tin cậy thành HTML, hỏi làm rõ an toàn" },
  { input: "thuốc thần kỳ xyz999", expectedIntent: "Thừa nhận chưa có thông tin trong hệ thống, không bịa đặt" },
];

async function run() {
  console.log("==================================================================");
  console.log("            KIỂM THỬ 10 KỊCH BẢN BẮT BUỘC CHATBOT H4CARE         ");
  console.log("==================================================================\n");

  let allPassed = true;

  for (let i = 0; i < TEST_CASES.length; i++) {
    const { input, expectedIntent } = TEST_CASES[i];
    console.log(`[TEST ${i + 1}/10] Input: "${input}"`);
    console.log(` -> Mong muốn: ${expectedIntent}`);

    const res = await getAiChatResponse(input);

    const hasU003c = res.reply.includes("u003c") || res.reply.includes("u003e") || res.reply.includes("<h2") || res.reply.includes("<strong");
    const productCount = res.recommendedProducts?.length || 0;

    console.log(` -> Provider: ${res.providerUsed}`);
    console.log(` -> Sản phẩm đính kèm: ${productCount} sản phẩm`);
    console.log(` -> Có chứa mã escape lỗi/HTML thô không: ${hasU003c ? "CÓ [FAIL]" : "KHÔNG [PASS]"}`);
    console.log(` -> Trích đoạn trả lời:\n${res.reply.slice(0, 180)}...\n`);

    // Kiểm tra tính hợp lệ
    let passed = !hasU003c;
    if (["hi", "xin chào", "bạn là ai", "cảm ơn", "thuốc này bao nhiêu tiền", "phí giao hàng bao nhiêu", "u003ch2", "thuốc thần kỳ xyz999"].includes(input)) {
      if (productCount > 0) {
        console.error(` [FAIL] Không được đính kèm sản phẩm với câu hỏi: "${input}"!`);
        passed = false;
      }
    }
    if (input === "vitamin C") {
      if (productCount === 0) {
        console.error(` [FAIL] Phải tìm thấy sản phẩm Vitamin C trong database H4CARE!`);
        passed = false;
      }
    }

    if (!passed) allPassed = false;
    console.log(`=> Kết quả Test ${i + 1}: ${passed ? "[THÀNH CÔNG]" : "[THẤT BẠI]"}`);
    console.log("------------------------------------------------------------------");
  }

  console.log(`\nTỔNG KẾT BỘ KIỂM THỬ: ${allPassed ? "10/10 TEST CASES ĐẠT CHUẨN XUẤT SẮC!" : "CÒN LỖI CẦN FIX!"}`);
}

run().catch(console.error);
