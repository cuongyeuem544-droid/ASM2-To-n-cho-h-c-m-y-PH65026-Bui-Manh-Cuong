export interface DrugKnowledgeItem {
  name: string;
  aliases: string[];
  activeIngredient: string;
  drugClass: string;
  isPrescription: boolean;
  indications: string;
  contraindications: string;
  commonSideEffects: string;
  seriousSideEffects: string;
  overdoseWarnings: string;
  importantPrecautions: string;
  interactions: string;
  generalDosageGuidance: string;
}

export const DRUG_KNOWLEDGE_BASE: DrugKnowledgeItem[] = [
  {
    name: "Paracetamol",
    aliases: ["paracetamol", "panadol", "efferalgan", "hapacol", "acetaminophen", "tylenol"],
    activeIngredient: "Paracetamol (Acetaminophen)",
    drugClass: "Thuốc giảm đau, hạ sốt không chứa opioid (NSAID-like / Aniline analgesic)",
    isPrescription: false,
    indications: "Hạ sốt trong các trường hợp cảm cúm, sốt siêu vi, sau tiêm chủng. Giảm các cơn đau nhẹ đến vừa: đau đầu, đau nửa đầu, đau răng, đau nhức cơ bắp, đau họng, đau bụng kinh.",
    contraindications: "Người quá mẫn với Paracetamol. Bệnh nhân suy gan nặng, viêm gan cấp tính tiến triển. Người thiếu hụt men G6PD.",
    commonSideEffects: "Hiếm khi xuất hiện ở liều thông thường. Đôi khi có thể gặp ban da nhẹ, ngứa mày đay, buồn nôn, rối loạn tiêu hóa nhẹ.",
    seriousSideEffects: "Phản ứng da nghiêm trọng (hội chứng Stevens-Johnson, hoại tử biểu bì nhiễm độc TEN - rất hiếm). Hoại tử tế bào gan cấp tính, suy gan tiến triển không hồi phục khi dùng quá liều hoặc dùng kéo dài.",
    overdoseWarnings: "⚠️ **CẢNH BÁO QUÁ LIỀU & ĐỘC TÍNH TRÊN GAN:**\n- Liều tối đa ở người lớn là **4.000 mg (4g)/ngày**, mỗi lần cách nhau tối thiểu 4 - 6 giờ. Tuyệt đối không dùng quá 1.000 mg/lần.\n- Liều ở trẻ em tính theo cân nặng: **10 - 15 mg/kg/lần**, tối đa 60 mg/kg/ngày.\n- Dùng quá liều (trên 10g ở người lớn) có thể gây hoại tử tế bào gan không hồi phục. Tuyệt đối không uống rượu bia khi dùng thuốc vì tăng gấp đôi độc tính cho gan.",
    importantPrecautions: "Kiểm tra kỹ thành phần các loại thuốc đang dùng chung (như thuốc trị cảm sốt, thuốc ho tổng hợp) để tránh vô tình uống trùng hoạt chất Paracetamol dẫn đến quá liều tích lũy.",
    interactions: "Thuốc chống đông máu (Warfarin): dùng Paracetamol liều cao kéo dài làm tăng nhẹ tác dụng chống đông. Rượu bia: làm tăng nguy cơ tổn thương gan nặng. Thuốc chống co giật (Phenytoin, Barbiturat, Carbamazepin) làm tăng chuyển hóa độc của paracetamol.",
    generalDosageGuidance: "Người lớn: 500mg - 1000mg/lần, uống cách nhau 4 - 6 giờ khi cần (tối đa không quá 4g/ngày). Uống với nhiều nước. Không tự ý dùng giảm đau quá 10 ngày ở người lớn hoặc quá 5 ngày ở trẻ em nếu không có chỉ định bác sĩ.",
  },
  {
    name: "Ibuprofen",
    aliases: ["ibuprofen", "advil", "motrin", "gofen", "brufen"],
    activeIngredient: "Ibuprofen",
    drugClass: "Thuốc chống viêm không steroid (NSAID)",
    isPrescription: false,
    indications: "Giảm đau, kháng viêm và hạ sốt trong các trường hợp: đau răng, đau khớp, đau mỏi cơ, đau đầu, đau bụng kinh, viêm khớp dạng thấp thoái hóa nhẹ.",
    contraindications: "Người có tiền sử loét dạ dày - tá tràng tiến triển, xuất huyết tiêu hóa. Suy gan, suy thận nặng, suy tim nặng. Phụ nữ mang thai 3 tháng cuối (nguy cơ đóng sớm ống động mạch của thai nhi).",
    commonSideEffects: "Rối loạn tiêu hóa: đau thượng vị, ợ nóng, đầy bụng, buồn nôn. Chóng mặt, ù tai nhẹ.",
    seriousSideEffects: "Loét thủng dạ dày - tá tràng, xuất huyết tiêu hóa (phân đen, nôn ra máu). Suy giảm chức năng thận cấp, tăng huyết áp, tăng nhẹ nguy cơ biến cố tim mạch khi dùng liều cao dài ngày.",
    overdoseWarnings: "⚠️ **CẢNH BÁO NSAID:** Uống sau bữa ăn no để hạn chế kích ứng niêm mạc dạ dày. Không dùng cho bệnh nhân hen phế quản có tiền sử co thắt phế quản do aspirin/NSAID.",
    importantPrecautions: "Thận trọng ở người cao tuổi, người có tiền sử bệnh tim mạch hoặc bệnh thận. Phải uống thuốc cùng với bữa ăn hoặc sữa.",
    interactions: "Không dùng chung với các NSAID khác (Aspirin, Naproxen, Diclofenac) hoặc Corticoid vì tăng nguy cơ loét thủng dạ dày. Giảm tác dụng của thuốc hạ huyết áp. Tăng nồng độ Methotrexate và Lithium trong máu.",
    generalDosageGuidance: "Người lớn: 200mg - 400mg/lần, uống sau khi ăn no, cách mỗi 4 - 6 giờ (tối đa không quá 1.200 mg/ngày nếu tự điều trị không kê đơn).",
  },
  {
    name: "Vitamin C",
    aliases: ["vitamin c", "acid ascorbic", "ascorbic acid", "c sủi", "berocca"],
    activeIngredient: "Acid ascorbic (Vitamin C)",
    drugClass: "Vitamin tan trong nước / Chất chống oxy hóa",
    isPrescription: false,
    indications: "Dự phòng và điều trị thiếu hụt Vitamin C (bệnh Scorbut). Tăng cường sức đề kháng cho cơ thể trong giai đoạn cảm cúm, hồi phục sau ốm dậy. Hỗ trợ hấp thu chất sắt, chống oxy hóa.",
    contraindications: "Người có tiền sử sỏi thận (đặc biệt là sỏi oxalat), người tăng oxalat niệu, người mắc bệnh ứ sắt (Hemochromatosis), bệnh nhân thiếu hụt men G6PD (nguy cơ tan máu).",
    commonSideEffects: "Liều cao (trên 1g/ngày) có thể gây rối loạn tiêu hóa: tiêu chảy, cồn cào ruột, buồn nôn, co thắt dạ dày, mất ngủ nếu uống vào buổi tối.",
    seriousSideEffects: "Lắng đọng sỏi Calci Oxalat ở đường tiết niệu khi dùng liều cao kéo dài, tan máu ở người thiếu men G6PD.",
    overdoseWarnings: "Nhu cầu hàng ngày của người lớn chỉ khoảng 75 - 90mg. Liều bổ sung thông thường từ 100 - 500mg/ngày. Tránh lạm dụng liều cao trên 1.000mg (1g)/ngày trong thời gian dài vì nguy cơ tạo sỏi thận.",
    importantPrecautions: "Nên uống vào ban ngày (sau bữa ăn sáng hoặc trưa), uống nhiều nước. Hạn chế uống vào chiều muộn hoặc tối vì có thể gây kích thích thần kinh làm khó ngủ.",
    interactions: "Tăng hấp thu sắt ở ruột non. Dùng chung với Aspirin làm tăng bài tiết Vitamin C qua nước tiểu. Có thể làm sai lệch kết quả xét nghiệm đường huyết hoặc xét nghiệm máu ẩn trong phân.",
    generalDosageGuidance: "Người lớn: 100mg - 500mg/ngày, uống sau bữa ăn sáng. Viên sủi cần hòa tan hoàn toàn trong một ly nước (khoảng 150 - 200ml) trước khi uống.",
  },
  {
    name: "Smecta",
    aliases: ["smecta", "diosmectite", "diosmectit"],
    activeIngredient: "Diosmectite 3g",
    drugClass: "Thuốc bảo vệ niêm mạc đường tiêu hóa / Đất sét khoáng",
    isPrescription: false,
    indications: "Điều trị các triệu chứng trong tiêu chảy cấp ở trẻ em, nhũ nhi và người lớn (kết hợp bù nước điện giải Oresol). Hỗ trợ điều trị các triệu chứng đau do viêm thực quản, dạ dày và đại tràng.",
    contraindications: "Mẫn cảm với Diosmectite. Bệnh nhân hẹp đường tiêu hóa cơ học nặng.",
    commonSideEffects: "Táo bón nhẹ (thường hết khi giảm liều hoặc ngừng thuốc).",
    seriousSideEffects: "Hiếm gặp: phản ứng dị ứng, nổi mề đay, phù mạch.",
    overdoseWarnings: "Quan trọng nhất trong điều trị tiêu chảy là **BÙ ĐỦ NƯỚC VÀ ĐIỆN GIẢI (Oresol)**. Smecta chỉ có tác dụng bao niêm mạc và hấp phụ độc tố, không thay thế được việc bù nước.",
    importantPrecautions: "Vì thuốc có đặc tính hấp phụ cao, **PHẢI UỐNG CÁCH CÁC THUỐC KHÁC ÍT NHẤT 2 GIỜ** để tránh làm giảm sự hấp thu của các loại thuốc uống cùng.",
    interactions: "Làm giảm hoặc chậm hấp thu hầu hết các loại thuốc khác nếu uống cùng thời điểm.",
    generalDosageGuidance: "Người lớn: trung bình 3 gói/ngày, hòa vào nửa ly nước ấm. Trong tiêu chảy cấp, liều có thể tăng gấp đôi khi bắt đầu điều trị. Trẻ em dùng theo hướng dẫn của Dược sĩ/Bác sĩ.",
  },
];

