from flask import Blueprint, render_template, session, redirect, url_for, request, jsonify, make_response
from models import User, Labour, Employee, Site, LabourEntry, db
from sqlalchemy import func, and_, or_, case
from datetime import datetime, timedelta
import calendar
from collections import defaultdict

# Create blueprint
report_bp = Blueprint('report', __name__)

def get_date_range_from_request():
    """Extract and validate date range from request parameters"""
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # If no dates provided, default to current month
    if not date_from or not date_to:
        today = datetime.now()
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')
    
    try:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
        
        # Ensure date_to includes the entire day
        date_to_obj = date_to_obj.replace(hour=23, minute=59, second=59)
        
        return date_from_obj, date_to_obj, date_from, date_to
    except ValueError:
        # If invalid dates, default to current month
        today = datetime.now()
        date_from = today.replace(day=1).strftime('%Y-%m-%d')
        date_to = today.strftime('%Y-%m-%d')
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        
        return date_from_obj, date_to_obj, date_from, date_to

def calculate_previous_period_dates(date_from, date_to):
    """Calculate the previous period dates for comparison"""
    period_length = (date_to - date_from).days
    prev_date_to = date_from - timedelta(days=1)
    prev_date_from = prev_date_to - timedelta(days=period_length)
    
    return prev_date_from, prev_date_to

def get_labour_statistics(date_from, date_to, site_filter=None):
    """Get comprehensive labour statistics for the given period"""
    
    # Base query
    query = db.session.query(LabourEntry).filter(
        LabourEntry.timestamp.between(date_from, date_to)
    )
    
    # Apply site filter if provided
    if site_filter and site_filter != 'all':
        query = query.filter(LabourEntry.site_id == site_filter)
    
    entries = query.all()
    
    # Calculate statistics
    total_hours = sum(entry.total_hours or 0 for entry in entries)
    total_amount = sum(entry.amount or 0 for entry in entries)
    
    # Count present vs absent
    present_count = sum(1 for entry in entries if entry.status.lower() == 'present')
    absent_count = sum(1 for entry in entries if entry.status.lower() == 'absent')
    total_entries = len(entries)
    
    # Count unique labourers worked
    unique_labourers = len(set(entry.labour_id for entry in entries))
    
    # Count active sites
    active_sites = len(set(entry.site_id for entry in entries))
    
    # Calculate average daily hours
    days_in_period = (date_to - date_from).days + 1
    avg_daily_hours = total_hours / days_in_period if days_in_period > 0 else 0
    
    # Calculate productivity metrics
    productivity_rate = (present_count / total_entries * 100) if total_entries > 0 else 0
    
    return {
        'total_hours': round(total_hours, 2),
        'total_amount': round(total_amount, 2),
        'present_count': present_count,
        'absent_count': absent_count,
        'total_entries': total_entries,
        'unique_labourers': unique_labourers,
        'active_sites': active_sites,
        'avg_daily_hours': round(avg_daily_hours, 2),
        'productivity_rate': round(productivity_rate, 2),
        'attendance_rate': round((present_count / total_entries * 100) if total_entries > 0 else 0, 2)
    }

def get_site_wise_statistics(date_from, date_to):
    """Get site-wise breakdown of statistics"""
    
    # Query all entries in the date range
    entries = db.session.query(LabourEntry).filter(
        LabourEntry.timestamp.between(date_from, date_to)
    ).all()
    
    # Group by site
    site_stats = defaultdict(lambda: {
        'total_hours': 0,
        'total_amount': 0,
        'present_count': 0,
        'absent_count': 0,
        'unique_labourers': set(),
        'site_name': '',
        'site_location': ''
    })
    
    for entry in entries:
        site_id = entry.site_id
        site_stats[site_id]['total_hours'] += entry.total_hours or 0
        site_stats[site_id]['total_amount'] += entry.amount or 0
        site_stats[site_id]['unique_labourers'].add(entry.labour_id)
        site_stats[site_id]['site_name'] = entry.site.name
        site_stats[site_id]['site_location'] = entry.site.location
        
        if entry.status.lower() == 'present':
            site_stats[site_id]['present_count'] += 1
        else:
            site_stats[site_id]['absent_count'] += 1
    
    # Convert to list and calculate additional metrics
    result = []
    for site_id, stats in site_stats.items():
        total_entries = stats['present_count'] + stats['absent_count']
        attendance_rate = (stats['present_count'] / total_entries * 100) if total_entries > 0 else 0
        
        result.append({
            'site_id': site_id,
            'site_name': stats['site_name'],
            'site_location': stats['site_location'],
            'total_hours': round(stats['total_hours'], 2),
            'total_amount': round(stats['total_amount'], 2),
            'unique_labourers': len(stats['unique_labourers']),
            'total_entries': total_entries,
            'attendance_rate': round(attendance_rate, 2)
        })
    
    return sorted(result, key=lambda x: x['total_hours'], reverse=True)

