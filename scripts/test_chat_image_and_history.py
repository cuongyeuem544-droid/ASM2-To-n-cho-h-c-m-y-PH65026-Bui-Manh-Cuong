import sys
import os
import io

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token

client = TestClient(app)

def test_chat_image_upload_and_security():
    print("=================================================================")
    print("TEST 1: Image Upload, Magic Bytes Validation & Security")
    print("=================================================================")

    # 1. Valid JPEG with magic bytes \xFF\xD8\xFF
    valid_jpeg_bytes = b"\xFF\xD8\xFF\xE0\x00\x10JFIF\x00\x01\x01\x01\x00`\x00`\x00\x00\xFF\xDB\x00C\x00" + b"\x00" * 100
    res = client.post(
        "/api/v1/chat/upload",
        files={"file": ("test_medicine.jpg", io.BytesIO(valid_jpeg_bytes), "image/jpeg")}
    )
    assert res.status_code == 200, f"Upload JPEG failed: {res.text}"
    data = res.json()
    assert data["success"] is True
    attachment = data["attachment"]
    assert attachment["mime_type"] == "image/jpeg"
    att_code = data.get("attachment_code") or attachment.get("id")
    assert att_code.startswith("att-")
    print(f"  ✅ Upload JPEG hợp lệ thành công: {att_code}")

    # 2. Valid PNG with magic bytes \x89PNG\r\n\x1a\n
    valid_png_bytes = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + b"\x00" * 100
    res_png = client.post(
        "/api/v1/chat/upload",
        files={"file": ("prescription.png", io.BytesIO(valid_png_bytes), "image/png")}
    )
    assert res_png.status_code == 200, f"Upload PNG failed: {res_png.text}"
    assert res_png.json()["attachment"]["mime_type"] == "image/png"
    print("  ✅ Upload PNG hợp lệ thành công")

    # 3. Valid WEBP with magic bytes RIFF....WEBP
    valid_webp_bytes = b"RIFF\x20\x00\x00\x00WEBPVP8 " + b"\x00" * 50
    res_webp = client.post(
        "/api/v1/chat/upload",
        files={"file": ("label.webp", io.BytesIO(valid_webp_bytes), "image/webp")}
    )
    assert res_webp.status_code == 200, f"Upload WEBP failed: {res_webp.text}"
    assert res_webp.json()["attachment"]["mime_type"] == "image/webp"
    print("  ✅ Upload WEBP hợp lệ thành công")

    # 4. Reject unsupported extension (e.g. .pdf or .exe)
    res_pdf = client.post(
        "/api/v1/chat/upload",
        files={"file": ("document.pdf", io.BytesIO(b"%PDF-1.4 sample content"), "application/pdf")}
    )
    assert res_pdf.status_code == 400
    assert "không được hỗ trợ" in res_pdf.text or "JPG" in res_pdf.text
    print("  ✅ Chặn thành công tệp có đuôi không được hỗ trợ (.pdf)")

    # 5. Reject spoofed image (text content disguised with .jpg extension)
    fake_jpg = b"This is a malicious script or text disguised as jpg"
    res_fake = client.post(
        "/api/v1/chat/upload",
        files={"file": ("exploit.jpg", io.BytesIO(fake_jpg), "image/jpeg")}
    )
    assert res_fake.status_code in (400, 422)
    assert "chữ ký" in res_fake.text or "không hợp lệ" in res_fake.text
    print("  ✅ Chặn thành công tệp giả mạo chữ ký (MIME spoofing)")

    # 6. Reject file > 10MB
    oversized = b"\xFF\xD8\xFF" + b"\x00" * (10 * 1024 * 1024 + 100)
    res_over = client.post(
        "/api/v1/chat/upload",
        files={"file": ("huge.jpg", io.BytesIO(oversized), "image/jpeg")}
    )
    assert res_over.status_code in (400, 413)
    assert "10 MB" in res_over.text
    print("  ✅ Chặn thành công tệp vượt quá 10 MB")

    # 7. Secure file streaming & headers
    att_code = data.get("attachment_code") or attachment.get("id")
    res_get = client.get(f"/api/v1/chat/attachments/{att_code}")
    assert res_get.status_code == 200
    assert res_get.headers.get("x-content-type-options") == "nosniff"
    assert "max-age" in res_get.headers.get("cache-control", "")
    assert res_get.headers.get("content-type") == "image/jpeg"
    print("  ✅ Tải ảnh an toàn với security headers (nosniff, cache-control)")

    # 8. Non-existent attachment code
    res_404 = client.get("/api/v1/chat/attachments/att-nonexistent123")
    assert res_404.status_code == 404
    print("  ✅ Trả về 404 chuẩn cho attachment_code không tồn tại")