/**
 * Tra cứu thông tin dược lý hoạt chất theo tên hoặc alias
 */
export function findDrugKnowledge(query: string): DrugKnowledgeItem | null {
  const norm = query.toLowerCase().trim();

  for (const item of DRUG_KNOWLEDGE_BASE) {
    if (norm.includes(item.name.toLowerCase())) {
      return item;
    }
    for (const alias of item.aliases) {
      if (norm.includes(alias.toLowerCase())) {
        return item;
      }
    }
  }

  return null;
}

/**
 * Định dạng câu trả lời DRUG_INFORMATION chuẩn y khoa
 */
export function formatDrugInformationReply(drug: DrugKnowledgeItem): string {
  return `### 💊 Thông tin Dược chất: **${drug.name}** (${drug.activeIngredient})

- **Nhóm dược lý:** ${drug.drugClass}
- **Phân loại:** ${drug.isPrescription ? "🔴 Thuốc kê đơn (Rx - Yêu cầu đơn bác sĩ)" : "🟢 Thuốc không kê đơn (OTC)"}

#### 1. Công dụng & Chỉ định chính
${drug.indications}

#### 2. Cảnh báo an toàn quan trọng
${drug.overdoseWarnings}

#### 3. Chống chỉ định
- ${drug.contraindications}

#### 4. Tác dụng phụ cần lưu ý
- **Thường gặp / nhẹ:** ${drug.commonSideEffects}
- **Nghiêm trọng / hiếm gặp:** ${drug.seriousSideEffects}

#### 5. Liều dùng & Cách dùng tham khảo
${drug.generalDosageGuidance}

---
*⚠️ **Khuyến cáo y khoa từ Dược sĩ H4CARE:** Thông tin trên trích xuất từ Dược thư Quốc gia và tài liệu chính thức của nhà sản xuất. Quý khách tuyệt đối không tự ý tăng liều, không kết hợp tùy tiện các thuốc cùng loại và cần đọc kỹ hướng dẫn sử dụng trước khi dùng.*`;
}

