from flask import Blueprint, request, jsonify, send_file, render_template
from sqlalchemy import func, case, and_, cast, Float
from app import db
from app.models import toner_request, TonerCosting, spare_req, spares, Ticket, Assets

import pandas as pd
import io

financial_bp = Blueprint('financial', __name__)

HOURLY_SERVICE_RATE = 10

from datetime import datetime

def apply_filters(query, model):
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    customer = request.args.get('customer')
    contract = request.args.get('contract')
    serial = request.args.get('serial_number')

    # Always ensure query is valid
    if query is None:
        return db.session.query(model)

    # Check for a date field
    date_field = getattr(model, 'date_issued', None) or \
                 getattr(model, 'req_date', None) or \
                 getattr(model, 'created_at', None) or \
                 getattr(model, 'date', None)

    min_date = datetime(2025, 1, 1)

    # Apply default or custom date range filter
    if date_field is not None:
        if start_date and end_date:
            query = query.filter(date_field.between(start_date, end_date))
        else:
            query = query.filter(date_field >= min_date)

    if hasattr(model, 'customer_name') and customer:
        query = query.filter(model.customer_name.ilike(f"%{customer}%"))
    if hasattr(model, 'contract_code') and contract:
        query = query.filter(model.contract_code.ilike(f"%{contract}%"))
    if hasattr(model, 'contract') and contract:
        query = query.filter(model.contract.ilike(f"%{contract}%"))
    if hasattr(model, 'serial_number') and serial:
        query = query.filter(model.serial_number.ilike(f"%{serial}%"))

    return query

# 🔹 Shared Data Functions
def get_customer_data():
    toner = apply_filters(
        db.session.query(
            toner_request.customer_name,
            func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
        ).join(TonerCosting, and_(
            toner_request.toner_model == TonerCosting.toner_model,
            toner_request.toner_source == TonerCosting.source
        )),
        toner_request
    ).group_by(toner_request.customer_name).subquery()

    spare = apply_filters(
        db.session.query(
            spare_req.customer_name,
            func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )).label('spare_cost')
        ).join(spares, spare_req.product_code == spares.material_nr),
        spare_req
    ).group_by(spare_req.customer_name).subquery()

    service = apply_filters(
        db.session.query(
            Assets.customer_name,
            func.count(Ticket.id).label('service_count')
        ).join(Assets, Ticket.serial_number == Assets.serial_number),
        Ticket
    ).group_by(Assets.customer_name).subquery()

    results = db.session.query(
        toner.c.customer_name,
        func.coalesce(toner.c.toner_cost, 0),
        func.coalesce(spare.c.spare_cost, 0),
        func.coalesce(service.c.service_count, 0)
    ).outerjoin(spare, toner.c.customer_name == spare.c.customer_name
    ).outerjoin(service, toner.c.customer_name == service.c.customer_name).all()

    return [{
        "customer_name": r[0],
        "toner_cost": round(r[1], 2),
        "spare_cost": round(r[2], 2),
        "service_cost": r[3] * HOURLY_SERVICE_RATE,
        "total": round(r[1] + r[2] + r[3] * HOURLY_SERVICE_RATE, 2)
    } for r in results]

def get_contract_data():
    toner = apply_filters(
        db.session.query(
            toner_request.contract_code,
            func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
        ).join(TonerCosting, and_(
            toner_request.toner_model == TonerCosting.toner_model,

            toner_request.toner_source == TonerCosting.source
        )),
        toner_request
    ).group_by(toner_request.contract_code).subquery()

    spare = apply_filters(
        db.session.query(
            spare_req.contract.label('contract_code'),
            func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )).label('spare_cost')
        ).join(spares, spare_req.product_code == spares.material_nr),
        spare_req
    ).group_by(spare_req.contract).subquery()

    service = apply_filters(
        db.session.query(
            Assets.contract.label('contract_code'),
            func.count(Ticket.id).label('service_count')
        ).join(Assets, Ticket.serial_number == Assets.serial_number),
        Ticket
    ).group_by(Assets.contract).subquery()

    results = db.session.query(
        toner.c.contract_code,
        func.coalesce(toner.c.toner_cost, 0),
        func.coalesce(spare.c.spare_cost, 0),
        func.coalesce(service.c.service_count, 0)
    ).outerjoin(spare, toner.c.contract_code == spare.c.contract_code
    ).outerjoin(service, toner.c.contract_code == service.c.contract_code).all()

    return [{
        "contract_code": r[0],
        "toner_cost": round(r[1], 2),
        "spare_cost": round(r[2], 2),
        "service_cost": r[3] * HOURLY_SERVICE_RATE,
        "total": round(r[1] + r[2] + r[3] * HOURLY_SERVICE_RATE, 2)
    } for r in results]

def get_asset_data():
    toner = apply_filters(
        db.session.query(
            toner_request.serial_number,
            func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
        ).join(TonerCosting, and_(
            toner_request.toner_model == TonerCosting.toner_model,

            toner_request.toner_source == TonerCosting.source
        )),
        toner_request
    ).group_by(toner_request.serial_number).subquery()

    spare = apply_filters(
        db.session.query(
            spare_req.serial_number,
            func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )).label('spare_cost')
        ).join(spares, spare_req.product_code == spares.material_nr),
        spare_req
    ).group_by(spare_req.serial_number).subquery()

    service = apply_filters(
        db.session.query(
            Ticket.serial_number,
            func.count(Ticket.id).label('service_count')
        ).join(Assets, Ticket.serial_number == Assets.serial_number),
        Ticket
    ).group_by(Ticket.serial_number).subquery()

    results = db.session.query(
        toner.c.serial_number,
        func.coalesce(toner.c.toner_cost, 0),
        func.coalesce(spare.c.spare_cost, 0),
        func.coalesce(service.c.service_count, 0)
    ).outerjoin(spare, toner.c.serial_number == spare.c.serial_number
    ).outerjoin(service, toner.c.serial_number == service.c.serial_number).all()

    return [{
        "serial_number": r[0],
        "toner_cost": round(r[1], 2),
        "spare_cost": round(r[2], 2),
        "service_cost": r[3] * HOURLY_SERVICE_RATE,
        "total": round(r[1] + r[2] + r[3] * HOURLY_SERVICE_RATE, 2)
    } for r in results]

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
def financial_dashboard():
    return render_template('financial/financial_dashboard.html')
from app.models import Customer

@financial_bp.route('/customers_suggest')
def customers_suggest():
    term = request.args.get('term', '')
    customers = Customer.query.filter(Customer.cust_name.ilike(f"%{term}%")).limit(10).all()
    return jsonify([c.cust_name for c in customers])
