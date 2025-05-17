from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash
from app.models import Assets, TonerModel, toner_request , Contract , DeliveryTeam
from app.extensions import db
from datetime import datetime
import pandas as pd
from flask import send_file
import io
from dateutil import parser
from flask_login import login_required
from flask_login import login_required
from app.utils.permission_required import permission_required

toner_bp = Blueprint(
    'toner',  # 👈 used in url_for()
    __name__,
    template_folder='templates/toner',
    static_folder='static',
    static_url_path='/static/toner'
)


# 🔍 Asset Search Page
@toner_bp.route('/search_assets', methods=['GET', 'POST'])
@login_required
@permission_required('can_view_assets')
def search_assets():
    if request.method == 'POST':
        data = request.get_json()
        query = Assets.query

        if data.get("serial_number"):
            query = query.filter(Assets.serial_number.ilike(f"%{data['serial_number']}%"))
        if data.get("customer_name"):
            query = query.filter(Assets.customer_name.ilike(f"%{data['customer_name']}%"))
        if data.get("service_location"):
            query = query.filter(Assets.service_location.ilike(f"%{data['service_location']}%"))
        if data.get("region"):
            query = query.filter(Assets.region.ilike(f"%{data['region']}%"))

        results = query.limit(100).all()

        return jsonify([{
            "serial_number": a.serial_number,
            "customer_name": a.customer_name,
            "service_location": a.service_location,
            "region": a.region,
            "asset_description": a.asset_Description
        } for a in results])

    return render_template('toner/search_assets_toner.html')


@toner_bp.route('/request/<serial_number>', methods=['GET'])
@login_required
@permission_required('can_request_toner')
def load_toner_request(serial_number):
    asset = Assets.query.filter_by(serial_number=serial_number).first()
    if not asset:
        flash("Asset not found", "danger")
        return redirect(url_for("toner.search_assets"))

    requested_by = ""
    request_type = ""

    # Determine toner types from model
    toner_model = TonerModel.query.filter_by(part_number=asset.part_no).first()

    toner_types = []
    if toner_model:
        if toner_model.machine_type == 'MONO':
            toner_types = ['K']
        elif toner_model.machine_type == 'COLOR':
            toner_types = ['K', 'C', 'M', 'Y']

    # Fetch toner history
    history = toner_request.query.filter_by(serial_number=serial_number).order_by(
        toner_request.date_issued.desc()).limit(10).all()

    # 🔁 Fetch billing company from Contract table
    contract = Contract.query.filter_by(contract_code=asset.contract).first()
    billing_company = contract.billing_company if contract else ""

    return render_template('toner/toner_request.html',
                           asset=asset,
                           toner_types=toner_types,
                           history=history,
                           requested_by=requested_by,
                           request_type=request_type,
                           billing_company=billing_company)

# 🔁 Fetch Toner Models for Selected Machine
@toner_bp.route('/get_toner_models', methods=['POST'])
@login_required
def get_toner_models():
    data = request.get_json()
    model = data.get('model')
    toner_type = data.get('toner_type')

    results = TonerModel.query.filter_by(asset_model=model, toner_type=toner_type).all()
    return jsonify([{"model": t.model} for t in results])


# ✅ Submit Toner Request
@toner_bp.route('/submit_request', methods=['POST'])
@login_required
@permission_required('can_request_toner')
def submit_toner_request():
    data = request.get_json()
    try:
        new_request = toner_request(
            serial_number=data['serial_number'],
            asset_code=data['asset_code'],
            asset_description=data['asset_description'],
            customer_name=data['customer_name'],
            service_location=data['service_location'],
            region=data['region'],
            billing_company=data['billing_company'],
            contract_code=data['contract_code'],
            toner_type=data['toner_type'],
            toner_model=data['toner_model'],
            toner_source=data['toner_source'],
            issued_qty=int(data['issued_qty']),
            meter_reading=int(data['meter_reading']),
            requested_by=data['requested_by'],
            comments=data['comments'],
            date_issued=datetime.now()
        )
        db.session.add(new_request)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})


