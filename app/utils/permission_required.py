from functools import wraps
from flask import abort
from flask import abort, flash, redirect, url_for
from flask_login import current_user

def permission_required(permission):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if not getattr(current_user, permission, False):
                flash("⚠️ You do not have permission to access this page.", "warning")
                abort(403)

            return f(*args, **kwargs)
        return wrapper
    return decorator
