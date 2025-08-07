from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify
from models import db, User, Labour, LabourEntry
from sqlalchemy import func
from datetime import datetime
from calendar import monthrange

# Create blueprint
labour_bp = Blueprint('labour', __name__)

@labour_bp.route('/labour_m', methods=['GET', 'POST'])
def labour_m():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        labour_name = request.form.get('labour_name')
        labour_id = request.form.get('labour_id')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        db_id = request.form.get('db_id')  # Database ID for edit/delete operations
        
        # Validation
        if not labour_name or not labour_id:
            flash('Labour name and ID are required.', 'error')
            return redirect(url_for('labour.labour_m'))
        
        try:
            if action == 'add':
                # Check if labour with same ID already exists
                existing_labour = Labour.query.filter_by(labour_id=labour_id).first()
                if existing_labour:
                    flash('A labour with this ID already exists.', 'error')
                    return redirect(url_for('labour.labour_m'))
                
                # Validate password
                if not password:
                    flash('Password is required.', 'error')
                    return redirect(url_for('labour.labour_m'))
                
                if password != confirm_password:
                    flash('Passwords do not match.', 'error')
                    return redirect(url_for('labour.labour_m'))
                
                visa_cost = float(request.form.get('visa_cost') or 0)
                visa_paid = float(request.form.get('visa_paid') or 0)

                # Create new labour
                new_labour = Labour(
                    name=labour_name,
                    labour_id=labour_id,
                    is_active=True,
                    created_by=session['user_id'],
                    visa_cost=visa_cost,
                    visa_paid=visa_paid,
                    advance_payment=0.0  # Initialize advance payment to 0
                )
                new_labour.set_password(password)
                db.session.add(new_labour)
                db.session.commit()
                flash(f'Labour "{labour_name}" (ID: {labour_id}) has been added successfully.', 'success')
            
            elif action == 'edit' and db_id:
                # Update existing labour
                labour = Labour.query.get_or_404(db_id)
                
                # Check if another labour with same ID exists (excluding current labour)
                existing_labour = Labour.query.filter(Labour.labour_id == labour_id, Labour.id != db_id).first()
                if existing_labour:
                    flash('A labour with this ID already exists.', 'error')
                    return redirect(url_for('labour.labour_m'))
                
                labour.name = labour_name
                labour.labour_id = labour_id
                
                # Update password if provided
                if password:
                    if password != confirm_password:
                        flash('Passwords do not match.', 'error')
                        return redirect(url_for('labour.labour_m'))
                    labour.set_password(password)
                
                db.session.commit()
                flash(f'Labour "{labour_name}" has been updated successfully.', 'success')
            
            else:
                flash('Invalid action.', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash('An error occurred while processing your request.', 'error')
            print(f"Error in labour management: {e}")
    
    # Get all labour records for display
    labour_records = Labour.query.order_by(Labour.created_at.desc()).all()
    return render_template('labour_m.html', labour_records=labour_records)

@labour_bp.route('/wage_card', methods=['GET', 'POST'])
def wage_card():
    """Wage card page for labour users"""
    # Check if labour is logged in
    if 'user_id' not in session or session.get('user_type') != 'labour':
        return redirect(url_for('login'))
    
    # Get labour record
    labour = Labour.query.get(session['user_id'])
    if not labour or not labour.is_active:
        flash('Labour account not found or inactive.', 'danger')
        return redirect(url_for('logout'))

    # Get selected month from query parameter or default to current month
    selected_month = request.args.get('month')
    if selected_month:
        try:
            selected_date = datetime.strptime(selected_month, '%Y-%m')
        except ValueError:
            selected_date = datetime.now()
    else:
        selected_date = datetime.now()

    # Calculate attendance for the selected month
    year = selected_date.year
    month = selected_date.month
    
    # Get first and last day of the month
    _, days_in_month = monthrange(year, month)
    
    # Query labour entries for this labour in the selected month
    month_entries = LabourEntry.query.filter(
        LabourEntry.labour_id == labour.id,
        func.extract('year', LabourEntry.timestamp) == year,
        func.extract('month', LabourEntry.timestamp) == month
    ).all()

    # Calculate total money from work entries (sum of all entries)
    total_work_amount = sum(entry.amount or 0 for entry in month_entries)

    # Group entries by date and status for attendance calculation
    daily_status = {}  # {day: status}
    
    for entry in month_entries:
        day = entry.timestamp.day
        
        # If we already have an entry for this day, prioritize 'present' over 'absent'
        if day in daily_status:
            if entry.status.lower() == 'present' or daily_status[day].lower() == 'present':
                daily_status[day] = 'present'
            # If both are absent, keep it as absent
        else:
            daily_status[day] = entry.status.lower()
    
    # Count present and absent days based on unique days
    present_days_count = sum(1 for status in daily_status.values() if status == 'present')
    explicitly_absent_days = sum(1 for status in daily_status.values() if status == 'absent')
    
    # For current month, only count up to today's date
    # For past months, count all days in the month
    # For future months, count no days as they haven't occurred yet
    today = datetime.now().date()
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    if year == current_year and month == current_month:
        # Current month - only count up to today
        max_day_to_count = min(today.day, days_in_month)
    elif year < current_year or (year == current_year and month < current_month):
        # Past month - count all days
        max_day_to_count = days_in_month
    else:
        # Future month - count no days
        max_day_to_count = 0
    
    # Calculate attendance
    present_days = present_days_count
    # Days without any entries (neither present nor absent)
    days_without_entries = max_day_to_count - len(daily_status)
    # Total absent days = explicitly marked absent + days with no entries
    absent_days = days_without_entries + explicitly_absent_days
    total_countable_days = max_day_to_count
    
    # Calculate penalty for excessive absences
    PENALTY_PER_DAY = 25.0  # AED per day
    ALLOWED_ABSENT_DAYS = 2  # Free absent days per month
    INSURANCE_AMOUNT = 30.0  # AED per month (fixed deduction)
    
    penalty_days = max(0, absent_days - ALLOWED_ABSENT_DAYS)
    total_penalty = penalty_days * PENALTY_PER_DAY
    
    # Calculate final payable amount after penalty, insurance, and advance
    advance_amount = labour.advance_payment or 0.0  # Handle None case
    total_money_payable = total_work_amount - total_penalty - INSURANCE_AMOUNT - advance_amount
    
    # Calculate attendance stats
    attendance_stats = {
        'month_year': selected_date.strftime('%B %Y'),
        'days_in_month': days_in_month,
        'total_countable_days': total_countable_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'days_with_entries': len(daily_status),  # Unique days with entries
        'total_entries': len(month_entries),     # Total number of entries
        'explicitly_absent': explicitly_absent_days,
        'days_without_entries': days_without_entries,
        'present_percentage': round((present_days / total_countable_days) * 100, 1) if total_countable_days > 0 else 0,
        'absent_percentage': round((absent_days / total_countable_days) * 100, 1) if total_countable_days > 0 else 0,
        'is_current_month': year == current_year and month == current_month,
        'is_future_month': year > current_year or (year == current_year and month > current_month),
        # Penalty-related stats
        'penalty_days': penalty_days,
        'total_penalty': total_penalty,
        'penalty_per_day': PENALTY_PER_DAY,
        'allowed_absent_days': ALLOWED_ABSENT_DAYS,
        'total_work_amount': total_work_amount,
        'insurance_amount': INSURANCE_AMOUNT
    }

    return render_template("wage_card.html", 
                labour=labour, 
                attendance_stats=attendance_stats,
                selected_month=selected_date.strftime('%Y-%m'),
                total_money_payable=total_money_payable)

@labour_bp.route('/labour/<int:labour_id>', methods=['GET', 'POST'])
def labour_detail(labour_id):
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    labour = Labour.query.get_or_404(labour_id)

    # Get selected month from query parameter or default to current month
    selected_month = request.args.get('month')
    if selected_month:
        try:
            selected_date = datetime.strptime(selected_month, '%Y-%m')
        except ValueError:
            selected_date = datetime.now()
    else:
        selected_date = datetime.now()

    # Calculate attendance for the selected month
    year = selected_date.year
    month = selected_date.month
    
    # Get first and last day of the month
    _, days_in_month = monthrange(year, month)
    
    # Query labour entries for this labour in the selected month
    month_entries = LabourEntry.query.filter(
        LabourEntry.labour_id == labour_id,
        func.extract('year', LabourEntry.timestamp) == year,
        func.extract('month', LabourEntry.timestamp) == month
    ).all()

    # Calculate total money from work entries (sum of all entries)
    total_work_amount = sum(entry.amount or 0 for entry in month_entries)

    # Group entries by date and status for attendance calculation
    daily_status = {}  # {day: status}
    
    for entry in month_entries:
        day = entry.timestamp.day
        
        # If we already have an entry for this day, prioritize 'present' over 'absent'
        if day in daily_status:
            if entry.status.lower() == 'present' or daily_status[day].lower() == 'present':
                daily_status[day] = 'present'
            # If both are absent, keep it as absent
        else:
            daily_status[day] = entry.status.lower()
    
    # Count present and absent days based on unique days
    present_days_count = sum(1 for status in daily_status.values() if status == 'present')
    explicitly_absent_days = sum(1 for status in daily_status.values() if status == 'absent')
    
    # For current month, only count up to today's date
    # For past months, count all days in the month
    # For future months, count no days as they haven't occurred yet
    today = datetime.now().date()
    current_month = datetime.now().month
    current_year = datetime.now().year
    
    if year == current_year and month == current_month:
        # Current month - only count up to today
        max_day_to_count = min(today.day, days_in_month)
    elif year < current_year or (year == current_year and month < current_month):
        # Past month - count all days
        max_day_to_count = days_in_month
    else:
        # Future month - count no days
        max_day_to_count = 0
    
    # Calculate attendance
    present_days = present_days_count
    # Days without any entries (neither present nor absent)
    days_without_entries = max_day_to_count - len(daily_status)
    # Total absent days = explicitly marked absent + days with no entries
    absent_days = days_without_entries + explicitly_absent_days
    total_countable_days = max_day_to_count
    
    # Calculate penalty for excessive absences
    PENALTY_PER_DAY = 25.0  # AED per day
    ALLOWED_ABSENT_DAYS = 2  # Free absent days per month
    INSURANCE_AMOUNT = 30.0  # AED per month (fixed deduction)
    
    penalty_days = max(0, absent_days - ALLOWED_ABSENT_DAYS)
    total_penalty = penalty_days * PENALTY_PER_DAY
    
    # Calculate final payable amount after penalty, insurance, and advance
    advance_amount = labour.advance_payment or 0.0  # Handle None case
    total_money_payable = total_work_amount - total_penalty - INSURANCE_AMOUNT - advance_amount
    
    # Calculate attendance stats
    attendance_stats = {
        'month_year': selected_date.strftime('%B %Y'),
        'days_in_month': days_in_month,
        'total_countable_days': total_countable_days,
        'present_days': present_days,
        'absent_days': absent_days,
        'days_with_entries': len(daily_status),  # Unique days with entries
        'total_entries': len(month_entries),     # Total number of entries
        'explicitly_absent': explicitly_absent_days,
        'days_without_entries': days_without_entries,
        'present_percentage': round((present_days / total_countable_days) * 100, 1) if total_countable_days > 0 else 0,
        'absent_percentage': round((absent_days / total_countable_days) * 100, 1) if total_countable_days > 0 else 0,
        'is_current_month': year == current_year and month == current_month,
        'is_future_month': year > current_year or (year == current_year and month > current_month),
        # Penalty-related stats
        'penalty_days': penalty_days,
        'total_penalty': total_penalty,
        'penalty_per_day': PENALTY_PER_DAY,
        'allowed_absent_days': ALLOWED_ABSENT_DAYS,
        'total_work_amount': total_work_amount,
        'insurance_amount': INSURANCE_AMOUNT
    }

    if request.method == 'POST':
        # Handle visa payment update
        if 'additional_payment' in request.form:
            try:
                additional_payment = float(request.form.get('additional_payment') or 0)
                if additional_payment < 0:
                    flash("Amount cannot be negative", "danger")
                    return redirect(url_for('labour.labour_detail', labour_id=labour_id))

                labour.visa_paid += additional_payment
                db.session.commit()
                flash("Payment updated successfully", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error updating payment", "danger")
                print("Visa payment error:", e)

            return redirect(url_for('labour.labour_detail', labour_id=labour_id))
        
        # Handle advance payment update
        elif 'advance_amount' in request.form:
            try:
                advance_amount = float(request.form.get('advance_amount') or 0)
                if advance_amount < 0:
                    flash("Advance amount cannot be negative", "danger")
                    return redirect(url_for('labour.labour_detail', labour_id=labour_id))

                labour.advance_payment += advance_amount
                db.session.commit()
                flash(f"Advance payment of {advance_amount} AED added successfully", "success")
            except Exception as e:
                db.session.rollback()
                flash("Error updating advance payment", "danger")
                print("Advance payment error:", e)

    return render_template("labour_detail.html", 
        labour=labour, 
        attendance_stats=attendance_stats,
        selected_month=selected_date.strftime('%Y-%m'),
        total_money_payable=total_money_payable)


@labour_bp.route('/labour_m/delete', methods=['POST'])
def delete_labour():
    # Check permission
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        flash('You do not have permission to access this page.', 'danger')
        return redirect(url_for('admin.admin_dashboard'))
    
    labour_db_id = request.form.get('labour_id')
    
    if not labour_db_id:
        flash('Labour ID is required.', 'error')
        return redirect(url_for('labour.labour_m'))
    
    try:
        labour = Labour.query.get_or_404(labour_db_id)
        labour_name = labour.name  # Store name for flash message
        labour_id = labour.labour_id
        
        db.session.delete(labour)
        db.session.commit()
        
        flash(f'Labour "{labour_name}" (ID: {labour_id}) has been deleted successfully.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash('An error occurred while deleting the labour.', 'error')
        print(f"Error deleting labour: {e}")
    
    return redirect(url_for('labour.labour_m'))

@labour_bp.route('/labour_m/toggle_status', methods=['POST'])
def toggle_labour_status():
    # Check permission
    if 'user_id' not in session:
        return jsonify({'success': False, 'message': 'Not logged in'})
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        return jsonify({'success': False, 'message': 'Permission denied'})
    
    labour_db_id = request.form.get('labour_id')
    
    if not labour_db_id:
        return jsonify({'success': False, 'message': 'Labour ID is required'})
    
    try:
        labour = Labour.query.get_or_404(labour_db_id)
        labour.is_active = not labour.is_active  # Toggle status
        db.session.commit()
        
        status_text = 'active' if labour.is_active else 'inactive'
        return jsonify({
            'success': True, 
            'message': f'Labour "{labour.name}" status changed to {status_text}.',
            'new_status': labour.is_active
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': 'An error occurred while updating status.'})

# API endpoint to get labour details
@labour_bp.route('/api/labour/<int:labour_id>')
def get_labour(labour_id):
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    labour = Labour.query.get_or_404(labour_id)
    return jsonify(labour.to_dict())

# API endpoint to get all labour records
@labour_bp.route('/api/labour')
def get_all_labour():
    # Check permission
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401
    
    user = User.query.get(session['user_id'])
    if not user or not user.has_permission('labour_m'):
        return jsonify({'error': 'Permission denied'}), 403
    
    labour_records = Labour.query.order_by(Labour.created_at.desc()).all()
    return jsonify([labour.to_dict() for labour in labour_records])

@labour_bp.route('/api/labours', methods=['GET'])
def api_get_labours_for_employee():
    if 'user_id' not in session:
        return jsonify({'error': 'Not logged in'}), 401

    if session.get('user_type') != 'employee':
        return jsonify({'error': 'Access denied'}), 403

    # Only return active labours
    labours = Labour.query.filter_by(is_active=True).all()
    return jsonify([labour.to_dict() for labour in labours])