# 🖨 Print/Reprint Toner Request
@toner_bp.route('/print_request/<int:id>')
@login_required
@permission_required('can_view_toner_dashboard')
def print_toner_request(id):
    req = toner_request.query.get(id)
    if not req:
        flash("Request not found", "danger")
        return redirect(url_for("toner.search_assets"))

    history = toner_request.query.filter(
        toner_request.serial_number == req.serial_number,
        toner_request.id != id
    ).order_by(toner_request.date_issued.desc()).limit(10).all()

    return render_template("toner/print_toner_request.html",
                           requests=requests,
                           asset=asset,
                           history=history,
                           title_company=title_company,
                           now=datetime.now())  # ✅ Fix for the 'now' undefined error


# ✏️ Get Data for Editing a Request
@toner_bp.route('/get_request/<int:id>')
@login_required
@permission_required('can_edit_toner_requests')
def get_request(id):
    req = toner_request.query.get(id)
    if not req:
        return jsonify({"error": "Request not found"})

    return jsonify({
        "id": req.id,
        "serial_number": req.serial_number,
        "asset_description": req.asset_description,
        "customer_name": req.customer_name,
        "toner_type": req.toner_type,
        "toner_model": req.toner_model,
        "toner_source": req.toner_source,
        "issued_qty": req.issued_qty,
        "meter_reading": req.meter_reading,
        "requested_by": req.requested_by,
        "comments": req.comments,
        "delivery_status": req.delivery_status,
        "delivery_date": req.delivery_date.strftime('%Y-%m-%d') if req.delivery_date else "",
        "receiver_name": req.receiver_name
    })


# 💾 Update an Existing Request
@toner_bp.route('/update_request', methods=['POST'])
@login_required
@permission_required('can_edit_toner_requests')
def update_request():
    data = request.get_json()
    try:
        # Fetch the original request to get the request_group
        original_req = toner_request.query.get(data['id'])
        if not original_req:
            return jsonify({"success": False, "error": "Request not found"})

        # Get all requests in the same group
        group_requests = toner_request.query.filter_by(request_group=original_req.request_group).all()

        for req in group_requests:
            req.toner_source = data.get('toner_source')
            req.issued_qty = int(data.get('issued_qty', req.issued_qty))
            req.meter_reading = int(data.get('meter_reading', req.meter_reading))
            req.requested_by = data.get('requested_by')
            req.comments = data.get('comments')
            req.delivery_status = data.get('delivery_status')
            req.receiver_name = data.get('receiver_name')
            req.delivery_boy = data.get('delivery_boy')
            req.foc = data.get('foc')
            req.issued_by = data.get('issued_by')
            req.request_type = data.get('request_type')

            # Handle delivery_date only if Delivered
            if req.delivery_status == "Delivered":
                delivery_date = data.get('delivery_date')
                if delivery_date:
                    req.delivery_date = parser.parse(delivery_date)



            # Handle dispatch_time only if In Transit
            if req.delivery_status == "In Transit":
                dispatch_time = data.get('dispatch_time')
                if dispatch_time:
                    if dispatch_time:
                        req.dispatch_time = parser.parse(dispatch_time)

        db.session.commit()
        return jsonify({"success": True})


    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})
