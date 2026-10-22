import { NextRequest, NextResponse } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { productId, patientName, phoneNumber, prescriptionFileName, storageKey, notes } = body;

    if (!productId || typeof productId !== "number") {
      return NextResponse.json(
        { success: false, message: "Thiếu thông tin mã sản phẩm cần tư vấn." },
        { status: 400 }
      );
    }

    const cleanPhone = (phoneNumber || "").trim().replace(/\s+/g, "");
    if (!/^(0|\+84)(3|5|7|8|9)[0-9]{8}$/.test(cleanPhone)) {
      return NextResponse.json(
        { success: false, message: "Số điện thoại không đúng định dạng di động Việt Nam (10 số)." },
        { status: 400 }
      );
    }

    const cleanName = (patientName || "").trim();
    if (!cleanName || cleanName.length < 2) {
      return NextResponse.json(
        { success: false, message: "Vui lòng nhập họ và tên người bệnh hợp lệ (tối thiểu 2 ký tự)." },
        { status: 400 }
      );
    }

    const apiBase =
      process.env.INTERNAL_API_URL ||
      process.env.NEXT_PUBLIC_API_URL ||
      "http://127.0.0.1:8000";

    const backendRes = await fetch(`${apiBase}/api/v1/store/prescriptions/consult`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        product_id: productId,
        patient_name: cleanName,
        phone_number: cleanPhone,
        prescription_file_name: prescriptionFileName || undefined,
        storage_key: storageKey || undefined,
        notes: notes || undefined,
      }),
    });

    const data = await backendRes.json().catch(() => null);

    if (!backendRes.ok) {
      return NextResponse.json(
        {
          success: false,
          message: data?.detail || "Máy chủ không thể tiếp nhận yêu cầu tư vấn lúc này. Vui lòng thử lại.",
        },
        { status: backendRes.status }
      );
    }

    return NextResponse.json(data, { status: 200 });
  } catch (error) {
    console.error("[PrescriptionConsult API Error]", error);
    return NextResponse.json(
      {
        success: false,
        message: "Không thể kết nối đến hệ thống Dược sĩ. Vui lòng kiểm tra kết nối mạng và thử lại.",
      },
      { status: 502 }
    );
  }
}