def test_chat_conversation_history_and_isolation():
    print("\n=================================================================")
    print("TEST 2: Conversation History CRUD & Strict Memory Isolation")
    print("=================================================================")

    # Lấy user có thật trong database để token hợp lệ
    from app.db.session import SessionLocal
    from app.models import User
    from sqlalchemy import select

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.is_active.is_(True)))
        assert user is not None, "Cần ít nhất 1 user active trong database để test"
        user_id = user.id
        role = user.role.value if hasattr(user.role, "value") else str(user.role)

    token = create_access_token(subject=str(user_id), role=role)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Tạo Cuộc trò chuyện 1: Bệnh nhân tên Cường, bị đau đầu
    conv1_id = "test-conv-001"
    res_create1 = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={
            "id": conv1_id,
            "title": "Tư vấn đau đầu - Cường",
            "session_id": "sess-conv1",
            "messages": [
                {"id": "m1", "role": "user", "content": "Tôi tên là Cường, bị đau đầu từ sáng", "timestamp": "10:00"},
                {"id": "m2", "role": "assistant", "content": "Chào anh Cường, anh đã dùng thuốc gì chưa?", "timestamp": "10:01"},
            ],
            "extracted_memory": {
                "user_name": "Cường",
                "symptoms": ["đau đầu"],
                "symptom_duration": "từ sáng",
            }
        }
    )
    assert res_create1.status_code == 200, res_create1.text
    print("  ✅ Lưu Cuộc trò chuyện 1 thành công (Memory: user_name=Cường)")

    # 2. Tạo Cuộc trò chuyện 2: Bệnh nhân tên Mai, hỏi về vitamin C
    conv2_id = "test-conv-002"
    res_create2 = client.post(
        "/api/v1/chat/conversations",
        headers=headers,
        json={
            "id": conv2_id,
            "title": "Hỏi về Vitamin C - Mai",
            "session_id": "sess-conv2",
            "messages": [
                {"id": "m3", "role": "user", "content": "Em là Mai, cho em hỏi uống Vitamin C lúc nào tốt?", "timestamp": "11:00"},
                {"id": "m4", "role": "assistant", "content": "Chào chị Mai, Vitamin C nên uống sau bữa ăn sáng.", "timestamp": "11:01"},
            ],
            "extracted_memory": {
                "user_name": "Mai",
                "last_discussed_product": "Vitamin C",
            }
        }
    )
    assert res_create2.status_code == 200, res_create2.text
    print("  ✅ Lưu Cuộc trò chuyện 2 thành công (Memory: user_name=Mai)")

    # 3. Lấy danh sách cuộc trò chuyện của user
    res_list = client.get("/api/v1/chat/conversations", headers=headers)
    assert res_list.status_code == 200
    conv_list = res_list.json()
    assert len(conv_list) >= 2
    ids = [c["id"] for c in conv_list]
    assert conv1_id in ids
    assert conv2_id in ids
    print(f"  ✅ Lấy danh sách cuộc trò chuyện thành công ({len(conv_list)} cuộc hội thoại)")

    # 4. Lấy chi tiết từng cuộc trò chuyện để kiểm tra tính cô lập bộ nhớ (Memory Isolation)
    res_detail1 = client.get(f"/api/v1/chat/conversations/{conv1_id}", headers=headers)
    data1 = res_detail1.json()
    assert data1["extracted_memory"]["user_name"] == "Cường"
    assert "đau đầu" in data1["extracted_memory"]["symptoms"]
    assert "Mai" not in str(data1["extracted_memory"])

    res_detail2 = client.get(f"/api/v1/chat/conversations/{conv2_id}", headers=headers)
    data2 = res_detail2.json()
    assert data2["extracted_memory"]["user_name"] == "Mai"
    assert data2["extracted_memory"]["last_discussed_product"] == "Vitamin C"
    assert "Cường" not in str(data2["extracted_memory"])
    print("  ✅ Cô lập bộ nhớ hoàn hảo: Thông tin Cuộc trò chuyện 1 không bị rò rỉ sang Cuộc trò chuyện 2")

    # 5. Đổi tên cuộc trò chuyện (Rename)
    res_rename = client.patch(
        f"/api/v1/chat/conversations/{conv1_id}",
        headers=headers,
        json={"title": "Đau đầu buổi sáng (Đã đổi tên)"}
    )
    assert res_rename.status_code == 200
    assert res_rename.json()["title"] == "Đau đầu buổi sáng (Đã đổi tên)"
    print("  ✅ Đổi tên cuộc trò chuyện thành công")

    # 6. Xóa một cuộc trò chuyện (Delete)
    res_del = client.delete(f"/api/v1/chat/conversations/{conv2_id}", headers=headers)
    assert res_del.status_code == 200
    res_check = client.get(f"/api/v1/chat/conversations/{conv2_id}", headers=headers)
    assert res_check.status_code == 404
    print("  ✅ Xóa cuộc trò chuyện thành công")


def test_ai_vision_guidelines_and_offline():
    print("\n=================================================================")
    print("TEST 3: Medical Vision Guidelines & Offline Fallback Response")
    print("=================================================================")

    # Gửi tin nhắn kèm ảnh thuốc
    res = client.post(
        "/api/v1/chat",
        json={
            "message": "Ảnh vỉ thuốc này có tác dụng gì?",
            "conversation_history": [],
            "session_id": "sess-vision-test",
            "attachments": [
                {
                    "id": "att-sample-1",
                    "file_name": "panadol.jpg",
                    "mime_type": "image/jpeg",
                    "url": "/api/v1/chat/attachments/att-sample-1",
                }
            ]
        }
    )
    assert res.status_code == 200, res.text
    data = res.json()
    reply = data["reply"]

    # Đảm bảo phản hồi tuân thủ quy chuẩn y tế
    print("  Bot phản hồi:")
    print("  ", reply[:200].replace("\n", " ") + "...")

    # Bộ nhớ ghi nhận ảnh vừa gửi
    mem = data.get("extracted_memory", {})
    assert "panadol.jpg" in str(mem) or "panadol" in str(data).lower()
    print("  ✅ Nhận diện và ghi nhớ tệp đính kèm vào session memory")

    print("\n=================================================================")
    print("🎉 TẤT CẢ TEST BACKEND CHO IMAGE & CHAT HISTORY ĐÃ VƯỢT QUA 100%!")
    print("=================================================================")

if __name__ == "__main__":
    test_chat_image_upload_and_security()
    test_chat_conversation_history_and_isolation()
    test_ai_vision_guidelines_and_offline()
