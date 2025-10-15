from decimal import Decimal
from flask import jsonify, request, render_template, redirect, url_for, flash
from sqlalchemy import text
from app import db
from . import inventory_bp
from .models import Item, Location
from .services import create_move, transfer_between_bins, InventoryError

# ---- Utils ----
def _get_or_create_location(bin_code: str) -> Location:
    loc = Location.query.filter_by(code=bin_code).first()
    if loc:
        return loc
    # Try to parse SITE:AREA/RACK/BIN pattern
    site, area, rack, bin_name = None, None, None, None
    rest = bin_code
    if ":" in bin_code:
        site, rest = bin_code.split(":", 1)
    parts = rest.split("/")
    if len(parts) > 0: area = parts[0]
    if len(parts) > 1: rack = parts[1]
    if len(parts) > 2: bin_name = parts[2]
    loc = Location(code=bin_code, site=site, area=area, rack=rack, bin=bin_name, active=True)
    db.session.add(loc)
    db.session.flush()
    return loc

# ---- JSON APIs ----
@inventory_bp.get("/soh")
def soh_json():
    """Stock on hand per bin (JSON)."""
    rows = db.session.execute(text("""
        SELECT i.sku, i.name, l.code AS bin_code,
               s.qty_on_hand, s.avg_cost_usd,
               ROUND(s.qty_on_hand * s.avg_cost_usd, 2) AS value_usd
        FROM stocks s
        JOIN items i ON s.item_id = i.id
        JOIN locations l ON s.location_id = l.id
        ORDER BY i.sku, l.code
    """)).mappings().all()
    return jsonify([dict(r) for r in rows])

@inventory_bp.get("/valuation")
def valuation_json():
    row = db.session.execute(text("""
        SELECT ROUND(SUM(s.qty_on_hand * s.avg_cost_usd), 2) AS total_value_usd
        FROM stocks s
    """)).mappings().first()
    return jsonify(row or {"total_value_usd": 0})

@inventory_bp.post("/grn")
def grn_post():
    data = request.get_json(force=True)
    it = Item.query.filter_by(sku=data["sku"]).first_or_404()
    loc = Location.query.filter_by(code=data["bin_code"]).first_or_404()
    mv = create_move(item_id=it.id, location_id=loc.id, mtype="GRN",
                     qty=Decimal(str(data["qty"])),
                     unit_cost_usd=Decimal(str(data["unit_cost_usd"])),
                     ref_type="GRN", ref_id=str(data.get("ref_id") or "API"))
    db.session.commit()
    return jsonify({"ok": True, "move_id": mv.id}), 201

@inventory_bp.post("/issue")
def issue_post():
    data = request.get_json(force=True)
    it = Item.query.filter_by(sku=data["sku"]).first_or_404()
    loc = Location.query.filter_by(code=data["bin_code"]).first_or_404()
    mv = create_move(item_id=it.id, location_id=loc.id, mtype="Issue",
                     qty=Decimal(str(data["qty"])),
                     ref_type=str(data.get("ref_type") or None),
                     ref_id=str(data.get("ref_id") or None),
                     note=str(data.get("note") or None))
    db.session.commit()
    return jsonify({"ok": True, "move_id": mv.id}), 201

@inventory_bp.post("/return")
def return_post():
    data = request.get_json(force=True)
    it = Item.query.filter_by(sku=data["sku"]).first_or_404()
    loc = Location.query.filter_by(code=data["bin_code"]).first_or_404()
    mv = create_move(item_id=it.id, location_id=loc.id, mtype="Return",
                     qty=Decimal(str(data["qty"])),
                     ref_type=str(data.get("ref_type") or None),
                     ref_id=str(data.get("ref_id") or None),
                     note=str(data.get("note") or None))
    db.session.commit()
    return jsonify({"ok": True, "move_id": mv.id}), 201

# ---- HTML Pages ----
@inventory_bp.get("/ping")
def inv_ping():
    return {"ok": True, "msg": "inventory online"}

