from flask import Blueprint, request, jsonify, send_file, render_template, redirect, url_for
from sqlalchemy import func, case, and_, cast, Float
from app import db
from app.models import toner_request, TonerCosting, spare_req, spares, Ticket, Assets, Customer
from flask_login import login_required, current_user
from app.utils.permission_required import permission_required
import pandas as pd
import io
from collections import defaultdict
from datetime import datetime

financial_bp = Blueprint('financial', __name__)

HOURLY_SERVICE_RATE = 10

def apply_filters(query, model):
    from datetime import datetime

    today = datetime.today().date()
    default_start = datetime(today.year, 1, 1).date()

    def safe_date(date_str, fallback):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except:
            return fallback

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date = safe_date(start_str, default_start)
    end_date = safe_date(end_str, today)

    print(f"[FILTER] {model.__name__} | {start_date} to {end_date}")

    customer = request.args.get('customer')
    contract = request.args.get('contract')
    serial = request.args.get('serial_number')

    if query is None:
        query = db.session.query(model)

    date_field = getattr(model, 'date_issued', None) or \
                 getattr(model, 'req_date', None) or \
                 getattr(model, 'created_at', None) or \
                 getattr(model, 'date', None)

    if date_field is not None:
        query = query.filter(date_field.between(start_date, end_date))

    if hasattr(model, 'customer_name') and customer:
        query = query.filter(model.customer_name.ilike(f"%{customer}%"))
    if hasattr(model, 'contract_code') and contract:
        query = query.filter(model.contract_code.ilike(f"%{contract}%"))
    if hasattr(model, 'contract') and contract:
        query = query.filter(model.contract.ilike(f"%{contract}%"))
    if hasattr(model, 'serial_number') and serial:
        query = query.filter(model.serial_number.ilike(f"%{serial}%"))

    return query


# 🔹 Updated Logic with Manual Spare and Ticket Calculation

def get_customer_data():
    toner_costs, spare_costs, service_costs = defaultdict(float), defaultdict(float), defaultdict(float)

    toner_query = apply_filters(db.session.query(toner_request), toner_request)
    for t in toner_query.all():
        cost_entry = TonerCosting.query.filter_by(toner_model=t.toner_model, source=t.toner_source).first()
        unit_cost = cost_entry.unit_cost if cost_entry else 0.0
        total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0
        toner_costs[t.customer_name] += total_cost

    spare_query = apply_filters(db.session.query(spare_req), spare_req)
    for s in spare_query.all():
        spare_info = spares.query.filter_by(material_nr=s.product_code).first()
        unit_cost = 0.0 if s.warehouse and s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
        total_cost = unit_cost * s.qty
        spare_costs[s.customer_name] += total_cost

    ticket_query = apply_filters(db.session.query(Ticket), Ticket)
    for t in ticket_query.all():
        customer = t.customer or "Unknown"
        service_costs[customer] += HOURLY_SERVICE_RATE

    all_customers = set(toner_costs) | set(spare_costs) | set(service_costs)
    return [{
        "customer_name": cust,
        "toner_cost": round(toner_costs.get(cust, 0), 2),
        "spare_cost": round(spare_costs.get(cust, 0), 2),
        "service_cost": round(service_costs.get(cust, 0), 2),
        "total": round(toner_costs.get(cust, 0) + spare_costs.get(cust, 0) + service_costs.get(cust, 0), 2)
    } for cust in all_customers]

def get_contract_data():
    toner_costs, spare_costs, service_costs = defaultdict(float), defaultdict(float), defaultdict(float)

    # === TONER ===
    toner_query = apply_filters(db.session.query(toner_request), toner_request)
    for t in toner_query.all():
        contract = str(t.contract_code) if t.contract_code else ""
        cost_entry = TonerCosting.query.filter_by(toner_model=t.toner_model, source=t.toner_source).first()
        unit_cost = cost_entry.unit_cost if cost_entry else 0.0
        total_cost = unit_cost * (t.issued_qty or 0)
        toner_costs[contract] += total_cost

    # === SPARE ===
    spare_query = apply_filters(db.session.query(spare_req), spare_req)
    for s in spare_query.all():
        contract = str(s.contract) if s.contract else ""
        spare_info = spares.query.filter_by(material_nr=s.product_code).first()
        unit_cost = 0.0 if s.warehouse and s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
        total_cost = unit_cost * s.qty
        spare_costs[contract] += total_cost

    # === SERVICE ===
    ticket_query = apply_filters(db.session.query(Ticket), Ticket)
    for t in ticket_query.all():
        contract = str(t.contract) if t.contract else ""
        service_costs[contract] += HOURLY_SERVICE_RATE

    # === COMBINE ===
    all_contracts = set(toner_costs) | set(spare_costs) | set(service_costs)
    data = []
    for code in all_contracts:
        toner = toner_costs.get(code, 0)
        spare = spare_costs.get(code, 0)
        service = service_costs.get(code, 0)
        total = toner + spare + service
        data.append({
            "contract_code": code,
            "toner_cost": round(toner, 2),
            "spare_cost": round(spare, 2),
            "service_cost": round(service, 2),
            "total": round(total, 2)
        })

    return data

