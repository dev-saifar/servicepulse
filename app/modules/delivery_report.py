from flask import Blueprint
from flask import request, send_file, render_template
from app.models import toner_request, TonerCosting
from app.utils.permission_required import permission_required
from flask_login import login_required
from app import db
import pandas as pd
import io
from flask import current_app
from app.models import Ticket
from flask import render_template

from datetime import datetime
delivery_report_bp = Blueprint('delivery_report', __name__)
@delivery_report_bp.route('/export/toner', methods=['GET'])
@login_required
@permission_required('can_export_financials')
def export_toner_deliveries():
    from_date = request.args.get('start_date')
    to_date = request.args.get('end_date')
    customer = request.args.get('customer')

    query = db.session.query(toner_request).filter(toner_request.delivery_status == 'Delivered')

    if from_date:
        query = query.filter(toner_request.date_issued >= from_date)
    if to_date:
        query = query.filter(toner_request.date_issued <= to_date)
    if customer:
        query = query.filter(toner_request.customer_name.ilike(f"%{customer}%"))

    results = query.all()
    data = []

    for t in results:
        # Try fetching cost from TonerCosting
        cost_entry = TonerCosting.query.filter_by(
            toner_model=t.toner_model,

            source=t.toner_source
        ).first()

        unit_cost = cost_entry.unit_cost if cost_entry else 0.0
        total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0

        data.append({
            "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
            "Serial Number": t.serial_number,
            "Asset Code": t.asset_code,
            "Asset Description": t.asset_description,
            "Customer Code": t.cust_code,
            "Customer Name": t.customer_name,
            "Billing Company": t.billing_company,
            "Contract Code": t.contract_code,
            "Service Location": t.service_location,
            "Toner Type": t.toner_type,
            "Toner Model": t.toner_model,
            "Toner Source": t.toner_source,
            "Issued Qty": t.issued_qty,
            "Unit Cost": round(unit_cost, 2),
            "Total Cost": round(total_cost, 2),
            "Dispatch Time": t.dispatch_time.strftime('%Y-%m-%d %H:%M') if t.dispatch_time else '',
            "Delivery Date": t.delivery_date.strftime('%Y-%m-%d') if t.delivery_date else '',
            "Receiver Name": t.receiver_name,
            "Requested By": t.requested_by,
            "Request Type": t.request_type,
            "FOC": t.foc
        })

    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Toner")
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="toner_deliveries.xlsx")
@delivery_report_bp.route('/toner_report')
@login_required
@permission_required('can_view_financials')
def toner_report_ui():
    return render_template('delivery_report/delivery_report_toner.html')
from app.models import spare_req, spares  # Make sure these imports are present

@delivery_report_bp.route('/export/spare', methods=['GET'])
@login_required
@permission_required('can_export_financials')
def export_spare_deliveries():
    from_date = request.args.get('start_date')
    to_date = request.args.get('end_date')
    customer = request.args.get('customer')

    # Base query
    query = db.session.query(spare_req)

    if from_date:
        query = query.filter(spare_req.date >= from_date)
    if to_date:
        query = query.filter(spare_req.date <= to_date)
    if customer:
        query = query.filter(spare_req.customer_name.ilike(f"%{customer}%"))

    results = query.all()
    data = []

    for s in results:
        # Pricing logic: 0 if from WORKSHOP, else use spares.price
        spare_info = spares.query.filter_by(material_nr=s.product_code).first()
        unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
        total_cost = unit_cost * s.qty

        data.append({
            "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
            "Serial Number": s.serial_number,
            "Asset Description": s.asset_Description,
            "Asset Code": s.code,
            "Technician": s.technician_name,
            "Customer Name": s.customer_name,
            "Service Location": s.service_location,
            "Region": s.region,
            "Contract": s.contract,
            "FOC No": s.foc_no,
            "Product Code": s.product_code,
            "Description": s.description,
            "Spare Type": s.spare_type,
            "Warehouse": s.warehouse,
            "Qty": s.qty,
            "Unit Cost": round(unit_cost, 2),
            "Total Cost": round(total_cost, 2)
        })

    # Export to Excel
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Spare")
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="spare_deliveries.xlsx")

@delivery_report_bp.route('/spare_report')
@login_required
@permission_required('can_view_financials')
def spare_report_ui():
    return render_template('delivery_report/delivery_report_spare.html')

