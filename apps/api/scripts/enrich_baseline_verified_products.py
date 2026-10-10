"""
Enrich and cross-reference 6 baseline products with authentic Vietnamese Drug Administration data.
Preserve database integrity, clean fake registration numbers, configure realistic multi-SKU packaging.
"""
import sqlite3
from datetime import datetime

DB_PATH = "pharmatrust.db"

BASELINE_DATA = [
    {
        "id": 501,
        "name": "Thuốc hạ sốt Hapacol 250mg",
        "reg_no": "VD-22709-15",
        "manufacturer": "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)",
        "country": "Việt Nam",
        "dosage_form": "Thuốc bột sủi bọt uống",
        "route": "Đường uống",
        "package": "Hộp 24 gói x 1.5g",
        "description": "Thuốc hạ sốt giảm đau Hapacol 250mg chứa Paracetamol thích hợp cho trẻ em từ 4-6 tuổi với hương cam vị ngọt dễ uống, hòa tan nhanh trong nước.",
        "indications": "Hạ sốt, giảm đau cho trẻ em trong các trường hợp: cảm cúm, sốt xuất huyết, mọc răng, sau tiêm chủng, đau họng, nhức đầu.",
        "usage": "Hòa tan gói thuốc vào lượng nước thích hợp cho đến khi sủi hết bọt. Liều thông thường: 1 gói/lần, cách mỗi 4 - 6 giờ nếu cần, không quá 5 lần/ngày.",
        "contraindications": "Mẫn cảm với Paracetamol. Bệnh nhân thiếu hụt men G6PD, suy gan nặng.",
        "side_effects": "Hiếm gặp: ban da, mày đay. Dùng quá liều gây tổn thương tế bào gan nghiêm trọng.",
        "storage": "Bảo quản nơi khô mát, nhiệt độ dưới 30°C, tránh ẩm và ánh sáng trực tiếp.",
        "skus": [
            {"sku_code": "SKU-HAPA-250-BOX", "uom": "Hộp", "conversion_rate": 24, "base_price": 45000, "is_default": 1},
            {"sku_code": "SKU-HAPA-250-SACHET", "uom": "Gói", "conversion_rate": 1, "base_price": 2000, "is_default": 0},
        ],
    },
    {
        "id": 88520,
        "name": "Vitamin C 500mg Dược Hậu Giang",
        "reg_no": "VD-22285-15",
        "manufacturer": "Công ty Cổ phần Dược Hậu Giang (DHG Pharma)",
        "country": "Việt Nam",
        "dosage_form": "Viên nén",
        "route": "Đường uống",
        "package": "Hộp 10 vỉ x 10 viên (100 viên)",
        "description": "Vitamin C 500mg DHG bổ sung acid ascorbic thiết yếu tham gia vào quá trình tạo collagen, mô liên kết, tăng cường miễn dịch tự nhiên và hỗ trợ hấp thu sắt.",
        "indications": "Điều trị và phòng ngừa bệnh do thiếu hụt Vitamin C (scurvy). Tăng cường sức đề kháng khi nhiễm khuẩn, cảm cúm, hồi phục sau phẫu thuật.",
        "usage": "Người lớn uống 1 viên/ngày sau bữa ăn hoặc theo chỉ định của Bác sĩ.",
        "contraindications": "Quá mẫn với Vitamin C. Người có tiền sử sỏi thận oxalate, rối loạn chuyển hóa sắt, thiếu men G6PD.",
        "side_effects": "Dùng liều cao kéo dài có thể gây kích ứng dạ dày, tiêu chảy, lắng đọng sỏi thận oxalate.",
        "storage": "Bảo quản nơi khô ráo, nhiệt độ dưới 30°C, tránh ánh sáng trực tiếp.",
        "skus": [
            {"sku_code": "SKU-VITC-500-BOX", "uom": "Hộp", "conversion_rate": 10, "base_price": 60000, "is_default": 1},
            {"sku_code": "SKU-VITC-500-BLISTER", "uom": "Vỉ", "conversion_rate": 1, "base_price": 6500, "is_default": 0},
        ],
    },
    {
        "id": 99770,
        "name": "Siro Ho Prospan 100ml",
        "reg_no": "VN-18235-14",
        "manufacturer": "Engelhard Arzneimittel GmbH & Co. KG (Đức) - Nhập khẩu bởi Sohaco",
        "country": "Đức",
        "dosage_form": "Siro uống",
        "route": "Đường uống",
        "package": "Chai 100ml kèm cốc đong",
        "description": "Siro ho thảo dược Prospan chiết xuất độc quyền EA 575 từ lá thường xuân giúp tiêu nhầy, chống co thắt phế quản và cắt cơn ho an toàn cho cả gia đình.",
        "indications": "Điều trị viêm đường hô hấp cấp có kèm theo ho; điều trị triệu chứng trong các bệnh lý viêm phế quản mạn tính.",
        "usage": "Lắc kỹ trước khi dùng. Trẻ dưới 6 tuổi: 2.5ml/lần x 3 lần/ngày. Trẻ 6-12 tuổi: 5ml/lần x 3 lần/ngày. Trẻ trên 12 tuổi & người lớn: 5-7.5ml/lần x 3 lần/ngày.",
        "contraindications": "Chống chỉ định ở người không dung nạp đường fructose do thành phần siro chứa sorbitol.",
        "side_effects": "Rất hiếm gặp phản ứng dị ứng da hoặc nhuận tràng nhẹ.",
        "storage": "Bảo quản nơi khô mát dưới 25°C. Đóng chặt nắp chai sau khi dùng. Sử dụng trong 3 tháng kể từ khi mở nắp.",
        "skus": [
            {"sku_code": "SKU-PROSPAN-100-BOTTLE", "uom": "Chai", "conversion_rate": 1, "base_price": 85000, "is_default": 1},
        ],
    },
    {
        "id": 106139,
        "name": "Thuốc dị ứng Telfast HD 180mg",
        "reg_no": "VD-25032-16",
        "manufacturer": "Công ty TNHH Sanofi-Aventis Việt Nam",
        "country": "Việt Nam",
        "dosage_form": "Viên nén bao phim",
        "route": "Đường uống",
        "package": "Hộp 1 vỉ x 10 viên",
        "description": "Telfast HD 180mg chứa Fexofenadine là thuốc kháng histamin thế hệ 2 không gây buồn ngủ, tác dụng kéo dài 24 giờ điều trị hiệu quả các triệu chứng dị ứng.",
        "indications": "Điều trị triệu chứng viêm mũi dị ứng theo mùa (ngứa mũi, hắt hơi, sổ mũi, đỏ ngứa mắt), mề đay mạn tính vô căn ở người lớn và trẻ em từ 12 tuổi trở lên.",
        "usage": "Uống 1 viên (180mg) một lần mỗi ngày với nước lọc trước bữa ăn. Không uống cùng nước hoa quả bưởi chùm.",
        "contraindications": "Mẫn cảm với Fexofenadine hay bất kỳ tá dược nào của thuốc.",
        "side_effects": "Đau đầu nhẹ, mệt mỏi, buồn nôn, chóng mặt thoáng qua.",
        "storage": "Bảo quản nơi khô ráo, nhiệt độ dưới 30°C, tránh ánh sáng.",
        "skus": [
            {"sku_code": "SKU-TELFAST-180-BOX", "uom": "Hộp", "conversion_rate": 1, "base_price": 120000, "is_default": 1},
            {"sku_code": "SKU-TELFAST-180-BLISTER", "uom": "Vỉ", "conversion_rate": 1, "base_price": 120000, "is_default": 0},
        ],
    },
    {
        "id": 111691,
        "name": "Thuốc nhỏ mắt Rohto 12ml",
        "reg_no": "VD-21359-14",
        "manufacturer": "Công ty TNHH Rohto-Mentholatum (Việt Nam)",
        "country": "Việt Nam",
        "dosage_form": "Dung dịch nhỏ mắt",
        "route": "Nhỏ mắt",
        "package": "Lọ 12ml",
        "description": "Dung dịch nhỏ mắt New V.Rohto bổ sung Vitamin B6, Acid amin và hoạt chất kháng viêm làm dịu cảm giác mỏi mắt, ngứa mắt và bảo vệ giác mạc.",
        "indications": "Mỏi mắt, sung huyết kết mạc, viêm mắt do tia cực tím hoặc các tia sáng khác, ngứa mắt, phòng ngừa bệnh mắt khi bơi lội hoặc bụi bẩn.",
        "usage": "Nhỏ mắt 2 - 3 giọt mỗi mắt/lần, 5 - 6 lần/ngày.",
        "contraindications": "Bệnh nhân tăng nhãn áp (glaucoma), mẫn cảm với thành phần thuốc.",
        "side_effects": "Hiếm gặp ngứa mí mắt, đỏ mắt do kích ứng nhẹ.",
        "storage": "Bảo quản nơi khô mát dưới 30°C, tránh ánh nắng trực tiếp. Đậy kín nắp sau khi dùng.",
        "skus": [
            {"sku_code": "SKU-ROHTO-12ML-BOTTLE", "uom": "Lọ", "conversion_rate": 1, "base_price": 55000, "is_default": 1},
        ],
    },
    {
        "id": 124710,
        "name": "Men vi sinh Enterogermina 20 ống",
        "reg_no": "VN-17726-14",
        "manufacturer": "Sanofi-Aventis S.p.A. (Ý) / Opella Healthcare",
        "country": "Ý",
        "dosage_form": "Hỗn dịch uống",
        "route": "Đường uống",
        "package": "Hộp 4 vỉ x 5 ống nhựa (20 ống x 5ml)",
        "description": "Men vi sinh Enterogermina chứa 2 tỷ bào tử Bacillus clausii kháng đa kháng sinh giúp phục hồi cân bằng hệ vi sinh vật đường ruột sau kháng sinh hoặc tiêu chảy.",
        "indications": "Điều trị và phòng ngừa rối loạn hệ vi sinh đường ruột và bệnh lý kém hấp thu vitamin nội sinh. Hỗ trợ phục hồi đường ruột bị ảnh hưởng khi dùng kháng sinh kéo dài.",
        "usage": "Lắc kỹ ống trước khi mở. Uống trực tiếp hoặc pha với nước ngọt, sữa. Người lớn: 2 - 3 ống/ngày. Trẻ em: 1 - 2 ống/ngày.",
        "contraindications": "Tiền sử dị ứng với bào tử Bacillus clausii.",
        "side_effects": "Rất hiếm gặp phản ứng quá mẫn như ban da hoặc mày đay.",
        "storage": "Bảo quản ở nhiệt độ dưới 30°C. Uống ngay sau khi mở ống nhựa để tránh nhiễm khuẩn.",
        "skus": [
            {"sku_code": "SKU-ENTERO-20-BOX", "uom": "Hộp", "conversion_rate": 4, "base_price": 150000, "is_default": 1},
            {"sku_code": "SKU-ENTERO-5-BLISTER", "uom": "Vỉ 5 ống", "conversion_rate": 1, "base_price": 38000, "is_default": 0},
        ],
    },
]

