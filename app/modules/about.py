from flask import Blueprint, render_template

# Create a new Blueprint for About Page
about_bp = Blueprint('about', __name__, template_folder='../templates')

@about_bp.route('/about')
def about():
    return render_template('about/about.html')
