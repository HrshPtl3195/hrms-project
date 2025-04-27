from datetime import date
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse
from django.views import View
from django.views.generic import TemplateView
from django.core.mail import send_mail
from django.conf import settings
from django.http import HttpResponseRedirect, JsonResponse
from core.authentication import EmailAuthBackend
import logging, random, json
from django.db import connection
from django.utils import timezone
from .models import PasswordResetOTP, Users
from django.utils.timezone import now  

logger = logging.getLogger(__name__)

class LoginView(View):
    """Handles user login"""

    def get(self, request):
        if request.user.is_authenticated:
            logout(request)
            request.session.flush()

        storage = messages.get_messages(request)
        storage.used = True
        
        response = render(request, 'core/login.html')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response

    def post(self, request):
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            data = json.loads(request.body)
            email = data.get('email', '').strip()
            password = data.get('password', '')
        else:
            email = request.POST.get('email', '').strip()
            password = request.POST.get('password', '')

        user = EmailAuthBackend.authenticate(self, request, username=email, password=password)

        if user:
            backend = 'core.authentication.EmailAuthBackend'
            request.session['_auth_user_backend'] = backend
            login(request, user, backend=backend)
            request.session.set_expiry(1800)

            if request.headers.get('x-requested-with') == 'XMLHttpRequest':
                if user.u_role.lower() == 'hybrid':
                    request.session['is_hybrid'] = True
                    return JsonResponse({'success': True, 'role': 'hybrid'})
                else:
                    role_redirects = {
                        'hr_admin': 'hr_admin_dashboard',
                        'employee': 'employee_dashboard',
                        'office_admin': 'office_admin_dashboard',
                    }
                    return JsonResponse({
                        'success': True,
                        'role': user.u_role.lower(),
                        'redirect_url': reverse(role_redirects.get(user.u_role.lower(), 'login'))
                    })

            # fallback for non-AJAX
            return redirect(role_redirects.get(user.u_role.lower(), 'login'))

        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({'success': False, 'message': 'Invalid email or password'})

        # Legacy fallback (optional): can remove if unused
        return redirect('login')


