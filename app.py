from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from flask_migrate import Migrate
from models import db, User, Site, Labour, Employee, LabourEntry  
from config import Config
from functools import wraps

# Import blueprints
from admin import admin_bp
from site_m import site_bp
from labour import labour_bp
from employee import employee_bp
from report import report_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate = Migrate(app, db)

    # Register blueprints
    app.register_blueprint(admin_bp)
    app.register_blueprint(site_bp)
    app.register_blueprint(labour_bp)
    app.register_blueprint(employee_bp) 
    app.register_blueprint(report_bp)

    def login_required(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            return f(*args, **kwargs)
        return decorated_function

    def permission_required(permission):
        def decorator(f):
            @wraps(f)
            def decorated_function(*args, **kwargs):
                if 'user_id' not in session:
                    return redirect(url_for('login'))
                
                user = User.query.get(session['user_id'])
                if not user or not user.has_permission(permission):
                    flash('You do not have permission to access this page.', 'danger')
                    return redirect(url_for('admin.admin_dashboard'))
                
                return f(*args, **kwargs)
            return decorated_function
        return decorator

    # Make decorators available to blueprints
    app.login_required = login_required
    app.permission_required = permission_required

    @app.route('/')
    def home():
        return redirect(url_for('login'))

    @app.route('/login', methods=['GET', 'POST'])
    def login():
        if request.method == 'POST':
            username = request.form['username']
            password = request.form['password']
            
            # Debug: Print what we're looking for
            print(f"DEBUG: Attempting login with username: {username}")
            
            # First check if it's an admin user
            user = User.query.filter_by(username=username).first()
            
            if user:
                print(f"DEBUG: Admin user found - ID: {user.id}, Username: {user.username}")
                
                if user.check_password(password):
                    session['user_id'] = user.id
                    session['user_type'] = 'admin'  # Mark as admin
                    print(f"DEBUG: Admin login successful for user {username}")
                    return redirect(url_for('admin.admin_dashboard'))
                else:
                    print(f"DEBUG: Password validation failed for admin user {username}")
            else:
                # Try to find by email (in case they're using email to login)
                user_by_email = User.query.filter_by(email=username).first()
                if user_by_email:
                    print(f"DEBUG: Found admin user by email instead: {user_by_email.username}")
                    if user_by_email.check_password(password):
                        session['user_id'] = user_by_email.id
                        session['user_type'] = 'admin'  # Mark as admin
                        print(f"DEBUG: Admin login successful via email for user {user_by_email.username}")
                        return redirect(url_for('admin.admin_dashboard'))
                    else:
                        print(f"DEBUG: Password validation failed via email for admin user {user_by_email.username}")
            
            # If not found in admin users, check employee table
            employee = Employee.query.filter_by(username=username).first()
            
            if employee:
                print(f"DEBUG: Employee found - ID: {employee.id}, Username: {employee.username}")
                
                if not employee.is_active:
                    flash('Your account is inactive. Please contact administrator.', 'danger')
                    return render_template('login.html')
                
                if employee.check_password(password):
                    session['user_id'] = employee.id
                    session['user_type'] = 'employee'  # Mark as employee
                    print(f"DEBUG: Employee login successful for user {username}")
                    return redirect(url_for('employee.entry'))
                else:
                    print(f"DEBUG: Password validation failed for employee user {username}")
            else:
                print(f"DEBUG: No employee found with username: {username}")
            
            # If not found in admin or employee, check labour table
            labour = Labour.query.filter_by(labour_id=username).first()
            
            if labour:
                print(f"DEBUG: Labour found - ID: {labour.id}, Labour ID: {labour.labour_id}")
                
                if not labour.is_active:
                    flash('Your account is inactive. Please contact administrator.', 'danger')
                    return render_template('login.html')
                
                if labour.check_password(password):
                    session['user_id'] = labour.id
                    session['user_type'] = 'labour'  # Mark as labour
                    print(f"DEBUG: Labour login successful for user {username}")
                    return redirect(url_for('labour.wage_card'))
                else:
                    print(f"DEBUG: Password validation failed for labour user {username}")
            else:
                print(f"DEBUG: No labour found with labour_id: {username}")
            
            flash('Invalid credentials', 'danger')
        
        return render_template('login.html')
    
    # Add this temporary route for debugging (remove in production)
    @app.route('/debug/users')
    def debug_users():
        """Temporary debug route to see all users in database"""
        users = User.query.all()
        employees = Employee.query.all()
        labours = Labour.query.all()
        
        user_info = []
        for user in users:
            user_info.append({
                'type': 'admin',
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'is_super_admin': user.is_super_admin,
                'permissions': {
                    'site_m': user.can_access_site_m,
                    'employee_m': user.can_access_employee_m,
                    'labour_m': user.can_access_labour_m,
                    'admin_m': user.can_access_admin_m,
                }
            })
        
        for employee in employees:
            user_info.append({
                'type': 'employee',
                'id': employee.id,
                'username': employee.username,
                'site_id': employee.site_id,
                'is_active': employee.is_active
            })
        
        for labour in labours:
            user_info.append({
                'type': 'labour',
                'id': labour.id,
                'name': labour.name,
                'labour_id': labour.labour_id,
                'is_active': labour.is_active
            })
        
        return jsonify({'users': user_info, 'total': len(user_info)})

    @app.route('/logout')
    def logout():
        session.clear()
        flash('You have been logged out.', 'info')
        return redirect(url_for('login'))

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)