@inventory_bp.get("/stock")
def stock_page():
    rows = db.session.execute(text("""
        SELECT i.sku, i.name, l.code AS bin_code,
               s.qty_on_hand, s.avg_cost_usd,
               ROUND(s.qty_on_hand * s.avg_cost_usd, 2) AS value_usd
        FROM stocks s
        JOIN items i ON s.item_id = i.id
        JOIN locations l ON s.location_id = l.id
        ORDER BY i.sku, l.code
    """)).mappings().all()
    return render_template("inventory/stock.html", rows=rows)

@inventory_bp.route("/grn-form", methods=["GET","POST"])
def grn_form():
    if request.method == "GET":
        return render_template("inventory/grn_form.html")

    # accept either the new 'part_number' or old 'sku'
    part_number = (request.form.get("part_number") or request.form.get("sku") or "").strip()
    bin_code = request.form["bin_code"].strip()
    qty = Decimal(request.form["qty"])
    cost = Decimal(request.form["unit_cost_usd"])
    ref_id = (request.form.get("ref_id") or "UI").strip()

    it = Item.query.filter_by(sku=part_number).first()
    if not it:
        flash(f"Part Number '{part_number}' not found. Please create the item first.", "danger")
        return render_template("inventory/grn_form.html"), 400

    loc = _get_or_create_location(bin_code)
    try:
        create_move(item_id=it.id, location_id=loc.id, mtype="GRN",
                    qty=qty, unit_cost_usd=cost, ref_type="GRN", ref_id=ref_id)
        db.session.commit()
        flash(f"Received {qty} {it.uom} of {part_number} into {bin_code}.", "success")
        return redirect(url_for("inventory.stock_page"))
    except InventoryError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return render_template("inventory/grn_form.html"), 400

@inventory_bp.get("/api/po/<string:number>")
def api_po(number: str):
    """
    Return PO header + lines for the UI. Each line includes:
    part_number, name, ordered_qty, received_qty, remaining_qty, suggested_unit_cost_usd
    """
    # header
    header = db.session.execute(text("""
        SELECT p.id, p.number, p.currency
        FROM po_headers p
        WHERE p.number = :no
        LIMIT 1
    """), {"no": number}).mappings().first()
    if not header:
        return jsonify({"error": "PO not found"}), 404

    # lines
    lines = db.session.execute(text("""
        SELECT pl.id,
               i.sku AS part_number,
               i.name,
               pl.qty        AS ordered_qty,
               COALESCE(pl.received_qty,0) AS received_qty,
               (pl.qty - COALESCE(pl.received_qty,0)) AS remaining_qty,
               -- suggestion: use last landed USD from item if present; fallback to pl.price if exists
               COALESCE(i.last_landed_usd, pl.price) AS suggested_unit_cost_usd
        FROM po_lines pl
        JOIN items i ON i.id = pl.item_id
        WHERE pl.po_id = :po_id
        ORDER BY i.sku
    """), {"po_id": header["id"]}).mappings().all()

    return jsonify({
        "po": {"number": header["number"], "currency": header["currency"]},
        "lines": [dict(r) for r in lines]
    })

@inventory_bp.route("/grn-po", methods=["GET", "POST"])
def grn_po():
    if request.method == "GET":
        return render_template("inventory/grn_po.html")

    # POST: arrays from the form
    po_number = (request.form.get("po_number") or "").strip()
    parts = request.form.getlist("part_number[]")
    recv_qtys = request.form.getlist("recv_qty[]")
    bins = request.form.getlist("bin_code[]")
    costs = request.form.getlist("unit_cost_usd[]")

    if not parts:
        flash("No PO lines to receive.", "danger")
        return redirect(url_for("inventory.grn_po"))

    # receive line-by-line
    try:
        for idx, pn in enumerate(parts):
            part = (pn or "").strip()
            qty = Decimal((recv_qtys[idx] or "0").strip() or "0")
            if qty <= 0:
                continue
            bin_code = (bins[idx] or "").strip()
            cost = Decimal((costs[idx] or "0").strip() or "0")

            it = Item.query.filter_by(sku=part).first()
            if not it:
                raise InventoryError(f"Part Number '{part}' not found.")

            loc = _get_or_create_location(bin_code)
            create_move(
                item_id=it.id, location_id=loc.id, mtype="GRN",
                qty=qty, unit_cost_usd=cost, ref_type="PO", ref_id=po_number
            )

        db.session.commit()
        flash(f"GRN posted for PO {po_number}.", "success")
        return redirect(url_for("inventory.stock_page"))
    except InventoryError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return redirect(url_for("inventory.grn_po"))


