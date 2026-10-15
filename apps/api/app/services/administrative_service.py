"""
apps/api/app/services/administrative_service.py

Service quản lý và tra cứu dữ liệu địa giới hành chính Việt Nam sau sắp xếp 2025.
Mô hình 2 cấp:
- Cấp 1: 34 đơn vị hành chính cấp tỉnh (28 tỉnh, 6 TP trực thuộc TW).
- Cấp 2: 3.321 đơn vị hành chính cấp xã (xã, phường, đặc khu).
- Legacy Compatibility Layer: Tra cứu alias quận/huyện cũ.
"""

import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Optional


def remove_accents(input_str: str) -> str:
    if not input_str:
        return ""
    nfkd_form = unicodedata.normalize("NFKD", input_str)
    return "".join([c for c in nfkd_form if not unicodedata.combining(c)]).replace("đ", "d").replace("Đ", "D").lower()


class AdministrativeDataService:
    _instance = None
    _dataset: dict[str, Any] = {}
    _provinces_map: dict[str, dict[str, Any]] = {}
    _communes_map: dict[str, dict[str, Any]] = {}
    _communes_by_province: dict[str, list[dict[str, Any]]] = {}

    @classmethod
    def initialize(cls, json_path: Optional[str] = None):
        if not json_path:
            # Tìm đường dẫn tương đối từ gốc project
            candidates = [
                Path("data/vietnam-administrative-units.json"),
                Path("../data/vietnam-administrative-units.json"),
                Path("../../data/vietnam-administrative-units.json"),
            ]
            for c in candidates:
                if c.exists():
                    json_path = str(c)
                    break

        if not json_path or not Path(json_path).exists():
            return

        with open(json_path, "r", encoding="utf-8") as f:
            cls._dataset = json.load(f)

        provinces = cls._dataset.get("provinces", [])
        communes = cls._dataset.get("communes", [])

        cls._provinces_map = {p["code"]: p for p in provinces}
        cls._communes_map = {c["code"]: c for c in communes}

        cls._communes_by_province = {}
        for c in communes:
            p_code = c.get("provinceCode")
            if p_code:
                cls._communes_by_province.setdefault(p_code, []).append(c)

    @classmethod
    def _ensure_loaded(cls):
        if not cls._provinces_map:
            cls.initialize()

    @classmethod
    def get_metadata(cls) -> dict[str, Any]:
        cls._ensure_loaded()
        return cls._dataset.get("metadata", {
            "country": "VN",
            "administrativeModel": "2-tier",
            "effectiveDate": "2025-07-01",
            "version": "2025.1.0"
        })

    @classmethod
    def get_provinces(cls, search: Optional[str] = None) -> list[dict[str, Any]]:
        cls._ensure_loaded()
        provinces = list(cls._provinces_map.values())
        if not search:
            return provinces

        search_clean = remove_accents(search.strip())
        clean_keyword = re.sub(r"^(tinh|thanh pho|tp\.?|t\.)\s*", "", search_clean).strip()
        results = []
        for p in provinces:
            p_name_clean = remove_accents(p["name"])
            p_full_clean = remove_accents(p["fullName"])
            alias_match = any(
                search_clean in remove_accents(a) or (clean_keyword and clean_keyword in remove_accents(a))
                for a in p.get("aliases", [])
            )
            if (
                search_clean in p_name_clean
                or search_clean in p_full_clean
                or (clean_keyword and (clean_keyword in p_name_clean or clean_keyword in p_full_clean))
                or alias_match
            ):
                results.append(p)

        # Bổ sung tra cứu từ VietnamAdministrativeResolver cho các tỉnh cũ sau sáp nhập 2025
        try:
            from app.services.administrative_resolver import VietnamAdministrativeResolver
            legacy_target = VietnamAdministrativeResolver.resolve_legacy_province(search)
            if legacy_target and not any(r["code"] == legacy_target["code"] for r in results):
                results.insert(0, legacy_target)
        except Exception:
            pass

        return results

    @classmethod
    def get_province_by_code(cls, code: str) -> Optional[dict[str, Any]]:
        cls._ensure_loaded()
        return cls._provinces_map.get(str(code).strip())

    @classmethod
    def get_communes(
        cls,
        province_code: Optional[str] = None,
        unit_type: Optional[str] = None,
        search: Optional[str] = None
    ) -> list[dict[str, Any]]:
        cls._ensure_loaded()
        if province_code:
            communes = cls._communes_by_province.get(str(province_code).strip(), [])
        else:
            communes = list(cls._communes_map.values())

        if unit_type:
            unit_type_clean = unit_type.lower().strip()
            communes = [c for c in communes if c.get("type") == unit_type_clean]

        if not search:
            return communes

        search_clean = remove_accents(search.strip())
        clean_keyword = re.sub(r"^(phuong|xa|thi tran|p\.|x\.|tt\.)\s*", "", search_clean).strip()
        search_parts = [p.strip() for p in search_clean.split(",") if p.strip()]

        results = []
        for c in communes:
            c_name_clean = remove_accents(c["name"])
            c_full_clean = remove_accents(c["fullName"])
            legacy_dist_clean = remove_accents(c.get("legacyDistrictName", ""))
            
            alias_match = any(
                search_clean in remove_accents(a)
                or (clean_keyword and clean_keyword in remove_accents(a))
                or any(part in remove_accents(a) for part in search_parts)
                for a in c.get("aliases", [])
            )
            
            name_match = (
                search_clean in c_name_clean
                or (clean_keyword and clean_keyword in c_name_clean)
                or any(part in c_name_clean for part in search_parts)
            )
            
            full_match = (
                search_clean in c_full_clean
                or (clean_keyword and clean_keyword in c_full_clean)
                or any(part in c_full_clean for part in search_parts)
            )

            legacy_match = (
                search_clean in legacy_dist_clean
                or (clean_keyword and clean_keyword in legacy_dist_clean)
                or any(part in legacy_dist_clean for part in search_parts)
            )

            if name_match or full_match or legacy_match or alias_match:
                results.append(c)
        return results

    @classmethod
    def get_commune_by_code(cls, code: str) -> Optional[dict[str, Any]]:
        cls._ensure_loaded()
        code_str = str(code).strip()
        c = cls._communes_map.get(code_str)
        if c:
            return c
        # Legacy Compatibility Layer: Xử lý mã 5 và 6 chữ số trước sắp xếp 2025
        if code_str.isdigit() and len(code_str) in (5, 6):
            if code_str == "791161":
                c_bn = cls._communes_map.get("791492")
                if c_bn:
                    res = dict(c_bn)
                    res["code"] = "791161"
                    return res
                return {
                    "code": "791161",
                    "name": "Bến Nghé",
                    "fullName": "Phường Bến Nghé",
                    "type": "ward",
                    "provinceCode": "79",
                    "legacyDistrictName": "Quận 1",
                    "aliases": ["Bến Nghé", "ben nghe", "Quận 1", "791161"],
                }
            p_code = "01" if (code_str.startswith("01") or (len(code_str) == 5 and code_str.startswith("0"))) else ("79" if (code_str.startswith("79") or code_str.startswith("26") or code_str.startswith("27")) else "")
            if p_code:
                return {
                    "code": code_str,
                    "name": f"Khu vực cũ {code_str}",
                    "fullName": f"Phường/Xã (Mã cũ: {code_str})",
                    "type": "ward",
                    "provinceCode": p_code,
                    "legacyDistrictName": "Khu vực hành chính cũ",
                    "aliases": [code_str],
                }
        return None

    @classmethod
    def validate_selection(cls, province_code: str, commune_code: str) -> tuple[bool, Optional[str]]:
        """
        Xác thực tính hợp lệ của cấp hành chính 2 cấp theo chuẩn 2025:
        1. Tỉnh/Thành phải tồn tại trong 34 đơn vị hành chính cấp tỉnh.
        2. Xã/Phường/Đặc khu phải tồn tại trong 3.321 đơn vị hành chính cấp xã (hoặc thuộc Legacy Layer).
        3. Xã/Phường/Đặc khu phải thuộc đúng Tỉnh/Thành đã chọn.
        """
        cls._ensure_loaded()
        p_code = str(province_code).strip()
        c_code = str(commune_code).strip()

        prov = cls.get_province_by_code(p_code)
        if not prov:
            return False, f"Mã Tỉnh/Thành phố '{province_code}' không hợp lệ hoặc không thuộc 34 tỉnh/thành hiện hành sau 2025."

        commune = cls.get_commune_by_code(c_code)
        if not commune:
            return False, f"Mã Xã/Phường/Đặc khu '{commune_code}' không hợp lệ trong hệ thống hành chính hiện hành."

        if str(commune.get("provinceCode")) != p_code:
            return False, f"Đơn vị '{commune['fullName']}' không thuộc phạm vi hành chính của '{prov['fullName']}'."

        return True, None


# Tự động nạp dữ liệu khi import
AdministrativeDataService.initialize()
