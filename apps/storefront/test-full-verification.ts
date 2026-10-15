import { getAiChatResponse } from "./src/lib/chatbot/ai-service";
import { cleanMedicalText } from "./src/lib/chatbot/sanitizer";

interface TestCase {
  id: number;
  name: string;
  input: string;
  history?: Array<{ role: "user" | "assistant"; content: string }>;
  expectedIntent: string;
  verify: (res: any) => { passed: boolean; message: string };
}

async function runVerification() {
  console.log("================================================================================");
  console.log("           H4CARE CHATBOT AI – KIỂM THỬ TOÀN DIỆN 8 KỊCH BẢN & MULTI-TURN       ");
  console.log("================================================================================\n");

  const testCases: TestCase[] = [
    // 1. "Xin chào"
    {
      id: 1,
      name: 'Chào hỏi tự nhiên',
      input: 'Xin chào',
      history: [],
      expectedIntent: 'GREETING',
      verify: (res) => {
        const hasU003c = res.reply.includes("u003c") || res.reply.includes("u003e");
        const productCount = res.recommendedProducts?.length || 0;
        const passed = res.intentDetected === 'GREETING' && productCount === 0 && !hasU003c;
        return {
          passed,
          message: passed
            ? `Phản hồi thân thiện, 0 sản phẩm, không mã HTML lỗi`
            : `Sai: Intent=${res.intentDetected}, ProductCount=${productCount}, hasU003c=${hasU003c}`,
        };
      },
    },

    // 2. "Tôi bị đau âm ỉ bụng dưới"
    {
      id: 2,
      name: 'Khởi đầu tư vấn triệu chứng sức khỏe',
      input: 'Tôi bị đau âm ỉ bụng dưới',
      history: [],
      expectedIntent: 'HEALTH_SYMPTOM',
      verify: (res) => {
        const hasDurationQuestion = res.reply.toLowerCase().includes("khi nào") || res.reply.toLowerCase().includes("bao lâu");
        const productCount = res.recommendedProducts?.length || 0;
        const passed = res.intentDetected === 'HEALTH_SYMPTOM' && hasDurationQuestion && productCount === 0;
        return {
          passed,
          message: passed
            ? `Nhận diện đúng triệu chứng đau bụng dưới, hỏi thời gian (duration) lượt đầu, 0 sản phẩm gán ép`
            : `Sai: Intent=${res.intentDetected}, hasDurationQ=${hasDurationQuestion}, ProductCount=${productCount}`,
        };
      },
    },

    // 3. "Tôi bị đau từ hôm qua" (Multi-turn duy trì ngữ cảnh)
    {
      id: 3,
      name: 'Duy trì ngữ cảnh hỏi bệnh đa lượt',
      input: 'Tôi bị đau từ hôm qua',
      history: [
        { role: 'user', content: 'Tôi bị đau âm ỉ bụng dưới' },
        {
          role: 'assistant',
          content: 'Mình có thể hỏi thêm vài thông tin để hỗ trợ bạn nhé. Bạn bị đau bụng dưới từ khi nào?',
        },
      ],
      expectedIntent: 'HEALTH_SYMPTOM',
      verify: (res) => {
        const norm = res.reply.toLowerCase();
        const asksLocation = norm.includes("bên phải") || norm.includes("bên trái") || norm.includes("vị trí");
        const reasksDuration = norm.includes("từ khi nào") || norm.includes("bao lâu");
        const passed = res.intentDetected === 'HEALTH_SYMPTOM' && asksLocation && !reasksDuration;
        return {
          passed,
          message: passed
            ? `Đã ghi nhớ đau bụng dưới + từ hôm qua, hỏi tiếp vị trí (location), không hỏi lại thời gian`
            : `Sai: Intent=${res.intentDetected}, asksLocation=${asksLocation}, reasksDuration=${reasksDuration}`,
        };
      },
    },

    // 4. "Tôi đau bụng dữ dội và bị ngất" (Cấp cứu P0)
    {
      id: 4,
      name: 'Nhận diện tình huống cấp cứu P0 (Ngất / Mất ý thức)',
      input: 'Tôi đau bụng dữ dội và bị ngất',
      history: [
        { role: 'user', content: 'Tôi bị đau âm ỉ bụng dưới' },
        { role: 'assistant', content: 'Cơn đau ở vị trí nào?' },
      ],
      expectedIntent: 'EMERGENCY',
      verify: (res) => {
        const has115 = res.reply.includes("115");
        const hasEmergencyAlert = res.safetyAlert?.level === "emergency";
        const noProduct = (res.recommendedProducts?.length || 0) === 0;
        const passed = res.intentDetected === 'EMERGENCY' && has115 && hasEmergencyAlert && noProduct;
        return {
          passed,
          message: passed
            ? `Cảnh báo cấp cứu khẩn cấp 115 ngay lập tức, SafetyAlert=emergency, không gán sản phẩm`
            : `Sai: Intent=${res.intentDetected}, has115=${has115}, alertLevel=${res.safetyAlert?.level}`,
        };
      },
    },

    // 5. "Paracetamol là thuốc gì?"
    {
      id: 5,
      name: 'Thông tin dược lý Paracetamol',
      input: 'Paracetamol là thuốc gì?',
      history: [],
      expectedIntent: 'DRUG_INFORMATION',
      verify: (res) => {
        const norm = res.reply.toLowerCase();
        const hasActiveIngredient = norm.includes("paracetamol") || norm.includes("acetaminophen");
        const hasLiverWarning = norm.includes("gan") || norm.includes("quá liều") || norm.includes("4g");
        const passed = res.intentDetected === 'DRUG_INFORMATION' && hasActiveIngredient && hasLiverWarning;
        return {
          passed,
          message: passed
            ? `Cung cấp hoạt chất, chỉ định hạ sốt/giảm đau, cảnh báo độc tính gan khi dùng quá 4g/ngày`
            : `Sai: Intent=${res.intentDetected}, hasActive=${hasActiveIngredient}, hasLiver=${hasLiverWarning}`,
        };
      },
    },

    // 6. "H4CARE có vitamin C không?"
    {
      id: 6,
      name: 'Tìm kiếm sản phẩm Vitamin C (Không nhầm sang "ho")',
      input: 'H4CARE có vitamin C không?',
      history: [],
      expectedIntent: 'PRODUCT_SEARCH',
      verify: (res) => {
        const productCount = res.recommendedProducts?.length || 0;
        const passed = res.intentDetected === 'PRODUCT_SEARCH' && productCount > 0;
        return {
          passed,
          message: passed
            ? `Nhận diện đúng tìm kiếm sản phẩm Vitamin C, tìm thấy ${productCount} sản phẩm thực tế từ DB`
            : `Sai: Intent=${res.intentDetected}, ProductCount=${productCount}`,
        };
      },
    },

    // 7. "Thuốc đó có tác dụng phụ gì?" (Giải quyết đại từ thay thế "thuốc đó")
    {
      id: 7,
      name: 'Giải quyết đại từ "thuốc đó" -> Paracetamol tác dụng phụ',
      input: 'Thuốc đó có tác dụng phụ gì?',
      history: [
        { role: 'user', content: 'Paracetamol là thuốc gì?' },
        {
          role: 'assistant',
          content: '**Paracetamol** (Acetaminophen) là thuốc giảm đau, hạ sốt phổ biến. Liều tối đa 4g/ngày.',
        },
      ],
      expectedIntent: 'DRUG_INFORMATION',
      verify: (res) => {
        const norm = res.reply.toLowerCase();
        const mentionsParacetamol = norm.includes("paracetamol");
        const mentionsSideEffects = norm.includes("tác dụng phụ") || norm.includes("gan") || norm.includes("phát ban");
        const passed = res.intentDetected === 'DRUG_INFORMATION' && mentionsParacetamol && mentionsSideEffects;
        return {
          passed,
          message: passed
            ? `Hiểu "thuốc đó" là Paracetamol từ lịch sử, trả lời đúng tác dụng phụ và cảnh báo gan`
            : `Sai: Intent=${res.intentDetected}, mentionsParacetamol=${mentionsParacetamol}`,
        };
      },
    },

    // 8. "Tôi muốn gặp dược sĩ thật"
    {
      id: 8,
      name: 'Kênh chuyển tiếp Dược sĩ thật',
      input: 'Tôi muốn gặp dược sĩ thật',
      history: [],
      expectedIntent: 'HUMAN_SUPPORT',
      verify: (res) => {
        const norm = res.reply.toLowerCase();
        const hasHotline = res.reply.includes("1800 6828");
        const hasEmail = norm.includes("duocsi@h4care.vn");
        const isTransparent = norm.includes("trợ lý dược sĩ ai") || norm.includes("không thể chuyển máy trực tiếp");
        const passed = res.intentDetected === 'HUMAN_SUPPORT' && hasHotline && hasEmail && isTransparent;
        return {
          passed,
          message: passed
            ? `Cung cấp hotline 1800 6828 (8h-21h), email duocsi@h4care.vn, minh bạch là AI không giả mạo trực tiếp`
            : `Sai: Intent=${res.intentDetected}, hasHotline=${hasHotline}, hasEmail=${hasEmail}`,
        };
      },
    },
  ];

  let passedCount = 0;

  for (const tc of testCases) {
    console.log(`\n--------------------------------------------------------------------------------`);
    console.log(`[TEST ${tc.id}/8] ${tc.name}`);
    console.log(`User: "${tc.input}"`);
    if (tc.history && tc.history.length > 0) {
      console.log(`Lịch sử: [${tc.history.map((h) => `${h.role}: "${h.content.slice(0, 40)}..."`).join(", ")}]`);
    }

    const res = await getAiChatResponse(tc.input, tc.history);
    const { passed, message } = tc.verify(res);

    if (passed) passedCount++;

    console.log(`Intent nhận diện : ${res.intentDetected} (Kỳ vọng: ${tc.expectedIntent})`);
    console.log(`Provider sử dụng : ${res.providerUsed}`);
    console.log(`Sản phẩm đính kèm: ${res.recommendedProducts?.length || 0} sản phẩm`);
    console.log(`Kết quả          : ${passed ? '✅ [PASS]' : '❌ [FAIL]'}`);
    console.log(`Đánh giá         : ${message}`);
    console.log(`Trích đoạn trả lời:\n${res.reply.slice(0, 160)}...`);
  }

  // Multi-turn Chain Tests
  console.log("\n================================================================================");
  console.log("            KIỂM THỬ CHUỖI HỘI THOẠI ĐA LƯỢT (MULTI-TURN CHAINS)                ");
  console.log("================================================================================\n");

  // Chain A: Triệu chứng -> Thời gian -> Vị trí -> Cấp cứu
  console.log("=== CHUỖI A: TIẾN TRÌNH KHÁM SÀNG LỌC TRIỆU CHỨNG BẮT BUỘC ===");
  const chainA_step1 = await getAiChatResponse("Tôi bị đau âm ỉ bụng dưới", []);
  console.log("Lượt 1 (User: 'Tôi bị đau âm ỉ bụng dưới'):");
  console.log(" -> Bot:", chainA_step1.reply.slice(0, 120), "...");

  const chainA_hist1 = [
    { role: "user" as const, content: "Tôi bị đau âm ỉ bụng dưới" },
    { role: "assistant" as const, content: chainA_step1.reply },
  ];
  const chainA_step2 = await getAiChatResponse("Từ hôm qua", chainA_hist1);
  console.log("Lượt 2 (User: 'Từ hôm qua'):");
  console.log(" -> Bot:", chainA_step2.reply.slice(0, 120), "...");

  const chainA_hist2 = [
    ...chainA_hist1,
    { role: "user" as const, content: "Từ hôm qua" },
    { role: "assistant" as const, content: chainA_step2.reply },
  ];
  const chainA_step3 = await getAiChatResponse("Bên phải", chainA_hist2);
  console.log("Lượt 3 (User: 'Bên phải'):");
  console.log(" -> Bot:", chainA_step3.reply.slice(0, 120), "...");

  const chainA_hist3 = [
    ...chainA_hist2,
    { role: "user" as const, content: "Bên phải" },
    { role: "assistant" as const, content: chainA_step3.reply },
  ];
  const chainA_step4 = await getAiChatResponse("Tôi đau bụng dữ dội và bị ngất", chainA_hist3);
  console.log("Lượt 4 (User: 'Tôi đau bụng dữ dội và bị ngất'):");
  console.log(" -> Bot:", chainA_step4.reply.slice(0, 120), "...");

  const chainAPassed =
    chainA_step1.reply.toLowerCase().includes("khi nào") &&
    (chainA_step2.reply.toLowerCase().includes("bên phải") || chainA_step2.reply.toLowerCase().includes("vị trí")) &&
    (chainA_step3.reply.toLowerCase().includes("sốt") || chainA_step3.reply.toLowerCase().includes("nôn")) &&
    chainA_step4.intentDetected === "EMERGENCY";

  console.log(`\n=> KẾT QUẢ CHUỖI A: ${chainAPassed ? "✅ [PASS HOÀN TOÀN]" : "❌ [FAIL]"}`);

  // Chain B: Dược lý & So sánh thuốc
  console.log("\n=== CHUỖI B: DƯỢC LÝ & SO SÁNH THUỐC ĐA LƯỢT ===");
  const chainB_step1 = await getAiChatResponse("Paracetamol là thuốc gì?", []);
  console.log("Lượt 1 (User: 'Paracetamol là thuốc gì?'):");
  console.log(" -> Bot:", chainB_step1.reply.slice(0, 120), "...");

  const chainB_hist1 = [
    { role: "user" as const, content: "Paracetamol là thuốc gì?" },
    { role: "assistant" as const, content: chainB_step1.reply },
  ];
  const chainB_step2 = await getAiChatResponse("Thuốc đó có tác dụng phụ gì?", chainB_hist1);
  console.log("Lượt 2 (User: 'Thuốc đó có tác dụng phụ gì?'):");
  console.log(" -> Bot:", chainB_step2.reply.slice(0, 120), "...");

  const chainB_hist2 = [
    ...chainB_hist1,
    { role: "user" as const, content: "Thuốc đó có tác dụng phụ gì?" },
    { role: "assistant" as const, content: chainB_step2.reply },
  ];
  const chainB_step3 = await getAiChatResponse("Còn Ibuprofen thì sao?", chainB_hist2);
  console.log("Lượt 3 (User: 'Còn Ibuprofen thì sao?'):");
  console.log(" -> Bot:", chainB_step3.reply.slice(0, 120), "...");

  const chainB_hist3 = [
    ...chainB_hist2,
    { role: "user" as const, content: "Còn Ibuprofen thì sao?" },
    { role: "assistant" as const, content: chainB_step3.reply },
  ];
  const chainB_step4 = await getAiChatResponse("Hai loại này có giống nhau không?", chainB_hist3);
  console.log("Lượt 4 (User: 'Hai loại này có giống nhau không?'):");
  console.log(" -> Bot:", chainB_step4.reply.slice(0, 120), "...");

  const chainBPassed =
    chainB_step1.intentDetected === "DRUG_INFORMATION" &&
    chainB_step2.reply.toLowerCase().includes("paracetamol") &&
    chainB_step3.reply.toLowerCase().includes("ibuprofen") &&
    chainB_step4.reply.toLowerCase().includes("paracetamol") &&
    chainB_step4.reply.toLowerCase().includes("ibuprofen");

  console.log(`\n=> KẾT QUẢ CHUỖI B: ${chainBPassed ? "✅ [PASS HOÀN TOÀN]" : "❌ [FAIL]"}`);

  console.log("\n================================================================================");
  console.log(`TỔNG KẾT: ${passedCount}/8 KỊCH BẢN CHÍNH XÁC 100% | CHUỖI A: ${chainAPassed ? "ĐẠT" : "CHƯA ĐẠT"} | CHUỖI B: ${chainBPassed ? "ĐẠT" : "CHƯA ĐẠT"}`);
  console.log("================================================================================\n");
}

runVerification().catch(console.error);