@delivery_report_bp.route('/export/ticket_cost', methods=['GET'])
@login_required
@permission_required('can_export_financials')
def export_ticket_cost_report():
    from_date = request.args.get('start_date')
    to_date = request.args.get('end_date')
    customer = request.args.get('customer')

    query = db.session.query(Ticket)

    if from_date:
        query = query.filter(Ticket.created_at >= from_date)
    if to_date:
        query = query.filter(Ticket.created_at <= to_date)
    if customer:
        query = query.filter(Ticket.customer.ilike(f"%{customer}%"))

    results = query.all()
    data = []

    for t in results:
        service_cost = 10  # Fixed cost per ticket
        data.append({
            "Reference No": t.reference_no,
            "Title": t.title,
            "Customer": t.customer,
            "Call Type": t.call_type,
            "Service Location": t.service_location,
            "Asset Description": t.asset_Description,
            "Called By": t.called_by,
            "Created At": t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
            "Closed At": t.closed_at.strftime('%Y-%m-%d %H:%M') if t.closed_at else '',
            "Serial Number": t.serial_number,
            "Region": t.region,
            "Status": t.complete,
            "Service Cost": service_cost
        })

    # Export to Excel
    df = pd.DataFrame(data)
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name="Ticket Cost")
    output.seek(0)

    return send_file(output, as_attachment=True, download_name="ticket_cost_report.xlsx")

@delivery_report_bp.route('/ticket_cost_report')
@login_required
@permission_required('can_view_financials')
def ticket_cost_report_ui():
    return render_template('delivery_report/delivery_report_ticket_cost.html')