/**
 * Định dạng câu trả lời riêng về TÁC DỤNG PHỤ của hoạt chất
 */
export function formatDrugSideEffectsReply(drug: DrugKnowledgeItem): string {
  return `### ⚠️ Tác dụng phụ của thuốc **${drug.name}** (${drug.activeIngredient}):

#### 1. Tác dụng phụ thường gặp hoặc nhẹ:
- ${drug.commonSideEffects}
*(Các triệu chứng này thường nhẹ và tự thuyên giảm sau khi ngừng thuốc).*

#### 2. Tác dụng phụ nghiêm trọng & Dấu hiệu nguy hiểm:
- ${drug.seriousSideEffects}

#### 3. Cảnh báo quá liều & Ngộ độc:
${drug.overdoseWarnings}

#### 4. Cách phòng ngừa tác dụng phụ:
- Luôn uống thuốc đúng liều lượng chỉ định, không tự ý kéo dài số ngày uống.
- ${drug.importantPrecautions}
- Nếu xuất hiện phát ban, khó thở, sưng mí mắt/môi, hoặc nôn nao dữ dội, hãy ngưng dùng thuốc và đến cơ sở y tế ngay.

---
*Nguồn: Dược thư Quốc gia Việt Nam & Cơ sở dữ liệu Dược khoa H4CARE.*`;
}

