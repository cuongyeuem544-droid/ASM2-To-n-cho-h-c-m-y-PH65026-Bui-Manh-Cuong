"use client";

import React, { useEffect, useRef, useState } from "react";
import L from "leaflet";
import "leaflet/dist/leaflet.css";
import {
  MapPin,
  Navigation,
  Compass,
  Layers,
  ZoomIn,
  ZoomOut,
  Crosshair,
  Building2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";

export interface WarehousePinInfo {
  warehouse_name: string;
  warehouse_code: string;
  warehouse_address: string;
  lat?: number;
  lng?: number;
  distance_km: number;
  estimated_delivery_time?: string;
  is_central?: boolean;
}

interface DeliveryRealMapProps {
  customerCoords: { lat: number; lng: number } | null;
  nearestWarehouse: WarehousePinInfo | null;
  allWarehouses?: WarehousePinInfo[];
  onLocationSelect: (lat: number, lng: number) => void;
  isLocating?: boolean;
  onGetGps?: () => void;
}

export default function DeliveryRealMap({
  customerCoords,
  nearestWarehouse,
  allWarehouses = [],
  onLocationSelect,
  isLocating = false,
  onGetGps,
}: DeliveryRealMapProps) {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<L.Map | null>(null);
  const customerMarkerRef = useRef<L.Marker | null>(null);
  const warehouseMarkersRef = useRef<L.Marker[]>([]);
  const polylineRef = useRef<L.Polyline | null>(null);

  const [mapInitialized, setMapInitialized] = useState(false);
  const [activeAddressNotice, setActiveAddressNotice] = useState<string | null>(null);

  // Default coordinate center (Ho Chi Minh City Center)
  const defaultCenter: [number, number] = customerCoords
    ? [customerCoords.lat, customerCoords.lng]
    : nearestWarehouse && nearestWarehouse.lat && nearestWarehouse.lng
    ? [nearestWarehouse.lat, nearestWarehouse.lng]
    : [10.7769, 106.7009];

  // 1. Initialize Leaflet Map
  useEffect(() => {
    if (!mapContainerRef.current || mapInstanceRef.current) return;

    // Create Map Instance
    const map = L.map(mapContainerRef.current, {
      center: defaultCenter,
      zoom: 14,
      zoomControl: false,
    });

    // Defensive patch: Prevent Leaflet unmount race condition
    // When map is destroyed or unmounted during zoom/pan transitions, Leaflet's
    // _onZoomTransitionEnd timer still executes and calls getPosition(this._mapPane),
    // which throws "TypeError: Cannot read properties of undefined (reading '_leaflet_pos')".
    const origGetMapPanePos = (map as any)._getMapPanePos;
    (map as any)._getMapPanePos = function () {
      if (!this._mapPane) {
        return new L.Point(0, 0);
      }
      return origGetMapPanePos ? origGetMapPanePos.call(this) : new L.Point(0, 0);
    };

    const origOnZoomTransitionEnd = (map as any)._onZoomTransitionEnd;
    (map as any)._onZoomTransitionEnd = function () {
      if (!this._mapPane || !(this as any)._animatingZoom) return;
      if (origOnZoomTransitionEnd) {
        origOnZoomTransitionEnd.call(this);
      }
    };

    // Add OpenStreetMap Standard Tile Layer
    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors | PharmaTrust',
      maxZoom: 19,
    }).addTo(map);

    // Zoom controls at bottom-right
    L.control
      .zoom({
        position: "bottomright",
      })
      .addTo(map);

    // Handle Click on Map to Pin Delivery Location
    map.on("click", (e: L.LeafletMouseEvent) => {
      const { lat, lng } = e.latlng;
      onLocationSelect(lat, lng);
      setActiveAddressNotice(`Đã ghim tọa độ mới: ${lat.toFixed(4)}, ${lng.toFixed(4)}`);
      setTimeout(() => setActiveAddressNotice(null), 3000);
    });

    mapInstanceRef.current = map;
    setMapInitialized(true);

    return () => {
      if (mapInstanceRef.current) {
        const m = mapInstanceRef.current as any;
        m._animatingZoom = false;
        try {
          m.stop();
          m.off();
          m.remove();
        } catch (err) {
          // Ignore DOM unmount detachment errors
        }
        mapInstanceRef.current = null;
      }
    };
  }, []);

  // 2. Render & Update Customer Marker
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapInitialized) return;

    if (customerCoords) {
      const custLatLng: [number, number] = [customerCoords.lat, customerCoords.lng];

      // Custom pulsing HTML Pin for Customer
      const customerIcon = L.divIcon({
        className: "custom-customer-pin",
        html: `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 36px; height: 36px; transform: translate(-18px, -18px);">
            <span style="position: absolute; width: 36px; height: 36px; border-radius: 9999px; background-color: #38bdf8; opacity: 0.6; animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;"></span>
            <div style="position: relative; width: 32px; height: 32px; border-radius: 9999px; background: linear-gradient(135deg, #0052cc, #0284c7); color: white; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 12px rgba(0, 82, 204, 0.4); border: 2.5px solid #ffffff; font-size: 15px; font-weight: bold;">
              📍
            </div>
          </div>
        `,
        iconSize: [36, 36],
        iconAnchor: [18, 18],
      });

      if (!customerMarkerRef.current) {
        const marker = L.marker(custLatLng, {
          icon: customerIcon,
          draggable: true,
          title: "Vị trí nhận thuốc của bạn (Kéo thả để chỉnh sửa)",
        }).addTo(map);

        marker.on("dragend", (e: any) => {
          const pos = e.target.getLatLng();
          onLocationSelect(pos.lat, pos.lng);
        });

        marker.bindPopup(`
          <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4; padding: 2px;">
            <strong style="color: #0052cc; font-size: 13px;">📍 Điểm nhận hàng của bạn</strong>
            <p style="margin: 4px 0 0 0; color: #475569;">
              Tọa độ: ${customerCoords.lat.toFixed(4)}, ${customerCoords.lng.toFixed(4)}
            </p>
            <p style="margin: 2px 0 0 0; color: #059669; font-weight: bold;">
              ✓ Bạn có thể kéo thả ghim này tới số nhà chính xác.
            </p>
          </div>
        `);

        customerMarkerRef.current = marker;
      } else {
        customerMarkerRef.current.setLatLng(custLatLng);
      }
    } else {
      if (customerMarkerRef.current) {
        customerMarkerRef.current.remove();
        customerMarkerRef.current = null;
      }
    }
  }, [customerCoords, mapInitialized, onLocationSelect]);

  // 3. Render & Update Warehouse Markers and Route Polyline
  useEffect(() => {
    const map = mapInstanceRef.current;
    if (!map || !mapInitialized) return;

    // Clear existing warehouse markers
    warehouseMarkersRef.current.forEach((m) => m.remove());
    warehouseMarkersRef.current = [];

    // Clear polyline
    if (polylineRef.current) {
      polylineRef.current.remove();
      polylineRef.current = null;
    }

    const warehousesToDraw =
      allWarehouses.length > 0
        ? allWarehouses
        : nearestWarehouse
        ? [nearestWarehouse]
        : [];

    warehousesToDraw.forEach((wh) => {
      const isNearest = nearestWarehouse && nearestWarehouse.warehouse_code === wh.warehouse_code;

      const warehouseIcon = L.divIcon({
        className: "custom-warehouse-pin",
        html: `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; width: 34px; height: 34px; transform: translate(-17px, -17px);">
            <div style="position: relative; width: 30px; height: 30px; border-radius: 10px; background: ${
              isNearest
                ? "linear-gradient(135deg, #059669, #10b981)"
                : "linear-gradient(135deg, #475569, #64748b)"
            }; color: white; display: flex; align-items: center; justify-content: center; box-shadow: 0 4px 10px rgba(0, 0, 0, 0.2); border: 2px solid #ffffff; font-size: 14px;">
              🏥
            </div>
            ${
              isNearest
                ? `<span style="position: absolute; -top: 6px; -right: 6px; background-color: #dc2626; color: white; font-size: 9px; font-weight: 900; padding: 1px 4px; border-radius: 9999px; border: 1px solid white;">Kho Gần</span>`
                : ""
            }
          </div>
        `,
        iconSize: [34, 34],
        iconAnchor: [17, 17],
      });

      const whLat = wh.lat ?? (wh.warehouse_code?.includes("HN") ? 21.0253 : 10.7872);
      const whLng = wh.lng ?? (wh.warehouse_code?.includes("HN") ? 105.8552 : 106.7001);

      const whMarker = L.marker([whLat, whLng], {
        icon: warehouseIcon,
        title: `${wh.warehouse_name} (${wh.warehouse_code})`,
      }).addTo(map);

      whMarker.bindPopup(`
        <div style="font-family: sans-serif; font-size: 12px; line-height: 1.4; padding: 2px;">
          <strong style="color: #059669; font-size: 13px;">🏥 ${wh.warehouse_name}</strong>
          <p style="margin: 4px 0 0 0; color: #334155; font-size: 11px;">
            ${wh.warehouse_address}
          </p>
          <div style="margin-top: 6px; padding: 4px 6px; background-color: #ecfdf5; border: 1px solid #a7f3d0; border-radius: 6px;">
            <p style="margin: 0; color: #065f46; font-weight: bold;">
              Khoảng cách tới bạn: ~${wh.distance_km} km
            </p>
            ${
              wh.estimated_delivery_time
                ? `<p style="margin: 2px 0 0 0; color: #047857; font-size: 10.5px;">⚡ ${wh.estimated_delivery_time}</p>`
                : ""
            }
          </div>
        </div>
      `);

      warehouseMarkersRef.current.push(whMarker);
    });

    // Draw route dashed polyline if both exist
    if (customerCoords && nearestWarehouse) {
      const whLat = nearestWarehouse.lat ?? (nearestWarehouse.warehouse_code?.includes("HN") ? 21.0253 : 10.7872);
      const whLng = nearestWarehouse.lng ?? (nearestWarehouse.warehouse_code?.includes("HN") ? 105.8552 : 106.7001);
      const lineCoords: [number, number][] = [
        [customerCoords.lat, customerCoords.lng],
        [whLat, whLng],
      ];

      const poly = L.polyline(lineCoords, {
        color: "#0284c7",
        weight: 3,
        dashArray: "6, 8",
        opacity: 0.85,
      }).addTo(map);

      polylineRef.current = poly;

      // Fit bounds to display both customer pin & nearest warehouse comfortably
      try {
        const bounds = L.latLngBounds(lineCoords);
        map.fitBounds(bounds, { padding: [50, 50], maxZoom: 16, animate: false });
      } catch (err) {
        // Safe fallback if container size is pending
      }
    } else if (customerCoords) {
      try {
        map.setView([customerCoords.lat, customerCoords.lng], 15, { animate: false });
      } catch (err) {
        // Safe fallback if container size is pending
      }
    }
  }, [customerCoords, nearestWarehouse, allWarehouses, mapInitialized]);

  return (
    <div className="relative w-full rounded-2xl overflow-hidden border border-slate-200 bg-slate-100 shadow-xs">
      {/* Top Map Action Header */}
      <div className="bg-white/95 backdrop-blur-xs border-b border-slate-200 px-3.5 py-2 flex flex-wrap items-center justify-between gap-2 z-10 relative">
        <div className="flex items-center gap-2">
          <div className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse" />
          <span className="text-xs font-bold text-slate-800 flex items-center gap-1.5">
            <Compass className="w-3.5 h-3.5 text-brand-blue-600" />
            <span>Bản đồ định vị giao thuốc thực tế</span>
          </span>
          <span className="text-[10px] bg-slate-100 text-slate-600 px-2 py-0.5 rounded-md font-semibold border border-slate-200">
            OpenStreetMap Live
          </span>
        </div>

        <div className="flex items-center gap-1.5">
          {onGetGps && (
            <button
              type="button"
              onClick={onGetGps}
              disabled={isLocating}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-brand-blue-50 hover:bg-brand-blue-100 text-brand-blue-700 text-[11px] font-bold transition-all border border-brand-blue-200"
              title="Định vị tọa độ GPS của thiết bị"
            >
              <Crosshair className={`w-3.5 h-3.5 ${isLocating ? "animate-spin text-rose-500" : ""}`} />
              <span>{isLocating ? "Đang định vị..." : "Lấy vị trí GPS"}</span>
            </button>
          )}

          {nearestWarehouse && (
            <button
              type="button"
              onClick={() => {
                if (mapInstanceRef.current && nearestWarehouse) {
                  const whLat = nearestWarehouse.lat ?? (nearestWarehouse.warehouse_code?.includes("HN") ? 21.0253 : 10.7872);
                  const whLng = nearestWarehouse.lng ?? (nearestWarehouse.warehouse_code?.includes("HN") ? 105.8552 : 106.7001);
                  mapInstanceRef.current.flyTo(
                    [whLat, whLng],
                    15
                  );
                }
              }}
              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-800 text-[11px] font-bold transition-all border border-emerald-200"
              title="Xem vị trí kho thuốc phục vụ"
            >
              <Building2 className="w-3.5 h-3.5 text-emerald-600" />
              <span>Kho: {nearestWarehouse.warehouse_code}</span>
            </button>
          )}
        </div>
      </div>

      {/* Real Map Canvas Container */}
      <div
        ref={mapContainerRef}
        className="w-full h-72 sm:h-80 relative z-0 select-none cursor-crosshair"
      />

      {/* Floating Notice / Click Helper */}
      <div className="absolute bottom-2.5 left-2.5 right-12 z-[500] pointer-events-none">
        {activeAddressNotice ? (
          <div className="inline-flex items-center gap-1.5 bg-emerald-900/90 text-white text-[11px] font-semibold px-3 py-1.5 rounded-xl shadow-lg backdrop-blur-xs animate-in fade-in zoom-in-95">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400 shrink-0" />
            <span>{activeAddressNotice}</span>
          </div>
        ) : (
          <div className="inline-flex items-center gap-1.5 bg-slate-900/80 text-white text-[10.5px] px-2.5 py-1 rounded-lg shadow-md backdrop-blur-xs pointer-events-auto">
            <MapPin className="w-3 h-3 text-cyan-400 shrink-0" />
            <span>Chạm hoặc click bất kỳ điểm nào trên bản đồ để ghim địa chỉ nhận hàng</span>
          </div>
        )}
      </div>
    </div>
  );
}
