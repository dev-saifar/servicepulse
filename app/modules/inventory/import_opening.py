import csv
from datetime import datetime
from decimal import Decimal

from app import db
from .models import Segment, Location, Item
from .services import receive_opening_balance


def _get_or_create_segment(code: str, name: str | None = None) -> Segment:
    seg = Segment.query.filter_by(code=code).first()
    if seg:
        return seg
    seg = Segment(code=code, name=name or code.title())
    db.session.add(seg)
    db.session.flush()
    return seg


def _get_or_create_location(code: str) -> Location:
    loc = Location.query.filter_by(code=code).first()
    if loc:
        return loc
    # naive split helper (site:area/rack/bin) if you follow that convention
    site, area, rack, bin_code = None, None, None, None
    if ":" in code:
        site, rest = code.split(":", 1)
    else:
        rest = code
    parts = rest.split("/")
    if len(parts) > 0:
        area = parts[0]
    if len(parts) > 1:
        rack = parts[1]
    if len(parts) > 2:
        bin_code = parts[2]

    loc = Location(code=code, site=site, area=area, rack=rack, bin=bin_code, active=True)
    db.session.add(loc)
    db.session.flush()
    return loc


def _get_or_create_item(sku: str, name: str, segment_id: int | None, make: str | None, model: str | None) -> Item:
    it = Item.query.filter_by(sku=sku).first()
    if it:
        # update descriptive fields if changed
        it.name = name or it.name
        it.segment_id = segment_id or it.segment_id
        it.make = make or it.make
        it.model = model or it.model
        return it
    it = Item(sku=sku, name=name, segment_id=segment_id, make=make, model=model, is_active=True)
    db.session.add(it)
    db.session.flush()
    return it


def import_opening_csv(csv_path: str, default_currency: str = "USD"):
    """
    Reads the opening list CSV and posts GRN moves per row into the exact bin (location).
    CSV must have headers exactly as specified.
    """
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        required = [
            "Location","Segment","Product Description","Product Code","Make","Model",
            "QTY","Buying Currency","Buying Price","Unit Landed USD","Date of Arrival"
        ]
        for col in required:
            if col not in reader.fieldnames:
                raise ValueError(f"Missing column: {col}")

        for i, row in enumerate(reader, start=2):  # data starts on line 2
            loc_code = (row["Location"] or "").strip()
            seg_code = (row["Segment"] or "").strip() or "GENERAL"
            name = (row["Product Description"] or "").strip()
            sku = (row["Product Code"] or "").strip()
            make = (row["Make"] or "").strip() or None
            model = (row["Model"] or "").strip() or None
            qty = Decimal(row["QTY"] or "0")
            unit_landed_usd = Decimal((row["Unit Landed USD"] or "0"))
            # If no landed cost given, fall back to buying price (assumed already in USD for v1.0)
            if unit_landed_usd == 0:
                buying_cur = (row["Buying Currency"] or default_currency).strip().upper()
                buying_price = Decimal((row["Buying Price"] or "0"))
                # v1.0 assumption: if buying_cur != USD, you already converted before import.
                # (We can add FX conversion in v1.1)
                unit_landed_usd = buying_price

            arrived_on = None
            d = (row["Date of Arrival"] or "").strip()
            if d:
                for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
                    try:
                        arrived_on = datetime.strptime(d, fmt).date()
                        break
                    except Exception:
                        pass
                if not arrived_on:
                    raise ValueError(f"Bad date '{d}' on row {i}. Use YYYY-MM-DD.")

            if not (loc_code and sku and name and qty > 0 and unit_landed_usd >= 0):
                raise ValueError(f"Incomplete/malformed row {i}: {row}")

            seg = _get_or_create_segment(seg_code)
            loc = _get_or_create_location(loc_code)
            item = _get_or_create_item(sku=sku, name=name, segment_id=seg.id, make=make, model=model)

            mv = receive_opening_balance(
                item_id=item.id,
                location_id=loc.id,
                qty=qty,
                unit_landed_usd=unit_landed_usd,
                arrived_on=arrived_on,
                note="Opening balance import",
            )
            # convenience snapshots on item
            if arrived_on:
                item.last_arrival_date = arrived_on
            item.last_landed_usd = unit_landed_usd

        db.session.commit()