@toner_bp.route('/dashboard')
@login_required
@permission_required('can_view_toner_dashboard')
def toner_dashboard():
    page = request.args.get('page', 1, type=int)
    per_page = 100

    # Filters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    customer_filter = request.args.get("customer", "").strip()
    region_filter = request.args.get("region", "").strip()
    status_filter = request.args.get("status", "").strip()
    delivery_boy_filter = request.args.get("delivery_boy", "").strip()
    foc_filter = request.args.get("foc", "").strip()

    serial_filter = request.args.get("serial_number", "").strip()
    asset_desc_filter = request.args.get("asset_description", "").strip()

    # Base query
    query = toner_request.query

    # Apply filters
    if from_date:
        query = query.filter(toner_request.date_issued >= from_date)
    if to_date:
        query = query.filter(toner_request.date_issued <= to_date)
    if customer_filter:
        query = query.filter(toner_request.customer_name.ilike(f"%{customer_filter}%"))
    if region_filter:
        query = query.filter(toner_request.region == region_filter)
    if status_filter:
        query = query.filter(toner_request.delivery_status == status_filter)
    if delivery_boy_filter:
        query = query.filter(toner_request.delivery_boy.ilike(f"%{delivery_boy_filter}%"))
    if foc_filter:
        query = query.filter(toner_request.foc == foc_filter)
    if serial_filter:
        query = query.filter(toner_request.serial_number.ilike(f"%{serial_filter}%"))
    if asset_desc_filter:
        query = query.filter(toner_request.asset_description.ilike(f"%{asset_desc_filter}%"))

    # Summary counts (before pagination)
    delivered_count = query.filter(toner_request.delivery_status == 'Delivered').count()
    pending_count = query.filter(toner_request.delivery_status == 'Pending').count()
    in_transit_count = query.filter(toner_request.delivery_status == 'In Transit').count()
    foc_pending_count = query.filter(toner_request.foc == 'Pending').count()

    # Pagination
    query = query.order_by(toner_request.date_issued.desc())
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    requests = pagination.items

    from datetime import datetime

    now = datetime.now()
    for r in requests:
        if r.date_issued:
            if r.delivery_status == "Delivered" and r.delivery_date:
                r.tat_label = "Final"
                r.tat_hours = round((r.delivery_date - r.date_issued).total_seconds() / 3600, 2)
            else:
                r.tat_label = "Live"
                r.tat_hours = round((now - r.date_issued).total_seconds() / 3600, 2)
        else:
            r.tat_label = None
            r.tat_hours = None

    # Distinct region list for dropdown
    region_list = db.session.query(toner_request.region).distinct().all()
    regions = [r[0] for r in region_list if r[0]]

    # Return template with context
    return render_template(
        'toner/toner_dashboard.html',
        requests=requests,
        pagination=pagination,
        delivered_count=delivered_count,
        pending_count=pending_count,
        in_transit_count=in_transit_count,
        foc_pending_count=foc_pending_count,
        regions=regions,
        filters={
            "customer": customer_filter,
            "region": region_filter,
            "status": status_filter,
            "delivery_boy": delivery_boy_filter,
            "from_date": from_date,
            "to_date": to_date,
            "foc": foc_filter,
            "serial_number": serial_filter,
            "asset_description": asset_desc_filter
        }
    )

# 📦 Load Dashboard Data
@toner_bp.route('/dashboard_data')
@login_required
@permission_required('can_view_toner_dashboard')
def toner_dashboard_data():
    from_date = request.args.get("from")
    to_date = request.args.get("to")
    query = toner_request.query

    if from_date:
        query = query.filter(toner_request.date_issued >= from_date)
    if to_date:
        query = query.filter(toner_request.date_issued <= to_date)

    query = query.order_by(toner_request.date_issued.desc()).limit(500)

    return jsonify([{
        "id": r.id,
        "date_issued": r.date_issued.strftime('%Y-%m-%d'),
        "serial_number": r.serial_number,
        "customer_name": r.customer_name,
        "toner_type": r.toner_type,
        "toner_model": r.toner_model,
        "issued_qty": r.issued_qty,
        "meter_reading": r.meter_reading,
        "delivery_status": r.delivery_status or "Pending"
    } for r in query.all()])

@toner_bp.route('/get_toner_model_and_life', methods=['POST'])
@login_required
def get_toner_model_and_life():
    data = request.get_json()
    model = data.get('machine_model')  # match what JS sends
    ttype = data.get('toner_type')

    # Try to fetch matching toner model without machine_type filter
    toner = TonerModel.query.filter_by(part_number=model).first()

    if not toner:
        return jsonify({"model": "", "life": ""})

    model_field = f"tk_{ttype.lower()}"
    life_field = f"{ttype.lower()}_life"

    return jsonify({
        "model": getattr(toner, model_field, ""),
        "life": getattr(toner, life_field, "")
    })

@toner_bp.route('/fetch_previous_reading/<serial>/<toner_type>')
@login_required
def fetch_previous_reading(serial, toner_type):
    from app.models import toner_request
    last = toner_request.query.filter_by(
        serial_number=serial,
        toner_type=toner_type
    ).order_by(toner_request.date_issued.desc()).first()

    return jsonify({"previous": last.meter_reading if last else 0})
from datetime import datetime
import uuid