class LogoutView(View):
    """Handles user logout"""

    def get(self, request):
        logout(request)
        request.session.flush()

        response = HttpResponseRedirect('/login/')
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class HRAdminDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        print("\n||  Dashboard Page Visited!  ||\n")
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_dashboard_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
            # print()
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hr_admin/dashboard.html", data)

    def get_dashboard_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            # Total number of employees
            cursor.execute("SELECT COUNT(*) FROM employees WHERE is_deleted = 0")
            total_employees = cursor.fetchone()[0]

            # Total number of pending leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'PENDING'
                AND (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN';""")
            total_pending_leaves = cursor.fetchone()[0]

            # Total upcoming payroll (Sum of salaries)
            cursor.execute("SELECT ISNULL(SUM(salary), 0) FROM payslips")
            total_upcoming_payroll = cursor.fetchone()[0]

            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            notifications = []

            # 1. New Employees Registered in Last 7 Days
            cursor.execute("""
                SELECT first_name, last_name, date_of_joining FROM employees
                WHERE DATEDIFF(DAY, date_of_joining, GETDATE()) <= 7 AND is_deleted = 0
            """)
            for emp in cursor.fetchall():
                full_name = f"{emp[0]} {emp[1]}"
                doj = emp[2].strftime("%b %d")
                notifications.append({
                    "type": "success",
                    "message": f"{full_name} joined on {doj}."
                })

            # 2. Missing Documents (SIN/Passport)
            cursor.execute(f"""
                SELECT e.first_name, e.last_name, s.sin_document, p.passport_document
                FROM employees e
                LEFT JOIN sin_details s ON s.employee_id = e.employee_id
                LEFT JOIN passport_details p ON p.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE e.is_deleted = 0
                
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                if not row[2]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing SIN Certificate."
                    })
                if not row[3]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing Passport Document."
                    })

            # 3. Pending Leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'PENDING'
                AND (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN';""")
            pending_count = cursor.fetchone()[0]
            if pending_count > 0:
                notifications.append({
                    "type": "warning",
                    "message": f"{pending_count} leave requests need approval."
                })

            # 4. Recently Approved/Rejected Leaves (last 7 days)
            cursor.execute("""
                SELECT e.first_name, e.last_name, leave_type, L_status
                FROM leaves l
                JOIN employees e ON e.employee_id = l.employee_id
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE l.L_status IN ('APPROVED', 'REJECTED')
                AND DATEDIFF(DAY, l_apply_date, GETDATE()) <= 7
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                full_name = f"{row[0]} {row[1]}"
                leave_type = row[2]
                status = row[3]
                if status == "APPROVED":
                    notifications.append({
                        "type": "success",
                        "message": f"{full_name}'s {leave_type} was approved."
                    })
                else:
                    notifications.append({
                        "type": "error",
                        "message": f"{full_name}'s {leave_type} was rejected."
                    })

            # 5. Payslips generated recently
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.date_generated
                FROM payslips p
                JOIN employees e ON p.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE DATEDIFF(DAY, p.date_generated, GETDATE()) <= 5
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                gen_date = row[2].strftime("%b %d")
                notifications.append({
                    "type": "info",
                    "message": f"Payslip for {name} generated on {gen_date}."
                })

            # 6. Salary Below Threshold
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.salary
                FROM payslips p
                JOIN employees e ON e.employee_id = p.employee_id
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE p.date_generated = (
                SELECT MAX(p2.date_generated)
                FROM payslips p2 WHERE p2.employee_id = p.employee_id
                )
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                if row[2] and row[2] < 1500:
                    notifications.append({
                        "type": "error",
                        "message": f"{row[0]} {row[1]}'s salary is below threshold."
                    })

            # 7. Missing Academic or Contact Details
            cursor.execute("""
                SELECT e.first_name, e.last_name
                FROM employees e
                LEFT JOIN academic_details a ON a.employee_id = e.employee_id
                LEFT JOIN employee_contact_details c ON c.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE (a.academic_id IS NULL OR c.employee_contact_id IS NULL)
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]} has incomplete profile data."
                })

            # 8. Upcoming Joins (Next 7 Days)
            cursor.execute("""
                SELECT e.first_name, e.last_name, e.date_of_joining
                FROM employees e
                JOIN users u ON e.user_id = u.user_id  -- Joining the users table
                WHERE DATEDIFF(DAY, GETDATE(), e.date_of_joining) BETWEEN 0 AND 7
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "info",
                    "message": f"{row[0]} {row[1]} joining on {row[2].strftime('%b %d')}."
                })

            # 9. Delayed Leave Approvals (> 3 days old and still pending)
            cursor.execute("""
                SELECT e.first_name, e.last_name, l.l_apply_date
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id 
                WHERE l.L_status = 'PENDING'
                AND DATEDIFF(DAY, l.l_apply_date, GETDATE()) > 3
                AND e.is_deleted = 0; 
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]}'s leave pending for over 3 days."
                })

            # ✅ Get leave requests of Office Admins & Hybrid employees only (PENDING only)
            cursor.execute("""
                SELECT 
                    l.leave_id,
                    e.first_name,
                    e.last_name,
                    l.leave_type,
                    l.L_start_date,
                    l.L_end_date,
                    l.leave_reason,
                    od.profile_image
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE l.L_status = 'PENDING' 
                ORDER BY l.L_start_date DESC
            """)

            leave_status_list = []
            for row in cursor.fetchall():
                leave_status_list.append({
                    "leave_id": row[0],
                    "emp_name": f"{row[1]} {row[2]}",
                    "leave_type": row[3],
                    "start_date": row[4].strftime("%b %d, %Y"),
                    "end_date": row[5].strftime("%b %d, %Y"),
                    "reason": row[6],
                    "profile_image": row[7] or "default.png"
                })

        return {
            "user_name": user_name,
            "total_employees": total_employees,
            "total_pending_leaves": total_pending_leaves,
            "total_upcoming_payroll": total_upcoming_payroll,
            "profile_image": profile_image,
            "notifications":list(reversed(notifications)),
            "leave_status_list": leave_status_list
        }


