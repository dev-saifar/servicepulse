from flask import Blueprint

inventory_bp = Blueprint("inventory", __name__, url_prefix="/inventory")

# Optional: HTTP routes can come later
try:
    from . import routes  # noqa: F401
except Exception:
    pass