def get_labour_performance_data(date_from, date_to, limit=10):
    """Get top performing labourers"""
    
    # Query and group by labour
    performance_data = db.session.query(
        LabourEntry.labour_id,
        Labour.name,
        Labour.labour_id.label('labour_code'),
        func.sum(LabourEntry.total_hours).label('total_hours'),
        func.sum(LabourEntry.amount).label('total_amount'),
        func.count(LabourEntry.id).label('total_entries'),
        func.sum(case((LabourEntry.status == 'Present', 1), else_=0)).label('present_count')
    ).join(Labour, LabourEntry.labour_id == Labour.id).filter(
        LabourEntry.timestamp.between(date_from, date_to)
    ).group_by(LabourEntry.labour_id, Labour.name, Labour.labour_id).order_by(
        func.sum(LabourEntry.total_hours).desc()
    ).limit(limit).all()
    
    result = []
    for data in performance_data:
        attendance_rate = (data.present_count / data.total_entries * 100) if data.total_entries > 0 else 0
        
        result.append({
            'labour_id': data.labour_id,
            'name': data.name,
            'labour_code': data.labour_code,
            'total_hours': round(data.total_hours or 0, 2),
            'total_amount': round(data.total_amount or 0, 2),
            'total_entries': data.total_entries,
            'attendance_rate': round(attendance_rate, 2)
        })
    
    return result

def generate_report_metrics(current_stats, previous_stats):
    """Generate comparison metrics between current and previous periods"""
    
    def calculate_change(current, previous):
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 1)
    
    def get_status(change, metric_type='normal'):
        if metric_type == 'inverse':  # For metrics where lower is better (like absent count)
            if change <= -10:
                return 'good'
            elif change <= 10:
                return 'warning'
            else:
                return 'attention'
        else:  # Normal metrics where higher is better
            if change >= 10:
                return 'good'
            elif change >= -5:
                return 'warning'
            else:
                return 'attention'
    
    metrics = [
        {
            'metric': 'Total Hours Worked',
            'current': current_stats['total_hours'],
            'previous': previous_stats['total_hours'],
            'change': calculate_change(current_stats['total_hours'], previous_stats['total_hours']),
            'status': get_status(calculate_change(current_stats['total_hours'], previous_stats['total_hours']))
        },
        {
            'metric': 'Total Amount Earned',
            'current': f"AED {current_stats['total_amount']:,.2f}",
            'previous': f"AED {previous_stats['total_amount']:,.2f}",
            'change': calculate_change(current_stats['total_amount'], previous_stats['total_amount']),
            'status': get_status(calculate_change(current_stats['total_amount'], previous_stats['total_amount']))
        },
        {
            'metric': 'Attendance Rate',
            'current': f"{current_stats['attendance_rate']}%",
            'previous': f"{previous_stats['attendance_rate']}%",
            'change': calculate_change(current_stats['attendance_rate'], previous_stats['attendance_rate']),
            'status': get_status(calculate_change(current_stats['attendance_rate'], previous_stats['attendance_rate']))
        },
        {
            'metric': 'Active Labourers',
            'current': current_stats['unique_labourers'],
            'previous': previous_stats['unique_labourers'],
            'change': calculate_change(current_stats['unique_labourers'], previous_stats['unique_labourers']),
            'status': get_status(calculate_change(current_stats['unique_labourers'], previous_stats['unique_labourers']))
        },
        {
            'metric': 'Active Sites',
            'current': current_stats['active_sites'],
            'previous': previous_stats['active_sites'],
            'change': calculate_change(current_stats['active_sites'], previous_stats['active_sites']),
            'status': get_status(calculate_change(current_stats['active_sites'], previous_stats['active_sites']))
        },
        {
            'metric': 'Average Daily Hours',
            'current': current_stats['avg_daily_hours'],
            'previous': previous_stats['avg_daily_hours'],
            'change': calculate_change(current_stats['avg_daily_hours'], previous_stats['avg_daily_hours']),
            'status': get_status(calculate_change(current_stats['avg_daily_hours'], previous_stats['avg_daily_hours']))
        }
    ]
    
    return metrics

