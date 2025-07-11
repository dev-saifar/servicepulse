from flask import Blueprint, render_template, request, redirect, url_for, flash
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User
from flask_login import login_required
from app.utils.permission_required import permission_required
from app.modules.test_smtp import send_email

users_bp = Blueprint('users', __name__, template_folder='../templates/users')

@users_bp.route('/')
@login_required
@permission_required('can_add_user')
def user_list():
    users = User.query.all()
    return render_template('users/index.html', users=users)

@users_bp.route('/add', methods=['GET', 'POST'])
@login_required
@permission_required('can_add_user')
def add_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not username or not email or not password:
            flash("All fields are required!", "error")
            return redirect(url_for('users.add_user'))

        if User.query.filter_by(email=email).first():
            flash("Email already registered!", "error")
            return redirect(url_for('users.add_user'))

        plain_password = password  # Keep plain password to send email
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password))

        permission_fields = [
            'can_add_user', 'can_edit_user', 'can_delete_user', 'can_assign_roles',
            'can_view_tickets', 'can_create_tickets', 'can_edit_tickets', 'can_close_tickets', 'can_assign_tickets',
            'can_view_technicians', 'can_add_technicians', 'can_edit_technicians',
            'can_view_customers', 'can_manage_customers', 'can_delete_customers',
            'can_view_assets', 'can_add_assets', 'can_edit_assets', 'can_delete_assets',
            'can_view_contracts', 'can_add_contracts', 'can_edit_contracts', 'can_delete_contracts',
            'can_request_toner', 'can_edit_toner_requests', 'can_view_toner_dashboard', 'can_delete_toner_request',
            'can_request_spares', 'can_view_spare_dashboard', 'can_delete_spare_request',
            'can_view_reports', 'can_export_data', 'can_view_financials', 'can_export_financials',
            'can_schedule_pm', 'can_view_pm', 'can_edit_pm',
            'can_access_settings', 'can_upload_documents', 'can_view_audit_logs',
            'can_create_gatepass', 'can_view_gatepass', 'can_edit_gatepass', 'can_export_gatepass'
        ]

        for field in permission_fields:
            setattr(new_user, field, bool(request.form.get(field)))

        db.session.add(new_user)
        db.session.commit()

        if new_user.email:
            # Prepare permissions list
            permissions_list = []
            permission_labels = {
                'can_view_tickets': "View Tickets",
                'can_create_tickets': "Create Tickets",
                'can_edit_tickets': "Edit Tickets",
                'can_close_tickets': "Close Tickets",
                'can_assign_tickets': "Assign Tickets",
                'can_view_technicians': "View Technicians",
                'can_add_technicians': "Add Technicians",
                'can_edit_technicians': "Edit Technicians",
                'can_view_assets': "View Assets",
                'can_add_assets': "Add Assets",
                'can_edit_assets': "Edit Assets",
                'can_delete_assets': "Delete Assets",
                'can_view_customers': "View Customers",
                'can_manage_customers': "Manage Customers",
                'can_delete_customers': "Delete Customers",
                'can_view_contracts': "View Contracts",
                'can_add_contracts': "Add Contracts",
                'can_edit_contracts': "Edit Contracts",
                'can_delete_contracts': "Delete Contracts",
                'can_request_toner': "Request Toner",
                'can_edit_toner_requests': "Edit Toner Requests",
                'can_view_toner_dashboard': "View Toner Dashboard",
                'can_delete_toner_request': "Delete Toner Request",
                'can_request_spares': "Request Spares",
                'can_view_spare_dashboard': "View Spare Dashboard",
                'can_delete_spare_request': "Delete Spare Request",
                'can_view_reports': "View Reports",
                'can_export_data': "Export Data",
                'can_view_financials': "View Financials",
                'can_export_financials': "Export Financials",
                'can_view_pm': "View PM",
                'can_edit_pm': "Edit PM",
                'can_schedule_pm': "Schedule PM",
                'can_view_pm_dashboard': "View PM Dashboard",
                'can_access_settings': "Access Settings",
                'can_upload_documents': "Upload Documents",
                'can_view_audit_logs': "View Audit Logs",
                'can_view_gatepass_tasks': "View Gate Pass Tasks",
'can_add_gatepass': "Add Gate Pass",
'can_edit_gatepass': "Edit Gate Pass",
'can_export_gatepass': "Export Gate Pass",

            }

            for field, label in permission_labels.items():
                if getattr(new_user, field, False):
                    permissions_list.append(label)

            # Prepare email
            email_body = render_template('email_templates/new_user_email.html',
                                         username=new_user.username,
                                         password=plain_password,
                                         rights=permissions_list)

            try:
                send_email(
                    to_email=new_user.email,
                    subject="🎉 Welcome to ServicePulse - Your Login Details",
                    html=email_body  # ✅ Matches what `send_email()` expects
                )

                flash('✅ User created and welcome email sent!', 'success')
            except Exception as e:
                flash(f'⚠️ User created, but email sending failed: {str(e)}', 'warning')

        return redirect(url_for('users.user_list'))

    return render_template('users/add_user.html')

@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
@permission_required('can_edit_user')
def edit_user(user_id):
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')

        new_password = request.form.get('new_password')
        if new_password:
            user.password_hash = generate_password_hash(new_password)

        permission_fields = [
            'can_add_user', 'can_edit_user', 'can_delete_user', 'can_assign_roles',
            'can_view_tickets', 'can_create_tickets', 'can_edit_tickets', 'can_close_tickets', 'can_assign_tickets',
            'can_view_technicians', 'can_add_technicians', 'can_edit_technicians',
            'can_view_customers', 'can_manage_customers', 'can_delete_customers',
            'can_view_assets', 'can_add_assets', 'can_edit_assets', 'can_delete_assets',
            'can_view_contracts', 'can_add_contracts', 'can_edit_contracts', 'can_delete_contracts',
            'can_request_toner', 'can_edit_toner_requests', 'can_view_toner_dashboard', 'can_delete_toner_request',
            'can_request_spares', 'can_view_spare_dashboard', 'can_delete_spare_request',
            'can_view_reports', 'can_export_data', 'can_view_financials', 'can_export_financials',
            'can_schedule_pm', 'can_view_pm', 'can_edit_pm',
            'can_access_settings', 'can_upload_documents', 'can_view_audit_logs',
            'can_create_gatepass', 'can_view_gatepass', 'can_edit_gatepass', 'can_export_gatepass'
        ]

        for field in permission_fields:
            setattr(user, field, bool(request.form.get(field)))

        db.session.commit()
        flash("✅ User updated successfully!", "success")
        return redirect(url_for('users.user_list'))

    return render_template('users/edit_user.html', user=user)

@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
@permission_required('can_delete_user')
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("✅ User deleted successfully!", "success")
    return redirect(url_for('users.user_list'))
@users_bp.route('/reset_own_password', methods=['POST'])
@login_required
def reset_own_password():
    from flask_login import current_user
    from werkzeug.security import generate_password_hash

    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")

    if not new_password or new_password != confirm_password:
        flash("❌ Passwords do not match or are empty.", "danger")
        return redirect(request.referrer)

    user = User.query.get(current_user.id)
    user.password_hash = generate_password_hash(new_password)
    db.session.commit()
    flash("✅ Password updated successfully!", "success")
    return redirect(request.referrer)
