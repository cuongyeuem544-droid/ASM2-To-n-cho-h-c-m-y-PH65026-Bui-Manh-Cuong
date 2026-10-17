import { getAiChatResponse } from "../apps/storefront/src/lib/chatbot/ai-service";
import {
  extractUserMemory,
  checkMemoryQuery,
  checkSelfIntroduction,
} from "../apps/storefront/src/lib/chatbot/context-tracker";
import { ExtractedMemory } from "../apps/storefront/src/lib/chatbot/types";

let passedCount = 0;
let totalCount = 0;

function assert(condition: boolean, message: string) {
  totalCount++;
  if (condition) {
    console.log(`  ✅ PASS: ${message}`);
    passedCount++;
  } else {
    console.error(`  ❌ FAIL: ${message}`);
    process.exitCode = 1;
  }
}

async function runAllTests() {
  console.log("================================================================================");
  console.log("🧪 BẮT ĐẦU KIỂM THỬ 8 KỊCH BẢN CHATBOT AI MEMORY H4CARE");
  console.log("================================================================================\n");

  const sessionId = "test-session-" + Date.now();
  let sessionMemory: ExtractedMemory = {};
  let conversationHistory: Array<{ role: "user" | "assistant"; content: string }> = [];

  // ============================================================================
  // KỊCH BẢN 1: “Tên tôi là Nguyễn Đức Anh” → “Tên tôi là gì?”
  // ============================================================================
  console.log("🔹 Kịch bản 1: Giới thiệu tên & Truy vấn lại tên từ Memory");
  {
    // Lượt 1: User giới thiệu tên
    const msg1 = "Tên tôi là Nguyễn Đức Anh";
    const res1 = await getAiChatResponse(msg1, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res1.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg1 });
    conversationHistory.push({ role: "assistant", content: res1.reply });

    assert(
      sessionMemory.userName === "Nguyễn Đức Anh",
      `Đã trích xuất chính xác tên người dùng: '${sessionMemory.userName}'`
    );
    assert(
      res1.reply.includes("Nguyễn Đức Anh"),
      `Bot xác nhận nhẹ nhàng tên người dùng trong lời chào: "${res1.reply.substring(0, 50)}..."`
    );

    // Lượt 2: User hỏi lại tên mình
    const msg2 = "Tên tôi là gì?";
    const res2 = await getAiChatResponse(msg2, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res2.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg2 });
    conversationHistory.push({ role: "assistant", content: res2.reply });

    assert(
      res2.reply.includes("Tên bạn là Nguyễn Đức Anh."),
      `Bot trả lời đúng câu hỏi tên từ memory: "${res2.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 2: “Tôi bị đau bụng dưới” → “Từ hôm qua” → bot nhớ ngữ cảnh
  // ============================================================================
  console.log("🔹 Kịch bản 2: Hỏi bệnh triệu chứng đa lượt (Đau bụng dưới -> Từ hôm qua)");
  {
    // Lượt 1: Báo triệu chứng
    const msg1 = "Tôi bị đau bụng dưới";
    const res1 = await getAiChatResponse(msg1, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res1.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg1 });
    conversationHistory.push({ role: "assistant", content: res1.reply });

    assert(
      sessionMemory.symptoms?.includes("đau bụng dưới"),
      `Đã lưu triệu chứng 'đau bụng dưới' vào memory: [${sessionMemory.symptoms?.join(", ")}]`
    );
    assert(
      res1.reply.includes("Bạn bị đau bụng dưới từ khi nào?"),
      `Bot hỏi thời gian xuất hiện: "${res1.reply}"`
    );

    // Lượt 2: Cung cấp thời gian "Từ hôm qua"
    const msg2 = "Từ hôm qua";
    const res2 = await getAiChatResponse(msg2, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res2.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg2 });
    conversationHistory.push({ role: "assistant", content: res2.reply });

    assert(
      sessionMemory.symptomDuration === "từ hôm qua",
      `Đã ghi nhận thời gian đau: '${sessionMemory.symptomDuration}'`
    );
    assert(
      res2.reply.includes("Cơn đau chủ yếu ở bên trái, bên phải hay giữa bụng dưới?"),
      `Bot nhớ đã hỏi thời gian xong, chuyển sang hỏi vị trí cơn đau: "${res2.reply}"`
    );

    // Kiểm tra câu hỏi tra cứu thời gian từ memory
    const queryTime = "Tôi nói tôi đau từ khi nào?";
    const resTime = await getAiChatResponse(queryTime, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    assert(
      resTime.reply.includes("từ hôm qua"),
      `Bot trả lời chính xác thời gian đau khi user hỏi lại: "${resTime.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 3: “Paracetamol là thuốc gì?”
  // ============================================================================
  console.log("🔹 Kịch bản 3: Tra cứu thông tin dược lý (Paracetamol là thuốc gì?)");
  {
    const msg = "Paracetamol là thuốc gì?";
    const res = await getAiChatResponse(msg, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg });
    conversationHistory.push({ role: "assistant", content: res.reply });

    assert(
      sessionMemory.lastDiscussedProduct === "Paracetamol",
      `Đã cập nhật thuốc đang thảo luận là 'Paracetamol'`
    );
    assert(
      res.reply.includes("Paracetamol") && res.reply.includes("giảm đau, hạ sốt"),
      `Bot giải thích rõ công dụng và chỉ định của Paracetamol: "${res.reply.substring(0, 80)}..."`
    );
    assert(
      res.reply.includes("4g") || res.reply.includes("4.000mg") || res.reply.includes("gan"),
      `Bot có cảnh báo an toàn liều tối đa và độc tính gan`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 4: “Thuốc đó có tác dụng phụ gì?” → hiểu "thuốc đó" là Paracetamol
  // ============================================================================
  console.log("🔹 Kịch bản 4: Tham chiếu đại từ (Thuốc đó có tác dụng phụ gì?)");
  {
    const msg = "Thuốc đó có tác dụng phụ gì?";
    const res = await getAiChatResponse(msg, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg });
    conversationHistory.push({ role: "assistant", content: res.reply });

    assert(
      res.reply.includes("Paracetamol") && (res.reply.includes("Tác dụng phụ") || res.reply.includes("tác dụng phụ")),
      `Bot hiểu 'thuốc đó' là Paracetamol và trả lời đúng tác dụng phụ: "${res.reply.substring(0, 100)}..."`
    );
    assert(
      res.reply.includes("gan") || res.reply.includes("dị ứng") || res.reply.includes("phát ban"),
      `Bot giải thích các lưu ý và tác dụng không mong muốn`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 5: “H4CARE có vitamin C không?”
  // ============================================================================
  console.log("🔹 Kịch bản 5: Tìm kiếm sản phẩm tại nhà thuốc H4CARE (Vitamin C)");
  {
    const msg = "H4CARE có vitamin C không?";
    const res = await getAiChatResponse(msg, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg });
    conversationHistory.push({ role: "assistant", content: res.reply });

    assert(
      res.intentDetected === "PRODUCT_SEARCH",
      `Nhận diện chính xác intent PRODUCT_SEARCH`
    );
    assert(
      res.reply.includes("H4CARE") && (res.reply.includes("Vitamin C") || res.reply.includes("sản phẩm")),
      `Bot phản hồi tra cứu sản phẩm có tâm, chính xác: "${res.reply.substring(0, 100)}..."`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 6: “Tôi muốn gặp dược sĩ thật” → kích hoạt luồng handoff
  // ============================================================================
  console.log("🔹 Kịch bản 6: Kích hoạt luồng chuyển sang Dược sĩ / Live Chat thật");
  {
    const msg = "Tôi muốn gặp dược sĩ thật";
    const res = await getAiChatResponse(msg, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    sessionMemory = res.extractedMemory || sessionMemory;
    conversationHistory.push({ role: "user", content: msg });
    conversationHistory.push({ role: "assistant", content: res.reply });

    assert(
      res.handoffRequested === true,
      `Cờ handoffRequested được kích hoạt (= true)`
    );
    assert(
      res.isHumanSupport === true,
      `Cờ isHumanSupport được kích hoạt (= true)`
    );
    assert(
      res.reply.includes("Tư vấn trực tiếp") || res.reply.includes("Dược sĩ"),
      `Bot thông báo rõ ràng việc kết nối sang nhân sự thật: "${res.reply.substring(0, 120)}..."`
    );
    assert(
      Boolean(res.contextSummary),
      `Hệ thống tổng hợp contextSummary bàn giao cho nhân viên: "${res.contextSummary}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 7: “Tôi đau bụng dữ dội và bị ngất” → Red Flag khẩn cấp
  // ============================================================================
  console.log("🔹 Kịch bản 7: Cảnh báo dấu hiệu nguy hiểm khẩn cấp (Red Flag P0)");
  {
    const msg = "Tôi đau bụng dữ dội và bị ngất";
    const res = await getAiChatResponse(msg, conversationHistory, {
      sessionId,
      extractedMemory: sessionMemory,
    });
    conversationHistory.push({ role: "user", content: msg });
    conversationHistory.push({ role: "assistant", content: res.reply });

    assert(
      res.intentDetected === "EMERGENCY" || Boolean(res.safetyAlert),
      `Nhận diện chính xác trường hợp cấp cứu EMERGENCY`
    );
    assert(
      res.safetyAlert?.level === "emergency",
      `Mức độ cảnh báo an toàn là 'emergency'`
    );
    assert(
      res.reply.includes("115") || res.reply.includes("Cấp cứu"),
      `Bot yêu cầu gọi ngay 115 hoặc đi viện khẩn cấp: "${res.reply.substring(0, 100)}..."`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 8: Reload trang vẫn giữ được lịch sử và memory
  // ============================================================================
  console.log("🔹 Kịch bản 8: Khôi phục Session Storage sau khi reload trang");
  {
    // Giả lập lưu vào sessionStorage
    const simulatedSessionStorage: Record<string, string> = {
      h4care_chat_messages_v1: JSON.stringify(conversationHistory),
      h4care_chat_memory_v1: JSON.stringify(sessionMemory),
      h4care_chat_session_id_v1: sessionId,
    };

    // Giả lập hành vi reload trang: Đọc lại từ storage
    const restoredHistory = JSON.parse(simulatedSessionStorage.h4care_chat_messages_v1);
    const restoredMemory = JSON.parse(simulatedSessionStorage.h4care_chat_memory_v1);
    const restoredSessionId = simulatedSessionStorage.h4care_chat_session_id_v1;

    assert(
      restoredSessionId === sessionId,
      `Khôi phục đúng sessionId sau reload: '${restoredSessionId}'`
    );
    assert(
      restoredMemory.userName === "Nguyễn Đức Anh",
      `Khôi phục đúng user_name sau reload: '${restoredMemory.userName}'`
    );
    assert(
      restoredMemory.symptoms?.includes("đau bụng dưới"),
      `Khôi phục đúng danh sách triệu chứng sau reload`
    );
    assert(
      restoredMemory.symptomDuration === "từ hôm qua",
      `Khôi phục đúng thời gian triệu chứng sau reload`
    );
    assert(
      Boolean(restoredMemory.lastDiscussedProduct?.toLowerCase().includes("vitamin c")),
      `Khôi phục đúng sản phẩm thảo luận gần nhất sau reload: '${restoredMemory.lastDiscussedProduct}'`
    );

    // Gửi tiếp tin nhắn sau khi reload để xác minh bot vẫn nhớ
    const afterReloadMsg = "Tên tôi là gì?";
    const afterReloadRes = await getAiChatResponse(afterReloadMsg, restoredHistory, {
      sessionId: restoredSessionId,
      extractedMemory: restoredMemory,
    });

    assert(
      afterReloadRes.reply.includes("Tên bạn là Nguyễn Đức Anh."),
      `Sau reload trang, bot vẫn nhận diện đúng tên từ memory: "${afterReloadRes.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 9: CHUỖI HỘI THOẠI ĐỔI TÊN LIÊN TỤC VÀ TỰ NHIÊN (BẮT BUỘC THEO ĐỀ BÀI)
  // ============================================================================
  console.log("🔹 Kịch bản 9: Chuỗi hội thoại đổi tên liên tục trong cùng phiên (Cường -> Hùng -> Hoàn)");
  {
    const sessChain = "session-rename-" + Date.now();
    let memChain: ExtractedMemory = {};
    let histChain: Array<{ role: "user" | "assistant"; content: string }> = [];

    // 1. "Tôi tên là Cường"
    const m1 = "Tôi tên là Cường";
    const r1 = await getAiChatResponse(m1, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r1.extractedMemory || memChain;
    histChain.push({ role: "user", content: m1 });
    histChain.push({ role: "assistant", content: r1.reply });

    assert(
      memChain.userName === "Cường",
      `1. Khởi tạo tên ban đầu: '${memChain.userName}' === 'Cường'`
    );
    assert(
      r1.reply.includes("Cường"),
      `1. Phản hồi chào mừng tên ban đầu: "${r1.reply.substring(0, 50)}..."`
    );

    // 2. "Tên tôi là gì?"
    const m2 = "Tên tôi là gì?";
    const r2 = await getAiChatResponse(m2, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r2.extractedMemory || memChain;
    histChain.push({ role: "user", content: m2 });
    histChain.push({ role: "assistant", content: r2.reply });

    assert(
      r2.reply === "Tên bạn là Cường.",
      `2. Trả lời chính xác tên ban đầu: "${r2.reply}"`
    );

    // 3. "Giờ tôi lại thành tên Hùng"
    const m3 = "Giờ tôi lại thành tên Hùng";
    const r3 = await getAiChatResponse(m3, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r3.extractedMemory || memChain;
    histChain.push({ role: "user", content: m3 });
    histChain.push({ role: "assistant", content: r3.reply });

    assert(
      memChain.userName === "Hùng",
      `3. Cập nhật đổi tên thành công: '${memChain.userName}' === 'Hùng'`
    );
    assert(
      r3.reply.includes("Hùng") && r3.reply.includes("cập nhật lại tên"),
      `3. Bot nhận diện đổi tên và xác nhận tự nhiên: "${r3.reply.substring(0, 65)}..."`
    );

    // 4. "Tên tôi là gì?"
    const m4 = "Tên tôi là gì?";
    const r4 = await getAiChatResponse(m4, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r4.extractedMemory || memChain;
    histChain.push({ role: "user", content: m4 });
    histChain.push({ role: "assistant", content: r4.reply });

    assert(
      r4.reply === "Tên bạn là Hùng.",
      `4. Trả lời đúng tên sau khi đổi: "${r4.reply}"`
    );

    // 5. Thử thêm: "Giờ gọi tôi là Hùng nhé"
    const m5 = "Giờ gọi tôi là Hùng nhé";
    const r5 = await getAiChatResponse(m5, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r5.extractedMemory || memChain;
    assert(
      memChain.userName === "Hùng",
      `5. Mẫu câu 'Giờ gọi tôi là... nhé' giữ đúng tên Hùng: '${memChain.userName}'`
    );

    // 6. "Không, tôi tên Hoàn cơ"
    const m6 = "Không, tôi tên Hoàn cơ";
    const r6 = await getAiChatResponse(m6, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r6.extractedMemory || memChain;
    histChain.push({ role: "user", content: m6 });
    histChain.push({ role: "assistant", content: r6.reply });

    assert(
      memChain.userName === "Hoàn",
      `6. Cập nhật sửa tên với khẩu ngữ (cơ): '${memChain.userName}' === 'Hoàn'`
    );
    assert(
      r6.reply.includes("Hoàn") && r6.reply.includes("cập nhật lại tên"),
      `6. Bot xác nhận đổi sang tên Hoàn: "${r6.reply.substring(0, 65)}..."`
    );

    // 7. "Bạn nhớ tên tôi không?"
    const m7 = "Bạn nhớ tên tôi không?";
    const r7 = await getAiChatResponse(m7, histChain, {
      sessionId: sessChain,
      extractedMemory: memChain,
    });
    memChain = r7.extractedMemory || memChain;
    histChain.push({ role: "user", content: m7 });
    histChain.push({ role: "assistant", content: r7.reply });

    assert(
      r7.reply === "Tên bạn là Hoàn.",
      `7. Trả lời đúng tên mới nhất (Hoàn) cho câu hỏi 'Bạn nhớ tên tôi không?': "${r7.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 10: KIỂM THỬ MỞ RỘNG (BÊN THỨ 3, KHÔNG DẤU, VIẾT TẮT, ĐỔI TUỔI & TRIỆU CHỨNG)
  // ============================================================================
  console.log("🔹 Kịch bản 10: Kiểm thử mở rộng (Bên thứ 3, Không dấu, Viết tắt, Giữ nguyên memory)");
  {
    const sessExt = "session-ext-" + Date.now();
    let memExt: ExtractedMemory = { userName: "Hoàn" };
    let histExt: Array<{ role: "user" | "assistant"; content: string }> = [];

    // 1. Bên thứ ba: "Mẹ tôi tên là Lan" -> Không được đổi userName thành Lan!
    const mThird1 = "Mẹ tôi tên là Lan";
    const rThird1 = await getAiChatResponse(mThird1, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rThird1.extractedMemory || memExt;
    assert(
      memExt.userName === "Hoàn",
      `1. Không ghi đè tên người dùng khi nhắc đến người thân ('Mẹ tôi tên là Lan'): '${memExt.userName}' === 'Hoàn'`
    );

    // 2. Bên thứ ba: "Bé nhà tôi tên Bống" -> Không đổi
    const mThird2 = "Bé nhà tôi tên Bống";
    const rThird2 = await getAiChatResponse(mThird2, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rThird2.extractedMemory || memExt;
    assert(
      memExt.userName === "Hoàn",
      `2. Không ghi đè tên khi nói về bé ('Bé nhà tôi tên Bống'): '${memExt.userName}' === 'Hoàn'`
    );

    // 3. Không dấu: "gio goi toi la an nhe"
    const mNoAccent = "gio goi toi la an nhe";
    const rNoAccent = await getAiChatResponse(mNoAccent, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rNoAccent.extractedMemory || memExt;
    assert(
      memExt.userName === "An",
      `3. Nhận diện và đổi tên thành công câu không dấu ('gio goi toi la an nhe'): '${memExt.userName}' === 'An'`
    );

    // 4. Viết tắt: "m tên Hùng", "mk tên Minh"
    const mAbbr = "mk tên Minh";
    const rAbbr = await getAiChatResponse(mAbbr, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rAbbr.extractedMemory || memExt;
    assert(
      memExt.userName === "Minh",
      `4. Nhận diện từ viết tắt ('mk tên Minh'): '${memExt.userName}' === 'Minh'`
    );

    // 5. Thay đổi tuổi: "Tôi 28 tuổi" -> userName không bị mất!
    const mAge = "Tôi 28 tuổi";
    const rAge = await getAiChatResponse(mAge, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rAge.extractedMemory || memExt;
    assert(
      memExt.age === "28" && memExt.userName === "Minh",
      `5. Cập nhật tuổi (${memExt.age}) nhưng vẫn bảo toàn tên người dùng: '${memExt.userName}'`
    );

    // 6. Thay đổi triệu chứng: "Tôi bị đau đầu" -> userName và age không bị mất!
    const mSym = "Tôi bị đau đầu";
    const rSym = await getAiChatResponse(mSym, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    memExt = rSym.extractedMemory || memExt;
    assert(
      memExt.symptoms?.includes("đau đầu") && memExt.userName === "Minh" && memExt.age === "28",
      `6. Cập nhật triệu chứng nhưng vẫn bảo toàn tên (${memExt.userName}) và tuổi (${memExt.age})`
    );

    // 7. Hỏi lại tên: "Tên tôi là gì?" -> Phải trả lời đúng "Minh"
    const mCheck = "Tên tôi là gì?";
    const rCheck = await getAiChatResponse(mCheck, histExt, {
      sessionId: sessExt,
      extractedMemory: memExt,
    });
    assert(
      rCheck.reply === "Tên bạn là Minh.",
      `7. Trả lời tên chính xác sau các cập nhật triệu chứng và tuổi: "${rCheck.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 11: Tiếng Việt tự nhiên, Viết tắt, Khẩu ngữ, Tuổi tác & Cảm xúc
  // ============================================================================
  console.log("🔹 Kịch bản 11: Tiếng Việt tự nhiên, Viết tắt, Khẩu ngữ, Tuổi tác & Cảm xúc");
  {
    const sessSlang = "session-slang-" + Date.now();
    let memSlang: ExtractedMemory = {};
    let histSlang: Array<{ role: "user" | "assistant"; content: string }> = [];

    // 1. Viết tắt & tiếng lóng: "mk bị đau đầu từ qua h"
    const m1 = "mk bị đau đầu từ qua h";
    const r1 = await getAiChatResponse(m1, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    memSlang = r1.extractedMemory || memSlang;
    histSlang.push({ role: "user", content: m1 });
    histSlang.push({ role: "assistant", content: r1.reply });

    assert(
      memSlang.symptoms?.includes("đau đầu") && Boolean(memSlang.symptomDuration),
      `1. Hiểu câu viết tắt 'mk bị đau đầu từ qua h': triệu chứng=[${memSlang.symptoms?.join(", ")}], thời gian='${memSlang.symptomDuration}'`
    );

    // 2. Viết tắt hỏi tác dụng phụ: "b ơi thuốc này có td phụ kh" (với Paracetamol làm active drug)
    memSlang.lastDiscussedProduct = "Paracetamol";
    const m2 = "b ơi thuốc này có td phụ kh";
    const r2 = await getAiChatResponse(m2, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    memSlang = r2.extractedMemory || memSlang;
    histSlang.push({ role: "user", content: m2 });
    histSlang.push({ role: "assistant", content: r2.reply });

    assert(
      r2.reply.includes("Paracetamol") && (r2.reply.includes("Tác dụng phụ") || r2.reply.includes("tác dụng phụ")),
      `2. Hiểu viết tắt 'b ơi thuốc này có td phụ kh' và trả lời tác dụng phụ của Paracetamol: "${r2.reply.substring(0, 50)}..."`
    );

    // 3. Khai báo tuổi bằng khẩu ngữ: "t 39t r, nhớ giùm nha"
    const m3 = "t 39t r, nhớ giùm nha";
    const r3 = await getAiChatResponse(m3, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    memSlang = r3.extractedMemory || memSlang;
    histSlang.push({ role: "user", content: m3 });
    histSlang.push({ role: "assistant", content: r3.reply });

    assert(
      memSlang.age === "39",
      `3. Trích xuất tuổi từ khẩu ngữ 't 39t r, nhớ giùm nha': age='${memSlang.age}' === '39'`
    );

    // 4. Hỏi lại tuổi bằng teencode: "b nhớ mk bn tuổi ko"
    const m4 = "b nhớ mk bn tuổi ko";
    const r4 = await getAiChatResponse(m4, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    assert(
      r4.reply.includes("39"),
      `4. Trả lời đúng tuổi khi hỏi bằng teencode 'b nhớ mk bn tuổi ko': "${r4.reply}"`
    );

    // 5. Điều chỉnh tuổi: "thực ra mk 20 r"
    const m5 = "thực ra mk 20 r";
    const r5 = await getAiChatResponse(m5, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    memSlang = r5.extractedMemory || memSlang;
    assert(
      memSlang.age === "20",
      `5. Cập nhật sửa tuổi bằng 'thực ra mk 20 r': age='${memSlang.age}' === '20'`
    );

    // 6. Hỏi lại tuổi lần 2: "Tôi bao nhiêu tuổi?"
    const m6 = "Tôi bao nhiêu tuổi?";
    const r6 = await getAiChatResponse(m6, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    assert(
      r6.reply.includes("20"),
      `6. Trả lời đúng tuổi mới nhất (20) khi hỏi 'Tôi bao nhiêu tuổi?': "${r6.reply}"`
    );

    // 7. Chia sẻ cảm xúc / tâm trạng: "nay mk hơi buồn"
    const m7 = "nay mk hơi buồn";
    const r7 = await getAiChatResponse(m7, histSlang, {
      sessionId: sessSlang,
      extractedMemory: memSlang,
    });
    assert(
      r7.reply.includes("buồn") || r7.reply.includes("tâm sự") || r7.reply.includes("lắng nghe"),
      `7. Phản hồi thấu hiểu, ân cần khi người dùng chia sẻ tâm trạng 'nay mk hơi buồn': "${r7.reply.substring(0, 60)}..."`
    );
  }
  console.log("");

  // ============================================================================
  // KỊCH BẢN 12: Dấu hiệu tăng nặng & Cảnh báo Viêm ruột thừa cấp
  // ============================================================================
  console.log("🔹 Kịch bản 12: Dấu hiệu tăng nặng & Cảnh báo Viêm ruột thừa cấp");
  {
    const sessEsc = "session-esc-" + Date.now();
    let memEsc: ExtractedMemory = {};
    let histEsc: Array<{ role: "user" | "assistant"; content: string }> = [];

    // Người dùng báo đau hố chậu phải và đau tăng nặng: "đau bụng dưới bên phải, giờ đau hơn r"
    const mEsc = "đau bụng dưới bên phải, giờ đau hơn r";
    const rEsc = await getAiChatResponse(mEsc, histEsc, {
      sessionId: sessEsc,
      extractedMemory: memEsc,
    });

    assert(
      rEsc.safetyAlert !== undefined || rEsc.reply.includes("ruột thừa") || rEsc.reply.includes("Ruột thừa") || rEsc.reply.includes("ngoại khoa") || rEsc.reply.includes("bệnh viện"),
      `1. Phát hiện tình huống đau hố chậu phải leo thang cảnh báo ruột thừa/ngoại khoa: "${rEsc.reply.substring(0, 70)}..."`
    );

    // Câu hỏi đố tên: "đố bạn mình tên gì"
    const memNameTest: ExtractedMemory = { userName: "Hải Đăng" };
    const rDoTen = await getAiChatResponse("đố bạn mình tên gì", [], {
      sessionId: "session-doten",
      extractedMemory: memNameTest,
    });
    assert(
      rDoTen.reply.includes("Hải Đăng"),
      `2. Nhận diện câu đố tên 'đố bạn mình tên gì': "${rDoTen.reply}"`
    );
  }
  console.log("");

  // ============================================================================
  // TỔNG KẾT
  // ============================================================================
  console.log("================================================================================");
  console.log(`🎉 KẾT QUẢ KIỂM THỬ: ${passedCount}/${totalCount} TEST CASES PASSED`);
  console.log("================================================================================");

  if (passedCount === totalCount) {
    console.log("✅ TẤT CẢ 10 KỊCH BẢN BẮT BUỘC ĐÃ ĐẠT 100%!");
  } else {
    process.exit(1);
  }
}

runAllTests().catch((err) => {
  console.error("Test execution failed:", err);
  process.exit(1);
});