@delivery_report_bp.route('/export/total_service_summary', methods=['GET'])
@login_required
@permission_required('can_export_financials')
def export_total_service_summary():
    from app.models import toner_request, TonerCosting, spare_req, spares, Ticket
    from collections import defaultdict
    from sqlalchemy import func

    from_date = request.args.get('start_date')
    to_date = request.args.get('end_date')
    customer = request.args.get('customer')

    # === TONER ===
    toner_query = (db.session.query(toner_request))
                   #filter(toner_request.delivery_status == 'Delivered'))
    if from_date:
        toner_query = toner_query.filter(toner_request.date_issued >= from_date)
    if to_date:
        toner_query = toner_query.filter(toner_request.date_issued <= to_date)
    if customer:
        toner_query = toner_query.filter(toner_request.customer_name.ilike(f"%{customer}%"))

    toner_data = []
    toner_costs = defaultdict(float)

    for t in toner_query.all():
        cost_entry = TonerCosting.query.filter_by(
            toner_model=t.toner_model,
            source=t.toner_source
        ).first()
        unit_cost = cost_entry.unit_cost if cost_entry else 0.0
        total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0
        toner_costs[t.customer_name] += total_cost

        toner_data.append({
            "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
            "Serial Number": t.serial_number,
            "Asset Code": t.asset_code,
            "Asset Description": t.asset_description,
            "Customer Code": t.cust_code,
            "Customer Name": t.customer_name,
            "Billing Company": t.billing_company,
            "Contract Code": t.contract_code,
            "Service Location": t.service_location,
            "Toner Type": t.toner_type,
            "Toner Model": t.toner_model,
            "Toner Source": t.toner_source,
            "Issued Qty": t.issued_qty,
            "Unit Cost": round(unit_cost, 2),
            "Total Cost": round(total_cost, 2),
            "Dispatch Time": t.dispatch_time.strftime('%Y-%m-%d %H:%M') if t.dispatch_time else '',
            "Delivery Date": t.delivery_date.strftime('%Y-%m-%d') if t.delivery_date else '',
            "Receiver Name": t.receiver_name,
            "Requested By": t.requested_by,
            "Request Type": t.request_type,
            "FOC": t.foc
        })

    # === SPARE ===
    spare_query = db.session.query(spare_req)
    if from_date:
        spare_query = spare_query.filter(spare_req.date >= from_date)
    if to_date:
        spare_query = spare_query.filter(spare_req.date <= to_date)
    if customer:
        spare_query = spare_query.filter(spare_req.customer_name.ilike(f"%{customer}%"))

    spare_data = []
    spare_costs = defaultdict(float)

    for s in spare_query.all():
        spare_info = spares.query.filter_by(material_nr=s.product_code).first()
        unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
        total_cost = unit_cost * s.qty
        spare_costs[s.customer_name] += total_cost

        spare_data.append({
            "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
            "Serial Number": s.serial_number,
            "Asset Description": s.asset_Description,
            "Asset Code": s.code,
            "Technician": s.technician_name,
            "Customer Name": s.customer_name,
            "Service Location": s.service_location,
            "Region": s.region,
            "Contract": s.contract,
            "FOC No": s.foc_no,
            "Product Code": s.product_code,
            "Description": s.description,
            "Spare Type": s.spare_type,
            "Warehouse": s.warehouse,
            "Qty": s.qty,
            "Unit Cost": round(unit_cost, 2),
            "Total Cost": round(total_cost, 2)
        })

    # === TICKETS ===
    ticket_query = db.session.query(Ticket)
    if from_date:
        ticket_query = ticket_query.filter(Ticket.created_at >= from_date)
    if to_date:
        ticket_query = ticket_query.filter(Ticket.created_at <= to_date)
    if customer:
        ticket_query = ticket_query.filter(Ticket.customer.ilike(f"%{customer}%"))

    ticket_data = []
    service_costs = defaultdict(float)

    for t in ticket_query.all():
        service_cost = 10
        service_costs[t.customer] += service_cost

        ticket_data.append({
            "Reference No": t.reference_no,
            "Title": t.title,
            "Customer": t.customer,
            "Call Type": t.call_type,
            "Service Location": t.service_location,
            "Asset Description": t.asset_Description,
            "Called By": t.called_by,
            "Created At": t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
            "Closed At": t.closed_at.strftime('%Y-%m-%d %H:%M') if t.closed_at else '',
            "Serial Number": t.serial_number,
            "Region": t.region,
            "Status": t.complete,
            "Service Cost": service_cost
        })

    # === SUMMARY ===
    all_customers = set(toner_costs) | set(spare_costs) | set(service_costs)
    summary_data = []
    for cust in all_customers:
        toner = toner_costs.get(cust, 0)
        spare = spare_costs.get(cust, 0)
        service = service_costs.get(cust, 0)
        total = toner + spare + service
        summary_data.append({
            "Customer": cust,
            "Toner Cost": round(toner, 2),
            "Spare Cost": round(spare, 2),
            "Service Cost": round(service, 2),
            "Total Cost": round(total, 2)
        })

    # === WRITE TO EXCEL ===
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(toner_data).to_excel(writer, index=False, sheet_name="Toner")
        pd.DataFrame(spare_data).to_excel(writer, index=False, sheet_name="Spare")
        pd.DataFrame(ticket_data).to_excel(writer, index=False, sheet_name="Ticket Cost")
        df_summary = pd.DataFrame(summary_data)
        df_summary.to_excel(writer, index=False, sheet_name="Summary")

        # Insert a chart (Top 5 Customers)
        workbook = writer.book
        worksheet = writer.sheets["Summary"]
        chart = workbook.add_chart({'type': 'column'})

        top5 = df_summary.nlargest(5, 'Total Cost')
        chart.add_series({
            'name': 'Top 5 Customers',
            'categories': ['Summary', 1, 0, 5, 0],
            'values':     ['Summary', 1, 4, 5, 4],
        })
        chart.set_title({'name': 'Top 5 Customers by Total Cost'})
        chart.set_x_axis({'name': 'Customer'})
        chart.set_y_axis({'name': 'Cost ($)'})
        worksheet.insert_chart('G2', chart)

    output.seek(0)
    return send_file(output, as_attachment=True, download_name="total_service_summary.xlsx")


@delivery_report_bp.route('/summary_report')
@login_required
@permission_required('can_view_financials')
def total_service_summary_ui():
    return render_template('delivery_report/delivery_report_summary.html')

# ✅ Scheduler-compatible helper functions