class OfficeAdminDashboardView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        print("\n||  Dashboard Page Visited!  ||\n")
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_dashboard_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
            # print()
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "office_admin/dashboard.html", data)

    def get_dashboard_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            # Total number of employees
            cursor.execute("SELECT COUNT(*) FROM employees WHERE is_deleted = 0")
            total_employees = cursor.fetchone()[0]

            # Total number of pending leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'PENDING'
                AND (
                    -- Case when the logged-in user is an HR Admin
                    ( 
                        (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN'
                        AND (u.u_role = 'OFFICE_ADMIN' OR u.u_role = 'HYBRID')
                    )
                    OR 
                    -- Case when the logged-in user is an Office Admin
                    (
                        (SELECT u_role FROM users WHERE user_id = {user_id}) = 'OFFICE_ADMIN'
                        AND (u.u_role = 'EMPLOYEE' OR u.u_role = 'HYBRID')
                    )
                );""")
            total_pending_leaves = cursor.fetchone()[0]

            # Total upcoming payroll (Sum of salaries)
            cursor.execute("SELECT ISNULL(SUM(salary), 0) FROM payslips")
            total_upcoming_payroll = cursor.fetchone()[0]

            # Number of unique designations (departments)
            cursor.execute("SELECT COUNT(DISTINCT designation) FROM employees WHERE is_deleted = 0")
            total_departments = cursor.fetchone()[0]

            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            notifications = []

            # 1. New Employees Registered in Last 7 Days
            cursor.execute("""
                SELECT first_name, last_name, date_of_joining FROM employees
                WHERE DATEDIFF(DAY, date_of_joining, GETDATE()) <= 7 AND is_deleted = 0
            """)
            for emp in cursor.fetchall():
                full_name = f"{emp[0]} {emp[1]}"
                doj = emp[2].strftime("%b %d")
                notifications.append({
                    "type": "success",
                    "message": f"{full_name} joined on {doj}."
                })

            # 2. Missing Documents (SIN/Passport)
            cursor.execute("""
                SELECT e.first_name, e.last_name, s.sin_document, p.passport_document
                FROM employees e
                LEFT JOIN sin_details s ON s.employee_id = e.employee_id
                LEFT JOIN passport_details p ON p.employee_id = e.employee_id
                WHERE e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                if not row[2]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing SIN Certificate."
                    })
                if not row[3]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing Passport Document."
                    })

            # 3. Pending Leaves
            cursor.execute("""
                SELECT COUNT(*) FROM leaves
                WHERE L_status = 'PENDING'
            """)
            pending_count = cursor.fetchone()[0]
            if pending_count > 0:
                notifications.append({
                    "type": "warning",
                    "message": f"{pending_count} leave requests need approval."
                })

            # 4. Recently Approved/Rejected Leaves (last 7 days)
            cursor.execute("""
                SELECT e.first_name, e.last_name, leave_type, L_status
                FROM leaves l
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE l.L_status IN ('APPROVED', 'REJECTED')
                AND DATEDIFF(DAY, l_apply_date, GETDATE()) <= 7
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                full_name = f"{row[0]} {row[1]}"
                leave_type = row[2]
                status = row[3]
                if status == "APPROVED":
                    notifications.append({
                        "type": "success",
                        "message": f"{full_name}'s {leave_type} was approved."
                    })
                else:
                    notifications.append({
                        "type": "error",
                        "message": f"{full_name}'s {leave_type} was rejected."
                    })

            # 5. Payslips generated recently
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.date_generated
                FROM payslips p
                JOIN employees e ON p.employee_id = e.employee_id
                WHERE DATEDIFF(DAY, p.date_generated, GETDATE()) <= 5
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                gen_date = row[2].strftime("%b %d")
                notifications.append({
                    "type": "info",
                    "message": f"Payslip for {name} generated on {gen_date}."
                })

            # 6. Salary Below Threshold
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.salary
                FROM payslips p
                JOIN employees e ON e.employee_id = p.employee_id
                WHERE p.date_generated = (
                SELECT MAX(p2.date_generated)
                FROM payslips p2 WHERE p2.employee_id = p.employee_id
                )
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                if row[2] and row[2] < 1500:
                    notifications.append({
                        "type": "error",
                        "message": f"{row[0]} {row[1]}'s salary is below threshold."
                    })

            # 7. Missing Academic or Contact Details
            cursor.execute("""
                SELECT e.first_name, e.last_name
                FROM employees e
                LEFT JOIN academic_details a ON a.employee_id = e.employee_id
                LEFT JOIN employee_contact_details c ON c.employee_id = e.employee_id
                WHERE (a.academic_id IS NULL OR c.employee_contact_id IS NULL)
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]} has incomplete profile data."
                })

            # 8. Upcoming Joins (Next 7 Days)
            cursor.execute("""
                SELECT first_name, last_name, date_of_joining
                FROM employees
                WHERE DATEDIFF(DAY, GETDATE(), date_of_joining) BETWEEN 0 AND 7
                AND is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "info",
                    "message": f"{row[0]} {row[1]} joining on {row[2].strftime('%b %d')}."
                })

            # 9. Delayed Leave Approvals (> 3 days old and still pending)
            cursor.execute("""
                SELECT e.first_name, e.last_name, l.l_apply_date
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                WHERE l.L_status = 'PENDING'
                AND DATEDIFF(DAY, l.l_apply_date, GETDATE()) > 3
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]}'s leave pending for over 3 days."
                })

            # ✅ Get leave requests of Office Admins & Hybrid employees only (PENDING only)
            cursor.execute("""
                SELECT 
                    l.leave_id,
                    e.first_name,
                    e.last_name,
                    l.leave_type,
                    l.L_start_date,
                    l.L_end_date,
                    l.leave_reason,
                    od.profile_image
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE l.L_status = 'PENDING' AND u.u_role IN ('HYBRID', 'EMPLOYEE')
                ORDER BY l.L_start_date DESC
            """)

            leave_status_list = []
            for row in cursor.fetchall():
                leave_status_list.append({
                    "leave_id": row[0],
                    "emp_name": f"{row[1]} {row[2]}",
                    "leave_type": row[3],
                    "start_date": row[4].strftime("%b %d, %Y"),
                    "end_date": row[5].strftime("%b %d, %Y"),
                    "reason": row[6],
                    "profile_image": row[7] or "default.png"
                })

        return {
            "user_name": user_name,
            "total_employees": total_employees,
            "total_pending_leaves": total_pending_leaves,
            "total_upcoming_payroll": total_upcoming_payroll,
            "total_departments": total_departments,
            "profile_image": profile_image,
            "notifications":list(reversed(notifications)),
            "leave_status_list": leave_status_list
        }


