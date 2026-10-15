async function testHttpChat() {
  const url = "http://localhost:3000/api/chat";

  console.log("=== KIỂM THỬ HTTP TRỰC TIẾP TẠI http://localhost:3000/api/chat ===\n");

  const testRequests = [
    {
      label: "1. Chào hỏi",
      payload: { message: "Xin chào", conversationHistory: [] },
    },
    {
      label: "2. Triệu chứng ban đầu",
      payload: { message: "Tôi bị đau âm ỉ bụng dưới", conversationHistory: [] },
    },
    {
      label: "3. Ngữ cảnh đa lượt (Từ hôm qua)",
      payload: {
        message: "Từ hôm qua",
        conversationHistory: [
          { role: "user", content: "Tôi bị đau âm ỉ bụng dưới" },
          { role: "assistant", content: "Mình có thể hỏi thêm vài thông tin để hỗ trợ bạn nhé. Bạn đau bụng dưới từ khi nào?" },
        ],
      },
    },
    {
      label: "4. Cấp cứu P0 (Ngất)",
      payload: {
        message: "Tôi đau bụng dữ dội và bị ngất",
        conversationHistory: [
          { role: "user", content: "Tôi bị đau âm ỉ bụng dưới" },
          { role: "assistant", content: "Cơn đau chủ yếu ở bên trái, bên phải hay giữa bụng dưới?" },
        ],
      },
    },
    {
      label: "5. Thông tin thuốc Paracetamol",
      payload: { message: "Paracetamol là thuốc gì?", conversationHistory: [] },
    },
    {
      label: "6. Tìm kiếm Vitamin C",
      payload: { message: "H4CARE có vitamin C không?", conversationHistory: [] },
    },
    {
      label: "7. Tác dụng phụ đại từ thay thế",
      payload: {
        message: "Thuốc đó có tác dụng phụ gì?",
        conversationHistory: [
          { role: "user", content: "Paracetamol là thuốc gì?" },
          { role: "assistant", content: "**Paracetamol** là thuốc giảm đau, hạ sốt..." },
        ],
      },
    },
    {
      label: "8. Yêu cầu gặp Dược sĩ thật",
      payload: { message: "Tôi muốn gặp dược sĩ thật", conversationHistory: [] },
    },
  ];

  for (const t of testRequests) {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(t.payload),
    });

    const json = await res.json();
    console.log(`[${t.label}] HTTP ${res.status}`);
    console.log(` -> Intent: ${json.intentDetected}`);
    console.log(` -> Provider: ${json.providerUsed}`);
    console.log(` -> Products: ${json.recommendedProducts?.length || 0}`);
    console.log(` -> SafetyAlert: ${json.safetyAlert ? json.safetyAlert.level : "None"}`);
    console.log(` -> Reply: ${json.reply?.slice(0, 100)}...\n`);
  }
}

testHttpChat().catch(console.error);
