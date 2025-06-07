from flask import Blueprint, request, jsonify, send_file, render_template, make_response, current_app
from sqlalchemy import func, case, and_, cast, Float, or_
from app import db
from app.models import toner_request, TonerCosting, spare_req, spares, Ticket, Assets, Customer
from flask_login import login_required, current_user
from app.utils.permission_required import permission_required
import pandas as pd
import io
from collections import defaultdict
from datetime import datetime
from flask_caching import Cache
import os # Added for favicon route

financial_bp = Blueprint('financial', __name__)
cache = Cache(config={'CACHE_TYPE': 'SimpleCache'})

HOURLY_SERVICE_RATE = 10


def apply_filters(query, model):
    """Applies date and keyword filters to a given SQLAlchemy query."""
    def safe_date(date_str):
        try:
            # Attempt to parse the date; return None if parsing fails
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None # Return None if date_str is invalid or not provided

    start_str = request.args.get('start_date')
    end_str = request.args.get('end_date')

    start_date = safe_date(start_str)
    end_date = safe_date(end_str)

    customer = request.args.get('customer')
    contract = request.args.get('contract')
    serial = request.args.get('serial_number')

    # Determine the correct date field dynamically
    date_field_mapping = {
        Ticket: Ticket.created_at,
        toner_request: toner_request.date_issued,
        spare_req: spare_req.date,
        # Add other models and their respective date fields if needed
    }
    date_field = date_field_mapping.get(model) or \
                 getattr(model, 'date_issued', None) or \
                 getattr(model, 'req_date', None) or \
                 getattr(model, 'created_at', None) or \
                 getattr(model, 'date', None)

    # Apply date filter only if both start_date and end_date are valid
    if start_date and end_date and date_field is not None:
        query = query.filter(date_field.between(start_date, end_date))


    # Apply keyword filters based on model attributes
    if customer:
        if hasattr(model, 'customer_name'):
            query = query.filter(model.customer_name.ilike(f"%{customer}%"))
        elif hasattr(model, 'customer') and model == Ticket:  # Specific for Ticket model
            query = query.filter(model.customer.ilike(f"%{customer}%"))

    if contract:
        # Use or_ for contract fields that might vary
        contract_filters = []
        if hasattr(model, 'contract_code'):
            contract_filters.append(model.contract_code.ilike(f"%{contract}%"))
        if hasattr(model, 'contract'):
            contract_filters.append(model.contract.ilike(f"%{contract}%"))
        if contract_filters:
            query = query.filter(or_(*contract_filters))

    if serial and hasattr(model, 'serial_number'):
        query = query.filter(model.serial_number.ilike(f"%{serial}%"))

    return query


