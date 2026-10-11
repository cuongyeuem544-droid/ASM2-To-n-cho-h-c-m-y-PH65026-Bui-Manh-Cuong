"use client";

import React, { useState } from "react";
import { Product } from "@/types";
import { motion, AnimatePresence } from "framer-motion";
import {
  X,
  Stethoscope,
  PhoneCall,
  UploadCloud,
  CheckCircle2,
  ShieldCheck,
  AlertCircle,
  Clock,
} from "lucide-react";
import { Button } from "../ui/Button";
import { PHARMACY_CONTACT } from "@/lib/constants";

interface RxConsultModalProps {
  product: Product | null;
  isOpen: boolean;
  onClose: () => void;
}

export const RxConsultModal: React.FC<RxConsultModalProps> = ({
  product,
  isOpen,
  onClose,
}) => {
  const [phoneNumber, setPhoneNumber] = useState("");
  const [patientName, setPatientName] = useState("");
  const [prescriptionFile, setPrescriptionFile] = useState<string | null>(null);
  const [isSubmitted, setIsSubmitted] = useState(false);

  if (!isOpen || !product) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!phoneNumber) return;
    setIsSubmitted(true);
  };

  const handleReset = () => {
    setIsSubmitted(false);
    setPhoneNumber("");
    setPatientName("");
    setPrescriptionFile(null);
    onClose();
  };

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
        {/* Backdrop */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onClick={handleReset}
          className="absolute inset-0 bg-black/50 backdrop-blur-xs"
        />

        {/* Modal Window */}
        <motion.div
          initial={{ opacity: 0, scale: 0.95, y: 12 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: 12 }}
          transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }}
          className="relative w-full max-w-lg bg-white rounded-2xl shadow-xl border border-slate-200 overflow-hidden z-10"
        >
          {/* Header */}
          <div className="bg-brand-blue-600 text-white p-5 flex items-start justify-between border-b border-brand-blue-700">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center text-white shrink-0 border border-white/20">
                <Stethoscope className="w-5 h-5" />
              </div>
              <div>
                <span className="text-[10px] font-bold tracking-wider uppercase text-brand-blue-100 bg-white/10 px-2.5 py-0.5 rounded-full inline-block mb-1">
                  Chuẩn Y Khoa • Tư Vấn Theo Toa
                </span>
                <h3 className="text-base font-bold leading-snug">
                  Tư Vấn Thuốc Kê Đơn Cùng Dược Sĩ
                </h3>
              </div>
            </div>
            <button
              onClick={handleReset}
              className="p-1.5 rounded-xl text-white/80 hover:text-white hover:bg-white/10 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <div className="p-6">
            {!isSubmitted ? (
              <form onSubmit={handleSubmit} className="space-y-4">
                {/* Warning notice */}
                <div className="p-3.5 rounded-xl bg-amber-50 border border-amber-200 flex items-start gap-2.5">
                  <AlertCircle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
                  <div className="text-xs text-amber-900 leading-relaxed">
                    <span className="font-bold">Quy định của Bộ Y Tế: </span>
                    Sản phẩm <span className="font-semibold">{product.name}</span> là thuốc kê đơn (Rx). Thuốc chỉ được bán khi có đơn chỉ định hợp lệ của Bác sĩ. Dược sĩ H4CARE sẽ liên hệ xác nhận đơn thuốc của bạn.
                  </div>
                </div>

                {/* Patient Information Inputs */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Họ và tên người bệnh
                  </label>
                  <input
                    type="text"
                    required
                    value={patientName}
                    onChange={(e) => setPatientName(e.target.value)}
                    placeholder="Ví dụ: Nguyễn Văn A"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-blue-500 focus:border-brand-blue-500"
                  />
                </div>

                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Số điện thoại nhận tư vấn <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="tel"
                    required
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    placeholder="Ví dụ: 0912 345 678"
                    className="w-full px-3.5 py-2.5 rounded-xl border border-slate-200 text-sm text-slate-800 placeholder:text-slate-400 focus:outline-none focus:ring-1 focus:ring-brand-blue-500 focus:border-brand-blue-500"
                  />
                </div>

                {/* Upload prescription demo box */}
                <div>
                  <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-1.5">
                    Ảnh chụp đơn thuốc (nếu có)
                  </label>
                  <div
                    onClick={() => setPrescriptionFile("don-thuoc-benh-vien-cho-ray.jpg")}
                    className="border-2 border-dashed border-slate-200 hover:border-brand-blue-400 rounded-xl p-4 text-center cursor-pointer transition-colors bg-slate-50 hover:bg-brand-blue-50/40"
                  >
                    <UploadCloud className="w-7 h-7 text-slate-400 mx-auto mb-1.5" />
                    {prescriptionFile ? (
                      <p className="text-xs font-semibold text-emerald-600 flex items-center justify-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" />
                        Đã đính kèm: {prescriptionFile}
                      </p>
                    ) : (
                      <>
                        <p className="text-xs font-medium text-slate-700">
                          Bấm để tải lên ảnh chụp đơn thuốc hoặc toa khám
                        </p>
                        <p className="text-[10px] text-slate-400 mt-0.5">
                          Hỗ trợ định dạng JPG, PNG, PDF (Tối đa 10MB)
                        </p>
                      </>
                    )}
                  </div>
                </div>

                {/* Commitments */}
                <div className="pt-2 flex items-center justify-between text-[11px] text-slate-500">
                  <span className="flex items-center gap-1">
                    <ShieldCheck className="w-3.5 h-3.5 text-brand-emerald-500" />
                    Bảo mật dữ liệu bệnh án 100%
                  </span>
                  <span className="flex items-center gap-1">
                    <Clock className="w-3.5 h-3.5 text-brand-blue-500" />
                    Phản hồi trong vòng 5 phút
                  </span>
                </div>

                {/* Submit button */}
                <div className="pt-2">
                  <Button
                    type="submit"
                    variant="primary"
                    size="lg"
                    className="w-full shadow-xs"
                  >
                    Gửi Yêu Cầu Cho Dược Sĩ Ngay
                  </Button>
                </div>
              </form>
            ) : (
              <div className="py-6 text-center space-y-4">
                <div className="w-16 h-16 rounded-full bg-emerald-100 text-emerald-600 flex items-center justify-center mx-auto shadow-xs">
                  <CheckCircle2 className="w-9 h-9" />
                </div>
                <div>
                  <h4 className="text-lg font-bold text-slate-900">
                    Đã Tiếp Nhận Thông Tin Đơn Thuốc!
                  </h4>
                  <p className="text-xs text-slate-600 mt-1.5 max-w-sm mx-auto leading-relaxed">
                    Dược sĩ chuyên môn của H4CARE đang kiểm tra toa thuốc của bạn và sẽ gọi điện thoại tới số <span className="font-bold text-brand-blue-700">{phoneNumber}</span> trong vòng 5-10 phút tới.
                  </p>
                </div>

                <div className="p-3.5 rounded-xl bg-brand-blue-50 border border-brand-blue-100 text-left text-xs space-y-1">
                  <p className="font-bold text-brand-blue-900">Thông tin yêu cầu:</p>
                  <p className="text-slate-600">• Người bệnh: <span className="font-semibold">{patientName || "Khách hàng"}</span></p>
                  <p className="text-slate-600">• Thuốc quan tâm: <span className="font-semibold">{product.name}</span></p>
                  <p className="text-slate-600">• Kênh hỗ trợ Dược sĩ: <span className="font-semibold text-brand-blue-700">{PHARMACY_CONTACT.supportEmail}</span></p>
                </div>

                <Button variant="outline" size="md" onClick={handleReset} className="w-full">
                  Đóng cửa sổ
                </Button>
              </div>
            )}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
