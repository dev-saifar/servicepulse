from datetime import datetime
from app import db

# ---------- Master ----------

class Segment(db.Model):
    __tablename__ = "segments"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String, unique=True, nullable=False)   # TONER, SPARE, etc.
    name = db.Column(db.String, nullable=False)


class Location(db.Model):
    __tablename__ = "locations"
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String, unique=True, nullable=False)   # e.g. KLA:WH1/R1/BIN-03
    site = db.Column(db.String)   # optional
    area = db.Column(db.String)
    rack = db.Column(db.String)
    bin = db.Column(db.String)
    active = db.Column(db.Boolean, nullable=False, default=True)


class Supplier(db.Model):
    __tablename__ = "suppliers"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String, unique=True, nullable=False)
    currency = db.Column(db.String(8), nullable=False, default="USD")
    terms = db.Column(db.String)
    lead_time_days = db.Column(db.Integer, default=0)
    contact_json = db.Column(db.Text, default="{}")


class ExchangeRate(db.Model):
    __tablename__ = "exchange_rates"
    id = db.Column(db.Integer, primary_key=True)
    base = db.Column(db.String(8), nullable=False)   # USD
    quote = db.Column(db.String(8), nullable=False)  # UGX
    rate = db.Column(db.Numeric(18, 6), nullable=False)  # quote per base
    as_of = db.Column(db.Date, nullable=False)
    __table_args__ = (db.UniqueConstraint("base", "quote", "as_of", name="uq_fx_pair_date"),)

# ---------- Items & Stock ----------

class Item(db.Model):
    __tablename__ = "items"
    id = db.Column(db.Integer, primary_key=True)
    sku = db.Column(db.String, unique=True, nullable=False)    # Product Code
    name = db.Column(db.String, nullable=False)                # Product Description
    segment_id = db.Column(db.Integer, db.ForeignKey("segments.id"))
    make = db.Column(db.String)
    model = db.Column(db.String)
    uom = db.Column(db.String, nullable=False, default="EA")
    min_qty = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    last_arrival_date = db.Column(db.Date)
    last_landed_usd = db.Column(db.Numeric(18, 6))

    segment = db.relationship("Segment")