@report_bp.route('/report')
def report():
    # Check if user is logged in
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get user data
    user = User.query.get(session['user_id'])
    if not user:
        return redirect(url_for('login'))
    
    # Get date range from request
    date_from_obj, date_to_obj, date_from, date_to = get_date_range_from_request()
    
    # Get site filter
    site_filter = request.args.get('site_id', 'all')
    
    # Calculate previous period dates
    prev_date_from, prev_date_to = calculate_previous_period_dates(date_from_obj, date_to_obj)
    
    # Get current period statistics
    current_stats = get_labour_statistics(date_from_obj, date_to_obj, site_filter)
    
    # Get previous period statistics for comparison
    previous_stats = get_labour_statistics(prev_date_from, prev_date_to, site_filter)
    
    # Generate comparison metrics
    report_data = generate_report_metrics(current_stats, previous_stats)
    
    # Get site-wise statistics
    site_wise_stats = get_site_wise_statistics(date_from_obj, date_to_obj)
    
    # Get labour performance data
    labour_performance = get_labour_performance_data(date_from_obj, date_to_obj)
    
    # Get all sites for filter dropdown
    sites = Site.query.all()
    
    # Create stats summary for the header cards
    stats = {
        'total_hours': current_stats['total_hours'],
        'total_amount': current_stats['total_amount'],
        'active_labourers': current_stats['unique_labourers'],
        'active_sites': current_stats['active_sites'],
        'attendance_rate': current_stats['attendance_rate'],
        'present_count': current_stats['present_count'],
        'absent_count': current_stats['absent_count']
    }
    
    return render_template('report.html', 
                        user=user, 
                        stats=stats, 
                        report_data=report_data,
                        site_wise_stats=site_wise_stats,
                        labour_performance=labour_performance,
                        sites=sites,
                        current_site_filter=site_filter,
                        date_from=date_from,
                        date_to=date_to,
                        period_info={
                            'from': date_from_obj.strftime('%B %d, %Y'),
                            'to': date_to_obj.strftime('%B %d, %Y'),
                            'days': (date_to_obj - date_from_obj).days + 1
                        })

@report_bp.route('/report/api/chart-data')
def chart_data():
    """API endpoint for chart data"""
    if 'user_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get date range
    date_from_obj, date_to_obj, _, _ = get_date_range_from_request()
    
    # Get daily statistics for charts
    daily_stats = []
    current_date = date_from_obj
    
    while current_date <= date_to_obj:
        next_date = current_date + timedelta(days=1)
        day_stats = get_labour_statistics(current_date, next_date)
        
        daily_stats.append({
            'date': current_date.strftime('%Y-%m-%d'),
            'hours': day_stats['total_hours'],
            'amount': day_stats['total_amount'],
            'attendance': day_stats['attendance_rate']
        })
        
        current_date = next_date
    
    return jsonify(daily_stats)

# Export routes can be added here
@report_bp.route('/report/export/pdf')
def export_pdf():
    # Implementation for PDF export
    return "PDF export functionality to be implemented"

@report_bp.route('/report/export/excel')
def export_excel():
    # Implementation for Excel export
    return "Excel export functionality to be implemented"

@report_bp.route('/report/export/csv')
def export_csv():
    # Implementation for CSV export
    return "CSV export functionality to be implemented"