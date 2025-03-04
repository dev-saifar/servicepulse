from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required
from app.models import db, User
from werkzeug.security import generate_password_hash, check_password_hash

auth_bp = Blueprint("auth", __name__, template_folder="../templates/auth")

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            flash("Login successful!", "success")
            return redirect(url_for("dashboard.index"))
        else:
            flash("Invalid username or password", "danger")

    return render_template("auth/login.html")

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        # Check if user exists
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash("Username already exists. Choose a different one.", "warning")
            return redirect(url_for("auth.register"))

        # Create new user
        new_user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(new_user)
        db.session.commit()

        flash("Account created successfully! Please log in.", "success")
        return redirect(url_for("auth.login"))

    return render_template("auth/register.html")

@auth_bp.route('/import', methods=['GET', 'POST'])
def import_users():
    if request.method == 'POST':
        # Logic to handle import
        flash('Users imported successfully!', 'success')
        return redirect(url_for('users.user_list'))
    return render_template('users/import.html')
