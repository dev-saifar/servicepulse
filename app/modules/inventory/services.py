from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from typing import Optional

from app import db
from .models import Item, Location, Stock, StockMove

QTY_Q = Decimal("0.001")      # 3dp quantities
MNY_Q = Decimal("0.000001")   # 6dp money


class InventoryError(Exception):
    pass


def _q(x) -> Decimal:
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return d.quantize(QTY_Q, rounding=ROUND_HALF_UP)


def _m(x) -> Decimal:
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return d.quantize(MNY_Q, rounding=ROUND_HALF_UP)


def _get_stock(item_id: int, location_id: int) -> Stock:
    # FOR UPDATE is not supported in SQLite; rely on single-writer discipline
    stock = Stock.query.filter_by(item_id=item_id, location_id=location_id).first()
    if not stock:
        stock = Stock(item_id=item_id, location_id=location_id, qty_on_hand=_q(0), avg_cost_usd=_m(0))
        db.session.add(stock)
        db.session.flush()
    return stock


def _wac_receive(stock: Stock, qty_in: Decimal, unit_cost_usd: Decimal):
    old_qty = Decimal(stock.qty_on_hand or 0)
    old_avg = Decimal(stock.avg_cost_usd or 0)
    qty_in = _q(qty_in)
    unit_cost_usd = _m(unit_cost_usd)

    new_qty = old_qty + qty_in
    if new_qty <= 0:
        stock.avg_cost_usd = unit_cost_usd
        stock.qty_on_hand = _q(new_qty)
        return

    new_val = old_qty * old_avg + qty_in * unit_cost_usd
    stock.avg_cost_usd = _m(new_val / new_qty)
    stock.qty_on_hand = _q(new_qty)


def _issue(stock: Stock, qty_out: Decimal, allow_negative=False):
    qty_out = _q(qty_out)
    if not allow_negative and qty_out > Decimal(stock.qty_on_hand or 0):
        raise InventoryError("Insufficient stock for issue.")
    stock.qty_on_hand = _q(Decimal(stock.qty_on_hand or 0) - qty_out)
    # avg cost unchanged on issue


def create_move(
    *,
    item_id: int,
    location_id: int,
    mtype: str,
    qty: Decimal,
    unit_cost_usd: Decimal = Decimal("0"),
    ref_type: Optional[str] = None,
    ref_id: Optional[str] = None,
    note: Optional[str] = None,
    created_by: Optional[int] = None,
    allow_negative: bool = False,
) -> StockMove:
    """
    Create a ledger move and update the snapshot (stocks).
    mtype in {'GRN','Issue','Return','Adjust'}
    """
    item = Item.query.get(item_id)
    if not item or not item.is_active:
        raise InventoryError("Invalid or inactive item.")
    loc = Location.query.get(location_id)
    if not loc or not loc.active:
        raise InventoryError("Invalid or inactive location.")

    stock = _get_stock(item_id, location_id)

    if mtype == "GRN":
        _wac_receive(stock, qty, unit_cost_usd)
    elif mtype == "Issue":
        _issue(stock, qty, allow_negative=allow_negative)
    elif mtype == "Return":
        # returns add back at current avg cost unless explicit cost given
        use_cost = unit_cost_usd if unit_cost_usd and Decimal(unit_cost_usd) > 0 else Decimal(stock.avg_cost_usd or 0)
        _wac_receive(stock, qty, use_cost)
    elif mtype == "Adjust":
        qd = _q(qty)
        if qd > 0:
            _wac_receive(stock, qd, unit_cost_usd or stock.avg_cost_usd or 0)
        elif qd < 0:
            _issue(stock, -qd, allow_negative=False)
        else:
            raise InventoryError("Zero adjustment.")
    else:
        raise InventoryError("Invalid move type.")

    move = StockMove(
        item_id=item_id,
        location_id=location_id,
        type=mtype,
        qty=_q(qty),
        unit_cost_usd=_m(unit_cost_usd or 0),
        ref_type=ref_type,
        ref_id=str(ref_id) if ref_id is not None else None,
        note=note,
        created_by=created_by,
    )
    db.session.add(move)
    return move


def receive_opening_balance(
    *,
    item_id: int,
    location_id: int,
    qty: Decimal,
    unit_landed_usd: Decimal,
    arrived_on: Optional[date] = None,
    note: str = "Opening balance import",
    created_by: Optional[int] = None,
):
    mv = create_move(
        item_id=item_id,
        location_id=location_id,
        mtype="GRN",
        qty=qty,
        unit_cost_usd=unit_landed_usd,
        ref_type="GRN",
        ref_id="OPENING",
        note=note,
        created_by=created_by,
    )
    # stamp a back-dated ts if provided (SQLite stores naive datetime)
    if arrived_on:
        mv.ts = mv.ts.replace(year=arrived_on.year, month=arrived_on.month, day=arrived_on.day)
    return mv


def transfer_between_bins(*, item_id: int, from_location_id: int, to_location_id: int, qty: Decimal, created_by: Optional[int] = None):
    """
    Convenience wrapper: Issue from A, Return to B at current WAC (no cost change).
    """
    from_stock = _get_stock(item_id, from_location_id)
    cost = Decimal(from_stock.avg_cost_usd or 0)
    create_move(item_id=item_id, location_id=from_location_id, mtype="Issue", qty=qty, unit_cost_usd=0, ref_type="XFER", ref_id=None, created_by=created_by)
    create_move(item_id=item_id, location_id=to_location_id,   mtype="Return", qty=qty, unit_cost_usd=cost, ref_type="XFER", ref_id=None, created_by=created_by)
