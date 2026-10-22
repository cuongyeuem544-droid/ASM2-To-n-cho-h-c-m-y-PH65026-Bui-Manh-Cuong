"""Script to harden product image assignments in Neon DB.

- Clears generic Unsplash URLs from CanonicalProduct (prevents misleading packaging photos)
- Maps verified local packshots from apps/storefront/public/images/products/ to exact matching products
- Supports --dry-run and --commit flags (Rule 1.8 compliance)
"""

import argparse
import sys
from pathlib import Path

# Add apps/api to path
api_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(api_dir))

from app.db.session import SessionLocal
from app.models.entities import CanonicalProduct


EXACT_LOCAL_MAPPINGS = {
    # Panadol Extra Đỏ (15 vỉ x 12 viên = 180 viên)
    279185: "/images/products/panadol-extra-do-180v.jpg",
    279211: "/images/products/panadol-extra-do-180v.jpg",
    279252: "/images/products/panadol-extra-do-180v.jpg",
    279336: "/images/products/panadol-extra-do-180v.jpg",
    # Hapacol 500mg (chai 200 viên)
    279284: "/images/products/hapacol-500.jpg",
    # Enterogermina 2 tỷ / 20 ống
    120085: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    124535: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    124710: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    124960: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    125694: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    126418: "/images/products/enterogermina-gut-defense-2-ty.jpg",
    # Gaviscon 24 gói 10ml
    279189: "/images/products/gaviscon-24-goi-10ml.jpg",
    279238: "/images/products/gaviscon-24-goi-10ml.jpg",
    279257: "/images/products/gaviscon-24-goi-10ml.jpg",
    # Smecta 3g (30 gói)
    279236: "/images/products/smecta-3g-30-goi.jpg",
    279255: "/images/products/smecta-3g-30-goi.jpg",
}


def main():
    parser = argparse.ArgumentParser(description="Harden product images in database")
    parser.add_argument("--commit", action="store_true", help="Commit changes to database")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (default)")
    args = parser.parse_args()

    commit = args.commit and not args.dry_run

    db = SessionLocal()
    try:
        print(f"Running image hardening (commit={commit}, dry_run={not commit})...")

        # 1. Apply verified local mappings
        local_updated = 0
        for pid, local_path in EXACT_LOCAL_MAPPINGS.items():
            product = db.query(CanonicalProduct).filter(CanonicalProduct.id == pid).first()
            if product:
                prev_local = product.local_image_url
                prev_img = product.image_url
                product.local_image_url = local_path
                # If image_url was an unsplash URL, clear it so local_image_url is the primary
                if product.image_url and "unsplash" in product.image_url:
                    product.image_url = None
                print(f"  [MAPPED] Product {pid} ({product.canonical_name[:40]}): local={local_path} (was local={prev_local}, img={prev_img[:35] if prev_img else None})")
                local_updated += 1
            else:
                print(f"  [WARNING] Product {pid} not found in database!")

        # 2. Clear all remaining Unsplash images
        unsplash_products = (
            db.query(CanonicalProduct)
            .filter(CanonicalProduct.image_url.like("%unsplash.com%"))
            .all()
        )
        unsplash_cleared = 0
        for p in unsplash_products:
            prev_img = p.image_url
            p.image_url = None
            unsplash_cleared += 1
            print(f"  [CLEARED UNSPLASH] Product {p.id} ({p.canonical_name[:40]}): reset to placeholder fallback")

        print(f"\nSummary:")
        print(f"  - Verified local images assigned: {local_updated}")
        print(f"  - Unsplash generic stock photos cleared: {unsplash_cleared}")

        if commit:
            db.commit()
            print("  ==> CHANGES COMMITTED SUCCESSFULLY TO DATABASE.")
        else:
            db.rollback()
            print("  ==> DRY-RUN COMPLETE. No changes were committed.")

    except Exception as e:
        db.rollback()
        print(f"Error during image hardening: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