@toner_bp.route('/submit_bulk_request', methods=['POST'])
@login_required
@permission_required('can_request_toner')
def submit_bulk_request():
    data = request.get_json()
    success_count = 0
    try:
        request_group = f"TR-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"

        for item in data:
            asset = Assets.query.filter_by(serial_number=item['serial_number']).first()
            if not asset:
                continue

            contract = Contract.query.filter_by(contract_code=asset.contract).first()
            cust_code = contract.cust_code if contract else None

            new_request = toner_request(
                request_group=request_group,
                serial_number=item['serial_number'],
                asset_description=item['machine_model'],
                asset_code=asset.asset_code,
                customer_name=asset.customer_name,
                billing_company=item.get("billing_company"),
                contract_code=asset.contract,
                cust_code=cust_code,  # ✅ Now from Contract table
                service_location=asset.service_location,
                region=asset.region,
                toner_type=item['toner_type'],
                toner_model=item['toner_model'],
                toner_life=int(item['toner_life']),
                toner_source=item['toner_source'],
                issued_qty=int(item['issued_qty']),
                meter_reading=int(item['current_reading']),
                previous_reading=int(item['previous_reading']) if 'previous_reading' in item else 0,
                requested_by=item.get("requested_by") or "Web User",
                request_type=item.get("request_type") or "Call",
                comments=item['remarks'],
                date_issued=datetime.now(),
                foc = item.get("foc") or "Pending"

            )


            db.session.add(new_request)
            success_count += 1

        db.session.commit()
        return jsonify({"success": True, "request_group": request_group})

    except Exception as e:
        db.session.rollback()
        return jsonify({"success": False, "error": str(e)})

from collections import defaultdict

@toner_bp.route('/print_request/<request_group>', methods=['GET'])
@login_required
@permission_required('can_view_toner_dashboard')
def print_request(request_group):
    requests = toner_request.query.filter_by(request_group=request_group).all()
    if not requests:
        flash("Request not found", "danger")
        return redirect(url_for("toner.search_assets"))

    asset = Assets.query.filter_by(serial_number=requests[0].serial_number).first()

    # Get history
    raw_history = toner_request.query.filter(
        toner_request.serial_number == requests[0].serial_number,
        toner_request.date_issued < requests[0].date_issued
    ).order_by(toner_request.date_issued.desc()).all()

    # Calculate actual previous readings
    history = []
    last_reading = defaultdict(lambda: None)
    for entry in raw_history:
        prev = last_reading[entry.toner_type]
        entry.actual_previous = prev if prev is not None else 0
        last_reading[entry.toner_type] = entry.meter_reading or prev
        history.append(entry)

    title_company = (
        "MFI MANAGED DOCUMENT SOLUTIONS LIMITED"
        if requests[0].billing_company and requests[0].billing_company.upper() == "MDS"
        else "MFI DOCUMENT SOLUTIONS LIMITED"
    )

    return render_template("toner/print_toner_request.html",
                           requests=requests,
                           asset=asset,
                           history=history,
                           title_company=title_company,
                           now=datetime.now())

@toner_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
@permission_required('can_delete_toner_request')
def delete_request(id):
    req = toner_request.query.get_or_404(id)
    db.session.delete(req)
    db.session.commit()
    flash("Toner request deleted", "info")
    return redirect(url_for('toner.toner_dashboard'))

@toner_bp.route('/edit/<int:id>', methods=['GET'])
@login_required
@permission_required('can_edit_toner_requests')
def edit_request(id):
    req = toner_request.query.get_or_404(id)
    delivery_team = DeliveryTeam.query.all()
    return render_template('toner/edit_toner_request.html', req=req, delivery_team=delivery_team)


@toner_bp.route('/export_excel')
@login_required
@permission_required('can_export_data')
def export_excel():
    query = toner_request.query

    # Apply filters
    from_date = request.args.get("from_date")
    to_date = request.args.get("to_date")
    customer_filter = request.args.get("customer", "").strip()
    region_filter = request.args.get("region", "").strip()
    status_filter = request.args.get("status", "").strip()
    delivery_boy_filter = request.args.get("delivery_boy", "").strip()

    if from_date:
        query = query.filter(toner_request.date_issued >= from_date)
    if to_date:
        query = query.filter(toner_request.date_issued <= to_date)
    if customer_filter:
        query = query.filter(toner_request.customer_name.ilike(f"%{customer_filter}%"))
    if region_filter:
        query = query.filter(toner_request.region == region_filter)
    if status_filter:
        query = query.filter(toner_request.delivery_status == status_filter)
    if delivery_boy_filter:
        query = query.filter(toner_request.delivery_boy.ilike(f"%{delivery_boy_filter}%"))

    # Convert to DataFrame
    df = pd.DataFrame([{
        'Date Issued': r.date_issued.strftime('%Y-%m-%d %H:%M'),
        'Serial Number': r.serial_number,
        'Asset Code': r.asset_code,
        'Asset Description': r.asset_description,
        'Customer Code': r.cust_code,
        'Customer Name': r.customer_name,
        'Billing Company': r.billing_company,
        'Contract Code': r.contract_code,
        'Service Location': r.service_location,
        'Region': r.region,
        'Toner Type': r.toner_type,
        'Toner Model': r.toner_model,
        'Toner Source': r.toner_source,
        'Toner Life': r.toner_life,
        'Issued Qty': r.issued_qty,
        'Meter Reading': r.meter_reading,
        'Actual Coverage': r.actual_coverage,
        'Previous Reading': r.previous_reading,
        'Delivery Boy': r.delivery_boy,
        'Delivery Date': r.delivery_date.strftime('%Y-%m-%d') if r.delivery_date else '',
        'Receiver Name': r.receiver_name,
        'Delivery Status': r.delivery_status,
        'Requested By': r.requested_by,
        'Issued By': r.issued_by,
        'Comments': r.comments,
        'Request Type': r.request_type,
        'FOC': r.foc
    } for r in query.order_by(toner_request.date_issued.desc()).all()])

    # Generate Excel file in memory
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Toner Requests')

    output.seek(0)
    return send_file(output, download_name="Toner_Requests_Export.xlsx", as_attachment=True)
