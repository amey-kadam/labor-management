from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, current_app
from models import db, User, Site, Employee, Labour, LabourEntry
from sqlalchemy import func
from datetime import date

# Create blueprint
employee_bp = Blueprint('employee', __name__)

@employee_bp.route('/employee_m', methods=['GET', 'POST'])
def employee_m():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('employee_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
        
    if request.method == 'POST':
        action = request.form.get('action')
        username = request.form.get('username')
        password = request.form.get('password')
        site_id = request.form.get('site_id')
        employee_id = request.form.get('employee_id')  # For edit operations
        
        # Validation
        if not username or not site_id:
            flash('Username and site selection are required.', 'error')
            return redirect(url_for('employee.employee_m'))
        
        try:
            if action == 'add':
                # Validate password for new employee
                if not password or len(password) < 6:
                    flash('Password is required and must be at least 6 characters long.', 'error')
                    return redirect(url_for('employee.employee_m'))
                
                # Check if employee with same username already exists
                existing_employee = Employee.query.filter_by(username=username).first()
                if existing_employee:
                    flash('An employee with this username already exists.', 'error')
                    return redirect(url_for('employee.employee_m'))
                
                # Check if site exists
                site = Site.query.get(site_id)
                if not site:
                    flash('Selected site does not exist.', 'error')
                    return redirect(url_for('employee.employee_m'))
                
                # Create new employee
                new_employee = Employee(
                    username=username,
                    site_id=site_id,
                    is_active=True,
                    created_by=session['user_id']
                )
                new_employee.set_password(password)
                
                db.session.add(new_employee)
                db.session.commit()
                flash(f'Employee "{username}" has been added successfully to site "{site.name}".', 'success')
            
            elif action == 'edit' and employee_id:
                # Update existing employee
                employee = Employee.query.get_or_404(employee_id)
                
                # Check if another employee with same username exists (excluding current employee)
                existing_employee = Employee.query.filter(Employee.username == username, Employee.id != employee_id).first()
                if existing_employee:
                    flash('An employee with this username already exists.', 'error')
                    return redirect(url_for('employee.employee_m'))
                
                # Check if site exists
                site = Site.query.get(site_id)
                if not site:
                    flash('Selected site does not exist.', 'error')
                    return redirect(url_for('employee.employee_m'))
                
                employee.username = username
                employee.site_id = site_id
                
                # Update password only if provided
                if password:
                    if len(password) < 6:
                        flash('Password must be at least 6 characters long.', 'error')
                        return redirect(url_for('employee.employee_m'))
                    employee.set_password(password)
                
                db.session.commit()
                flash(f'Employee "{username}" has been updated successfully.', 'success')
            
            else:
                flash('Invalid action.', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while processing your request.', 'error')
            print(f"Error in employee management: {e}")
    
    # Get all employees with their site information
    employees = Employee.query.join(Site).order_by(Employee.created_at.desc()).all()
    # Get all sites for dropdown
    sites = Site.query.order_by(Site.name).all()
    
    return render_template('employee_m.html', employees=employees, sites=sites)

@employee_bp.route('/employee_m/delete', methods=['POST'])
def delete_employee():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('employee_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    employee_id = request.form.get('employee_id')
    
    if not employee_id:
        flash('Employee ID is required.', 'error')
        return redirect(url_for('employee.employee_m'))
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        username = employee.username  # Store username for flash message
        
        db.session.delete(employee)
        db.session.commit()
        
        flash(f'Employee "{username}" has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the employee.', 'error')
        print(f"Error deleting employee: {e}")
    
    return redirect(url_for('employee.employee_m'))

@employee_bp.route('/employee_m/toggle_status', methods=['POST'])
def toggle_employee_status():
    # Check permission
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('employee_m'):
        return jsonify({'success': False, 'message': 'Permission denied'})
    
    employee_id = request.form.get('employee_id')
    
    if not employee_id:
        return jsonify({'success': False, 'message': 'Employee ID is required'})
    
    try:
        employee = Employee.query.get_or_404(employee_id)
        employee.is_active = not employee.is_active  # Toggle status
        db.session.commit()
        
        status_text = 'active' if employee.is_active else 'inactive'
        return jsonify({
            'success': True, 
            'message': f'Employee "{employee.username}" status changed to {status_text}.',
            'new_status': employee.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while updating status.'})

@employee_bp.route('/entry', methods=['GET', 'POST'])
def entry():
    # Only employees can use this view
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    if session.get('user_type') != 'employee':
        flash('Access denied.', 'danger')
        return redirect(url_for('login'))

    employee = Employee.query.get_or_404(session['user_id'])

    # Dropdown data
    activities = [
        "Corner Bead", "Plaster", "Spot Level", "Conduit Filling",
        "Keycoat", "Mesh Fixing", "Mesh Filling", "Fiber Mesh Fixing"
    ]
    active_labours = Labour.query.filter_by(is_active=True).all()

    # ------------------------ POST  ------------------------
    if request.method == 'POST':
        action = request.form.get('action', 'add')
        
        if action == 'edit':
            # Handle edit entry
            entry_id = request.form.get('entry_id')
            if not entry_id:
                flash('Entry ID is required for editing.', 'error')
                return redirect(url_for('employee.entry'))
            
            try:
                entry = LabourEntry.query.get_or_404(entry_id)
                
                # Verify that this entry belongs to the current employee's site
                if entry.site_id != employee.site_id:
                    flash('You can only edit entries from your site.', 'error')
                    return redirect(url_for('employee.entry'))
                
                # Get labour by labour_id string
                labour_code = request.form.get('labour_id')
                labour = Labour.query.filter_by(labour_id=labour_code).first()
                if not labour:
                    flash('Labour ID not found.', 'error')
                    return redirect(url_for('employee.entry'))
                
                # Update entry fields
                entry.labour_id = labour.id
                entry.activity = request.form.get('activity')
                entry.status = request.form.get('status')
                entry.unit = request.form.get('unit')
                entry.rate_type = request.form.get('rate_type')
                entry.rate = float(request.form.get('rate') or 0)
                entry.total_hours = float(request.form.get('total_hours') or 0) or None
                entry.qty = float(request.form.get('qty') or 0) or None
                entry.amount = float(request.form.get('amount') or 0)
                
                db.session.commit()
                flash('Labour entry updated successfully!', 'success')
                
            except Exception as e:
                db.session.rollback()
                current_app.logger.exception(e)
                flash('Error updating labour entry.', 'danger')
            
            return redirect(url_for('employee.entry'))
        
        else:
            # Handle add entry (existing code)
            labour_code = request.form.get('labour_id')            
            labour = Labour.query.filter_by(labour_id=labour_code).first()

            if not labour:
                flash('Labour ID not found.', 'error')
                return redirect(url_for('employee.entry'))

            # Build new entry
            new_entry = LabourEntry(
                labour_id=labour.id,
                employee_id=employee.id,
                site_id=employee.site_id,
                activity=request.form.get('activity'),
                status=request.form.get('status'),
                unit=request.form.get('unit'),
                rate_type=request.form.get('rate_type'),
                rate=float(request.form.get('rate') or 0),
                total_hours=float(request.form.get('total_hours') or 0) or None,
                qty=float(request.form.get('qty') or 0) or None,
                amount=float(request.form.get('amount') or 0)
            )

            try:
                db.session.add(new_entry)
                db.session.commit()
                flash('Labour entry recorded successfully!', 'success')
            except Exception as e:
                db.session.rollback()
                current_app.logger.exception(e)
                flash('Error saving labour entry.', 'danger')

            return redirect(url_for('employee.entry'))        # PRG pattern

    # ------------------------ GET  ------------------------
    today = date.today()
    today_entries = (LabourEntry.query
                    .filter(
                        LabourEntry.site_id == employee.site_id,       # this site only
                        func.date(LabourEntry.timestamp) == today      # today's rows
                    )
                    .order_by(LabourEntry.timestamp.desc())
                    .all())

    return render_template(
        'entry.html',
        employee=employee,
        activities=activities,
        labours=active_labours,
        labour_entries=today_entries          
    )

@employee_bp.route('/entry/delete/<int:entry_id>', methods=['POST'])
def delete_entry(entry_id):
    # Only employees can use this view
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
        
    if session.get('user_type') != 'employee':
        return jsonify({'success': False, 'message': 'Access denied'})

    employee = Employee.query.get_or_404(session['user_id'])
    
    try:
        entry = LabourEntry.query.get_or_404(entry_id)
        
        # Verify that this entry belongs to the current employee's site
        if entry.site_id != employee.site_id:
            return jsonify({'success': False, 'message': 'You can only delete entries from your site'})
        
        # Store entry info for flash message
        labour_name = entry.labour.name
        activity = entry.activity
        
        db.session.delete(entry)
        db.session.commit()
        
        return jsonify({
            'success': True, 
            'message': f'Entry for {labour_name} ({activity}) deleted successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.exception(e)
        return jsonify({'success': False, 'message': 'Error deleting entry'})

@employee_bp.route('/api/entry/<int:entry_id>')
def get_entry(entry_id):
    # Only employees can use this API
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
        
    if session.get('user_type') != 'employee':
        return jsonify({'error': 'Access denied'}), 403

    employee = Employee.query.get_or_404(session['user_id'])
    
    try:
        entry = LabourEntry.query.get_or_404(entry_id)
        
        # Verify that this entry belongs to the current employee's site
        if entry.site_id != employee.site_id:
            return jsonify({'error': 'Access denied'}), 403
        
        return jsonify({
            'id': entry.id,
            'labour_id': entry.labour.labour_id,
            'activity': entry.activity,
            'status': entry.status,
            'unit': entry.unit,
            'rate_type': entry.rate_type,
            'rate': entry.rate,
            'total_hours': entry.total_hours,
            'qty': entry.qty,
            'amount': entry.amount
        })
        
    except Exception as e:
        current_app.logger.exception(e)
        return jsonify({'error': 'Entry not found'}), 404

# API endpoint to get employee details
@employee_bp.route('/api/employee/<int:employee_id>')
def get_employee(employee_id):
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('employee_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    employee = Employee.query.get_or_404(employee_id)
    return jsonify(employee.to_dict())

# API endpoint to get all employees
@employee_bp.route('/api/employees')
def get_all_employees():
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('employee_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    employees = Employee.query.join(Site).order_by(Employee.created_at.desc()).all()
    return jsonify([employee.to_dict() for employee in employees])