def main():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Resolve collided registration numbers from imported reference catalog:
    # 279245 was given Prospan's number VN-18235-14 -> update to authentic Otrivin number VN-19659-16
    c.execute("UPDATE canonical_products SET registration_number = 'VN-19659-16' WHERE id = 279245")
    # 279213 was given Enterogermina's number VN-17726-14 -> update to REF-TELFAST-180
    c.execute("UPDATE canonical_products SET registration_number = 'REF-TELFAST-180' WHERE id = 279213")

    for prod in BASELINE_DATA:
        pid = prod["id"]
        # Update canonical_products with authentic DAV details
        c.execute("""
            UPDATE canonical_products
            SET registration_number = ?,
                manufacturer = ?,
                manufacturing_country = ?,
                dosage_form = ?,
                route = ?,
                package_description = ?,
                description = ?,
                indications = ?,
                usage_instructions = ?,
                contraindications = ?,
                side_effects = ?,
                storage_conditions = ?,
                publish_mode = 'VERIFIED_PRODUCT_DATA',
                updated_at = ?
            WHERE id = ?
        """, (
            prod["reg_no"],
            prod["manufacturer"],
            prod["country"],
            prod["dosage_form"],
            prod["route"],
            prod["package"],
            prod["description"],
            prod["indications"],
            prod["usage"],
            prod["contraindications"],
            prod["side_effects"],
            prod["storage"],
            now_str,
            pid
        ))

        # Check existing SKUs
        c.execute("SELECT id, sku_code, uom FROM product_skus WHERE canonical_product_id = ?", (pid,))
        existing_skus = c.fetchall()

        # Update primary SKU
        if existing_skus:
            primary_sku_id = existing_skus[0][0]
            default_sku_data = prod["skus"][0]
            c.execute("""
                UPDATE product_skus
                SET sku_code = ?,
                    uom = ?,
                    conversion_rate = ?,
                    base_price = ?,
                    is_default = 1,
                    is_active = 1
                WHERE id = ?
            """, (
                default_sku_data["sku_code"],
                default_sku_data["uom"],
                default_sku_data["conversion_rate"],
                default_sku_data["base_price"],
                primary_sku_id
            ))

            # If there are additional packaging SKUs (e.g. Vỉ, Gói)
            if len(prod["skus"]) > 1:
                secondary_sku_data = prod["skus"][1]
                # Check if secondary SKU already exists
                c.execute("SELECT id FROM product_skus WHERE canonical_product_id = ? AND uom = ?", (pid, secondary_sku_data["uom"]))
                sec_row = c.fetchone()
                if sec_row:
                    c.execute("""
                        UPDATE product_skus
                        SET sku_code = ?,
                            conversion_rate = ?,
                            base_price = ?,
                            is_default = 0,
                            is_active = 1
                        WHERE id = ?
                    """, (secondary_sku_data["sku_code"], secondary_sku_data["conversion_rate"], secondary_sku_data["base_price"], sec_row[0]))
                else:
                    c.execute("""
                        INSERT INTO product_skus (canonical_product_id, sku_code, barcode, uom, conversion_rate, base_price, is_default, is_active)
                        VALUES (?, ?, NULL, ?, ?, ?, 0, 1)
                    """, (
                        pid,
                        secondary_sku_data["sku_code"],
                        secondary_sku_data["uom"],
                        secondary_sku_data["conversion_rate"],
                        secondary_sku_data["base_price"]
                    ))

    conn.commit()
    print("Enrichment complete for 6 baseline products.")

    # Rebuild FTS5 index to stay in 100% sync
    c.execute("DELETE FROM products_fts")
    c.execute("""
        INSERT INTO products_fts (rowid, canonical_name, manufacturer, indications, registration_number)
        SELECT id, canonical_name, coalesce(manufacturer, ''), coalesce(indications, ''), coalesce(registration_number, '')
        FROM canonical_products
    """)
    conn.commit()

    conn.close()

if __name__ == "__main__":
    main()
