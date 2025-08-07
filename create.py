#!/usr/bin/env python3
import getpass
from app import create_app
from models import db, User

app = create_app()

def prompt_new_admin():
    print("Create Super Admin User")
    print("-" * 25)
    
    username = input("Enter new admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    
    email = input("Enter admin email (optional): ").strip()
    if not email:
        email = None
    
    password = getpass.getpass("Enter password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return

    with app.app_context():
        # Ensure the table exists
        db.create_all()

        # Check if user already exists
        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return
        
        if email and User.query.filter_by(email=email).first():
            print(f"User with email '{email}' already exists.")
            return

        # Create super admin user
        user = User(
            username=username, 
            email=email,
            is_super_admin=True,  # This makes them a super admin
            # Super admin gets all permissions by default
            can_access_site_m=True,
            can_access_employee_m=True,
            can_access_labour_m=True,
            can_access_admin_m=True
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        print(f"Super admin user '{username}' created successfully.")
        print("This user has access to all modules and can create other admins.")

def create_regular_admin():
    """Alternative function to create regular admins via command line"""
    print("Create Regular Admin User")
    print("-" * 26)
    
    username = input("Enter admin username: ").strip()
    if not username:
        print("Username cannot be empty.")
        return
    
    email = input("Enter admin email: ").strip()
    if not email:
        print("Email cannot be empty for regular admins.")
        return
    
    password = getpass.getpass("Enter password: ")
    confirm = getpass.getpass("Confirm password: ")
    if password != confirm:
        print("Passwords do not match.")
        return
    
    print("\nSelect permissions (y/n):")
    perms = {}
    perms['site_m'] = input("Site Management (y/n): ").lower().startswith('y')
    perms['employee_m'] = input("Employee Management (y/n): ").lower().startswith('y')
    perms['labour_m'] = input("Labour Management (y/n): ").lower().startswith('y')
    perms['admin_m'] = input("Admin Management (y/n): ").lower().startswith('y')

    with app.app_context():
        db.create_all()

        if User.query.filter_by(username=username).first():
            print(f"User '{username}' already exists.")
            return
        
        if User.query.filter_by(email=email).first():
            print(f"User with email '{email}' already exists.")
            return

        user = User(
            username=username,
            email=email,
            is_super_admin=False,
            can_access_site_m=perms['site_m'],
            can_access_employee_m=perms['employee_m'],
            can_access_labour_m=perms['labour_m'],
            can_access_admin_m=perms['admin_m']
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        print(f"Regular admin user '{username}' created successfully.")

if __name__ == '__main__':
    print("Admin Creation Tool")
    print("==================")
    print("1. Create Super Admin (full access)")
    print("2. Create Regular Admin (limited access)")
    
    choice = input("Choose option (1 or 2): ").strip()
    
    if choice == '1':
        prompt_new_admin()
    elif choice == '2':
        create_regular_admin()
    else:
        print("Invalid choice. Please run again and select 1 or 2.")