class EmployeeDashboardView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        print("\n||  Employee Dashboard Page Visited!  ||\n")
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
                
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "employee/dashboard.html", data)

    def get_data(self, user_id):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            cursor.execute(f"SELECT date_of_joining FROM employees WHERE is_deleted = 0 and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            date_of_joining = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM leaves WHERE L_status = 'PENDING' and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            pending_requests = cursor.fetchone()[0]

            cursor.execute(f"SELECT ISNULL(SUM(salary), 0) FROM payslips where\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            last_payroll = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT (MAX(total_leaves) - COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)) AS leaves_left\
            FROM leaves WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            leave_balance = cursor.fetchone()[0]
            leave_balance = 0 if leave_balance == None else leave_balance
            
            cursor.execute(f"SELECT  COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)\
            FROM leaves WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            leaves_taken = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT designation FROM employees WHERE is_deleted = 0 and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            designation = cursor.fetchone()[0]

            cursor.execute(f"SELECT employee_id FROM employees WHERE user_id = {user_id}")
            employee_id = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            # Fetch leave history for dashboard
            cursor.execute("EXEC GetEmployeeLeaveHistory @user_id = %s", [user_id])
            leave_history = cursor.fetchall()

            # Build list of dicts
            leave_list = []
            for row in leave_history:
                leave_list.append({
                    "type": row[1],
                    "start": row[2],
                    "end": row[3],
                    "status": row[5]
                })
            notifications = []

            # 1. Recently approved/rejected leaves
            cursor.execute("""
                SELECT leave_type, L_start_date, L_end_date, L_status
                FROM leaves
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                AND L_apply_date >= DATEADD(DAY, -15, GETDATE())
                ORDER BY L_apply_date DESC
            """, [user_id])

            for leave in cursor.fetchall():
                leave_type, start, end, status = leave
                date_range = start.strftime("%b %d") if start == end else f"{start.strftime('%b %d')}–{end.strftime('%b %d')}"

                if status == 'APPROVED':
                    notifications.append({
                        "type": "success",
                        "message": f"Your leave from {date_range} has been approved."
                    })
                elif status == 'REJECTED':
                    notifications.append({
                        "type": "error",
                        "message": f"Your leave from {date_range} was rejected."
                    })

            # 2. Upcoming approved leave
            cursor.execute("""
                SELECT L_start_date, L_end_date
                FROM leaves
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                AND L_status = 'APPROVED'
                AND L_start_date BETWEEN GETDATE() AND DATEADD(DAY, 3, GETDATE())
                ORDER BY L_start_date ASC
            """, [user_id])
            upcoming = cursor.fetchone()
            if upcoming:
                start, end = upcoming
                date_range = start.strftime("%b %d") if start == end else f"{start.strftime('%b %d')}–{end.strftime('%b %d')}"
                notifications.append({
                    "type": "warning",
                    "message": f"You have an approved leave starting soon ({date_range})."
                })

            # 3. New payslip generated this month
            cursor.execute("""
                SELECT TOP 1 date_generated
                FROM payslips
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                ORDER BY date_generated DESC
            """, [user_id])
            last_payslip = cursor.fetchone()
            if last_payslip:
                date_generated = last_payslip[0]
                if date_generated.month == date.today().month:
                    notifications.append({
                        "type": "info",
                        "message": f"Your payslip for {date_generated.strftime('%B')} is now available."
                    })

            # 4. Missing SIN or Passport documents
            cursor.execute("""
                SELECT sin_document, passport_document
                FROM employees e
                LEFT JOIN sin_details s ON s.employee_id = e.employee_id
                LEFT JOIN passport_details p ON p.employee_id = e.employee_id
                WHERE e.user_id = %s
            """, [user_id])
            docs = cursor.fetchone()
            if docs:
                if not docs[0]:
                    notifications.append({
                        "type": "warning",
                        "message": "Your SIN Certificate is missing."
                    })
                if not docs[1]:
                    notifications.append({
                        "type": "warning",
                        "message": "Your Passport Document is missing."
                    })

            # 5. Optional: low salary alert
            cursor.execute("""
                SELECT TOP 1 salary FROM payslips
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                ORDER BY date_generated DESC
            """, [user_id])
            salary = cursor.fetchone()
            if salary and salary[0] < 1500:  # threshold
                notifications.append({
                    "type": "error",
                    "message": "Your recent salary is below expected range."
                })

        return {
            "user_name": user_name,
            "profile_image": profile_image,
            "leave_balance": leave_balance,
            "pending_requests": pending_requests,
            "last_payroll": last_payroll,
            "designation": designation,
            'employee_id': employee_id,
            'date_of_joining': date_of_joining,
            "dashboard_leave_history": leave_list[:3],
            "notifications": notifications,
            "leaves_taken": leaves_taken
        }


class ChooseRoleView(LoginRequiredMixin, TemplateView):
    def get(self, request, role):
        if request.user.is_authenticated and request.session.get('is_hybrid'):
            del request.session['is_hybrid']
            if role == 'employee':
                request.session['current_user'] = "employee"
                return redirect('hybrid_employee_dashboard')
            elif role == 'office_admin':
                request.session['current_user'] = "office_admin"
                return redirect('hybrid_office_admin_dashboard')
        return redirect('login')


class HybridDashboardView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        print("\n||  Dashboard Page Visited!  ||\n")
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_dashboard_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
            # print()
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hybrid/office_admin/dashboard.html", data)

    def get_dashboard_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            # Total number of employees
            cursor.execute("SELECT COUNT(*) FROM employees WHERE is_deleted = 0")
            total_employees = cursor.fetchone()[0]

            # Total number of pending leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'PENDING'
                AND (
                    -- Case when the logged-in user is an HR Admin
                    ( 
                        (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN'
                        AND (u.u_role = 'OFFICE_ADMIN' OR u.u_role = 'HYBRID')
                    )
                    OR 
                    -- Case when the logged-in user is an Office Admin
                    (
                        (SELECT u_role FROM users WHERE user_id = {user_id}) = 'OFFICE_ADMIN'
                        AND (u.u_role = 'EMPLOYEE' OR u.u_role = 'HYBRID')
                    )OR 
                    -- Case when the logged-in user is an Hybrid
                    (
                        (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HYBRID'
                        AND (u.u_role = 'EMPLOYEE' OR u.u_role = 'HYBRID')
                    )
                );""")
            total_pending_leaves = cursor.fetchone()[0]

            # Total upcoming payroll (Sum of salaries)
            cursor.execute("SELECT ISNULL(SUM(salary), 0) FROM payslips")
            total_upcoming_payroll = cursor.fetchone()[0]

            # Number of unique designations (departments)
            cursor.execute("SELECT COUNT(DISTINCT designation) FROM employees WHERE is_deleted = 0")
            total_departments = cursor.fetchone()[0]

            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            notifications = []

            # 1. New Employees Registered in Last 7 Days
            cursor.execute("""
                SELECT first_name, last_name, date_of_joining FROM employees
                WHERE DATEDIFF(DAY, date_of_joining, GETDATE()) <= 7 AND is_deleted = 0
            """)
            for emp in cursor.fetchall():
                full_name = f"{emp[0]} {emp[1]}"
                doj = emp[2].strftime("%b %d")
                notifications.append({
                    "type": "success",
                    "message": f"{full_name} joined on {doj}."
                })

            # 2. Missing Documents (SIN/Passport)
            cursor.execute("""
                SELECT e.first_name, e.last_name, s.sin_document, p.passport_document
                FROM employees e
                LEFT JOIN sin_details s ON s.employee_id = e.employee_id
                LEFT JOIN passport_details p ON p.employee_id = e.employee_id
                WHERE e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                if not row[2]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing SIN Certificate."
                    })
                if not row[3]:
                    notifications.append({
                        "type": "warning",
                        "message": f"{name} is missing Passport Document."
                    })

            # 3. Pending Leaves
            cursor.execute("""
                SELECT COUNT(*) FROM leaves
                WHERE L_status = 'PENDING'
            """)
            pending_count = cursor.fetchone()[0]
            if pending_count > 0:
                notifications.append({
                    "type": "warning",
                    "message": f"{pending_count} leave requests need approval."
                })

            # 4. Recently Approved/Rejected Leaves (last 7 days)
            cursor.execute("""
                SELECT e.first_name, e.last_name, leave_type, L_status
                FROM leaves l
                JOIN employees e ON e.employee_id = l.employee_id
                WHERE l.L_status IN ('APPROVED', 'REJECTED')
                AND DATEDIFF(DAY, l_apply_date, GETDATE()) <= 7
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                full_name = f"{row[0]} {row[1]}"
                leave_type = row[2]
                status = row[3]
                if status == "APPROVED":
                    notifications.append({
                        "type": "success",
                        "message": f"{full_name}'s {leave_type} was approved."
                    })
                else:
                    notifications.append({
                        "type": "error",
                        "message": f"{full_name}'s {leave_type} was rejected."
                    })

            # 5. Payslips generated recently
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.date_generated
                FROM payslips p
                JOIN employees e ON p.employee_id = e.employee_id
                WHERE DATEDIFF(DAY, p.date_generated, GETDATE()) <= 5
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                name = f"{row[0]} {row[1]}"
                gen_date = row[2].strftime("%b %d")
                notifications.append({
                    "type": "info",
                    "message": f"Payslip for {name} generated on {gen_date}."
                })

            # 6. Salary Below Threshold
            cursor.execute("""
                SELECT e.first_name, e.last_name, p.salary
                FROM payslips p
                JOIN employees e ON e.employee_id = p.employee_id
                WHERE p.date_generated = (
                SELECT MAX(p2.date_generated)
                FROM payslips p2 WHERE p2.employee_id = p.employee_id
                )
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                if row[2] and row[2] < 1500:
                    notifications.append({
                        "type": "error",
                        "message": f"{row[0]} {row[1]}'s salary is below threshold."
                    })

            # 7. Missing Academic or Contact Details
            cursor.execute("""
                SELECT e.first_name, e.last_name
                FROM employees e
                LEFT JOIN academic_details a ON a.employee_id = e.employee_id
                LEFT JOIN employee_contact_details c ON c.employee_id = e.employee_id
                WHERE (a.academic_id IS NULL OR c.employee_contact_id IS NULL)
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]} has incomplete profile data."
                })

            # 8. Upcoming Joins (Next 7 Days)
            cursor.execute("""
                SELECT first_name, last_name, date_of_joining
                FROM employees
                WHERE DATEDIFF(DAY, GETDATE(), date_of_joining) BETWEEN 0 AND 7
                AND is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "info",
                    "message": f"{row[0]} {row[1]} joining on {row[2].strftime('%b %d')}."
                })

            # 9. Delayed Leave Approvals (> 3 days old and still pending)
            cursor.execute("""
                SELECT e.first_name, e.last_name, l.l_apply_date
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                WHERE l.L_status = 'PENDING'
                AND DATEDIFF(DAY, l.l_apply_date, GETDATE()) > 3
                AND e.is_deleted = 0
            """)
            for row in cursor.fetchall():
                notifications.append({
                    "type": "warning",
                    "message": f"{row[0]} {row[1]}'s leave pending for over 3 days."
                })

            # ✅ Get leave requests of Office Admins & Hybrid employees only (PENDING only)
            cursor.execute("""
                SELECT 
                    l.leave_id,
                    e.first_name,
                    e.last_name,
                    l.leave_type,
                    l.L_start_date,
                    l.L_end_date,
                    l.leave_reason,
                    od.profile_image
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE l.L_status = 'PENDING' AND u.u_role IN ('OFFICE_ADMIN', 'EMPLOYEE')
                ORDER BY l.L_start_date DESC
            """)

            leave_status_list = []
            for row in cursor.fetchall():
                leave_status_list.append({
                    "leave_id": row[0],
                    "emp_name": f"{row[1]} {row[2]}",
                    "leave_type": row[3],
                    "start_date": row[4].strftime("%b %d, %Y"),
                    "end_date": row[5].strftime("%b %d, %Y"),
                    "reason": row[6],
                    "profile_image": row[7] or "default.png"
                })

        return {
            "user_name": user_name,
            "total_employees": total_employees,
            "total_pending_leaves": total_pending_leaves,
            "total_upcoming_payroll": total_upcoming_payroll,
            "total_departments": total_departments,
            "profile_image": profile_image,
            "notifications":list(reversed(notifications)),
            "leave_status_list": leave_status_list
        }


class HybridEmployeeDashboardView(LoginRequiredMixin, TemplateView):
    def get(self, request):
        print("\n||  Employee Dashboard Page Visited!  ||\n")
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
                
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hybrid/employee/dashboard.html", data)

    def get_data(self, user_id):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            cursor.execute(f"SELECT date_of_joining FROM employees WHERE is_deleted = 0 and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            date_of_joining = cursor.fetchone()[0]

            cursor.execute(f"SELECT COUNT(*) FROM leaves WHERE L_status = 'PENDING' and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            pending_requests = cursor.fetchone()[0]

            cursor.execute(f"SELECT ISNULL(SUM(salary), 0) FROM payslips where\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            last_payroll = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT (MAX(total_leaves) - COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)) AS leaves_left\
            FROM leaves WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            leave_balance = cursor.fetchone()[0]
            leave_balance = 0 if leave_balance == None else leave_balance
            
            cursor.execute(f"SELECT  COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)\
            FROM leaves WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            leaves_taken = cursor.fetchone()[0]
            
            cursor.execute(f"SELECT designation FROM employees WHERE is_deleted = 0 and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            designation = cursor.fetchone()[0]

            cursor.execute(f"SELECT employee_id FROM employees WHERE user_id = {user_id}")
            employee_id = cursor.fetchone()[0]
            
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            # Fetch leave history for dashboard
            cursor.execute("EXEC GetEmployeeLeaveHistory @user_id = %s", [user_id])
            leave_history = cursor.fetchall()

            # Build list of dicts
            leave_list = []
            for row in leave_history:
                leave_list.append({
                    "type": row[1],
                    "start": row[2],
                    "end": row[3],
                    "status": row[5]
                })
            notifications = []

            # 1. Recently approved/rejected leaves
            cursor.execute("""
                SELECT leave_type, L_start_date, L_end_date, L_status
                FROM leaves
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                AND L_apply_date >= DATEADD(DAY, -15, GETDATE())
                ORDER BY L_apply_date DESC
            """, [user_id])

            for leave in cursor.fetchall():
                leave_type, start, end, status = leave
                date_range = start.strftime("%b %d") if start == end else f"{start.strftime('%b %d')}–{end.strftime('%b %d')}"

                if status == 'APPROVED':
                    notifications.append({
                        "type": "success",
                        "message": f"Your leave from {date_range} has been approved."
                    })
                elif status == 'REJECTED':
                    notifications.append({
                        "type": "error",
                        "message": f"Your leave from {date_range} was rejected."
                    })

            # 2. Upcoming approved leave
            cursor.execute("""
                SELECT L_start_date, L_end_date
                FROM leaves
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                AND L_status = 'APPROVED'
                AND L_start_date BETWEEN GETDATE() AND DATEADD(DAY, 3, GETDATE())
                ORDER BY L_start_date ASC
            """, [user_id])
            upcoming = cursor.fetchone()
            if upcoming:
                start, end = upcoming
                date_range = start.strftime("%b %d") if start == end else f"{start.strftime('%b %d')}–{end.strftime('%b %d')}"
                notifications.append({
                    "type": "warning",
                    "message": f"You have an approved leave starting soon ({date_range})."
                })

            # 3. New payslip generated this month
            cursor.execute("""
                SELECT TOP 1 date_generated
                FROM payslips
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                ORDER BY date_generated DESC
            """, [user_id])
            last_payslip = cursor.fetchone()
            if last_payslip:
                date_generated = last_payslip[0]
                if date_generated.month == date.today().month:
                    notifications.append({
                        "type": "info",
                        "message": f"Your payslip for {date_generated.strftime('%B')} is now available."
                    })

            # 4. Missing SIN or Passport documents
            cursor.execute("""
                SELECT sin_document, passport_document
                FROM employees e
                LEFT JOIN sin_details s ON s.employee_id = e.employee_id
                LEFT JOIN passport_details p ON p.employee_id = e.employee_id
                WHERE e.user_id = %s
            """, [user_id])
            docs = cursor.fetchone()
            if docs:
                if not docs[0]:
                    notifications.append({
                        "type": "warning",
                        "message": "Your SIN Certificate is missing."
                    })
                if not docs[1]:
                    notifications.append({
                        "type": "warning",
                        "message": "Your Passport Document is missing."
                    })

            # 5. Optional: low salary alert
            cursor.execute("""
                SELECT TOP 1 salary FROM payslips
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                ORDER BY date_generated DESC
            """, [user_id])
            salary = cursor.fetchone()
            if salary and salary[0] < 1500:  # threshold
                notifications.append({
                    "type": "error",
                    "message": "Your recent salary is below expected range."
                })

        return {
            "user_name": user_name,
            "profile_image": profile_image,
            "leave_balance": leave_balance,
            "pending_requests": pending_requests,
            "last_payroll": last_payroll,
            "designation": designation,
            'employee_id': employee_id,
            'date_of_joining': date_of_joining,
            "dashboard_leave_history": leave_list[:3],
            "notifications": notifications,
            "leaves_taken": leaves_taken
        }
        

class ForgotPasswordView(View):
    def get(self, request):
        return render(request, "core/forgot_password.html")

    def post(self, request):
        email = request.POST.get("email")

        try:
            user = Users.objects.get(email=email)
        except Users.DoesNotExist:
            response = render(request, "core/forgot_password.html")
            response.set_cookie("toast", "otp_failed", max_age=3)  # ❌ Show error toast
            return response

        # Generate and store OTP
        otp = f"{random.randint(100000, 999999)}"
        PasswordResetOTP.objects.create(
            user_id=user.user_id,
            otp=otp,
            created_at=now(),
            is_used=False
        )

        try:
            send_mail(
                subject="Your HRMS Password Reset OTP",
                message=f"Your OTP is: {otp}. It expires in 5 minutes.",
                from_email="noreply@hrms.com",
                recipient_list=[email],
                fail_silently=False
            )

            # ✅ On success, render page and trigger toast via cookie
            response = render(request, "core/forgot_password.html", {
                "user_id": user.user_id,
                "step": "otp"
            })
            response.set_cookie("toast", "otp_sent", max_age=3)
            return response

        except Exception:
            response = render(request, "core/forgot_password.html")
            response.set_cookie("toast", "otp_failed", max_age=3)
            return response

        
class VerifyOTPAjaxView(View):
    def post(self, request):
        user_id = request.POST.get("user_id")
        otp_input = request.POST.get("otp")

        try:
            otp_entry = PasswordResetOTP.objects.filter(user_id=user_id, is_used=False).order_by('-created_at').first()

            if not otp_entry:
                return JsonResponse({"success": False, "message": "No OTP found. Please request again."})

            if otp_entry.is_expired():
                return JsonResponse({"success": False, "message": "OTP expired. Request a new one."})

            if otp_entry.otp != otp_input:
                return JsonResponse({"success": False, "message": "Incorrect OTP."})

            otp_entry.is_used = True
            otp_entry.save()

            return JsonResponse({"success": True, "message": "OTP verified successfully."})
        except Exception:
            return JsonResponse({"success": False, "message": "Something went wrong."})
        

class ResendOTPView(View):
    def post(self, request, user_id):
        try:
            user = Users.objects.get(user_id=user_id)
        except Users.DoesNotExist:
            return JsonResponse({"success": False, "message": "User not found."})

        # Get latest OTP
        last_otp = PasswordResetOTP.objects.filter(user_id=user_id).order_by('-created_at').first()
        if last_otp and (timezone.now() - last_otp.created_at).total_seconds() < 30:
            return JsonResponse({"success": False, "message": "Please wait before requesting a new OTP."})

        # Generate and save new OTP
        new_otp = f"{random.randint(100000, 999999)}"
        PasswordResetOTP.objects.create(
            user_id=user_id,
            otp=new_otp,
            created_at=timezone.now(),
            is_used=False
        )

        try:
            send_mail(
                subject="Your New HRMS OTP",
                message=f"Your new OTP is: {new_otp}. It will expire in 5 minutes.",
                from_email="noreply@hrms.com",
                recipient_list=[user.email],
                fail_silently=False
            )
            return JsonResponse({"success": True, "message": "OTP resent successfully."})
        except Exception:
            return JsonResponse({"success": False, "message": "Failed to resend OTP."})


class ResetPasswordView(View):
    def post(self, request, user_idd):
        password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if not password or not confirm_password:
            return JsonResponse({"success": False, "message": "All fields are required."})

        if password != confirm_password:
            return JsonResponse({"success": False, "message": "Passwords do not match."})

        try:
            user = Users.objects.get(user_id=user_idd)
            user.password_hash = make_password(password)
            user.save()
            return JsonResponse({"success": True, "message": "Password reset successful."})
        except Users.DoesNotExist:
            return JsonResponse({"success": False, "message": "User not found."})


class HelpPageView(TemplateView):
    """Help & Support Page"""
    template_name = "core/help.html"

    def post(self, request):
        """Handles form submission and sends email to HR Admin"""
        name = request.POST.get("name", "").strip()
        email = request.POST.get("email", "").strip()
        subject = request.POST.get("subject", "").strip()
        message_body = request.POST.get("message", "").strip()

        if not name or not email or not subject or not message_body:
            messages.error(request, "All fields are required.")
            return render(request, self.template_name)

        # Construct a well-formatted email content
        full_message = f"""
    📌 Help Request from HR Management System 📌

    Sender Details:
    Name: {name}
    Email: {email}

    Subject: {subject}

    Message:
    {message_body}

    --------------------------------------------
    This is an automated message from the HR Management System.
    """

        try:
            send_mail(
                subject=f"Help Request - {subject}",
                message=full_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.HR_ADMIN_EMAIL], 
                fail_silently=False,
            )
            messages.success(request, "Your message has been submitted. We will get back to you soon!")
        except Exception as e:
            messages.error(request, "There was an error sending your message. Please try again later.")

        return render(request, self.template_name)


class TermsPrivacyView(TemplateView):
    """Terms & Privacy Page"""
    template_name = 'core/terms_privacy.html'