def get_asset_data():
    toner_costs, spare_costs, service_costs = defaultdict(float), defaultdict(float), defaultdict(float)

    toner_query = apply_filters(db.session.query(toner_request), toner_request)
    for t in toner_query.all():
        cost_entry = TonerCosting.query.filter_by(toner_model=t.toner_model, source=t.toner_source).first()
        unit_cost = cost_entry.unit_cost if cost_entry else 0.0
        total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0
        toner_costs[t.serial_number] += total_cost

    spare_query = apply_filters(db.session.query(spare_req), spare_req)
    for s in spare_query.all():
        spare_info = spares.query.filter_by(material_nr=s.product_code).first()
        unit_cost = 0.0 if s.warehouse and s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
        total_cost = unit_cost * s.qty
        spare_costs[s.serial_number] += total_cost

    ticket_query = apply_filters(db.session.query(Ticket), Ticket)
    for t in ticket_query.all():
        key = t.serial_number or "Unspecified"
        service_costs[key] += HOURLY_SERVICE_RATE

    all_assets = set(toner_costs) | set(spare_costs) | set(service_costs)
    return [{
        "serial_number": sn,
        "toner_cost": round(toner_costs.get(sn, 0), 2),
        "spare_cost": round(spare_costs.get(sn, 0), 2),
        "service_cost": round(service_costs.get(sn, 0), 2),
        "total": round(toner_costs.get(sn, 0) + spare_costs.get(sn, 0) + service_costs.get(sn, 0), 2)
    } for sn in all_assets]

# Routes

@financial_bp.route('/summary')
def summary():
    toner_cost = sum([r['toner_cost'] for r in get_customer_data()])
    spare_cost = sum([r['spare_cost'] for r in get_customer_data()])
    service_cost = sum([r['service_cost'] for r in get_customer_data()])
    return jsonify({
        "toner_cost": round(toner_cost, 2),
        "spare_cost": round(spare_cost, 2),
        "service_cost": round(service_cost, 2),
        "total_cost": round(toner_cost + spare_cost + service_cost, 2)
    })

@financial_bp.route('/by_customer')
def by_customer():
    return jsonify(get_customer_data())

@financial_bp.route('/by_contract')
def by_contract():
    return jsonify(get_contract_data())

@financial_bp.route('/by_asset')
def by_asset():
    return jsonify(get_asset_data())

@financial_bp.route('/monthly_trends')
def monthly_trends():
    toner = apply_filters(
        db.session.query(
            func.strftime('%Y-%m', toner_request.date_issued).label('month'),
            func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
        ).join(TonerCosting, and_(
            toner_request.toner_model == TonerCosting.toner_model,

            toner_request.toner_source == TonerCosting.source
        )),
        toner_request
    ).group_by('month').subquery()

    spare = apply_filters(
        db.session.query(
            func.strftime('%Y-%m', spare_req.date).label('month'),
            func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )).label('spare_cost')
        ).join(spares, spare_req.product_code == spares.material_nr),
        spare_req
    ).group_by('month').subquery()

    service = apply_filters(
        db.session.query(
            func.strftime('%Y-%m', Ticket.created_at).label('month'),
            func.count(Ticket.id).label('service_count')
        ).join(Assets, Ticket.serial_number == Assets.serial_number),
        Ticket
    ).group_by('month').subquery()

    results = db.session.query(
        toner.c.month,
        func.coalesce(toner.c.toner_cost, 0),
        func.coalesce(spare.c.spare_cost, 0),
        func.coalesce(service.c.service_count, 0)
    ).outerjoin(spare, toner.c.month == spare.c.month
    ).outerjoin(service, toner.c.month == service.c.month).order_by(toner.c.month).all()

    return jsonify([{
        "month": r[0],
        "toner_cost": round(r[1], 2),
        "spare_cost": round(r[2], 2),
        "service_cost": r[3] * HOURLY_SERVICE_RATE,
        "total": round(r[1] + r[2] + r[3] * HOURLY_SERVICE_RATE, 2)
    } for r in results])

@financial_bp.route('/export_excel')
def export_excel():
    data_type = request.args.get('type', 'customer')
    if data_type == 'customer':
        data = get_customer_data()
    elif data_type == 'contract':
        data = get_contract_data()
    elif data_type == 'asset':
        data = get_asset_data()
    else:
        return jsonify({"error": "Invalid export type"}), 400

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=data_type.title())
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=f"{data_type}_financial_report.xlsx")

@financial_bp.route('/dashboard')
@login_required
@permission_required('can_view_financials')
def financial_dashboard():
    return render_template('financial/financial_dashboard.html')
from app.models import Customer

@financial_bp.route('/customers_suggest')
def customers_suggest():
    term = request.args.get('term', '')
    customers = Customer.query.filter(Customer.cust_name.ilike(f"%{term}%")).limit(10).all()
    return jsonify([c.cust_name for c in customers])
@financial_bp.route('/')
@login_required
@permission_required('can_view_financials')
def financial_home():
    return redirect(url_for('financial.financial_dashboard'))

