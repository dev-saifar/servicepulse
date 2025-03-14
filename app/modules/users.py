from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models import User
from flask_login import login_required

users_bp = Blueprint('users', __name__, template_folder='../templates/users')

@users_bp.route('/')
@login_required
def user_list():
    """Show all users"""
    users = User.query.all()
    return render_template('users/index.html', users=users)

@users_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_user():
    """Add a new user via UI"""
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

        new_user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        flash("User added successfully!", "success")
        return redirect(url_for('users.user_list'))

    return render_template('users/add_user.html')

@users_bp.route('/delete/<int:user_id>', methods=['POST'])
@login_required
def delete_user(user_id):
    """Delete a user"""
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    flash("User deleted successfully!", "success")
    return redirect(url_for('users.user_list'))

from werkzeug.security import generate_password_hash

@users_bp.route('/edit/<int:user_id>', methods=['GET', 'POST'])
@login_required
def edit_user(user_id):
    """Edit an existing user, including an optional password change"""
    user = User.query.get_or_404(user_id)

    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.role = request.form.get('role')

        new_password = request.form.get('new_password')
        if new_password:  # Update only if a new password is provided
            user.password_hash = generate_password_hash(new_password)

        db.session.commit()
        flash("User details updated successfully!", "success")
        return redirect(url_for('users.user_list'))

    return render_template('users/edit_user.html', user=user)
