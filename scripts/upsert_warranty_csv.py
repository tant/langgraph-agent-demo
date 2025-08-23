import asyncio
import csv
import argparse
from datetime import datetime, date
from pathlib import Path
import sys
from agent.database import async_session, WarrantyRecord

# Ensure repository root is on sys.path when running as a file (e.g., `uv run scripts/upsert_warranty_csv.py`)
_here = Path(__file__).resolve()
_repo_root = _here.parents[1]
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))


def normalize_serial(s: str) -> str:
    """Normalize serial to a canonical form: strip spaces and keep as-is casing.
    Adjust here later if you want uppercasing or dash rules.
    """
    return (s or "").strip().replace(" ", "")


async def upsert_row(session, serial: str, product_name: str, warranty_end_date: date):
    serial_norm = normalize_serial(serial)
    rec = await session.get(WarrantyRecord, serial_norm)
    if rec:
        rec.product_name = product_name
        rec.warranty_end_date = warranty_end_date
    else:
        rec = WarrantyRecord(
            serial=serial_norm,
            product_name=product_name,
            warranty_end_date=warranty_end_date,
        )
        session.add(rec)


async def main(file_path: str, dry_run: bool = False):
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"CSV not found: {file_path}")

    async with async_session() as session:
        # Open and parse CSV
        with p.open("r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            required = {"serial", "product_name", "warranty_end_date"}
            if not required.issubset(set((reader.fieldnames or []))):
                raise ValueError(
                    f"CSV must contain headers: {sorted(required)}. Got: {reader.fieldnames}"
                )

            count = 0
            for row in reader:
                serial = (row.get("serial") or "").strip()
                product_name = (row.get("product_name") or "").strip()
                wed_raw = (row.get("warranty_end_date") or "").strip()
                if not serial or not product_name or not wed_raw:
                    continue  # skip incomplete rows

                # Expect YYYY-MM-DD; accept DD/MM/YYYY as fallback
                d: date
                try:
                    d = datetime.strptime(wed_raw, "%Y-%m-%d").date()
                except ValueError:
                    try:
                        d = datetime.strptime(wed_raw, "%d/%m/%Y").date()
                    except ValueError as ve:
                        raise ValueError(
                            f"Invalid date '{wed_raw}' for serial '{serial}'. Use YYYY-MM-DD or DD/MM/YYYY."
                        ) from ve

                await upsert_row(session, serial, product_name, d)
                count += 1

            if dry_run:
                await session.rollback()
                print(f"[DRY-RUN] Parsed {count} rows. No changes committed.")
            else:
                await session.commit()
                print(f"Upserted {count} rows.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Upsert warranty CSV into database (commits by default)"
    )
    parser.add_argument(
        "--file",
        default="knowledge/warranty.csv",
        help="Path to warranty CSV (default: knowledge/warranty.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and validate only; do not write to DB.",
    )
    args = parser.parse_args()
    asyncio.run(main(args.file, args.dry_run))
