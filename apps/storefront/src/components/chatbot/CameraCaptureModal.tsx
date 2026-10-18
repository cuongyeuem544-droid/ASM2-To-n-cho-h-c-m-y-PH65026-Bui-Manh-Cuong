"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Camera,
  X,
  RotateCcw,
  Check,
  AlertCircle,
  UploadCloud,
  Loader2,
} from "lucide-react";

interface CameraCaptureModalProps {
  isOpen: boolean;
  onClose: () => void;
  onCapture: (file: File) => void;
  onFallbackToFile: () => void;
}

export const CameraCaptureModal: React.FC<CameraCaptureModalProps> = ({
  isOpen,
  onClose,
  onCapture,
  onFallbackToFile,
}) => {
  const [stream, setStream] = useState<MediaStream | null>(null);
  const [capturedBlob, setCapturedBlob] = useState<Blob | null>(null);
  const [capturedUrl, setCapturedUrl] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);

  const stopStream = useCallback(() => {
    if (stream) {
      stream.getTracks().forEach((track) => track.stop());
      setStream(null);
    }
  }, [stream]);

  const startCamera = useCallback(async () => {
    setErrorMsg(null);
    setIsLoading(true);
    setCapturedBlob(null);
    if (capturedUrl) {
      URL.revokeObjectURL(capturedUrl);
      setCapturedUrl(null);
    }

    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Trình duyệt không hỗ trợ truy cập máy ảnh trực tiếp qua web.");
      }

      const mediaStream = await navigator.mediaDevices.getUserMedia({
        video: {
          facingMode: { ideal: "environment" },
          width: { ideal: 1280 },
          height: { ideal: 720 },
        },
        audio: false,
      });

      setStream(mediaStream);
      if (videoRef.current) {
        videoRef.current.srcObject = mediaStream;
        await videoRef.current.play();
      }
    } catch (err: any) {
      console.warn("[Camera access error]:", err);
      let userFriendly = "Không thể kết nối đến máy ảnh.";
      if (err.name === "NotAllowedError" || err.name === "PermissionDeniedError") {
        userFriendly = "Bạn đã từ chối quyền truy cập máy ảnh. Vui lòng cấp quyền hoặc tải ảnh từ thiết bị.";
      } else if (err.name === "NotFoundError" || err.name === "DevicesNotFoundError") {
        userFriendly = "Không tìm thấy thiết bị máy ảnh trên máy tính / điện thoại của bạn.";
      }
      setErrorMsg(userFriendly);
    } finally {
      setIsLoading(false);
    }
  }, [capturedUrl]);

  useEffect(() => {
    if (isOpen) {
      startCamera();
    } else {
      stopStream();
      if (capturedUrl) {
        URL.revokeObjectURL(capturedUrl);
        setCapturedUrl(null);
      }
      setCapturedBlob(null);
      setErrorMsg(null);
    }
    return () => {
      stopStream();
    };
  }, [isOpen]);

  const handleSnap = () => {
    if (!videoRef.current || !canvasRef.current) return;
    const video = videoRef.current;
    const canvas = canvasRef.current;

    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob(
      (blob) => {
        if (blob) {
          setCapturedBlob(blob);
          const url = URL.createObjectURL(blob);
          setCapturedUrl(url);
          stopStream();
        }
      },
      "image/jpeg",
      0.92
    );
  };

  const handleConfirm = () => {
    if (!capturedBlob) return;
    const file = new File([capturedBlob], `camera_${Date.now()}.jpg`, {
      type: "image/jpeg",
    });
    onCapture(file);
    onClose();
  };

  const handleRetake = () => {
    startCamera();
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="fixed inset-0 z-[120] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs">
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.95 }}
          className="relative w-full max-w-lg bg-slate-900 text-white rounded-3xl overflow-hidden shadow-2xl border border-slate-800 flex flex-col"
        >
          {/* Header */}
          <div className="p-4 flex items-center justify-between border-b border-slate-800">
            <div className="flex items-center gap-2">
              <div className="w-8 h-8 rounded-xl bg-brand-blue-600 flex items-center justify-center">
                <Camera className="w-4 h-4 text-white" />
              </div>
              <div>
                <h3 className="text-sm font-bold">Chụp ảnh đơn thuốc / sản phẩm</h3>
                <p className="text-[11px] text-slate-400">Canh nét chữ rõ ràng trước khi bấm chụp</p>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="p-1.5 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          {/* Viewfinder area */}
          <div className="relative aspect-video bg-black flex items-center justify-center overflow-hidden">
            {isLoading && (
              <div className="flex flex-col items-center gap-2 text-slate-400">
                <Loader2 className="w-8 h-8 animate-spin text-brand-blue-400" />
                <span className="text-xs">Đang khởi động máy ảnh...</span>
              </div>
            )}

            {errorMsg ? (
              <div className="p-6 text-center max-w-sm">
                <AlertCircle className="w-10 h-10 text-rose-400 mx-auto mb-2" />
                <p className="text-xs text-rose-200 leading-relaxed mb-4">{errorMsg}</p>
                <button
                  type="button"
                  onClick={() => {
                    onClose();
                    onFallbackToFile();
                  }}
                  className="px-4 py-2 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-700 text-white text-xs font-bold transition-all flex items-center gap-2 mx-auto"
                >
                  <UploadCloud className="w-4 h-4" />
                  <span>Chọn ảnh từ thiết bị</span>
                </button>
              </div>
            ) : capturedUrl ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={capturedUrl}
                alt="Captured snapshot"
                className="w-full h-full object-contain"
              />
            ) : (
              <>
                <video
                  ref={videoRef}
                  playsInline
                  autoPlay
                  muted
                  className="w-full h-full object-cover"
                />
                {/* Viewfinder target guides */}
                <div className="absolute inset-4 border border-white/20 rounded-2xl pointer-events-none flex flex-col justify-between p-3">
                  <div className="flex justify-between">
                    <span className="w-4 h-4 border-t-2 border-l-2 border-brand-cyan-400" />
                    <span className="w-4 h-4 border-t-2 border-r-2 border-brand-cyan-400" />
                  </div>
                  <div className="flex justify-between">
                    <span className="w-4 h-4 border-b-2 border-l-2 border-brand-cyan-400" />
                    <span className="w-4 h-4 border-b-2 border-r-2 border-brand-cyan-400" />
                  </div>
                </div>
              </>
            )}

            <canvas ref={canvasRef} className="hidden" />
          </div>

          {/* Controls Footer */}
          <div className="p-4 bg-slate-950 flex items-center justify-center gap-4">
            {capturedUrl ? (
              <>
                <button
                  type="button"
                  onClick={handleRetake}
                  className="px-4 py-2.5 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold flex items-center gap-1.5 transition-colors"
                >
                  <RotateCcw className="w-4 h-4" />
                  <span>Chụp lại</span>
                </button>
                <button
                  type="button"
                  onClick={handleConfirm}
                  className="px-5 py-2.5 rounded-xl bg-brand-blue-600 hover:bg-brand-blue-500 text-white text-xs font-bold flex items-center gap-1.5 shadow-md transition-colors"
                >
                  <Check className="w-4 h-4" />
                  <span>Sử dụng ảnh này</span>
                </button>
              </>
            ) : !errorMsg ? (
              <button
                type="button"
                onClick={handleSnap}
                disabled={isLoading}
                className="w-14 h-14 rounded-full border-4 border-white/80 bg-white/20 hover:bg-white active:scale-95 transition-all flex items-center justify-center shadow-lg disabled:opacity-40"
                title="Bấm chụp"
              >
                <div className="w-10 h-10 rounded-full bg-white" />
              </button>
            ) : null}
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};
