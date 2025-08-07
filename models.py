from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.orm import relationship

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)  # Added email field
    password_hash = db.Column(db.Text, nullable=False)
    is_super_admin = db.Column(db.Boolean, default=False)  # To identify main admin

    # Permission columns
    can_access_site_m = db.Column(db.Boolean, default=False)
    can_access_employee_m = db.Column(db.Boolean, default=False)
    can_access_labour_m = db.Column(db.Boolean, default=False)
    can_access_admin_m = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def has_permission(self, permission):
        """Check if user has specific permission"""
        if self.is_super_admin:  # Super admin has all permissions
            return True
        
        permission_map = {
            'site_m': self.can_access_site_m,
            'employee_m': self.can_access_employee_m,
            'labour_m': self.can_access_labour_m,
            'admin_m': self.can_access_admin_m,
        }
        
        return permission_map.get(permission, False)
    
    def set_permissions(self, permissions):
        """Set multiple permissions at once"""
        self.can_access_site_m = 'site_m' in permissions
        self.can_access_employee_m = 'employee_m' in permissions
        self.can_access_labour_m = 'labour_m' in permissions
        self.can_access_admin_m = 'admin_m' in permissions


class Site(db.Model):
    __tablename__ = 'sites'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationship to User
    creator = db.relationship('User', backref=db.backref('sites', lazy=True))
    # Relationship to Employee
    employees = db.relationship('Employee', backref='site', lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Site {self.name}>'
    
    def to_dict(self):
        """Convert site object to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'location': self.location,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }



# Add this field to the Labour model in models.py

class Labour(db.Model):
    __tablename__ = 'labour'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    labour_id = db.Column(db.String(50), nullable=False, unique=True)
    password_hash = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    visa_cost = db.Column(db.Float, default=0.0)              # Total cost of visa
    visa_paid = db.Column(db.Float, default=0.0)              # Amount paid by labour
    advance_payment = db.Column(db.Float, default=0.0)        # NEW: Advance payment given to labour

    creator = relationship('User', backref=db.backref('labour_records', lazy=True))

    def set_password(self, password):
        """Set password for labour"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check password for labour"""
        return check_password_hash(self.password_hash, password)

    def pending_visa_amount(self):
        return max(0.0, self.visa_cost - self.visa_paid)
    
    def calculate_penalty(self, absent_days, penalty_per_day=25.0, allowed_absent_days=2, insurance_amount=30.0):
        """
        Calculate penalty for excessive absences and insurance deduction.
        
        Args:
            absent_days (int): Total number of absent days
            penalty_per_day (float): Penalty amount per excess day (default: 25.0 AED)
            allowed_absent_days (int): Number of allowed absent days without penalty (default: 2)
            insurance_amount (float): Monthly insurance deduction (default: 30.0 AED)
        
        Returns:
            dict: Dictionary containing penalty and insurance details
        """
        penalty_days = max(0, absent_days - allowed_absent_days)
        total_penalty = penalty_days * penalty_per_day
        
        return {
            'penalty_days': penalty_days,
            'total_penalty': total_penalty,
            'penalty_per_day': penalty_per_day,
            'allowed_absent_days': allowed_absent_days,
            'insurance_amount': insurance_amount,
            'total_deductions': total_penalty + insurance_amount,
            'has_penalty': penalty_days > 0
        }
    
    def to_dict(self):
        """Convert labour object to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'labour_id': self.labour_id,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by,
            'visa_cost': self.visa_cost,
            'visa_paid': self.visa_paid,
            'advance_payment': self.advance_payment or 0.0,  # Handle None case
            'pending_visa_amount': self.pending_visa_amount()
        }



class Employee(db.Model):
    __tablename__ = 'employees'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Relationships
    creator = db.relationship('User', backref=db.backref('created_employees', lazy=True))

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<Employee {self.username}>'
    
    def to_dict(self):
        """Convert employee object to dictionary"""
        return {
            'id': self.id,
            'username': self.username,
            'site_id': self.site_id,
            'site_name': self.site.name if self.site else None,
            'site_location': self.site.location if self.site else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'created_by': self.created_by
        }
    
class LabourEntry(db.Model):
    __tablename__ = 'labour_entries'

    id = db.Column(db.Integer, primary_key=True)
    labour_id = db.Column(db.Integer, db.ForeignKey('labour.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    site_id = db.Column(db.Integer, db.ForeignKey('sites.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    labour = db.relationship('Labour', backref='entries')
    employee = db.relationship('Employee', backref='entries')
    site = db.relationship('Site', backref='entries')

    activity = db.Column(db.String(100), nullable=False)
    status = db.Column(db.String(20), nullable=False)  # Present/Absent
    unit = db.Column(db.String(20), nullable=False)
    rate = db.Column(db.Float, nullable=False)
    total_hours = db.Column(db.Float, nullable=True)
    qty = db.Column(db.Float, nullable=True)
    amount = db.Column(db.Float, nullable=True)
    rate_type = db.Column(db.String(20), nullable=False)  # 'Unit' or 'Hour'


    def __repr__(self):
            return f'<LabourEntry Labour:{self.labour_id} by Employee:{self.employee_id}>'