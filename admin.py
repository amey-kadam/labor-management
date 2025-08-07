from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from models import db, User, Site, Labour, Employee, LabourEntry

# Create blueprint
admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/admin')
def admin_dashboard():
    # Check if user is admin
    if session.get('user_type') != 'admin':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))
        
    user = User.query.get(session['user_id'])
    
    # Calculate dynamic statistics
    stats = {
        'total_labour': Labour.query.count(),  # Total labour records
        'total_employees': Employee.query.count(),  # Total employee records
        'active_sites': Site.query.count()  # Total sites (no is_active filter needed)
    }
    
    return render_template('admin.html', user=user, stats=stats)

@admin_bp.route('/admin_m', methods=['GET', 'POST'])
def admin_m():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('admin_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        permissions = request.form.getlist('perms')  # Get list of selected permissions
        
        # Validation
        if not email or not password:
            flash('Email and password are required.', 'danger')
        elif len(password) < 6:
            flash('Password must be at least 6 characters long.', 'danger')
        else:
            # Check if user already exists
            existing_user = User.query.filter_by(email=email).first()
            if existing_user:
                flash('An admin with this email already exists.', 'danger')
            else:
                # Create new admin user
                try:
                    # Generate username from email (you can modify this logic)
                    username = email.split('@')[0]
                    counter = 1
                    original_username = username
                    while User.query.filter_by(username=username).first():
                        username = f"{original_username}{counter}"
                        counter += 1
                    
                    new_admin = User(
                        username=username,
                        email=email,
                        is_super_admin=False
                    )
                    new_admin.set_password(password)
                    new_admin.set_permissions(permissions)
                    
                    db.session.add(new_admin)
                    db.session.commit()
                    
                    flash(f'Admin user "{email}" created successfully with username "{username}".', 'success')
                    return redirect(url_for('admin.admin_m'))
                    
                except Exception as e:
                    db.session.rollback()
                    flash('An error occurred while creating the admin user.', 'danger')
                    print(f"Error creating admin: {e}")  # For debugging
    
    # Get all admin users (both super admin and regular admins)
    admins = User.query.all()  # You might want to exclude the current user or filter differently
    
    return render_template('admin_m.html', admins=admins)

@admin_bp.route('/admin_m/edit/<int:admin_id>', methods=['GET', 'POST'])
def edit_admin(admin_id):
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('admin_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    admin_to_edit = User.query.get_or_404(admin_id)
    current_user = User.query.get(session['user_id'])
    
    # Prevent editing super admin or self-editing restrictions
    if admin_to_edit.is_super_admin:
        flash('Cannot edit super admin user.', 'danger')
        return redirect(url_for('admin.admin_m'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        permissions = request.form.getlist('perms')
        
        # Validation
        if not email:
            flash('Email is required.', 'danger')
        else:
            try:
                # Check if email is taken by another user
                existing_user = User.query.filter(User.email == email, User.id != admin_id).first()
                if existing_user:
                    flash('Email is already taken by another user.', 'danger')
                else:
                    # Update user details
                    admin_to_edit.email = email
                    
                    # Update password only if provided
                    if password and len(password) >= 6:
                        admin_to_edit.set_password(password)
                    elif password and len(password) < 6:
                        flash('Password must be at least 6 characters long.', 'danger')
                        return render_template('edit_admin.html', admin=admin_to_edit)
                    
                    # Update permissions
                    admin_to_edit.set_permissions(permissions)
                    
                    db.session.commit()
                    flash(f'Admin user "{email}" updated successfully.', 'success')
                    return redirect(url_for('admin.admin_m'))
                    
            except Exception as e:
                db.session.rollback()
                flash('An error occurred while updating the admin user.', 'danger')
                print(f"Error updating admin: {e}")
    
    return render_template('edit_admin.html', admin=admin_to_edit)

@admin_bp.route('/admin_m/delete/<int:admin_id>', methods=['POST'])
def delete_admin(admin_id):
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('admin_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    admin_to_delete = User.query.get_or_404(admin_id)
    current_user = User.query.get(session['user_id'])
    
    # Prevent deleting super admin or self
    if admin_to_delete.is_super_admin:
        flash('Cannot delete super admin user.', 'danger')
        return redirect(url_for('admin.admin_m'))
    
    if admin_to_delete.id == current_user.id:
        flash('Cannot delete your own account.', 'danger')
        return redirect(url_for('admin.admin_m'))
    
    try:
        db.session.delete(admin_to_delete)
        db.session.commit()
        flash(f'Admin user "{admin_to_delete.email or admin_to_delete.username}" deleted successfully.', 'success')
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the admin user.', 'danger')
        print(f"Error deleting admin: {e}")
    
    return redirect(url_for('admin.admin_m'))

# API endpoint to get current user permissions (useful for frontend)
@admin_bp.route('/api/user-permissions')
def get_user_permissions():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    permissions = {
        'site_m': user.has_permission('site_m'),
        'employee_m': user.has_permission('employee_m'),
        'labour_m': user.has_permission('labour_m'),
        'admin_m': user.has_permission('admin_m'),
        'is_super_admin': user.is_super_admin
    }
    return jsonify(permissions)

# Route to list all admins (optional - for admin management page)
@admin_bp.route('/admin_m/list')
def list_admins():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('admin_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    admins = User.query.filter_by(is_super_admin=False).all()
    return render_template('admin_list.html', admins=admins)