class Stock(db.Model):
    __tablename__ = "stocks"
    id = db.Column(db.Integer, primary_key=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id", ondelete="CASCADE"), nullable=False)
    qty_on_hand = db.Column(db.Numeric(18, 3), nullable=False, default=0)
    avg_cost_usd = db.Column(db.Numeric(18, 6), nullable=False, default=0)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    item = db.relationship("Item")
    location = db.relationship("Location")
    __table_args__ = (db.UniqueConstraint("item_id", "location_id", name="uq_stock_item_location"),)


class StockMove(db.Model):
    __tablename__ = "stock_moves"
    id = db.Column(db.Integer, primary_key=True)
    ts = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id", ondelete="CASCADE"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    type = db.Column(db.String, nullable=False)  # GRN|Issue|Return|Adjust
    ref_type = db.Column(db.String)              # PO|GRN|Ticket|TonerReq|ADJ...
    ref_id = db.Column(db.String)
    qty = db.Column(db.Numeric(18, 3), nullable=False)  # positive; sign implied by type
    unit_cost_usd = db.Column(db.Numeric(18, 6), nullable=False, default=0)
    note = db.Column(db.String)
    created_by = db.Column(db.Integer)

    item = db.relationship("Item")
    location = db.relationship("Location")
    __table_args__ = (
        db.CheckConstraint("qty > 0", name="ck_move_qty_pos"),
        db.CheckConstraint("type in ('GRN','Issue','Return','Adjust')", name="ck_move_type"),
    )

# ---------- Procurement shells (to flesh out next) ----------

class PR(db.Model):
    __tablename__ = "prs"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String, unique=True, nullable=False)     # PR-YYMM-####
    requester_id = db.Column(db.Integer)
    status = db.Column(db.String, nullable=False, default="Draft") # Draft|Submitted|Approved|Rejected|ConvertedToPO|Closed
    needed_by = db.Column(db.Date)
    reason = db.Column(db.String)
    total_estimate = db.Column(db.Numeric(18, 6), default=0)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class PRLine(db.Model):
    __tablename__ = "pr_lines"
    id = db.Column(db.Integer, primary_key=True)
    pr_id = db.Column(db.Integer, db.ForeignKey("prs.id", ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    qty = db.Column(db.Numeric(18, 3), nullable=False)
    est_price = db.Column(db.Numeric(18, 6), default=0)

    pr = db.relationship("PR")
    item = db.relationship("Item")
    location = db.relationship("Location")


class PO(db.Model):
    __tablename__ = "pos"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String, unique=True, nullable=False)     # PO-YYMM-####
    supplier_id = db.Column(db.Integer, db.ForeignKey("suppliers.id"), nullable=False)
    status = db.Column(db.String, nullable=False, default="Draft") # Draft|Submitted|Approved|PartiallyReceived|FullyReceived|Closed|Cancelled
    currency = db.Column(db.String(8), nullable=False, default="USD")
    ordered_at = db.Column(db.DateTime)
    created_by = db.Column(db.Integer)
    notes = db.Column(db.Text)

    supplier = db.relationship("Supplier")


class POLine(db.Model):
    __tablename__ = "po_lines"
    id = db.Column(db.Integer, primary_key=True)
    po_id = db.Column(db.Integer, db.ForeignKey("pos.id", ondelete="CASCADE"), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    qty = db.Column(db.Numeric(18, 3), nullable=False)
    price = db.Column(db.Numeric(18, 6), nullable=False)          # in PO currency
    uom = db.Column(db.String, nullable=False, default="EA")
    received_qty = db.Column(db.Numeric(18, 3), nullable=False, default=0)

    po = db.relationship("PO")
    item = db.relationship("Item")
    location = db.relationship("Location")


class GRN(db.Model):
    __tablename__ = "grns"
    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String, unique=True, nullable=False)     # GRN-YYMM-####
    po_id = db.Column(db.Integer, db.ForeignKey("pos.id"))
    posted_by = db.Column(db.Integer)
    posted_at = db.Column(db.DateTime)
    freight_cost_usd = db.Column(db.Numeric(18, 6), default=0)
    other_cost_usd = db.Column(db.Numeric(18, 6), default=0)

    po = db.relationship("PO")


class GRNLine(db.Model):
    __tablename__ = "grn_lines"
    id = db.Column(db.Integer, primary_key=True)
    grn_id = db.Column(db.Integer, db.ForeignKey("grns.id", ondelete="CASCADE"), nullable=False)
    po_line_id = db.Column(db.Integer, db.ForeignKey("po_lines.id"))
    item_id = db.Column(db.Integer, db.ForeignKey("items.id"), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey("locations.id"), nullable=False)
    qty = db.Column(db.Numeric(18, 3), nullable=False)
    unit_cost_usd = db.Column(db.Numeric(18, 6), nullable=False)   # landed USD unit
    source_currency = db.Column(db.String(8), nullable=False)
    source_unit_price = db.Column(db.Numeric(18, 6), nullable=False)
    fx_rate = db.Column(db.Numeric(18, 6), nullable=False)
    arrived_on = db.Column(db.Date)

    grn = db.relationship("GRN")
    item = db.relationship("Item")
    location = db.relationship("Location")


class Approval(db.Model):
    __tablename__ = "approvals"
    id = db.Column(db.Integer, primary_key=True)
    entity_type = db.Column(db.String, nullable=False)  # PR|PO
    entity_id = db.Column(db.Integer, nullable=False)
    step = db.Column(db.Integer, nullable=False)
    approver_id = db.Column(db.Integer, nullable=False)
    decision = db.Column(db.String, nullable=False, default="Pending")  # Pending|Approved|Rejected|Override
    decided_at = db.Column(db.DateTime)
    comment = db.Column(db.Text)
    __table_args__ = (db.UniqueConstraint("entity_type", "entity_id", "step", "approver_id", name="uq_approval_step"),)
