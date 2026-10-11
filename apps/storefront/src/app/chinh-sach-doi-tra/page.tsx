"use client";

import React from "react";
import Link from "next/link";
import { Header } from "@/components/layout/Header";
import { Footer } from "@/components/layout/Footer";
import {
  RotateCcw,
  ShieldCheck,
  AlertTriangle,
  Clock,
  Truck,
  CreditCard,
  CheckCircle2,
  PhoneCall,
  FileText,
  Building2,
  PackageCheck,
  ArrowRight,
} from "lucide-react";

export default function ChinhSachDoiTraPage() {
  return (
    <div className="min-h-screen flex flex-col bg-[#f8fafc]">
      <Header />

      <main className="flex-1 max-w-4xl w-full mx-auto px-4 py-8 sm:py-12">
        {/* Breadcrumb */}
        <div className="flex items-center gap-2 text-xs text-slate-500 mb-6">
          <Link href="/" className="hover:text-brand-blue-600 transition-colors">Trang chủ</Link>
          <span>/</span>
          <span className="font-semibold text-slate-800">Chính sách đổi trả & hoàn tiền</span>
        </div>

        {/* Hero Header */}
        <div className="bg-white rounded-3xl p-6 sm:p-10 border border-slate-200 shadow-xs mb-8">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-brand-blue-50 text-brand-blue-700 text-xs font-bold border border-brand-blue-100 mb-4">
            <ShieldCheck className="w-4 h-4" />
            <span>Tiêu chuẩn Nhà thuốc Chuẩn GPP Bộ Y Tế</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-black text-slate-900 tracking-tight">
            Chính Sách Đổi Trả & Hoàn Tiền H4Care
          </h1>
          <p className="text-sm text-slate-600 mt-2 max-w-2xl leading-relaxed">
            H4Care cam kết 100% thuốc và vật tư y tế chính hãng, bảo quản đúng tiêu chuẩn GSP. Chúng tôi xây dựng chính sách đổi trả minh bạch nhằm bảo vệ tối đa quyền lợi và sức khỏe của quý khách hàng.
          </p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mt-6 pt-6 border-t border-slate-100 text-xs">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-emerald-50 text-emerald-700 flex items-center justify-center font-bold">
                <Clock className="w-5 h-5" />
              </div>
              <div>
                <p className="font-extrabold text-slate-900">7 Ngày đổi trả</p>
                <p className="text-slate-500">Đối với thuốc OTC nguyên seal</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-brand-blue-50 text-brand-blue-700 flex items-center justify-center font-bold">
                <Truck className="w-5 h-5" />
              </div>
              <div>
                <p className="font-extrabold text-slate-900">Miễn phí thu hồi</p>
                <p className="text-slate-500">Nếu lỗi do vận chuyển / nhà thuốc</p>
              </div>
            </div>

            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-purple-50 text-purple-700 flex items-center justify-center font-bold">
                <CreditCard className="w-5 h-5" />
              </div>
              <div>
                <p className="font-extrabold text-slate-900">Hoàn tiền 24H</p>
                <p className="text-slate-500">MoMo hoặc tài khoản ngân hàng</p>
              </div>
            </div>
          </div>
        </div>

        {/* Content Sections */}
        <div className="space-y-6">
          {/* Section 1 */}
          <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
            <h2 className="text-lg font-black text-slate-900 flex items-center gap-2 mb-3">
              <span className="w-7 h-7 rounded-lg bg-brand-blue-600 text-white flex items-center justify-center text-xs font-black">1</span>
              Thời Gian & Phạm Vi Áp Dụng
            </h2>
            <div className="text-xs sm:text-sm text-slate-600 space-y-2 leading-relaxed">
              <p>
                • Thời hạn yêu cầu đổi trả là <strong>07 ngày</strong> kể từ ngày quý khách nhận được bưu phẩm thành công theo dữ liệu bưu tá giao hàng.
              </p>
              <p>
                • Áp dụng cho toàn bộ các sản phẩm: Thuốc không kê đơn (OTC), Thực phẩm chức năng, Mỹ phẩm dược liệu, Dụng cụ và Thiết bị y tế gia đình được mua trực tiếp trên nền tảng trực tuyến H4Care.
              </p>
            </div>
          </div>

          {/* Section 2 */}
          <div className="bg-white rounded-2xl p-6 sm:p-8 border border-rose-200/80 bg-rose-50/20 shadow-xs">
            <h2 className="text-lg font-black text-rose-900 flex items-center gap-2 mb-3">
              <span className="w-7 h-7 rounded-lg bg-rose-600 text-white flex items-center justify-center text-xs font-black">2</span>
              Các Sản Phẩm KHÔNG ĐƯỢC Đổi Trả (Quy Định Pháp Luật Dược)
            </h2>
            <p className="text-xs text-rose-700 mb-3">
              Căn cứ theo Luật Dược và Tiêu chuẩn Thực hành tốt Phân phối thuốc (GDP) của Bộ Y Tế, nhằm đảm bảo tuyệt đối tính an toàn, tránh nguy cơ nhiễm khuẩn chéo và duy trì chuỗi bảo quản chất lượng thuốc:
            </p>
            <ul className="text-xs sm:text-sm text-slate-700 space-y-2.5 list-disc pl-5">
              <li>
                <strong>Thuốc kê đơn (Rx):</strong> H4Care KHÔNG nhận đổi trả các thuốc thuộc danh mục kê đơn sau khi bưu phẩm đã được giao thành công và khách hàng đã ký nhận.
              </li>
              <li>
                <strong>Vaccine và Sinh phẩm dây chuyền lạnh (2°C - 8°C):</strong> Không đổi trả vì nhiệt độ môi trường ngoài kho dược có thể làm hỏng hoạt tính sinh học.
              </li>
              <li>
                <strong>Sản phẩm đã bị bóc tem niêm phong, vỡ seal hoặc rách bao bì:</strong> Trừ trường hợp quý khách quay video mở hộp ghi nhận sản phẩm đã bị hư hỏng trước khi mở.
              </li>
              <li>
                <strong>Sản phẩm bảo quản sai khuyến nghị:</strong> Bị ẩm ướt, mốc, chảy rữa hoặc phơi dưới ánh nắng trực tiếp do bảo quản tại gia đình.
              </li>
            </ul>
          </div>

          {/* Section 3 */}
          <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
            <h2 className="text-lg font-black text-slate-900 flex items-center gap-2 mb-3">
              <span className="w-7 h-7 rounded-lg bg-brand-blue-600 text-white flex items-center justify-center text-xs font-black">3</span>
              Trách Nhiệm Chi Phí Vận Chuyển Đổi Trả
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-xs sm:text-sm">
              <div className="p-4 rounded-xl bg-emerald-50/70 border border-emerald-200 space-y-2">
                <span className="font-extrabold text-emerald-900 text-sm block">100% Miễn phí vận chuyển</span>
                <p className="text-slate-700">
                  H4Care chịu toàn bộ phí vận chuyển thu hồi bưu phẩm và phí gửi hàng đổi mới khi:
                </p>
                <ul className="list-disc pl-4 text-slate-600 text-xs space-y-1">
                  <li>Giao nhầm thuốc, sai quy cách, sai liều lượng so với đơn đặt.</li>
                  <li>Sản phẩm bị bể vỡ, móp méo, trào dung dịch trong quá trình vận chuyển.</li>
                  <li>Hạn sử dụng của thuốc còn dưới 06 tháng tại thời điểm giao.</li>
                </ul>
              </div>

              <div className="p-4 rounded-xl bg-slate-50 border border-slate-200 space-y-2">
                <span className="font-extrabold text-slate-900 text-sm block">Khách hàng chi trả phí gửi</span>
                <p className="text-slate-700">
                  Quý khách vui lòng thanh toán phí chuyển phát về kho H4Care khi:
                </p>
                <ul className="list-disc pl-4 text-slate-600 text-xs space-y-1">
                  <li>Đặt nhầm loại thuốc hoặc số lượng.</li>
                  <li>Không còn nhu cầu sử dụng (Sản phẩm còn nguyên tem niêm phong).</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Section 4 */}
          <div className="bg-white rounded-2xl p-6 sm:p-8 border border-slate-200 shadow-xs">
            <h2 className="text-lg font-black text-slate-900 flex items-center gap-2 mb-4">
              <span className="w-7 h-7 rounded-lg bg-brand-blue-600 text-white flex items-center justify-center text-xs font-black">4</span>
              Quy Trình 4 Bước Đổi Trả & Thẩm Định Kho
            </h2>

            <div className="space-y-4">
              <div className="flex items-start gap-3.5">
                <div className="w-8 h-8 rounded-full bg-brand-blue-100 text-brand-blue-700 font-black text-xs flex items-center justify-center shrink-0 mt-0.5">
                  1
                </div>
                <div>
                  <h3 className="font-bold text-xs sm:text-sm text-slate-900">Gửi Yêu Cầu Trực Tuyến</h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Đăng nhập tài khoản H4Care, vào mục <strong>Lịch sử đơn hàng</strong> hoặc <strong>Đổi trả & Hoàn tiền</strong>, chọn sản phẩm và tải ảnh chụp hiện trạng/hóa đơn.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3.5">
                <div className="w-8 h-8 rounded-full bg-brand-blue-100 text-brand-blue-700 font-black text-xs flex items-center justify-center shrink-0 mt-0.5">
                  2
                </div>
                <div>
                  <h3 className="font-bold text-xs sm:text-sm text-slate-900">Dược Sĩ Phê Duyệt Sơ Bộ</h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Dược sĩ chuyên môn H4Care kiểm tra hồ sơ thuốc trong vòng 2-4 giờ làm việc và thông báo kết quả phê duyệt kèm hướng dẫn gửi hàng.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3.5">
                <div className="w-8 h-8 rounded-full bg-brand-blue-100 text-brand-blue-700 font-black text-xs flex items-center justify-center shrink-0 mt-0.5">
                  3
                </div>
                <div>
                  <h3 className="font-bold text-xs sm:text-sm text-slate-900">Gửi Bưu Phẩm Về Kho & Cập Nhật Mã Vận Đơn</h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Quý khách đóng gói cẩn thận, gửi về Kho Dược H4Care và điền mã bưu tá (VNPost, ViettelPost, GHTK, GHN...) trực tiếp trên trang đổi trả của tài khoản.
                  </p>
                </div>
              </div>

              <div className="flex items-start gap-3.5">
                <div className="w-8 h-8 rounded-full bg-brand-blue-100 text-brand-blue-700 font-black text-xs flex items-center justify-center shrink-0 mt-0.5">
                  4
                </div>
                <div>
                  <h3 className="font-bold text-xs sm:text-sm text-slate-900">Thẩm Định Thực Tế & Hoàn Tiền / Giao Đổi Mới</h3>
                  <p className="text-xs text-slate-600 mt-0.5">
                    Ngay khi kho tiếp nhận bưu phẩm, dược sĩ kiểm tra seal và số lô (Batch/Lot). Tiền hoàn được giải ngân tự động qua MoMo hoặc chuyển khoản ngân hàng trong 24 giờ.
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Section 5: Warehouse info & CTA */}
          <div className="bg-slate-900 text-white rounded-3xl p-6 sm:p-8 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-6">
            <div>
              <div className="flex items-center gap-2 mb-2">
                <Building2 className="w-5 h-5 text-brand-cyan-400" />
                <h3 className="font-extrabold text-base">Địa chỉ tiếp nhận hàng đổi trả H4Care:</h3>
              </div>
              <p className="text-xs text-slate-300">
                Kho Trung Tâm Dược Phẩm H4Care: 123 Đường Nguyễn Huệ, Phường Bến Nghé, Quận 1, TP. Hồ Chí Minh
              </p>
              <p className="text-xs text-slate-400 mt-1">
                Kênh hỗ trợ đổi trả Dược khoa: <strong className="text-white">duocsi@h4care.vn</strong> (Phản hồi 8h00 - 21h00 hàng ngày)
              </p>
            </div>

            <Link
              href="/account#returns"
              className="px-5 py-3 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-500 text-white font-bold text-xs flex items-center gap-2 transition-all shrink-0 shadow-lg"
            >
              <span>Vào trang Đổi Trả Của Tôi</span>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </main>

      <Footer />
    </div>
  );
}