@financial_bp.route('/summary')
@login_required
@permission_required('can_view_financials')
@cache.cached(timeout=300, query_string=True)
def summary():
    """Calculates and returns a summary of toner, spare, and service costs."""
    try:
        # Optimize subqueries to directly get the sum
        toner_cost_subquery = db.session.query(
            func.coalesce(func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost), 0.0)
        ).select_from(toner_request).join(
            TonerCosting,
            and_(
                toner_request.toner_model == TonerCosting.toner_model,
                toner_request.toner_source == TonerCosting.source
            )
        )
        toner_query_result = apply_filters(toner_cost_subquery, toner_request).scalar() or 0.0

        spare_cost_subquery = db.session.query(
            func.coalesce(func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )), 0.0)
        ).join(spares, spare_req.product_code == spares.material_nr)
        spare_query_result = apply_filters(spare_cost_subquery, spare_req).scalar() or 0.0

        ticket_count_subquery = db.session.query(func.count(Ticket.id))
        ticket_count_result = apply_filters(ticket_count_subquery, Ticket).scalar() or 0
        service_cost = ticket_count_result * HOURLY_SERVICE_RATE

        return jsonify({
            "toner_cost": round(float(toner_query_result), 2),
            "spare_cost": round(float(spare_query_result), 2),
            "service_cost": round(float(service_cost), 2),
            "total_cost": round(float(toner_query_result + spare_query_result + service_cost), 2)
        })
    except Exception as e:
        db.session.rollback() # VERY IMPORTANT: Rollback the session on error
        print(f"Error in summary: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@financial_bp.route('/by_customer')
@login_required
@permission_required('can_view_financials')
@cache.cached(timeout=300, query_string=True)
def by_customer():
    """Retrieves financial data grouped by customer."""
    try:
        query = db.session.query(
            Customer.cust_name.label('customer_name'),
            func.coalesce(func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost), 0.0).label(
                'toner_cost'),
            func.coalesce(func.sum(case(
                (spare_req.warehouse.ilike('WORKSHOP'), 0),
                else_=(spare_req.qty * spares.price)
            )), 0.0).label('spare_cost'),
            func.coalesce(func.count(Ticket.id) * HOURLY_SERVICE_RATE, 0.0).label('service_cost')
        ).outerjoin(toner_request, Customer.cust_name == toner_request.customer_name) \
            .outerjoin(TonerCosting, and_(
            toner_request.toner_model == TonerCosting.toner_model,
            toner_request.toner_source == TonerCosting.source
        )) \
            .outerjoin(spare_req, Customer.cust_name == spare_req.customer_name) \
            .outerjoin(spares, spare_req.product_code == spares.material_nr) \
            .outerjoin(Ticket, Customer.cust_name == Ticket.customer) \
            .group_by(Customer.cust_name)

        query = apply_filters(query, Customer)
        results = query.all()
        return jsonify([{
            "customer_name": r.customer_name,
            "toner_cost": round(float(r.toner_cost), 2),
            "spare_cost": round(float(r.spare_cost), 2),
            "service_cost": round(float(r.service_cost), 2),
            "total": round(float(r.toner_cost + r.spare_cost + r.service_cost), 2)
        } for r in results])
    except Exception as e:
        db.session.rollback() # VERY IMPORTANT: Rollback the session on error
        print(f"Error in by_customer: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@financial_bp.route('/by_contract')
@login_required
@permission_required('can_view_financials')
@cache.cached(timeout=300, query_string=True)
def by_contract():
    """Retrieves financial data grouped by contract."""
    try:
        # Define subqueries for each cost type, applying filters
        toner_subq = apply_filters(
            db.session.query(
                toner_request.contract_code.label('contract_code'),
                func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
            ).join(TonerCosting, and_(
                toner_request.toner_model == TonerCosting.toner_model,
                toner_request.toner_source == TonerCosting.source
            )).group_by(toner_request.contract_code),
            toner_request
        ).subquery()

        spare_subq = apply_filters(
            db.session.query(
                spare_req.contract.label('contract_code'),
                func.sum(case(
                    (spare_req.warehouse.ilike('WORKSHOP'), 0),
                    else_=(spare_req.qty * spares.price)
                )).label('spare_cost')
            ).join(spares, spare_req.product_code == spares.material_nr).group_by(spare_req.contract),
            spare_req
        ).subquery()

        service_subq = apply_filters(
            db.session.query(
                Ticket.contract.label('contract_code'),
                (func.count(Ticket.id) * HOURLY_SERVICE_RATE).label('service_cost')
            ).group_by(Ticket.contract),
            Ticket
        ).subquery()

        # Combine results using full outer joins on the 'contract_code'
        results = db.session.query(
            func.coalesce(toner_subq.c.contract_code, spare_subq.c.contract_code, service_subq.c.contract_code).label(
                'contract_code'),
            func.coalesce(toner_subq.c.toner_cost, 0.0).label('toner_cost'),
            func.coalesce(spare_subq.c.spare_cost, 0.0).label('spare_cost'),
            func.coalesce(service_subq.c.service_cost, 0.0).label('service_cost')
        ).outerjoin(spare_subq, toner_subq.c.contract_code == spare_subq.c.contract_code) \
            .outerjoin(service_subq, or_(
            toner_subq.c.contract_code == service_subq.c.contract_code,
            spare_subq.c.contract_code == service_subq.c.contract_code
        )).all()

        # Aggregate the results into a single dictionary to ensure correct totals
        contract_data = defaultdict(
            lambda: {'contract_code': '', 'toner_cost': 0.0, 'spare_cost': 0.0, 'service_cost': 0.0})

        for r in results:
            key = r.contract_code
            if key:
                contract_data[key]['contract_code'] = key
                contract_data[key]['toner_cost'] += float(r.toner_cost or 0)
                contract_data[key]['spare_cost'] += float(r.spare_cost or 0)
                contract_data[key]['service_cost'] += float(r.service_cost or 0)

        return jsonify([{
            "contract_code": data['contract_code'],
            "toner_cost": round(data['toner_cost'], 2),
            "spare_cost": round(data['spare_cost'], 2),
            "service_cost": round(data['service_cost'], 2),
            "total": round(data['toner_cost'] + data['spare_cost'] + data['service_cost'], 2)
        } for data in contract_data.values()])
    except Exception as e:
        db.session.rollback() # VERY IMPORTANT: Rollback the session on error
        print(f"Error in by_contract: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@financial_bp.route('/monthly_trends')
@login_required
@permission_required('can_view_financials')
@cache.cached(timeout=300, query_string=True)
def monthly_trends():
    """Retrieves monthly financial trends."""
    try:
        # Subqueries for each cost type, grouped by month and filtered
        toner_subq = apply_filters(
            db.session.query(
                func.strftime('%Y-%m', toner_request.date_issued).label('month'),
                func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
            ).join(TonerCosting, and_(
                toner_request.toner_model == TonerCosting.toner_model,
                toner_request.toner_source == TonerCosting.source
            )).group_by('month'),
            toner_request
        ).subquery()

        spare_subq = apply_filters(
            db.session.query(
                func.strftime('%Y-%m', spare_req.date).label('month'),
                func.sum(case(
                    (spare_req.warehouse.ilike('WORKSHOP'), 0),
                    else_=(spare_req.qty * spares.price)
                )).label('spare_cost')
            ).join(spares, spare_req.product_code == spares.material_nr).group_by('month'),
            spare_req
        ).subquery()

        service_subq = apply_filters(
            db.session.query(
                func.strftime('%Y-%m', Ticket.created_at).label('month'),
                (func.count(Ticket.id) * HOURLY_SERVICE_RATE).label('service_cost')
            ).group_by('month'),
            Ticket
        ).subquery()

        # Outer join the subqueries on the 'month' field
        results = db.session.query(
            func.coalesce(toner_subq.c.month, spare_subq.c.month, service_subq.c.month).label('month'),
            func.coalesce(toner_subq.c.toner_cost, 0.0).label('toner_cost'),
            func.coalesce(spare_subq.c.spare_cost, 0.0).label('spare_cost'),
            func.coalesce(service_subq.c.service_cost, 0.0).label('service_cost')
        ).outerjoin(spare_subq, toner_subq.c.month == spare_subq.c.month) \
            .outerjoin(service_subq, or_(
            toner_subq.c.month == service_subq.c.month,
            spare_subq.c.month == service_subq.c.month
        )).order_by('month').all()

        return jsonify([{
            "month": r.month,
            "toner_cost": round(float(r.toner_cost), 2),
            "spare_cost": round(float(r.spare_cost), 2),
            "service_cost": round(float(r.service_cost), 2),
            "total": round(float(r.toner_cost + r.spare_cost + r.service_cost), 2)
        } for r in results])
    except Exception as e:
        db.session.rollback() # VERY IMPORTANT: Rollback the session on error
        print(f"Error in monthly_trends: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


@financial_bp.route('/dashboard')
@login_required
@permission_required('can_view_financials')
def financial_dashboard():
    """Renders the financial dashboard HTML page."""
    return render_template('financial/financial_dashboard.html')


@financial_bp.route('/customers_suggest')
def customers_suggest():
    """Provides customer name suggestions for autocompletion."""
    term = request.args.get('term', '')
    if not term:
        return jsonify([])

    suggestions = (
        Customer.query
        .filter(Customer.cust_name.ilike(f'%{term}%'))
        .order_by(Customer.cust_name.asc())
        .limit(10)
        .all()
    )

    return jsonify([cust.cust_name for cust in suggestions])


@financial_bp.route('/export_excel')
@login_required
@permission_required('can_view_financials')
def export_excel():
    report_type = request.args.get('type')
    # Using apply_filters for date arguments here too for consistency,
    # though it needs to be adapted slightly as apply_filters works on a query.
    # For now, manually parse dates to keep it simple.
    # Updated: Use safe_date_export with None as fallback
    def safe_date_export(date_str):
        try:
            return datetime.strptime(date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            return None

    start_date_param = request.args.get('start_date')
    end_date_param = request.args.get('end_date')

    start_date = safe_date_export(start_date_param)
    end_date = safe_date_export(end_date_param)

    customer_filter = request.args.get('customer')
    contract_filter = request.args.get('contract')
    serial_filter = request.args.get('serial_number')

    data_for_export = []
    file_name = "financial_report.xlsx"

    try:
        if report_type == 'customer':
            query = db.session.query(
                Customer.cust_name.label('customer_name'),
                func.coalesce(func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost), 0.0).label('toner_cost'),
                func.coalesce(func.sum(case((spare_req.warehouse.ilike('WORKSHOP'), 0), else_=(spare_req.qty * spares.price))), 0.0).label('spare_cost'),
                func.coalesce(func.count(Ticket.id) * HOURLY_SERVICE_RATE, 0.0).label('service_cost')
            ).outerjoin(toner_request, Customer.cust_name == toner_request.customer_name) \
             .outerjoin(TonerCosting, and_(
                 toner_request.toner_model == TonerCosting.toner_model,
                 toner_request.toner_source == TonerCosting.source
             )) \
             .outerjoin(spare_req, Customer.cust_name == spare_req.customer_name) \
             .outerjoin(spares, spare_req.product_code == spares.material_nr) \
             .outerjoin(Ticket, Customer.cust_name == Ticket.customer) \
             .group_by(Customer.cust_name)

            # Apply date filters to the joined tables if present
            date_filters = []
            if start_date and end_date:
                date_filters.append(toner_request.date_issued.between(start_date, end_date))
                date_filters.append(spare_req.date.between(start_date, end_date))
                date_filters.append(Ticket.created_at.between(start_date, end_date))
                query = query.filter(or_(*date_filters))

            if customer_filter:
                query = query.filter(Customer.cust_name.ilike(f"%{customer_filter}%"))
            # Apply contract and serial filters if they can apply across joined tables
            if contract_filter:
                query = query.filter(or_(
                    toner_request.contract_code.ilike(f"%{contract_filter}%"),
                    spare_req.contract.ilike(f"%{contract_filter}%"),
                    Ticket.contract.ilike(f"%{contract_filter}%")
                ))
            if serial_filter:
                 # This filtering needs careful consideration as serial_number might only be on Assets
                 # For simplicity, if Assets is relevant to the query context, add a join and filter.
                 # Otherwise, if serial_number is implicitly linked via other models, filter accordingly.
                 # Assuming for now it's not directly in Customer, toner_request, spare_req, Ticket
                 # Add specific serial_number filtering if necessary, potentially by joining Assets
                 query = query.outerjoin(Assets, or_(
                     toner_request.serial_number == Assets.serial_number,
                     spare_req.serial_number == Assets.serial_number,
                     Ticket.serial_number == Assets.serial_number
                 ))
                 query = query.filter(Assets.serial_number.ilike(f"%{serial_filter}%"))


            results = query.all()

            for r in results:
                total_cost = round(float(r.toner_cost + r.spare_cost + r.service_cost), 2)
                data_for_export.append({
                    "Customer Name": r.customer_name,
                    "Toner Cost": round(float(r.toner_cost), 2),
                    "Spare Cost": round(float(r.spare_cost), 2),
                    "Service Cost": round(float(r.service_cost), 2),
                    "Total Cost": total_cost
                })
            file_name = "financial_by_customer.xlsx"

        elif report_type == 'contract':
            # Replicate the by_contract logic here, applying filters carefully
            toner_subq_base = db.session.query(
                toner_request.contract_code.label('contract_code'),
                func.sum(cast(toner_request.issued_qty, Float) * TonerCosting.unit_cost).label('toner_cost')
            ).join(TonerCosting, and_(
                toner_request.toner_model == TonerCosting.toner_model,
                toner_request.toner_source == TonerCosting.source
            ))
            if start_date and end_date:
                toner_subq_base = toner_subq_base.filter(toner_request.date_issued.between(start_date, end_date))
            if customer_filter:
                toner_subq_base = toner_subq_base.filter(toner_request.customer_name.ilike(f"%{customer_filter}%"))
            if contract_filter:
                toner_subq_base = toner_subq_base.filter(toner_request.contract_code.ilike(f"%{contract_filter}%"))
            if serial_filter:
                toner_subq_base = toner_subq_base.filter(toner_request.serial_number.ilike(f"%{serial_filter}%"))
            toner_subq = toner_subq_base.group_by(toner_request.contract_code).subquery()

            spare_subq_base = db.session.query(
                spare_req.contract.label('contract_code'),
                func.sum(case(
                    (spare_req.warehouse.ilike('WORKSHOP'), 0),
                    else_=(spare_req.qty * spares.price)
                )))
            if start_date and end_date:
                spare_subq_base = spare_subq_base.filter(spare_req.date.between(start_date, end_date))
            if customer_filter:
                spare_subq_base = spare_subq_base.filter(spare_req.customer_name.ilike(f"%{customer_filter}%"))
            if contract_filter:
                spare_subq_base = spare_subq_base.filter(spare_req.contract.ilike(f"%{contract_filter}%"))
            if serial_filter:
                spare_subq_base = spare_subq_base.filter(spare_req.serial_number.ilike(f"%{serial_filter}%"))
            spare_subq = spare_subq_base.join(spares, spare_req.product_code == spares.material_nr).group_by(spare_req.contract).subquery()

            service_subq_base = db.session.query(
                Ticket.contract.label('contract_code'),
                (func.count(Ticket.id) * HOURLY_SERVICE_RATE).label('service_cost')
            )
            if start_date and end_date:
                service_subq_base = service_subq_base.filter(Ticket.created_at.between(start_date, end_date))
            if customer_filter:
                service_subq_base = service_subq_base.filter(Ticket.customer.ilike(f"%{customer_filter}%"))
            if contract_filter:
                service_subq_base = service_subq_base.filter(Ticket.contract.ilike(f"%{contract_filter}%"))
            if serial_filter:
                service_subq_base = service_subq_base.filter(Ticket.serial_number.ilike(f"%{serial_filter}%"))
            service_subq = service_subq_base.group_by(Ticket.contract).subquery()

            combined_results = db.session.query(
                func.coalesce(toner_subq.c.contract_code, spare_subq.c.contract_code, service_subq.c.contract_code).label('contract_code'),
                func.coalesce(toner_subq.c.toner_cost, 0.0).label('toner_cost'),
                func.coalesce(spare_subq.c.spare_cost, 0.0).label('spare_cost'),
                func.coalesce(service_subq.c.service_cost, 0.0).label('service_cost')
            ).outerjoin(spare_subq, toner_subq.c.contract_code == spare_subq.c.contract_code) \
             .outerjoin(service_subq, or_(
                 toner_subq.c.contract_code == service_subq.c.contract_code,
                 spare_subq.c.contract_code == service_subq.c.contract_code
             )).all()

            contract_data_dict = defaultdict(lambda: {'contract_code': '', 'toner_cost': 0.0, 'spare_cost': 0.0, 'service_cost': 0.0})
            for r in combined_results:
                key = r.contract_code
                if key:
                    contract_data_dict[key]['contract_code'] = key
                    contract_data_dict[key]['toner_cost'] += float(r.toner_cost or 0)
                    contract_data_dict[key]['spare_cost'] += float(r.spare_cost or 0)
                    contract_data_dict[key]['service_cost'] += float(r.service_cost or 0)

            for data in contract_data_dict.values():
                total_cost = round(data['toner_cost'] + data['spare_cost'] + data['service_cost'], 2)
                data_for_export.append({
                    "Contract Code": data['contract_code'],
                    "Toner Cost": round(data['toner_cost'], 2),
                    "Spare Cost": round(data['spare_cost'], 2),
                    "Service Cost": round(data['service_cost'], 2),
                    "Total Cost": total_cost
                })
            file_name = "financial_by_contract.xlsx"

        else:
            return jsonify({"error": "Invalid report type specified."}), 400

        # Create DataFrame and Excel file
        df = pd.DataFrame(data_for_export)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='Financial Report')
        output.seek(0)

        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={file_name}'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        return response

    except Exception as e:
        db.session.rollback() # VERY IMPORTANT: Rollback the session on error
        print(f"Error during Excel export: {e}")
        return jsonify({"error": f"An error occurred during export: {e}"}), 500
    finally:
        # Flask-SQLAlchemy usually handles session removal at the end of the request context.
        # Explicit `db.session.rollback()` in `except` is the key for error recovery.
        pass

# Route for favicon.ico to prevent unnecessary errors
@financial_bp.route('/favicon.ico')
def favicon():
    """Serves the favicon.ico file."""
    # Ensure 'app' is accessible or use current_app.root_path
    from flask import send_from_directory
    return send_from_directory(os.path.join(current_app.root_path, 'static'),
                               'favicon.ico', mimetype='image/vnd.microsoft.icon')