@inventory_bp.route("/issue-form", methods=["GET","POST"])
def issue_form():
    if request.method == "GET":
        return render_template("inventory/issue_form.html")

    mtype = request.form["mtype"]
    sku = request.form["sku"].strip()
    bin_code = request.form["bin_code"].strip()
    qty = Decimal(request.form["qty"])
    ref_type = (request.form.get("ref_type") or None)
    ref_id = (request.form.get("ref_id") or None)
    note = (request.form.get("note") or None)

    it = Item.query.filter_by(sku=sku).first()
    if not it:
        flash(f"SKU '{sku}' not found.", "danger")
        return render_template("inventory/issue_form.html"), 400

    loc = Location.query.filter_by(code=bin_code).first()
    if not loc:
        flash(f"Bin '{bin_code}' not found.", "danger")
        return render_template("inventory/issue_form.html"), 400

    try:
        create_move(item_id=it.id, location_id=loc.id, mtype=mtype,
                    qty=qty, ref_type=ref_type, ref_id=ref_id, note=note)
        db.session.commit()
        flash(f"{mtype} {qty} {it.uom} of {sku} @ {bin_code} OK.", "success")
        return redirect(url_for("inventory.stock_page"))
    except InventoryError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return render_template("inventory/issue_form.html"), 400

@inventory_bp.route("/transfer-form", methods=["GET","POST"])
def transfer_form():
    if request.method == "GET":
        return render_template("inventory/transfer_form.html")
    sku = request.form["sku"].strip()
    from_bin = request.form["from_bin"].strip()
    to_bin = request.form["to_bin"].strip()
    qty = Decimal(request.form["qty"])
    try:
        it = Item.query.filter_by(sku=sku).first_or_404()
        src = Location.query.filter_by(code=from_bin).first_or_404()
        dst = Location.query.filter_by(code=to_bin).first_or_404()
        transfer_between_bins(item_id=it.id, from_location_id=src.id, to_location_id=dst.id, qty=qty)
        db.session.commit()
        flash(f"Transferred {qty} of {sku} from {from_bin} → {to_bin}.", "success")
        return redirect(url_for("inventory.stock_page"))
    except InventoryError as e:
        db.session.rollback()
        flash(str(e), "danger")
        return render_template("inventory/transfer_form.html"), 400

