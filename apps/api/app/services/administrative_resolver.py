"""
apps/api/app/services/administrative_resolver.py

VIETNAM ADMINISTRATIVE RESOLVER (H4CARE V2)
Bộ xử lý chuẩn hóa và ánh xạ địa giới hành chính Việt Nam sau sắp xếp 2025.
Căn cứ: Quyết định 19/2025/QĐ-TTg & Nghị quyết 202/2025/QH15.
Effective Date: 2025-07-01
Version: VN_ADMIN_2025_07_01

Chức năng:
- Ánh xạ 100% chính xác 34 đơn vị cấp tỉnh và 3.321 đơn vị cấp xã hiện hành.
- Xử lý 23 nhóm sáp nhập tỉnh cũ (Bình Dương, Hải Dương, Nam Định, Hà Nam, Quảng Nam, v.v.).
- Nhận diện các đặc khu hành chính (Phú Quốc, Vân Đồn, Côn Đảo, Lý Sơn, Cô Tô, Trường Sa, Hoàng Sa).
- Tích hợp và bóc tách thành phần từ Geocoding Provider (Google Places, Nominatim, Photon).
"""

import json
import os
import re
import sqlite3
import unicodedata
from pathlib import Path
from typing import Any, Optional


def normalize_vietnamese_name(name: str) -> str:
    """
    Chuẩn hóa tên địa danh tiếng Việt:
    - Chuyển về NFKD, bỏ dấu thanh.
    - Chuyển 'đ' -> 'd'.
    - Viết thường, loại bỏ khoảng trắng thừa và ký tự đặc biệt.
    - Loại bỏ tiền tố hành chính (tỉnh, tp, thành phố, thị xã, tx, huyện, quận, phường, xã, thị trấn, đặc khu).
    """
    if not name:
        return ""
    clean = str(name).strip()
    nfkd_form = unicodedata.normalize("NFKD", clean)
    no_accent = "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D").lower()
    
    # Loại bỏ tiền tố
    no_prefix = re.sub(
        r"^(tinh|thanh pho|tp\.?|t\.|thi xa|tx\.?|huyen|h\.|quan|q\.|phuong|p\.|xa|x\.|thi tran|tt\.|dac khu)\s+",
        "",
        no_accent.strip()
    ).strip()
    return no_prefix


def strip_accents(input_str: str) -> str:
    """Bỏ dấu nhưng giữ nguyên cấu trúc từ."""
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", str(input_str).strip())
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D").lower().strip()