def generate_toner_delivery_excel(start_date=None, end_date=None, customer=None):
    request_args = {'start_date': start_date, 'end_date': end_date, 'customer': customer}
    with current_app.test_request_context(query_string=request_args):
        from_date = request_args['start_date']
        to_date = request_args['end_date']
        customer = request_args['customer']

        query = db.session.query(toner_request).filter(toner_request.delivery_status == 'Delivered')
        if from_date:
            query = query.filter(toner_request.date_issued >= from_date)
        if to_date:
            query = query.filter(toner_request.date_issued <= to_date)
        if customer:
            query = query.filter(toner_request.customer_name.ilike(f"%{customer}%"))

        results = query.all()
        data = []

        for t in results:
            cost_entry = TonerCosting.query.filter_by(
                toner_model=t.toner_model,
                source=t.toner_source
            ).first()
            unit_cost = cost_entry.unit_cost if cost_entry else 0.0
            total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0

            data.append({
                "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
                "Serial Number": t.serial_number,
                "Customer Name": t.customer_name,
                "Toner Model": t.toner_model,
                "Source": t.toner_source,
                "Qty": t.issued_qty,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Toner")
        output.seek(0)
        return output, "toner_delivery_report.xlsx"



def generate_spare_delivery_excel(start_date=None, end_date=None, customer=None):
    request_args = {'start_date': start_date, 'end_date': end_date, 'customer': customer}
    with current_app.test_request_context(query_string=request_args):
        from_date = request_args['start_date']
        to_date = request_args['end_date']
        customer = request_args['customer']

        query = db.session.query(spare_req)
        if from_date:
            query = query.filter(spare_req.date >= from_date)
        if to_date:
            query = query.filter(spare_req.date <= to_date)
        if customer:
            query = query.filter(spare_req.customer_name.ilike(f"%{customer}%"))

        results = query.all()
        data = []

        for s in results:
            spare_info = spares.query.filter_by(material_nr=s.product_code).first()
            unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
            total_cost = unit_cost * s.qty
            data.append({
                "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
                "Serial Number": s.serial_number,
                "Product Code": s.product_code,
                "Description": s.description,
                "Qty": s.qty,
                "Warehouse": s.warehouse,
                "Customer Name": s.customer_name,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Spare")
        output.seek(0)
        return output, "spare_delivery_report.xlsx"



def generate_ticket_cost_excel(start_date=None, end_date=None, customer=None):
    request_args = {'start_date': start_date, 'end_date': end_date, 'customer': customer}
    with current_app.test_request_context(query_string=request_args):
        from_date = request_args['start_date']
        to_date = request_args['end_date']
        customer = request_args['customer']

        query = db.session.query(Ticket)
        if from_date:
            query = query.filter(Ticket.created_at >= from_date)
        if to_date:
            query = query.filter(Ticket.created_at <= to_date)
        if customer:
            query = query.filter(Ticket.customer.ilike(f"%{customer}%"))

        results = query.all()
        data = []
        for t in results:
            data.append({
                "Reference No": t.reference_no,
                "Customer": t.customer,
                "Created At": t.created_at.strftime('%Y-%m-%d') if t.created_at else '',
                "Service Cost": 10
            })

        df = pd.DataFrame(data)
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name="Ticket Cost")
        output.seek(0)
        return output, "ticket_cost_report.xlsx"


def generate_total_service_summary_excel(start_date=None, end_date=None, customer=None):
    from app.models import toner_request, TonerCosting, spare_req, spares, Ticket
    from collections import defaultdict
    from sqlalchemy import func

    request_args = {'start_date': start_date, 'end_date': end_date, 'customer': customer}
    with current_app.test_request_context(query_string=request_args):
        from_date = request.args.get('start_date')
        to_date = request.args.get('end_date')
        customer = request.args.get('customer')

        toner_query = db.session.query(toner_request)
        if from_date:
            toner_query = toner_query.filter(toner_request.date_issued >= from_date)
        if to_date:
            toner_query = toner_query.filter(toner_request.date_issued <= to_date)
        if customer:
            toner_query = toner_query.filter(toner_request.customer_name.ilike(f"%{customer}%"))

        toner_data = []
        toner_costs = defaultdict(float)

        for t in toner_query.all():
            cost_entry = TonerCosting.query.filter_by(
                toner_model=t.toner_model,
                source=t.toner_source
            ).first()
            unit_cost = cost_entry.unit_cost if cost_entry else 0.0
            total_cost = unit_cost * t.issued_qty if t.issued_qty else 0.0
            toner_costs[t.customer_name] += total_cost

            toner_data.append({
                "Date Issued": t.date_issued.strftime('%Y-%m-%d') if t.date_issued else '',
                "Serial Number": t.serial_number,
                "Asset Code": t.asset_code,
                "Asset Description": t.asset_description,
                "Customer Code": t.cust_code,
                "Customer Name": t.customer_name,
                "Billing Company": t.billing_company,
                "Contract Code": t.contract_code,
                "Service Location": t.service_location,
                "Toner Type": t.toner_type,
                "Toner Model": t.toner_model,
                "Toner Source": t.toner_source,
                "Issued Qty": t.issued_qty,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2),
                "Dispatch Time": t.dispatch_time.strftime('%Y-%m-%d %H:%M') if t.dispatch_time else '',
                "Delivery Date": t.delivery_date.strftime('%Y-%m-%d') if t.delivery_date else '',
                "Receiver Name": t.receiver_name,
                "Requested By": t.requested_by,
                "Request Type": t.request_type,
                "FOC": t.foc
            })

        # === Spare Section ===
        spare_query = db.session.query(spare_req)
        if from_date:
            spare_query = spare_query.filter(spare_req.date >= from_date)
        if to_date:
            spare_query = spare_query.filter(spare_req.date <= to_date)
        if customer:
            spare_query = spare_query.filter(spare_req.customer_name.ilike(f"%{customer}%"))

        spare_data = []
        spare_costs = defaultdict(float)

        for s in spare_query.all():
            spare_info = spares.query.filter_by(material_nr=s.product_code).first()
            unit_cost = 0.0 if s.warehouse.upper() == 'WORKSHOP' else (spare_info.price if spare_info else 0.0)
            total_cost = unit_cost * s.qty
            spare_costs[s.customer_name] += total_cost

            spare_data.append({
                "Date": s.date.strftime('%Y-%m-%d') if s.date else '',
                "Serial Number": s.serial_number,
                "Asset Description": s.asset_Description,
                "Asset Code": s.code,
                "Technician": s.technician_name,
                "Customer Name": s.customer_name,
                "Service Location": s.service_location,
                "Region": s.region,
                "Contract": s.contract,
                "FOC No": s.foc_no,
                "Product Code": s.product_code,
                "Description": s.description,
                "Spare Type": s.spare_type,
                "Warehouse": s.warehouse,
                "Qty": s.qty,
                "Unit Cost": round(unit_cost, 2),
                "Total Cost": round(total_cost, 2)
            })

        # === Ticket Section ===
        ticket_query = db.session.query(Ticket)
        if from_date:
            ticket_query = ticket_query.filter(Ticket.created_at >= from_date)
        if to_date:
            ticket_query = ticket_query.filter(Ticket.created_at <= to_date)
        if customer:
            ticket_query = ticket_query.filter(Ticket.customer.ilike(f"%{customer}%"))

        ticket_data = []
        service_costs = defaultdict(float)

        for t in ticket_query.all():
            service_cost = 10
            service_costs[t.customer] += service_cost
            ticket_data.append({
                "Reference No": t.reference_no,
                "Title": t.title,
                "Customer": t.customer,
                "Call Type": t.call_type,
                "Service Location": t.service_location,
                "Asset Description": t.asset_Description,
                "Called By": t.called_by,
                "Created At": t.created_at.strftime('%Y-%m-%d %H:%M') if t.created_at else '',
                "Closed At": t.closed_at.strftime('%Y-%m-%d %H:%M') if t.closed_at else '',
                "Serial Number": t.serial_number,
                "Region": t.region,
                "Status": t.complete,
                "Service Cost": service_cost
            })

        # === Summary Section ===
        all_customers = set(toner_costs) | set(spare_costs) | set(service_costs)
        summary_data = []
        for cust in all_customers:
            toner = toner_costs.get(cust, 0)
            spare = spare_costs.get(cust, 0)
            service = service_costs.get(cust, 0)
            total = toner + spare + service
            summary_data.append({
                "Customer": cust,
                "Toner Cost": round(toner, 2),
                "Spare Cost": round(spare, 2),
                "Service Cost": round(service, 2),
                "Total Cost": round(total, 2)
            })

        # === Write Excel Output ===
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            pd.DataFrame(toner_data).to_excel(writer, index=False, sheet_name="Toner")
            pd.DataFrame(spare_data).to_excel(writer, index=False, sheet_name="Spare")
            pd.DataFrame(ticket_data).to_excel(writer, index=False, sheet_name="Ticket Cost")
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, index=False, sheet_name="Summary")

            # Insert chart
            workbook = writer.book
            worksheet = writer.sheets["Summary"]
            chart = workbook.add_chart({'type': 'column'})
            top5 = df_summary.nlargest(5, 'Total Cost')
            chart.add_series({
                'name': 'Top 5 Customers',
                'categories': ['Summary', 1, 0, 5, 0],
                'values': ['Summary', 1, 4, 5, 4],
            })
            chart.set_title({'name': 'Top 5 Customers by Total Cost'})
            chart.set_x_axis({'name': 'Customer'})
            chart.set_y_axis({'name': 'Cost ($)'})
            worksheet.insert_chart('G2', chart)

        output.seek(0)
        return output, "total_service_summary.xlsx"