/**
 * So sánh hai loại thuốc (ví dụ Paracetamol và Ibuprofen)
 */
export function formatDrugComparisonReply(drugA: DrugKnowledgeItem, drugB: DrugKnowledgeItem): string {
  return `### ⚖️ So sánh dược lý giữa **${drugA.name}** và **${drugB.name}**:

| Tiêu chí | ${drugA.name} (${drugA.activeIngredient}) | ${drugB.name} (${drugB.activeIngredient}) |
| :--- | :--- | :--- |
| **Nhóm thuốc** | ${drugA.drugClass} | ${drugB.drugClass} |
| **Tác dụng kháng viêm** | ❌ **Không** có tác dụng chống viêm | ✅ **Có** tác dụng kháng viêm mạnh |
| **Hạ sốt & Giảm đau** | ✅ Tốt, an toàn cho dạ dày | ✅ Tốt, phù hợp đau do viêm |
| **Độc tính chính cần tránh** | ⚠️ Độc trên **Gan** khi quá liều | ⚠️ Kích ứng **Dạ dày** (loét, xuất huyết) & thận |
| **Thời điểm uống** | Có thể uống trước hoặc sau ăn | **Bắt buộc** uống sau khi ăn no |

#### 💡 Điểm giống và khác nhau cốt lõi:
- **Giống nhau:** Cả hai đều có tác dụng giảm đau từ nhẹ đến vừa và hạ sốt.
- **Khác nhau cơ bản:** ${drugB.name} thuộc nhóm NSAID có tính kháng viêm (giảm sưng, đỏ, viêm khớp), nhưng dễ gây đau dạ dày. Trong khi đó, ${drugA.name} là lựa chọn đầu tay an toàn hơn cho người có bệnh lý dạ dày, trẻ em và người cao tuổi.
- **Lưu ý an toàn:** Không nên tự ý phối hợp hai thuốc nếu không có chỉ định chuyên môn từ bác sĩ hoặc dược sĩ.`;
}