# ---- Items page (create/edit + list) ----
@inventory_bp.route("/items", methods=["GET","POST"])
def items_page():
    if request.method == "POST":
        sku_new = request.form["sku"].strip()
        sku_old = (request.form.get("orig_sku") or "").strip() or sku_new
        name = request.form["name"].strip()
        segment = (request.form.get("segment") or "GENERAL").strip().upper()
        make = (request.form.get("make") or "").strip() or None
        model = (request.form.get("model") or "").strip() or None
        uom = (request.form.get("uom") or "EA").strip().upper()
        min_qty = Decimal((request.form.get("min_qty") or "0").strip() or "0")
        last_landed_usd_raw = (request.form.get("last_landed_usd") or "").strip()
        last_landed_usd = Decimal(last_landed_usd_raw) if last_landed_usd_raw else None

        # ensure segment exists
        seg_id = db.session.execute(text("SELECT id FROM segments WHERE code=:c"), {"c": segment}).scalar()
        if not seg_id:
            db.session.execute(text("INSERT INTO segments(code,name) VALUES(:c,:n)"),
                               {"c": segment, "n": segment.title()})
            seg_id = db.session.execute(text("SELECT id FROM segments WHERE code=:c"), {"c": segment}).scalar()

        it = Item.query.filter_by(sku=sku_old).first()
        if it:
            it.sku = sku_new
            it.name = name
            it.segment_id = seg_id
            it.make = make
            it.model = model
            it.uom = uom
            it.min_qty = min_qty
            if last_landed_usd is not None:
                it.last_landed_usd = last_landed_usd
            flash(f"Updated item {sku_new}.", "success")
        else:
            db.session.add(Item(
                sku=sku_new, name=name, segment_id=seg_id, make=make, model=model,
                uom=uom, min_qty=min_qty, last_landed_usd=last_landed_usd, is_active=True
            ))
            flash(f"Created item {sku_new}.", "success")

        db.session.commit()
        return redirect(url_for("inventory.items_page"))

    # GET list with totals
    rows = db.session.execute(text("""
        WITH agg AS (
          SELECT s.item_id,
                 ROUND(SUM(s.qty_on_hand), 3) AS tot_qty,
                 SUM(s.qty_on_hand * s.avg_cost_usd) AS tot_value
          FROM stocks s
          GROUP BY s.item_id
        )
        SELECT i.sku, i.name, COALESCE(sg.code,'') AS segment,
               COALESCE(i.make,'') AS make,
               COALESCE(i.model,'') AS model,
               i.uom,
               COALESCE(i.min_qty,0) AS min_qty,
               COALESCE(i.last_landed_usd,0) AS last_landed_usd,
               i.last_arrival_date AS last_arrival_date,
               ROUND(COALESCE(a.tot_qty,0), 3) AS total_qty,
               CASE WHEN COALESCE(a.tot_qty,0) > 0
                    THEN ROUND(a.tot_value / a.tot_qty, 6)
                    ELSE 0 END AS global_wac_usd,
               ROUND(COALESCE(a.tot_value,0), 2) AS total_value_usd
        FROM items i
        LEFT JOIN segments sg ON sg.id = i.segment_id
        LEFT JOIN agg a ON a.item_id = i.id
        WHERE i.is_active = 1
        ORDER BY i.sku
    """)).mappings().all()

    return render_template("inventory/items.html", rows=rows)

# ---- Delete or Deactivate item ----
@inventory_bp.post("/items/<string:sku>/delete")
def items_delete(sku: str):
    """Deactivate item; if it has no stock/moves/po/pr usage, hard-delete."""
    it = Item.query.filter_by(sku=sku).first()
    if not it:
        return jsonify({"ok": False, "message": "Item not found"}), 404

    stocks_cnt = db.session.execute(
        text("SELECT COUNT(*) FROM stocks WHERE item_id=:i AND ROUND(qty_on_hand,6) <> 0"),
        {"i": it.id}
    ).scalar() or 0
    moves_cnt = db.session.execute(
        text("SELECT COUNT(*) FROM stock_moves WHERE item_id=:i"),
        {"i": it.id}
    ).scalar() or 0
    po_cnt = db.session.execute(
        text("SELECT COUNT(*) FROM po_lines WHERE item_id=:i"),
        {"i": it.id}
    ).scalar() or 0
    pr_cnt = db.session.execute(
        text("SELECT COUNT(*) FROM pr_lines WHERE item_id=:i"),
        {"i": it.id}
    ).scalar() or 0

    if stocks_cnt == 0 and moves_cnt == 0 and po_cnt == 0 and pr_cnt == 0:
        db.session.delete(it)
        db.session.commit()
        return jsonify({"ok": True, "message": "Item deleted."})
    else:
        it.is_active = False
        db.session.commit()
        return jsonify({"ok": True, "message": "Item deactivated (in use)."})