from flask import request, render_template
from collections import defaultdict
from datetime import datetime, date, timedelta
from sqlalchemy import func
from app.models import toner_request, DeliveryTeam
@toner_bp.route('/delivery_dashboard')
@login_required
@permission_required('can_view_toner_dashboard')
def delivery_dashboard():
    today = date.today()
    filter_boy = request.args.get('delivery_boy')
    filter_date = request.args.get('filter_date')

    delivery_team = DeliveryTeam.query.all()
    stats = []

    for member in delivery_team:
        queries = toner_request.query.filter_by(delivery_boy=member.name)

        if filter_boy:
            queries = queries.filter(toner_request.delivery_boy.ilike(f'%{filter_boy}%'))
        if filter_date:
            queries = queries.filter(func.date(toner_request.date_issued) == filter_date)

        deliveries = queries.all()

        delivered_today = sum(
            1 for r in deliveries
            if r.delivery_status == 'Delivered' and r.delivery_date and r.delivery_date.date() == today
        )
        pending = sum(1 for r in deliveries if r.delivery_status == 'Pending')
        in_transit = sum(1 for r in deliveries if r.delivery_status == 'In Transit')

        # ✅ Safe Average Delivery Time
        completed = []
        for r in deliveries:
            if r.delivery_date and r.date_issued:
                issued_dt = (
                    datetime.combine(r.date_issued, datetime.min.time())
                    if isinstance(r.date_issued, date) and not isinstance(r.date_issued, datetime)
                    else r.date_issued
                )
                diff = (r.delivery_date - issued_dt).total_seconds()
                if diff >= 0:
                    completed.append(diff)

        avg_minutes = round(sum(completed) / 60 / len(completed), 1) if completed else 0

        # ✅ Average Transit Time
        transit_times = []
        for r in deliveries:
            if r.delivery_date and r.dispatch_time and r.dispatch_time <= r.delivery_date:
                diff = (r.delivery_date - r.dispatch_time).total_seconds()
                if diff >= 0:
                    transit_times.append(diff)

        avg_transit = round(sum(transit_times) / 60 / len(transit_times), 1) if transit_times else 0

        stats.append({
            'name': member.name,
            'delivered_today': delivered_today,
            'pending': pending,
            'in_transit': in_transit,
            'avg_time': avg_minutes,
            'avg_transit': avg_transit
        })

    # 🔁 Build trend data for last 7 days
    trend_labels = []
    trend_data = defaultdict(lambda: [0] * 7)
    for i in range(6, -1, -1):
        day = today - timedelta(days=i)
        trend_labels.append(day.strftime('%b %d'))
        day_records = toner_request.query.filter(
            toner_request.delivery_status == 'Delivered',
            func.date(toner_request.delivery_date) == day
        ).all()
        for r in day_records:
            trend_data[r.delivery_boy][6 - i] += 1
    today_request_count = toner_request.query.filter(func.date(toner_request.date_issued) == today).count()

    return render_template(
        'toner/delivery_dashboard.html',
        stats=stats,
        trend_labels=trend_labels,
        trend_data=dict(trend_data),
    today_request_count = today_request_count
    )
from app.utils.permission_required import permission_required
