import sys
import os

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Đảm bảo import được module app
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "apps", "api"))

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_fastapi_chat_memory():
    print("Testing FastAPI Chat Memory...")
    
    # Lượt 1: Giới thiệu tên
    res1 = client.post("/api/v1/chat", json={
        "message": "Tên tôi là Nguyễn Đức Anh",
        "conversation_history": [],
        "session_id": "test-fastapi-sess",
    })
    assert res1.status_code == 200, res1.text
    data1 = res1.json()
    assert data1["extracted_memory"]["user_name"] == "Nguyễn Đức Anh"
    print("  ✅ FastAPI trích xuất tên thành công:", data1["extracted_memory"]["user_name"])

    # Lượt 2: Hỏi lại tên
    res2 = client.post("/api/v1/chat", json={
        "message": "Tên tôi là gì?",
        "conversation_history": [
            {"role": "user", "content": "Tên tôi là Nguyễn Đức Anh"},
            {"role": "assistant", "content": data1["reply"]},
        ],
        "session_id": "test-fastapi-sess",
        "extracted_memory": data1["extracted_memory"],
    })
    assert res2.status_code == 200, res2.text
    data2 = res2.json()
    assert "Nguyễn Đức Anh" in data2["reply"]
    print("  ✅ FastAPI trả lời đúng tên từ memory:", data2["reply"])

    # Lượt 3: Hỏi Paracetamol
    res3 = client.post("/api/v1/chat", json={
        "message": "Paracetamol là thuốc gì?",
        "conversation_history": [],
        "session_id": "test-fastapi-sess",
        "extracted_memory": data2["extracted_memory"],
    })
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["extracted_memory"]["last_discussed_product"] == "Paracetamol"
    print("  ✅ FastAPI ghi nhận thuốc thảo luận:", data3["extracted_memory"]["last_discussed_product"])

    # Lượt 4: Thuốc đó có tác dụng phụ gì?
    res4 = client.post("/api/v1/chat", json={
        "message": "Thuốc đó có tác dụng phụ gì?",
        "conversation_history": [],
        "session_id": "test-fastapi-sess",
        "extracted_memory": data3["extracted_memory"],
    })
    assert res4.status_code == 200
    data4 = res4.json()
    assert "Paracetamol" in data4["reply"] and "Tác dụng phụ" in data4["reply"]
    print("  ✅ FastAPI hiểu đại từ 'thuốc đó' là Paracetamol")

    # Lượt 5: Gặp dược sĩ thật (Handoff)
    res5 = client.post("/api/v1/chat", json={
        "message": "Tôi muốn gặp dược sĩ thật",
        "conversation_history": [],
        "session_id": "test-fastapi-sess",
        "extracted_memory": data4["extracted_memory"],
    })
    assert res5.status_code == 200
    data5 = res5.json()
    assert data5["handoff_requested"] is True
    print("  ✅ FastAPI kích hoạt handoff_requested = True")

    # Lượt 6: Red Flag cấp cứu
    res6 = client.post("/api/v1/chat", json={
        "message": "Tôi đau bụng dữ dội và bị ngất",
        "conversation_history": [],
        "session_id": "test-fastapi-sess",
        "extracted_memory": data5["extracted_memory"],
    })
    assert res6.status_code == 200
    data6 = res6.json()
    assert data6.get("safety_alert") is not None
    assert data6["safety_alert"]["level"] == "emergency"
    print("  ✅ FastAPI phát hiện Red Flag cấp cứu 115")

    # =========================================================================
    # CHUỖI KIỂM THỬ ĐỔI TÊN LIÊN TỤC VÀ HỘI THOẠI TỰ NHIÊN
    # =========================================================================
    print("\nTesting Continuous Multi-turn Rename & Memory Update...")
    sess_rename = "test-rename-sess"
    mem_rename = {}

    # Bước 1: "Tôi tên là Cường"
    r1 = client.post("/api/v1/chat", json={
        "message": "Tôi tên là Cường",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r1.status_code == 200
    mem_rename = r1.json()["extracted_memory"]
    assert mem_rename["user_name"] == "Cường"
    print("  ✅ 1. Nhận diện tên ban đầu:", mem_rename["user_name"])

    # Bước 2: "Tên tôi là gì?"
    r2 = client.post("/api/v1/chat", json={
        "message": "Tên tôi là gì?",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r2.status_code == 200
    assert "Cường" in r2.json()["reply"]
    print("  ✅ 2. Trả lời đúng tên ban đầu:", r2.json()["reply"])

    # Bước 3: "Giờ tôi lại thành tên Hùng"
    r3 = client.post("/api/v1/chat", json={
        "message": "Giờ tôi lại thành tên Hùng",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r3.status_code == 200
    mem_rename = r3.json()["extracted_memory"]
    assert mem_rename["user_name"] == "Hùng"
    print("  ✅ 3. Cập nhật đổi tên thành công:", mem_rename["user_name"])

    # Bước 4: "Tên tôi là gì?"
    r4 = client.post("/api/v1/chat", json={
        "message": "Tên tôi là gì?",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r4.status_code == 200
    assert "Hùng" in r4.json()["reply"]
    print("  ✅ 4. Trả lời đúng tên mới nhất:", r4.json()["reply"])

    # Bước 5: "Không, tôi tên Hoàn cơ"
    r5 = client.post("/api/v1/chat", json={
        "message": "Không, tôi tên Hoàn cơ",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r5.status_code == 200
    mem_rename = r5.json()["extracted_memory"]
    assert mem_rename["user_name"] == "Hoàn"
    print("  ✅ 5. Cập nhật sửa tên với khẩu ngữ (cơ):", mem_rename["user_name"])

    # Bước 6: "Bạn nhớ tên tôi không?"
    r6 = client.post("/api/v1/chat", json={
        "message": "Bạn nhớ tên tôi không?",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r6.status_code == 200
    assert "Hoàn" in r6.json()["reply"]
    print("  ✅ 6. Trả lời câu hỏi 'Bạn nhớ tên tôi không?':", r6.json()["reply"])

    # Bước 7: Người khác ("Mẹ tôi tên là Lan") -> Không ghi đè tên khách hàng
    r7 = client.post("/api/v1/chat", json={
        "message": "Mẹ tôi tên là Lan",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r7.status_code == 200
    mem_after_mom = r7.json()["extracted_memory"]
    assert mem_after_mom.get("user_name") == "Hoàn"
    print("  ✅ 7. Không ghi đè tên người dùng khi nhắc đến người khác (Mẹ tôi tên là Lan):", mem_after_mom.get("user_name"))

    # Bước 8: Câu không dấu ("gio goi toi la an nhe")
    r8 = client.post("/api/v1/chat", json={
        "message": "gio goi toi la an nhe",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_rename,
    })
    assert r8.status_code == 200
    mem_no_accent = r8.json()["extracted_memory"]
    assert mem_no_accent["user_name"] == "An"
    print("  ✅ 8. Nhận diện và đổi tên câu không dấu:", mem_no_accent["user_name"])

    # Bước 9: Khai báo tuổi bằng khẩu ngữ ("t 39t r, nhớ giùm nha")
    r9 = client.post("/api/v1/chat", json={
        "message": "t 39t r, nhớ giùm nha",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_no_accent,
    })
    assert r9.status_code == 200
    mem_age = r9.json()["extracted_memory"]
    assert mem_age.get("age") == 39
    print("  ✅ 9. Khai báo tuổi bằng khẩu ngữ/slang ('t 39t r'):", mem_age.get("age"))

    # Bước 10: Hỏi lại tuổi bằng teencode ("b nhớ mk bn tuổi ko")
    r10 = client.post("/api/v1/chat", json={
        "message": "b nhớ mk bn tuổi ko",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_age,
    })
    assert r10.status_code == 200
    assert "39" in r10.json()["reply"]
    print("  ✅ 10. Truy vấn tuổi bằng teencode ('b nhớ mk bn tuổi ko'):", r10.json()["reply"])

    # Bước 11: Đổi tuổi ("thực ra mk 20 r")
    r11 = client.post("/api/v1/chat", json={
        "message": "thực ra mk 20 r",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_age,
    })
    assert r11.status_code == 200
    mem_age2 = r11.json()["extracted_memory"]
    assert mem_age2.get("age") == 20
    print("  ✅ 11. Đổi tuổi thành công ('thực ra mk 20 r'):", mem_age2.get("age"))

    # Bước 12: Chia sẻ tâm trạng ("nay mk hơi buồn")
    r12 = client.post("/api/v1/chat", json={
        "message": "nay mk hơi buồn",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_age2,
    })
    assert r12.status_code == 200
    assert "buồn" in r12.json()["reply"] or "tâm sự" in r12.json()["reply"]
    print("  ✅ 12. Phản hồi thấu cảm khi chia sẻ tâm trạng ('nay mk hơi buồn'):", r12.json()["reply"][:50])

    # Bước 13: Cảnh báo đau hố chậu phải leo thang ("đau bụng dưới bên phải, giờ đau hơn r")
    r13 = client.post("/api/v1/chat", json={
        "message": "đau bụng dưới bên phải, giờ đau hơn r",
        "conversation_history": [],
        "session_id": sess_rename,
        "extracted_memory": mem_age2,
    })
    assert r13.status_code == 200
    data13 = r13.json()
    assert data13.get("safety_alert") is not None
    assert "RUỘT THỪA" in data13["safety_alert"]["title"]
    print("  ✅ 13. Cảnh báo nguy cơ viêm ruột thừa cấp khi đau hố chậu phải tăng nặng:", data13["safety_alert"]["title"])

    print("\n🎉 TOÀN BỘ TEST CASES FASTAPI CHAT MEMORY ĐẠT 100%!")

if __name__ == "__main__":
    test_fastapi_chat_memory()
