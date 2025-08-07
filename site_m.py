from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Site

# Create blueprint
site_bp = Blueprint('site', __name__)

@site_bp.route('/site_m', methods=['GET', 'POST'])
def site_m():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('site_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        site_name = request.form.get('site_name')
        location = request.form.get('location')
        site_id = request.form.get('site_id')
        
        # Validation
        if not site_name or not location:
            flash('Site name and location are required.', 'error')
            return redirect(url_for('site.site_m'))
        
        try:
            if action == 'add':
                # Check if site with same name already exists
                existing_site = Site.query.filter_by(name=site_name).first()
                if existing_site:
                    flash('A site with this name already exists.', 'error')
                    return redirect(url_for('site.site_m'))
                
                # Create new site
                new_site = Site(
                    name=site_name,
                    location=location,
                    created_by=session['user_id']
                )
                db.session.add(new_site)
                db.session.commit()
                flash(f'Site "{site_name}" has been added successfully.', 'success')
            
            elif action == 'edit' and site_id:
                # Update existing site
                site = Site.query.get_or_404(site_id)
                
                # Check if another site with same name exists (excluding current site)
                existing_site = Site.query.filter(Site.name == site_name, Site.id != site_id).first()
                if existing_site:
                    flash('A site with this name already exists.', 'error')
                    return redirect(url_for('site.site_m'))
                
                site.name = site_name
                site.location = location
                db.session.commit()
                flash(f'Site "{site_name}" has been updated successfully.', 'success')
            
            else:
                flash('Invalid action.', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while processing your request.', 'error')
            print(f"Error in site management: {e}")
    
    # Get all sites for display
    sites = Site.query.order_by(Site.created_at.desc()).all()
    return render_template('site_m.html', sites=sites)

@site_bp.route('/site_m/delete', methods=['POST'])
def delete_site():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('site_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    site_id = request.form.get('site_id')
    
    if not site_id:
        flash('Site ID is required.', 'error')
        return redirect(url_for('site.site_m'))
    
    try:
        site = Site.query.get_or_404(site_id)
        site_name = site.name  # Store name for flash message
        
        # Check if site has employees
        if site.employees:
            flash(f'Cannot delete site "{site_name}" because it has employees assigned to it.', 'error')
            return redirect(url_for('site.site_m'))
        
        db.session.delete(site)
        db.session.commit()
        
        flash(f'Site "{site_name}" has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the site.', 'error')
        print(f"Error deleting site: {e}")
    
    return redirect(url_for('site.site_m'))

# API endpoint to get site details (useful for AJAX operations)
@site_bp.route('/api/site/<int:site_id>')
def get_site(site_id):
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('site_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    site = Site.query.get_or_404(site_id)
    return jsonify(site.to_dict())

# API endpoint to get all sites
@site_bp.route('/api/sites')
def get_all_sites():
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('site_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    sites = Site.query.order_by(Site.created_at.desc()).all()
    return jsonify([site.to_dict() for site in sites])