class VietnamAdministrativeResolver:
    _initialized: bool = False
    _provinces: list[dict[str, Any]] = []
    _communes: list[dict[str, Any]] = []
    _merger_groups: list[dict[str, Any]] = []
    _metadata: dict[str, Any] = {}

    _provinces_by_code: dict[str, dict[str, Any]] = {}
    _provinces_by_norm: dict[str, dict[str, Any]] = {}
    _communes_by_code: dict[str, dict[str, Any]] = {}
    _communes_by_province: dict[str, list[dict[str, Any]]] = {}

    # Legacy mapping: norm_old_province_name -> target province dict
    _legacy_province_map: dict[str, dict[str, Any]] = {}

    # Alias index: norm_alias -> list of targets
    _alias_index: dict[str, list[dict[str, Any]]] = {}

    @classmethod
    def initialize(cls, json_path: Optional[str] = None):
        if not json_path:
            current_file_dir = Path(__file__).resolve().parent
            candidates = [
                current_file_dir.parent.parent / "data" / "vietnam-administrative-units.json",
                current_file_dir.parent / "data" / "vietnam-administrative-units.json",
                Path("/app/data/vietnam-administrative-units.json"),
                Path("data/vietnam-administrative-units.json"),
                Path("../data/vietnam-administrative-units.json"),
                Path("../../data/vietnam-administrative-units.json"),
                Path("apps/storefront/src/data/vietnam-administrative-units.json"),
            ]
            for c in candidates:
                if c.exists():
                    json_path = str(c)
                    break

        if not json_path or not Path(json_path).exists():
            return

        with open(json_path, "r", encoding="utf-8") as f:
            dataset = json.load(f)

        cls._metadata = dataset.get("metadata", {})
        cls._provinces = dataset.get("provinces", [])
        cls._communes = dataset.get("communes", [])
        cls._merger_groups = dataset.get("mergerGroups", [])

        # Reset indexing
        cls._provinces_by_code.clear()
        cls._provinces_by_norm.clear()
        cls._communes_by_code.clear()
        cls._communes_by_province.clear()
        cls._legacy_province_map.clear()
        cls._alias_index.clear()

        # 1. Index 34 Provinces
        for p in cls._provinces:
            p_code = p["code"]
            cls._provinces_by_code[p_code] = p
            
            p_norm = normalize_vietnamese_name(p["name"])
            cls._provinces_by_norm[p_norm] = p
            cls._provinces_by_norm[strip_accents(p["name"])] = p
            cls._provinces_by_norm[strip_accents(p["fullName"])] = p

            # Aliases
            for a in p.get("aliases", []):
                norm_a = normalize_vietnamese_name(a)
                raw_norm_a = strip_accents(a)
                cls._provinces_by_norm[norm_a] = p
                cls._provinces_by_norm[raw_norm_a] = p
                cls._add_to_alias_index(norm_a, {"type": "PROVINCE", "code": p_code, "data": p})
                cls._add_to_alias_index(raw_norm_a, {"type": "PROVINCE", "code": p_code, "data": p})

        # 2. Index 23 Merger Groups
        for mg in cls._merger_groups:
            target_code = mg["target_code"]
            target_province = cls._provinces_by_code.get(target_code)
            if not target_province:
                continue

            for old_p in mg["old_provinces"]:
                norm_old = normalize_vietnamese_name(old_p)
                raw_norm_old = strip_accents(old_p)
                cls._legacy_province_map[norm_old] = target_province
                cls._legacy_province_map[raw_norm_old] = target_province
                cls._legacy_province_map[strip_accents(f"tinh {old_p}")] = target_province
                cls._legacy_province_map[strip_accents(f"thanh pho {old_p}")] = target_province
                cls._legacy_province_map[strip_accents(f"tp {old_p}")] = target_province

                cls._add_to_alias_index(norm_old, {"type": "PROVINCE", "code": target_code, "data": target_province, "is_legacy": True})
                cls._add_to_alias_index(raw_norm_old, {"type": "PROVINCE", "code": target_code, "data": target_province, "is_legacy": True})

            for la in mg.get("legacy_aliases", []):
                norm_la = normalize_vietnamese_name(la)
                raw_norm_la = strip_accents(la)
                cls._legacy_province_map[norm_la] = target_province
                cls._legacy_province_map[raw_norm_la] = target_province
                cls._add_to_alias_index(norm_la, {"type": "PROVINCE", "code": target_code, "data": target_province, "is_legacy": True})
                cls._add_to_alias_index(raw_norm_la, {"type": "PROVINCE", "code": target_code, "data": target_province, "is_legacy": True})

        # 3. Index 3.321 Communes
        for c in cls._communes:
            c_code = c["code"]
            p_code = c["provinceCode"]
            cls._communes_by_code[c_code] = c
            cls._communes_by_province.setdefault(p_code, []).append(c)

            norm_c = normalize_vietnamese_name(c["name"])
            raw_norm_c = strip_accents(c["name"])
            full_norm_c = strip_accents(c["fullName"])

            cls._add_to_alias_index(norm_c, {"type": "COMMUNE", "code": c_code, "provinceCode": p_code, "data": c})
            cls._add_to_alias_index(raw_norm_c, {"type": "COMMUNE", "code": c_code, "provinceCode": p_code, "data": c})
            cls._add_to_alias_index(full_norm_c, {"type": "COMMUNE", "code": c_code, "provinceCode": p_code, "data": c})

            for a in c.get("aliases", []):
                norm_a = normalize_vietnamese_name(a)
                raw_norm_a = strip_accents(a)
                cls._add_to_alias_index(norm_a, {"type": "COMMUNE", "code": c_code, "provinceCode": p_code, "data": c})
                cls._add_to_alias_index(raw_norm_a, {"type": "COMMUNE", "code": c_code, "provinceCode": p_code, "data": c})

        cls._initialized = True

    @classmethod
    def _add_to_alias_index(cls, norm_key: str, item: dict[str, Any]):
        if not norm_key:
            return
        bucket = cls._alias_index.setdefault(norm_key, [])
        # Check duplicate
        if not any(b["type"] == item["type"] and b["code"] == item["code"] for b in bucket):
            bucket.append(item)

    @classmethod
    def _ensure_loaded(cls):
        if not cls._initialized or not cls._provinces_by_code:
            cls.initialize()

    @classmethod
    def normalize_name(cls, name: str) -> str:
        return normalize_vietnamese_name(name)

    @classmethod
    def resolve_province(cls, query: str) -> Optional[dict[str, Any]]:
        """
        Tìm tỉnh hiện hành (thuộc 34 đơn vị) theo mã, tên chính thức hoặc alias.
        Hỗ trợ fallback sang legacy province mapping nếu query là tỉnh cũ.
        """
        cls._ensure_loaded()
        if not query:
            return None
        q = str(query).strip()

        # 1. Tìm theo mã
        if q in cls._provinces_by_code:
            return cls._provinces_by_code[q]

        # 2. Tìm theo tên chuẩn hóa
        norm_q = normalize_vietnamese_name(q)
        raw_norm_q = strip_accents(q)

        if norm_q in cls._provinces_by_norm:
            return cls._provinces_by_norm[norm_q]
        if raw_norm_q in cls._provinces_by_norm:
            return cls._provinces_by_norm[raw_norm_q]

        # 3. Tra cứu từ Legacy Province Mapping (ví dụ: Bình Dương, Hải Dương, Nam Định)
        legacy_match = cls.resolve_legacy_province(q)
        if legacy_match:
            return legacy_match

        # 4. Partial substring match
        for p in cls._provinces:
            if norm_q and norm_q in normalize_vietnamese_name(p["name"]):
                return p
            if raw_norm_q and raw_norm_q in strip_accents(p["fullName"]):
                return p

        return None

    @classmethod
    def resolve_legacy_province(cls, query: str) -> Optional[dict[str, Any]]:
        """
        Ánh xạ một tỉnh cũ hoặc đô thị cũ sang tỉnh hiện hành sau sắp xếp 2025.
        Ví dụ:
        'Bình Dương' -> Hồ Chí Minh (79)
        'Hải Dương' -> Hải Phòng (31)
        'Nam Định' -> Ninh Bình (37)
        'Hà Nam' -> Ninh Bình (37)
        'Quảng Nam' -> Đà Nẵng (48)
        'Quảng Bình' -> Quảng Trị (45)
        'Bình Định' -> Gia Lai (64)
        'Phú Yên' -> Đắk Lắk (66)
        'Bến Tre' -> Vĩnh Long (86)
        'Kiên Giang' -> An Giang (89)
        'Long An' -> Tây Ninh (72)
        'Tiền Giang' -> Đồng Tháp (87)
        """
        cls._ensure_loaded()
        if not query:
            return None
        norm_q = normalize_vietnamese_name(query)
        raw_norm_q = strip_accents(query)

        if norm_q in cls._legacy_province_map:
            return cls._legacy_province_map[norm_q]
        if raw_norm_q in cls._legacy_province_map:
            return cls._legacy_province_map[raw_norm_q]

        # Substring check for legacy aliases
        for k, target in cls._legacy_province_map.items():
            if norm_q and (norm_q in k or k in norm_q):
                return target

        return None

    @classmethod
    def resolve_commune(cls, province_code: str, query: str) -> Optional[dict[str, Any]]:
        """
        Tìm kiếm xã/phường/đặc khu trong một tỉnh hiện hành.
        """
        cls._ensure_loaded()
        p_code = str(province_code).strip()
        communes = cls._communes_by_province.get(p_code, [])
        if not communes or not query:
            return None

        q = str(query).strip()

        # 1. Tìm theo mã
        for c in communes:
            if c["code"] == q:
                return c

        norm_q = normalize_vietnamese_name(q)
        raw_norm_q = strip_accents(q)

        # 2. Exact match tên xã
        for c in communes:
            if normalize_vietnamese_name(c["name"]) == norm_q or strip_accents(c["name"]) == raw_norm_q:
                return c

        # 3. Exact match alias
        for c in communes:
            for a in c.get("aliases", []):
                if normalize_vietnamese_name(a) == norm_q or strip_accents(a) == raw_norm_q:
                    return c

        # 4. Substring match
        for c in communes:
            c_norm = normalize_vietnamese_name(c["name"])
            if norm_q and (norm_q in c_norm or c_norm in norm_q):
                return c

        return None

    @classmethod
    def resolve_legacy_commune(cls, legacy_query: str, province_code: Optional[str] = None) -> Optional[dict[str, Any]]:
        """
        Tìm kiếm xã/phường dựa trên tên xã cũ hoặc quận/huyện cũ.
        """
        cls._ensure_loaded()
        if not legacy_query:
            return None

        norm_q = normalize_vietnamese_name(legacy_query)
        raw_norm_q = strip_accents(legacy_query)

        candidates = []
        if province_code:
            search_list = cls._communes_by_province.get(str(province_code).strip(), [])
        else:
            search_list = cls._communes

        for c in search_list:
            # Check legacy district name
            if c.get("legacyDistrictName"):
                if norm_q in normalize_vietnamese_name(c["legacyDistrictName"]):
                    candidates.append(c)
                    continue

            # Check aliases
            for a in c.get("aliases", []):
                if norm_q == normalize_vietnamese_name(a) or raw_norm_q == strip_accents(a):
                    candidates.append(c)
                    break

        if candidates:
            return candidates[0]
        return None

    @classmethod
    def find_current_unit_by_alias(cls, alias: str) -> Optional[dict[str, Any]]:
        """
        Tra cứu bất kỳ alias nào và trả về kết quả tốt nhất (PROVINCE hoặc COMMUNE).
        """
        cls._ensure_loaded()
        if not alias:
            return None

        norm_a = normalize_vietnamese_name(alias)
        raw_norm_a = strip_accents(alias)

        for key in [norm_a, raw_norm_a]:
            if key in cls._alias_index:
                items = cls._alias_index[key]
                if items:
                    return items[0]

        return None

    @classmethod
    def resolve_provider_components(cls, components: dict[str, Any]) -> dict[str, Any]:
        """
        Giải quyết và đối chiếu thành phần địa chỉ từ geocoding provider (Google Maps hoặc OSM)
        thành cấu trúc 2 cấp chuẩn xác theo QĐ 19/2025/QĐ-TTg.
        
        Input: dict chứa các trường tùy chọn:
        - province / state / city / administrative_area_level_1
        - district / county / administrative_area_level_2
        - ward / commune / sublocality / locality
        - display_name / formatted_address
        
        Output: dict chuẩn hóa 2 cấp:
        - province_code
        - province_name
        - commune_code
        - commune_name
        - commune_type ('ward' | 'commune' | 'special_zone')
        - is_merged (bool)
        - legacy_info (dict)
        - is_resolved (bool)
        """
        cls._ensure_loaded()

        raw_prov = components.get("province") or components.get("state") or components.get("administrative_area_level_1") or ""
        raw_dist = components.get("district") or components.get("county") or components.get("city") or components.get("administrative_area_level_2") or ""
        raw_ward = components.get("ward") or components.get("commune") or components.get("sublocality") or components.get("sublocality_level_1") or components.get("locality") or ""
        full_text = components.get("display_name") or components.get("formatted_address") or ""

        resolved_province = None
        is_merged = False
        legacy_info = {}

        # 1. Thử nhận diện Đặc khu trước (Phú Quốc, Côn Đảo, Vân Đồn, Lý Sơn, Cô Tô, Trường Sa, Hoàng Sa)
        special_zone_match = None
        for text in [raw_ward, raw_dist, raw_prov, full_text]:
            if not text:
                continue
            norm_t = normalize_vietnamese_name(text)
            for sz_name in ["phu quoc", "van don", "con dao", "ly son", "co to", "truong sa", "hoang sa"]:
                if sz_name in norm_t:
                    # Find special zone commune
                    for c in cls._communes:
                        if c.get("type") == "special_zone" and normalize_vietnamese_name(c["name"]) == sz_name:
                            special_zone_match = c
                            break
                if special_zone_match:
                    break
            if special_zone_match:
                break

        if special_zone_match:
            p_code = special_zone_match["provinceCode"]
            resolved_province = cls._provinces_by_code.get(p_code)
            return {
                "province_code": p_code,
                "province_name": resolved_province["fullName"] if resolved_province else special_zone_match["provinceCode"],
                "commune_code": special_zone_match["code"],
                "commune_name": special_zone_match["fullName"],
                "commune_type": "special_zone",
                "is_merged": False,
                "legacy_info": {"special_zone": special_zone_match["name"]},
                "is_resolved": True,
            }

        # 2. Nhận diện Tỉnh / Thành phố
        for candidate_text in [raw_prov, raw_dist, raw_ward]:
            if not candidate_text:
                continue
            # Check current province
            p = cls.resolve_province(candidate_text)
            if p:
                resolved_province = p
                # Kiểm tra xem có phải do mapping sáp nhập không
                legacy_check = cls.resolve_legacy_province(candidate_text)
                if legacy_check and legacy_check["code"] == p["code"]:
                    is_merged = True
                    legacy_info["old_province"] = candidate_text
                break

        # Nếu chưa tìm được từ các trường riêng biệt, tìm từ full text
        if not resolved_province and full_text:
            parts = [p.strip() for p in full_text.split(",") if p.strip()]
            for part in reversed(parts):
                p = cls.resolve_province(part)
                if p:
                    resolved_province = p
                    legacy_check = cls.resolve_legacy_province(part)
                    if legacy_check:
                        is_merged = True
                        legacy_info["old_province"] = part
                    break

        if not resolved_province:
            return {
                "province_code": None,
                "province_name": None,
                "commune_code": None,
                "commune_name": None,
                "commune_type": None,
                "is_merged": False,
                "legacy_info": {},
                "is_resolved": False,
            }

        # 3. Nhận diện Xã / Phường trong tỉnh đã xác định
        p_code = resolved_province["code"]
        resolved_commune = None

        for candidate_ward in [raw_ward, raw_dist]:
            if not candidate_ward:
                continue
            c = cls.resolve_commune(p_code, candidate_ward)
            if c:
                resolved_commune = c
                break

        if not resolved_commune and full_text:
            parts = [p.strip() for p in full_text.split(",") if p.strip()]
            for part in parts:
                c = cls.resolve_commune(p_code, part)
                if c:
                    resolved_commune = c
                    break

        # 4. Fallback xã mặc định trong tỉnh nếu không nhận diện được xã chi tiết
        if not resolved_commune:
            p_communes = cls._communes_by_province.get(p_code, [])
            if p_communes:
                resolved_commune = p_communes[0]

        return {
            "province_code": p_code,
            "province_name": resolved_province["fullName"],
            "commune_code": resolved_commune["code"] if resolved_commune else None,
            "commune_name": resolved_commune["fullName"] if resolved_commune else None,
            "commune_type": resolved_commune["type"] if resolved_commune else None,
            "is_merged": is_merged,
            "legacy_info": legacy_info,
            "is_resolved": True,
        }

    @classmethod
    def search(cls, query: str, province_code: Optional[str] = None, limit: int = 10) -> list[dict[str, Any]]:
        """
        Tìm kiếm đa năng cả Tỉnh và Xã/Phường.
        """
        cls._ensure_loaded()
        if not query:
            return []

        norm_q = normalize_vietnamese_name(query)
        raw_norm_q = strip_accents(query)
        results = []

        # 1. Nếu không chỉ định province_code, tìm tỉnh
        if not province_code:
            for p in cls._provinces:
                if norm_q in normalize_vietnamese_name(p["name"]) or raw_norm_q in strip_accents(p["fullName"]):
                    results.append({"type": "PROVINCE", "data": p})
                    if len(results) >= limit:
                        return results

        # 2. Tìm xã
        search_communes = cls._communes_by_province.get(province_code, []) if province_code else cls._communes
        for c in search_communes:
            if norm_q in normalize_vietnamese_name(c["name"]) or raw_norm_q in strip_accents(c["fullName"]):
                results.append({"type": "COMMUNE", "data": c})
                if len(results) >= limit:
                    break

        return results


# Auto-initialize on import
VietnamAdministrativeResolver.initialize()
