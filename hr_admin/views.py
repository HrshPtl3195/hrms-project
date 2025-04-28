import pyodbc, os, openpyxl, logging, json, base64, pdfkit
from datetime import date
from PIL import Image
from django.contrib.auth.hashers import make_password
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import logout
from django.db import connection
from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import TemplateView, RedirectView
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest
from django.utils.cache import add_never_cache_headers
from django.http import JsonResponse
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet

logger = logging.getLogger(__name__)

class HRAdminRequiredMixin(LoginRequiredMixin):
    """ Custom Mixin to restrict access to HR Admins only """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if str(request.user.u_role).lower() != 'hr_admin':
            return redirect('access_denied')

        return super().dispatch(request, *args, **kwargs)


class HRAdminDashboardView(HRAdminRequiredMixin, View):
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
            cursor.execute("""SELECT COUNT(*) 
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE e.is_deleted = 0 AND u.u_role != 'HR_ADMIN';
                """)
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
        

class HRAdminProfileView(HRAdminRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            edit_data = self.get_employee_edit_modal_data(request.user.user_id)
            data = self.get_employee_data(request.user.user_id)

            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")

            # Merge `edit_data` into the main context
            context = {
                **data,
                "edit_data": edit_data
            }

        except Exception as e:
            logger.error("❌ Error fetching data:", exc_info=True)
            context = {}

        return render(request, "hr_admin/profile.html", context)
    
    def dictfetchone(self,cursor):
        row = cursor.fetchone()
        if row is None:
            return {}
        return {col[0]: row[idx] for idx, col in enumerate(cursor.description)}

    def dictfetchall(self,cursor):
        columns = [col[0] for col in cursor.description]
        return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_employee_edit_modal_data(self, user_id):
        with connection.cursor() as cursor:
            cursor.execute("EXEC GetEmployeeEditProfileData @user_id = %s", [user_id])

            contact_info = self.dictfetchone(cursor)

            cursor.nextset()
            academic_info = self.dictfetchone(cursor)

            cursor.nextset()
            references = self.dictfetchall(cursor)

            cursor.nextset()
            documents = self.dictfetchone(cursor)

            cursor.nextset()
            middle_info = self.dictfetchone(cursor)

        # Merge everything into a single dictionary
        return {
            # 🔹 Contact Info
            "current_email": contact_info.get("current_email", ""),
            "current_phone": contact_info.get("current_phone", ""),
            "permanent_email": contact_info.get("permanent_email", ""),
            "permanent_phone": contact_info.get("permanent_phone", ""),
            "current_address": contact_info.get("current_address", ""),
            "permanent_address": contact_info.get("permanent_address", ""),

            # 🔸 Academic Info
            "degree": academic_info.get("degree", "") if academic_info else "",
            "passing_year": academic_info.get("year_of_passing", "") if academic_info else "",
            "board_university": academic_info.get("board_university", "") if academic_info else "",
            "grade": academic_info.get("grade", "") if academic_info else "",

            # 🔹 References
            "references": references,
            "has_references": len(references) > 0,

            # 📄 Documents
            "has_passport": documents.get("has_passport", 0) == 1,
            "passport_expiring": documents.get("passport_expiring", 0) == 1,
            "has_sin": documents.get("has_sin", 0) == 1,
            "sin_expiring": documents.get("sin_expiring", 0) == 1,
            "has_work_permit": documents.get("has_work_permit", 0) == 1,
            "work_permit_expiring": documents.get("work_permit_expiring", 0) == 1,
            "has_license": documents.get("has_license", 0) == 1,
            "license_expiring": documents.get("license_expiring", 0) == 1,

            # 🟨 Middle Name / Gender
            "middle_name": middle_info.get("middle_name", ""),
            "show_middle_name_option": middle_info.get("gender", "").upper() == "FEMALE",
        }


    def get_employee_data(self, user_id):
        """ Fetch HR Admin profile details using stored procedure """

        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]
            # Execute stored procedure using EXEC instead of callproc()
            cursor.execute("EXEC GetEmployeeProfile @user_id = %s", [user_id])

            # Fetch Personal Information
            personal_info = cursor.fetchone()

            # Move to next result set (Academic Info)
            cursor.nextset()
            academic_info = cursor.fetchone()

            # Move to next result set (Job Info)
            cursor.nextset()
            job_info = cursor.fetchone()

            # Move to next result set (Profile Image)
            cursor.nextset()
            profile_image = cursor.fetchone()

        return {
            "user_name":user_name,
            "full_name": personal_info[1] if personal_info else "N/A",
            "current_email": personal_info[2] if personal_info else "N/A",
            "current_phone": personal_info[3] if personal_info else "N/A",
            "gender": personal_info[4] if personal_info else "N/A",
            "date_of_birth": personal_info[5] if personal_info else "N/A",
            "current_address": personal_info[6] if personal_info else "N/A",

            "degree": academic_info[0] if academic_info else "N/A",
            "passing_year": academic_info[1] if academic_info else "N/A",
            "board_university": academic_info[2] if academic_info else "N/A",

            "designation": job_info[0] if job_info else "N/A",
            "joining_date": job_info[1] if job_info else "N/A",
            "company_name": job_info[2] if job_info else "N/A",
            "old_designation": job_info[3] if job_info else "N/A",

            "profile_image": profile_image[0] if profile_image else "default.png",
        }
        
    def post(self, request):
        if request.FILES.get("profile_image"):
            try:
                user_id = request.user.user_id
                new_image = request.FILES["profile_image"]

                # Step 1: Get existing filename from DB
                with connection.cursor() as cursor:
                    cursor.execute("""
                        SELECT profile_image 
                        FROM other_documents 
                        WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)
                    """, [user_id])
                    row = cursor.fetchone()
                    old_file_path = row[0] if row else None

                # Step 2: Determine filename
                extension = new_image.name.split('.')[-1]
                if old_file_path:
                    filename = os.path.basename(old_file_path)
                else:
                    filename = f"user_{user_id}_profile.{extension}"

                folder_path = os.path.join(settings.MEDIA_ROOT, "profile")
                os.makedirs(folder_path, exist_ok=True)
                save_path = os.path.join(folder_path, filename)

                # Step 3: Open the uploaded image and crop to square
                image = Image.open(new_image)

                # Convert to RGB if needed (e.g., PNG with alpha)
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                width, height = image.size
                min_dim = min(width, height)
                left = (width - min_dim) // 2
                top = (height - min_dim) // 2
                right = left + min_dim
                bottom = top + min_dim
                image = image.crop((left, top, right, bottom))

                # Step 4: Save the cropped image
                image.save(save_path)

                # Step 5: Return relative path
                relative_path = os.path.relpath(save_path, settings.MEDIA_ROOT).replace("\\", "/")
                media_url = f"/media/{relative_path}"

                if not old_file_path:
                    return JsonResponse({"success": False, "error": "Failed to Save Photo.\nPlease Try Again Later!"})

                return JsonResponse({"success": True, "image_url": media_url})

            except Exception as e:
                logger.error("❌ Error updating profile image", exc_info=True)
                return JsonResponse({"success": False, "error": "Internal server error."})

        try:
            user_id = request.user.user_id

            # Get employee_id from user_id
            with connection.cursor() as cursor:
                cursor.execute("SELECT employee_id FROM employees WHERE user_id = %s", [user_id])
                row = cursor.fetchone()
                if not row:
                    return JsonResponse({"success": False, "error": "Employee not found."})
                employee_id = row[0]

            # 🔹 Get emp_file_id from DB for file naming
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT e.first_name, e.last_name, u.email, e.date_of_birth
                    FROM employees e
                    JOIN users u ON e.user_id = u.user_id
                    WHERE e.employee_id = %s
                """, [employee_id])
                row = cursor.fetchone()
                if not row:
                    return JsonResponse({"success": False, "error": "Employee data not found."})

                first_name, last_name, email, dob = row
                dob_clean = dob.strftime("%Y%m%d")

                def generate_employee_file_id(first_name, last_name, email, dob_str):
                    return f"{first_name[:2].lower()}{last_name[:2].lower()}{email[:2].lower()}_{dob_str}"

                emp_file_id = generate_employee_file_id(first_name, last_name, email, dob_clean)

            def save_uploaded_file(file, folder_name, emp_file_id, doc_type):
                if file:
                    folder_path = os.path.join(settings.MEDIA_ROOT, folder_name)
                    os.makedirs(folder_path, exist_ok=True)
                    ext = file.name.split('.')[-1]
                    file_name = f"{emp_file_id}_{doc_type}.{ext}"
                    full_path = os.path.join(folder_path, file_name)
                    with open(full_path, 'wb+') as f:
                        for chunk in file.chunks():
                            f.write(chunk)
                    return os.path.relpath(full_path, settings.MEDIA_ROOT)
                return None

            section = request.POST.get("section")
            with connection.cursor() as cursor:

                def escape(val):
                    return f"'{val}'" if val is not None else "NULL"

                def exec_update_proc(params):
                    if len(params) != 33:
                        raise ValueError("Exactly 33 parameters required.")

                    sql = f"""
                        EXEC UpdateEmployeeProfile 
                        {", ".join([escape(param) for param in params])}
                    """
                    cursor.execute(sql)

                if section == "contact":
                    exec_update_proc([
                        section, employee_id,
                        request.POST.get("current_email"), request.POST.get("permanent_email"),
                        request.POST.get("current_phone"), request.POST.get("permanent_phone"),
                        request.POST.get("current_address"), request.POST.get("permanent_address"),
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None
                    ])

                elif section == "academic":
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        request.POST.get("degree"), request.POST.get("passing_year"),
                        request.POST.get("board_university"), request.POST.get("grade"),
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None
                    ])

                elif section == "reference":
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        request.POST.get("reference_name"),
                        request.POST.get("reference_phone"),
                        request.POST.get("reference_email"),
                        request.POST.get("reference_relation"),
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None
                    ])

                elif section == "passport":
                    passport_path = save_uploaded_file(
                        request.FILES.get("passport_document"), "passport", emp_file_id, "passport"
                    )
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        request.POST.get("passport_number"),
                        request.POST.get("passport_issue_date"),
                        request.POST.get("passport_expiry_date"),
                        passport_path,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None
                    ])

                elif section == "sin":
                    sin_path = save_uploaded_file(
                        request.FILES.get("sin_document"), "sinCerti", emp_file_id, "sin"
                    )
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        request.POST.get("sin_number"),
                        request.POST.get("sin_issue_date"),
                        request.POST.get("sin_expiry_date"),
                        sin_path,
                        None, None, None, None,
                        None, None, None, None,
                        None
                    ])

                elif section == "permit":
                    permit_path = save_uploaded_file(
                        request.FILES.get("work_permit_document"), "workPermit", emp_file_id, "workpermit"
                    )
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        request.POST.get("work_permit_number"),
                        request.POST.get("work_permit_issue_date"),
                        request.POST.get("work_permit_expiry_date"),
                        permit_path,
                        None, None, None, None,
                        None
                    ])

                elif section == "license":
                    license_path = save_uploaded_file(
                        request.FILES.get("driving_license_document"), "drivingLicense", emp_file_id, "license"
                    )
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        request.POST.get("license_number"),
                        request.POST.get("license_issue_date"),
                        request.POST.get("license_expiry_date"),
                        license_path,
                        None
                    ])

                elif section == "middle":
                    exec_update_proc([
                        section, employee_id,
                        None, None, None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        None, None, None, None,
                        request.POST.get("middle_name")
                    ])

            # ✅ Redirect to trigger success toast
            return redirect("hr_profile")

        except Exception as e:
            logger.error("❌ Error updating profile info", exc_info=True)
            return JsonResponse({"success": False, "error": "Internal server error."})


class EmployeeManagementView(HRAdminRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")
 
        try:
            data = self.get_employee_data(request.user.user_id)

            # Get filters
            search_query = request.GET.get("q", "")
            page_number = int(request.GET.get("page", 1))
            page_size = 5

            # Fetch data
            employee_list, total_count, start, end = self.get_all_employees(
                request.user.user_id, search_query, page_number, page_size
            )

            paginator = Paginator(range(total_count), page_size)
            page_obj = paginator.get_page(page_number)

            data.update({
                "employee_list": employee_list,
                "page_obj": page_obj,
                "total_count": total_count,
                "start": start,
                "end": end,
            })

            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")

        except Exception as e:
            logger.error("❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hr_admin/employee_management.html", data)

    def get_employee_data(self, user_id):
        with connection.cursor() as cursor:
            # Get Profile Image
            cursor.execute(f"""
                SELECT e.first_name, e.middle_name, e.last_name
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE u.user_id = {user_id};
            """)
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})
            """)
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None


        return {
            "user_name": user_name,
            "profile_image": profile_image,
        }

    def get_all_employees(self, user_id, search_query="", page=1, page_size=5):
        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    e.employee_id,
                    e.first_name,
                    e.middle_name, 
                    e.last_name,
                    u.email,
                    e.designation,
                    e.date_of_joining,
                    od.profile_image,

                    -- 🔹 Contact Info
                    cd.current_email,
                    cd.current_phone,
                    cd.permanent_email,
                    cd.permanent_phone,
                    cd.current_address,
                    cd.permanent_address
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                LEFT JOIN employee_contact_details cd ON e.employee_id = cd.employee_id
                WHERE 
                    e.is_deleted = 0
                    AND u.u_role != 'HR_ADMIN'
                    AND u.user_id != %s
            """
            params = [user_id]

            if search_query:
                sql += """ AND (
                    LOWER(e.first_name) LIKE LOWER(%s) OR
                    LOWER(e.last_name) LIKE LOWER(%s) OR
                    LOWER(u.email) LIKE LOWER(%s)
                )"""
                search_term = f"%{search_query}%"
                params += [search_term, search_term, search_term]

            # Count total
            count_sql = f"SELECT COUNT(*) FROM ({sql}) AS total"
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]

            # Pagination
            offset = (page - 1) * page_size
            sql += " ORDER BY CONCAT(e.first_name, ' ', COALESCE(e.middle_name, ''), ' ', e.last_name) ASC OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
            params += [offset, page_size]

            cursor.execute(sql, params)
            rows = cursor.fetchall()

        employee_list = []
        for row in rows:
            full_name = f"{row[1]} {row[2]} {row[3]}".strip()
            employee_list.append({
                "employee_id": row[0],
                "name": full_name,
                "email": row[4],
                "designation": row[5],
                "joining_date": row[6].strftime("%b %d, %Y") if row[6] else "N/A",
                "profile_image": row[7] or "default.png",
                "contact": {
                    "current_email": row[8] or "",
                    "current_phone": row[9] or "",
                    "permanent_email": row[10] or "",
                    "permanent_phone": row[11] or "",
                    "current_address": row[12] or "",
                    "permanent_address": row[13] or "",
                }
            })

        start = (page - 1) * page_size + 1
        end = min(start + len(employee_list) - 1, total_count)
        return employee_list, total_count, start, end

    def post(self, request):
        try:
            section = request.POST.get("section")
            employee_id = request.POST.get("employee_id")
            
            with connection.cursor() as cursor:
                def escape(val):
                    return f"'{val}'" if val is not None else "NULL"

                def exec_update_proc(params):
                    if len(params) != 11:
                        raise ValueError("Exactly 11 parameters required for UpdateEmployeeBasicInfo.")
                    sql = f"""
                        EXEC UpdateEmployeeBasicInfo 
                        {", ".join([escape(p) for p in params])}
                    """
                    cursor.execute(sql)
                
                if section == "contact":
                    exec_update_proc([
                        employee_id,
                        section,
                        request.POST.get("current_email"),
                        request.POST.get("current_phone"),
                        request.POST.get("permanent_email"),
                        request.POST.get("permanent_phone"),
                        request.POST.get("current_address"),
                        request.POST.get("permanent_address"),
                        None,  # designation
                        None   # joining_date
                    ])
                elif section == "job":
                    exec_update_proc([
                        employee_id,
                        section,
                        None, None, None, None, None, None,
                        request.POST.get("new_designation"),
                        request.POST.get("new_joining_date")
                    ])
                else:
                    return JsonResponse({"success": False, "message": "Invalid section provided."})

            return JsonResponse({"success": True})

        except Exception as e:
            logger.error("❌ Error in UpdateEmployeeBasicInfo", exc_info=True)
            return JsonResponse({"success": False, "message": "Internal server error"})


class EmployeeSearchView(HRAdminRequiredMixin, View):
    def get(self, request):
        search_query = request.GET.get("q", "").strip().lower()
        page_number = int(request.GET.get("page", 1))
        page_size = 5

        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    e.employee_id,
                    e.first_name,
                    e.middle_name,
                    e.last_name,
                    u.email,
                    e.designation,
                    e.date_of_joining,
                    od.profile_image,

                    -- 🔹 Contact Info
                    cd.current_email,
                    cd.current_phone,
                    cd.permanent_email,
                    cd.permanent_phone,
                    cd.current_address,
                    cd.permanent_address
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                LEFT JOIN employee_contact_details cd ON e.employee_id = cd.employee_id
                WHERE e.is_deleted = 0 AND u.u_role != 'HR_ADMIN' AND u.user_id != %s
            """
            params = [request.user.user_id]

            # Enhanced Search Logic
            if search_query:
                search_terms = search_query.split()
                conditions = []

                for term in search_terms:
                    if len(term) == 1:
                        search_term = f"{term}%"
                        conditions.extend([
                            "LOWER(e.first_name) LIKE LOWER(%s)",
                            "LOWER(e.middle_name) LIKE LOWER(%s)",
                            "LOWER(e.last_name) LIKE LOWER(%s)",
                            "LOWER(u.email) LIKE LOWER(%s)"
                        ])
                        params.extend([search_term] * 4)
                    else:
                        full_name_search = f"%{term}%"
                        search_term = f"{term}%"
                        conditions.extend([
                            "LOWER(e.first_name) LIKE LOWER(%s)",
                            "LOWER(e.middle_name) LIKE LOWER(%s)",
                            "LOWER(e.last_name) LIKE LOWER(%s)",
                            "LOWER(u.email) LIKE LOWER(%s)",
                            "LOWER(CONCAT_WS(' ', e.first_name, COALESCE(e.middle_name, ''), e.last_name)) LIKE LOWER(%s)"
                        ])
                        params.extend([search_term, search_term, search_term, search_term, full_name_search])

                sql += " AND (" + " OR ".join(conditions) + ")"

            # Count total filtered results
            count_sql = f"SELECT COUNT(*) FROM ({sql}) AS total"
            cursor.execute(count_sql, params)
            total_count = cursor.fetchone()[0]

            # Pagination calculation
            offset = (page_number - 1) * page_size
            sql += " ORDER BY LOWER(e.first_name), LOWER(e.middle_name), LOWER(e.last_name)"
            sql += " OFFSET %s ROWS FETCH NEXT %s ROWS ONLY"
            params.extend([offset, page_size])

            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # Calculate the range for "Showing X to Y of Z entries"
        if total_count == 0:
            start_index = 0
            end_index = 0
        else:
            start_index = (page_number - 1) * page_size + 1
            end_index = min(start_index + page_size - 1, total_count)

        results = []
        for row in rows:
            full_name = f"{row[1]} {row[2] or ''} {row[3]}".strip()
            results.append({
                "employee_id": row[0],
                "name": full_name,
                "email": row[4],
                "designation": row[5],
                "joining_date": row[6].strftime("%b %d, %Y") if row[6] else "N/A",
                "profile_image": row[7] or "default.png",
                "contact": {
                    "current_email": row[8] or "",
                    "current_phone": row[9] or "",
                    "permanent_email": row[10] or "",
                    "permanent_phone": row[11] or "",
                    "current_address": row[12] or "",
                    "permanent_address": row[13] or "",
                }
            })

        return JsonResponse({
            "employees": results,
            "total_count": total_count,
            "page_number": page_number,
            "page_size": page_size,
            "start_index": start_index,
            "end_index": end_index
        })


class EmployeeExportView(HRAdminRequiredMixin, View):
    def get(self, request):
        search_query = request.GET.get("q", "")
        export_format = request.GET.get("format", "excel")

        with connection.cursor() as cursor:
            sql = """
                SELECT 
                    e.first_name,
                    e.middle_name,
                    e.last_name,
                    u.email,
                    e.designation,
                    e.date_of_joining
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE e.is_deleted = 0 AND u.u_role != 'HR_ADMIN' AND u.user_id != %s
            """
            params = [request.user.user_id]

            if search_query:
                sql += " AND (LOWER(e.first_name) LIKE LOWER(%s) OR LOWER(e.last_name) LIKE LOWER(%s) OR LOWER(u.email) LIKE LOWER(%s))"
                search_term = f"%{search_query}%"
                params += [search_term, search_term, search_term]

            sql += " ORDER BY e.date_of_joining DESC"

            cursor.execute(sql, params)
            rows = cursor.fetchall()

        # Excel Export
        if export_format == "excel":
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Employees"

            headers = ["Full Name", "Email", "Designation", "Joining Date"]
            ws.append(headers)

            for row in rows:
                full_name = f"{row[0]} {row[1]} {row[2]}".strip()
                ws.append([
                    full_name,
                    row[3],  # email
                    row[4],  # designation
                    row[5].strftime("%d-%m-%Y") if row[5] else ""
                ])

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename=EmployeeList.xlsx'
            wb.save(response)
            return response

        # PDF Export
        elif export_format == "pdf":
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="EmployeeList.pdf"'

            buffer = []

            # Setup the PDF
            doc = SimpleDocTemplate(response, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            # Title
            title = Paragraph("Employee List", styles["Title"])
            elements.append(title)
            elements.append(Spacer(1, 12))

            # Table Data
            table_data = [["Full Name", "Email", "Designation", "Joining Date"]]

            for row in rows:
                full_name = f"{row[0]} {row[1]} {row[2]}".strip()
                joining_date = row[5].strftime("%d-%m-%Y") if row[5] else ""
                table_data.append([
                    full_name,
                    row[3],  # email
                    row[4],  # designation
                    joining_date
                ])

            # Create table
            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))

            elements.append(table)

            # Build PDF
            doc.build(elements)
            return response


class EmployeeDeleteView(HRAdminRequiredMixin, View):
    def post(self, request, employee_id):
        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE employees SET is_deleted = 1 
                    WHERE employee_id = %s
                """, [employee_id])

            response = redirect("hr_employee_management")
            response.set_cookie("employeeDeleteStatus", "success", max_age=5)
            return response

        except Exception as e:
            logger.error("❌ Error deleting employee:", exc_info=True)
            response = redirect("hr_employee_management")
            response.set_cookie("employeeDeleteStatus", "error", max_age=5)
            return response


class AddEmployeeView(HRAdminRequiredMixin, TemplateView):
    template_name = "hr_admin/add_employee.html"

    def dispatch(self, request, *args, **kwargs):
        print("\n||  Add Employee Page Visited!  ||\n")
        if not request.user.is_authenticated:
            return redirect('login')  # Redirect unauthenticated users to login
        if request.user.u_role.lower() != 'hr_admin':
            return redirect('access_denied')  # Redirect unauthorized users to Access Denied page
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_employee_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
            # print()
            
        except Exception as e:
            logger.error("❌ Error fetching data:", exc_info=True)
            data = {}

        response = render(request, "hr_admin/add_employee.html", data)
        add_never_cache_headers(response)  # Prevent browser from caching the form
        return response

    def get_employee_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]
            
            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})
            """)
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None

        return {
            "user_name": user_name,
            "profile_image": profile_image,
        }
    
    def post(self, request):
        print("\n📂 Saving Employee Files...\n")

        # Retrieve Employee Details
        firstName = request.POST.get("firstName")
        lastName = request.POST.get("lastName")
        currentEmail = request.POST.get("currentEmail")
        dateOfBirth = request.POST.get("dateOfBirth")
        dob = dateOfBirth.strip().replace("-", "")

        # Generate Unique Employee ID for File Naming
        def generate_employee_file_id(first_name, last_name, email, dob):
            return f"{first_name[:2].lower()}{last_name[:2].lower()}{email[:2].lower()}_{dob}"

        emp_file_id = generate_employee_file_id(firstName, lastName, currentEmail, dob)
        # print(f"🔹 Generated Unique Employee File ID: {emp_file_id}")

        # Define File Saving Helper Function
        def save_uploaded_file(file, folder_name, emp_file_id, doc_type):
            if file:
                folder_path = os.path.join(settings.MEDIA_ROOT, folder_name)
                os.makedirs(folder_path, exist_ok=True)  # Create folder if it doesn’t exist
                file_extension = file.name.split('.')[-1]  # Get file extension
                file_name = f"{emp_file_id}_{doc_type}.{file_extension}"  # Rename file
                file_path = os.path.join(folder_path, file_name)

                with open(file_path, 'wb+') as destination:
                    for chunk in file.chunks():
                        destination.write(chunk)

                return os.path.relpath(file_path, settings.MEDIA_ROOT)  # Return relative path
            return None

        # Save Files and Get Paths
        passport_path = save_uploaded_file(request.FILES.get("passportFile"), "passport", emp_file_id, "passport")
        sin_path = save_uploaded_file(request.FILES.get("sinFile"), "sinCerti", emp_file_id, "sin")
        driving_license_path = save_uploaded_file(request.FILES.get("licenseFile"), "drivingLicense", emp_file_id, "license")
        work_permit_path = save_uploaded_file(request.FILES.get("prFile"), "workPermit", emp_file_id, "workpermit")
        offer_letter_path = save_uploaded_file(request.FILES.get("offerLetterFile"), "offerLetter", emp_file_id, "offerletter")
        contract_letter_path = save_uploaded_file(request.FILES.get("contractLetterFile"), "contractLetter", emp_file_id, "contractletter")
        
        # Crop and save profile image to square (centered)
        profile_image = request.FILES.get("profileImage")
        profile_image_path = None

        if profile_image:
            try:
                folder_path = os.path.join(settings.MEDIA_ROOT, "profile")
                os.makedirs(folder_path, exist_ok=True)

                file_extension = profile_image.name.split('.')[-1]
                filename = f"{emp_file_id}_profile.{file_extension}"
                save_path = os.path.join(folder_path, filename)

                # Open image
                image = Image.open(profile_image)

                # Convert if needed
                if image.mode in ("RGBA", "P"):
                    image = image.convert("RGB")

                # Crop to square
                width, height = image.size
                min_dim = min(width, height)
                left = (width - min_dim) // 2
                top = (height - min_dim) // 2
                right = left + min_dim
                bottom = top + min_dim
                image = image.crop((left, top, right, bottom))

                # Save cropped image
                image.save(save_path)

                # Set relative path
                profile_image_path = f"profile/{filename}"

            except Exception as e:
                logger.error("❌ Error processing profile image", exc_info=True)
                profile_image_path = None


        print("\n✅ File Paths Generated:")
        print(f"Passport: {passport_path}")
        print(f"SIN Certificate: {sin_path}")
        print(f"Driving License: {driving_license_path}")
        print(f"Work Permit: {work_permit_path}")
        print(f"Offer Letter: {offer_letter_path}")
        print(f"Contract Letter: {contract_letter_path}")
        print(f"Profile Image: {profile_image_path}")

        # Manually retrieving form data from request.POST
        # Personal Information
        middleName = request.POST.get("middleName")
        gender = request.POST.get("gender")
        dateOfBirth = request.POST.get("dateOfBirth")
        placeOfBirth = request.POST.get("placeOfBirth")
        nationality = request.POST.get("nationality")
        
        criminalRecord = "YES" if request.POST.get("criminalRecord", "no").strip().lower() == "yes" else "NO"
        
        userRole = request.POST.get("userRole", "").strip().upper()
        if userRole == "OA":
            userRole = "OFFICE_ADMIN"
        elif userRole == "EM":
            userRole = "EMPLOYEE"
        elif userRole == "HY":
            userRole = "HYBRID"
        # print(userRole)

        currentPhone = request.POST.get("currentPhone")
        permanentPhone = request.POST.get("permanentPhone")
        currentEmail = request.POST.get("currentEmail")
        permanentEmail = request.POST.get("permanentEmail")
        currentAddress = request.POST.get("currentAddress")
        permanentAddress = request.POST.get("permanentAddress")
        rawPassword = request.POST.get("passwordField")
        password = make_password(rawPassword)
        rawConfirmPassword = request.POST.get("confirmPasswordField")
        confirmPassword = make_password(rawConfirmPassword)
        
        # Academic Information
        highestDegree = request.POST.get("highestDegree")
        passingYear = request.POST.get("passingYear")
        boardUniversity = request.POST.get("boardUniversity")
        result = request.POST.get("result")
        
        # Current Job Details
        dateOfJoining = request.POST.get("dateOfJoining")
        designation = request.POST.get("designation")
        
        date_fields = ["passportIssueDate", "passportExpiryDate", "prInforceFrom", 
               "prExpiryDate", "sinIssueDate", "sinExpiryDate", 
               "licenseIssueDate", "licenseExpiryDate", "employmentFrom", "employmentTo"]

        dates = {field: request.POST.get(field, "").strip() or None for field in date_fields}
        
        # Passport Information
        passportNumber = request.POST.get("passportNumber") or "" 
        passportIssueDate = dates["passportIssueDate"]
        passportExpiryDate = dates["passportExpiryDate"]
        passportFile =  passport_path if passport_path else ""
        
        # PR/Work Permit Information
        permitCheck = 0
        prNumber = request.POST.get("prNumber") or ""
        prInforceFrom = dates["prInforceFrom"]
        prExpiryDate = dates["prExpiryDate"]
        prFile = work_permit_path if work_permit_path else ""
        if prNumber != "":
            permitCheck = 1
            
        # Driving License Information
        licenseNumber = request.POST.get("licenseNumber") or ""
        licenseIssueDate = dates["licenseIssueDate"]
        licenseExpiryDate = dates["licenseExpiryDate"]
        licenseFile = driving_license_path if driving_license_path else ""
        
        # SIN Certificate Information
        sinCheck = 0
        sinNumber = request.POST.get("sinNumber") or None
        sinIssueDate = dates["sinIssueDate"]
        sinExpiryDate = dates["sinExpiryDate"]
        sinFile = sin_path if sin_path else ""
        if sinNumber != None:
            sinCheck = 1
            
        # Employment History
        historyCheck = 0
        companyName = request.POST.get("companyName") or ""
        designationEH = request.POST.get("designationEH") or ""
        employmentFrom = dates["employmentFrom"]
        employmentTo = dates["employmentTo"]
        if companyName != "":
            historyCheck = 1
            
        # Extracting Multiple References from Form
        referenceCheck = 0
        reference_names = request.POST.getlist("referenceName[]")
        reference_contacts = request.POST.getlist("referencePhone[]")  # Maps to reference_contact
        reference_emails = request.POST.getlist("referenceEmail[]")
        reference_relationships = request.POST.getlist("referenceType[]")  # Professional/Personal
        if reference_names != [""]:
            referenceCheck = 1
        
        # Convert lists into comma-separated strings
        reference_name_str = ",".join(reference_names)
        reference_contact_str = ",".join(reference_contacts)
        reference_email_str = ",".join(reference_emails)
        relationship_str = ",".join(reference_relationships)

        # print("\n", reference_name_str, reference_email_str, reference_contact_str, relationship_str)
        
        # Document Upload
        profileImage = profile_image_path if profile_image_path else ""
        offerLetterFile = offer_letter_path if offer_letter_path else ""
        contractLetterFile = contract_letter_path if contract_letter_path else ""
        
        # Debugging: Print received data
        print("\n\nReceived Employee Data:")
        print(f"Name: {firstName} {middleName} {lastName}, Gender: {gender}, DOB: {dateOfBirth}, Place of Birth: {placeOfBirth}, Nationality: {nationality}")
        print(f"Criminal Record: {criminalRecord}, Email: {currentEmail} / {permanentEmail}, Phone: {currentPhone} / {permanentPhone}")
        print(f"Address: {currentAddress} / {permanentAddress}")
        print(f"Password: {password} / {confirmPassword}")
        print(f"Academic: {highestDegree}, {boardUniversity}, {passingYear}, {result}")
        print(f"Current Job: {dateOfJoining}, {designation}")
        print(f"Passport: {passportNumber}, {passportIssueDate}, {passportExpiryDate}")
        print(f"License: {licenseNumber}, {licenseIssueDate}, {licenseExpiryDate}")
        print(f"Permit: {prNumber}, {prInforceFrom}, {prExpiryDate}")
        print(f"SIN: {sinNumber}, {sinIssueDate}, {sinExpiryDate}")
        print(f"History: {companyName}, {designationEH}, {employmentFrom}, {employmentTo}")
        # print(f"{relationship}: {referenceName}, {referencePhone}, {referenceEmail}, {relationship}")
        
        
        print("\n📂 Uploaded Files", request.FILES.keys())
        if passportFile:
            print(f"✅ Passport File: {passportFile}")
        else:
            print("❌ No Passport File Uploaded")

        if prFile:
            print(f"✅ PR/Work Permit File: {prFile}")
        else:
            print("❌ No PR/Work Permit File Uploaded")

        if licenseFile:
            print(f"✅ Driving License File: {licenseFile}")
        else:
            print("❌ No Driving License File Uploaded")

        if sinFile:
            print(f"✅ SIN Certificate File: {sinFile}")
        else:
            print("❌ No SIN Certificate File Uploaded")

        if profileImage:
            print(f"✅ Profile Image File: {profileImage}")
        else:
            print("❌ No Profile Image Uploaded")

        if offerLetterFile:
            print(f"✅ Offer Letter File: {offerLetterFile}")
        else:
            print("❌ No Offer Letter File Uploaded")

        if contractLetterFile:
            print(f"✅ Contract Letter File: {contractLetterFile}")
        else:
            print("❌ No Contract Letter File Uploaded")
        
        try:
            # Establish DB connection
            server = 'HARSH'
            database = 'HRMS'
            driver = 'ODBC Driver 17 for SQL Server'

            # Create connection string
            conn_str = f"""
                DRIVER={{{driver}}};
                SERVER={server};
                DATABASE={database};
                Trusted_Connection=yes;
                TrustServerCertificate=yes;
            """
            conn=None
            # Establish connection
            try:
                conn = pyodbc.connect(conn_str)
                cursor = conn.cursor()
                print("✅ Connected to the SQL Server Database Successfully!")
                
                # Run a test query
                cursor.execute("SELECT 1")
                print("Test Query Result:", cursor.fetchone())

            except Exception as e:
                print("❌ Error connecting to the database:", e)

            
            cursor = conn.cursor()
            
            # Parameters for stored procedure
            params = (
                'add_employee',  # Operation Type

                # Optional Table Flags
                sinCheck,
                permitCheck,
                historyCheck,
                referenceCheck,
                
                # Users Table Fields 
                currentEmail,  # email
                password,  # password_hash (should be hashed in production)
                userRole,  # u_role

                # Employees Table Fields
                None,  # user_id (Auto-generated)
                firstName
                ,middleName
                ,lastName
                ,gender
                ,dateOfBirth
                ,placeOfBirth
                ,nationality
                ,criminalRecord
                ,dateOfJoining
                ,designation
                
                ,currentAddress
                ,permanentAddress
                ,currentEmail
                ,permanentEmail
                ,currentPhone
                ,permanentPhone
                
                ,passportNumber
                ,passportIssueDate
                ,passportExpiryDate
                ,passportFile
                
                ,prNumber
                ,prInforceFrom
                ,prExpiryDate
                ,prFile
                
                ,sinNumber
                ,sinIssueDate
                ,sinExpiryDate
                ,sinFile
                
                ,licenseNumber
                ,licenseIssueDate
                ,licenseExpiryDate
                ,licenseFile
                
                # Academic Details Table Fields
                ,highestDegree
                ,boardUniversity
                ,passingYear
                ,result

                # Employment History Table Fields
                ,companyName
                ,designationEH
                ,employmentFrom
                ,employmentTo

                # Employee References Table Fields
                ,reference_name_str
                ,reference_contact_str
                ,reference_email_str
                ,relationship_str

                # Documents 
                ,profileImage
                ,offerLetterFile
                ,contractLetterFile
            )

            print(f"Provided: {len(params)}") 
            # Execute stored procedure
            cursor.execute("""
            EXEC ManageEmployees ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?; 
            """,params)
            
            # Commit transaction
            conn.commit()
            print(f"✅ Inserted Employee")
            response = redirect("hr_employee_management")
            response.set_cookie("employeeAddStatus", "success", max_age=5)
            return response

        
        except Exception as e:
            if conn:
                conn.rollback()  # Rollback only if connection exists
            print(f"❌ Error: {e}")  # Debugging
            response = redirect("hr_employee_management")
            response.set_cookie("employeeAddStatus", "error", max_age=5)
            return response

        
        finally:
            # 🔄 Close Cursor and Connection if Open
            if cursor:
                cursor.close()
            if conn:
                conn.close()
                print("🔄 Connection closed.\n")


class LeaveApprovalView(HRAdminRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            data = self.get_leave_data(request.user.user_id)
            
            data.update(self.get_leave_list(request, request.user.user_id))

            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")

        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hr_admin/leave_approval.html", data)

    def get_leave_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]
            
            # Total number of pending leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'PENDING'
                AND (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN';""")
            total_pending_leaves = cursor.fetchone()[0]

            # Total number of leaves applied
            cursor.execute(f"SELECT MAX(total_leaves) FROM leaves")
            total_leaves = cursor.fetchone()[0]
            # print(total_leaves)
            total_leaves = 15 if total_leaves == None else total_leaves
            # print(total_leaves)

            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})
            """)
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            # Total number of approved leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'APPROVED'
                AND (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN' 
                AND approved_by = {user_id};""")
            total_approved_leaves = cursor.fetchone()[0]

            # Total number of rejected leaves
            cursor.execute(f"""SELECT COUNT(*)
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE l.L_status = 'REJECTED'
                AND (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN'
                AND approved_by = {user_id};""")
            total_rejected_leaves = cursor.fetchone()[0]

        return {
            "user_name":user_name,
            "profile_image": profile_image,
            "total_leaves": total_leaves,
            "total_pending_leaves": total_pending_leaves,
            "total_approved_leaves": total_approved_leaves,
            "total_rejected_leaves": total_rejected_leaves
        }

    def get_leave_list(self, request, user_id):
        search_query = request.GET.get("q", "")
        page_number = int(request.GET.get("page", 1))
        page_size = 5

        def sort_leaves(leaves):
            return sorted(
                leaves,
                key=lambda x: (
                    0 if x['status'] == 'PENDING' else 1,
                    x['L_start_date']
                ),
                reverse=False
            )

        with connection.cursor() as cursor:
            base_sql = f"""
                SELECT l.leave_id, 
                    e.first_name, 
                    e.last_name, 
                    l.leave_type, 
                    l.L_start_date, 
                    l.L_end_date, 
                    l.L_status,
                    l.leave_reason, 
                    od.profile_image
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON od.employee_id = e.employee_id
                WHERE (SELECT u_role FROM users WHERE user_id = {user_id}) = 'HR_ADMIN'
                    AND (
                        (l.L_status = 'PENDING')
                        OR
                        (l.L_status = 'APPROVED' AND l.approved_by = {user_id})
                        OR
                        (l.L_status = 'REJECTED' AND l.approved_by = {user_id})
                    )
            """
            params = []

            if search_query:
                base_sql += " AND (e.first_name LIKE %s OR e.last_name LIKE %s)"
                like_query = f"%{search_query}%"
                params += [like_query, like_query]

            # Execute without ORDER BY to avoid SQL Server subquery issues
            cursor.execute(base_sql, params)
            rows = cursor.fetchall()

        # Convert rows to structured dicts
        all_leaves = [{
            "leave_id": row[0],
            "first_name": row[1],
            "last_name": row[2],
            "leave_type": row[3],
            "L_start_date": row[4],
            "L_end_date": row[5],
            "status": row[6],
            "leave_reason": row[7],
            "profile_image": row[8] or "default.png"
        } for row in rows]

        # Sort by PENDING first, then by start date DESC
        sorted_leaves = sort_leaves(all_leaves)

        # Total before pagination
        total_count = len(sorted_leaves)

        # Python-side pagination
        paginator = Paginator(sorted_leaves, page_size)
        page_obj = paginator.get_page(page_number)
        page_data = page_obj.object_list

        # Transform final paginated list
        leave_list = [{
            "leave_id": item["leave_id"],
            "employee_name": f"{item['first_name']} {item['last_name']}",
            "leave_type": item["leave_type"],
            "start_date": item["L_start_date"].strftime("%b %d, %Y"),
            "end_date": item["L_end_date"].strftime("%b %d, %Y"),
            "status": item["status"],
            "reason": item["leave_reason"],
            "profile_image": item["profile_image"]
        } for item in page_data]

        # Indexes for display
        start_index = (page_number - 1) * page_size + 1
        end_index = min(start_index + page_size - 1, total_count)

        return {
            "leave_list": leave_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "start": start_index,
            "end": end_index
        }


class LeaveActionView(HRAdminRequiredMixin, View):
    def post(self, request):
        leave_id = request.POST.get("leave_id")
        action = request.POST.get("action")  # APPROVED or REJECTED
        hr_user_id = request.user.user_id

        try:
            with connection.cursor() as cursor:
                # Update leave
                cursor.execute("""
                    UPDATE leaves
                    SET L_status = %s, approved_by = %s
                    WHERE leave_id = %s
                """, [action, hr_user_id, leave_id])

                # Get employee details and leave info
                cursor.execute("""
                    SELECT u.email, e.first_name, e.last_name, l.leave_type, 
                           l.L_start_date, l.L_end_date, l.leave_reason
                    FROM users u
                    JOIN employees e ON e.user_id = u.user_id
                    JOIN leaves l ON l.employee_id = e.employee_id
                    WHERE l.leave_id = %s
                """, [leave_id])
                row = cursor.fetchone()

                if row:
                    email, first_name, last_name, leave_type, start_date, end_date, reason = row
                    full_name = f"{first_name} {last_name}"
                    total_days = (end_date - start_date).days + 1

                    subject = f"Leave Request {action.title()} – HR Management System"

                    message = f"""
                    <html>
                    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                        <div style="max-width: 600px; margin: auto; padding: 20px; border: 1px solid #eee; border-radius: 8px;">
                            <h2 style="color: #1B9AF5;">Leave Request {action.title()}</h2>

                            <p>Dear {full_name},</p>

                            <p>Your <strong>{leave_type}</strong> leave request with ID <strong>{leave_id}</strong> has been 
                            <strong style="color: {'green' if action == 'APPROVED' else 'red'};">{action.title()}</strong> by the HR department.</p>

                            <p><strong>Leave Duration:</strong> {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')} ({total_days} day{'s' if total_days > 1 else ''})</p>
                            <p><strong>Reason:</strong> {reason}</p>

                            <p>If you have any questions regarding this decision, please contact your HR manager.</p>

                            <p>Thank you,<br>
                            <strong>HR Management System</strong></p>

                            <hr style="margin-top: 30px;"/>
                            <p style="font-size: 12px; color: #777;">
                                This is an automated message. Please do not reply to this email.
                            </p>
                        </div>
                    </body>
                    </html>
                    """

                    send_mail(
                        subject=subject,
                        message="",
                        html_message=message,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email]
                    )

            return JsonResponse({"success": True})
        except Exception as e:
            logger.error("❌ Leave approval failed", exc_info=True)
            return JsonResponse({"success": False, "error": str(e)})


class LeaveExportView(HRAdminRequiredMixin, View):
    def get(self, request):
        export_format = request.GET.get("format", "excel")

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT e.first_name, e.last_name, l.leave_type, l.L_start_date, l.L_end_date, l.L_status, l.leave_reason
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON e.user_id = u.user_id
                WHERE approved_by = {request.user.user_id}
                ORDER BY l.created_at DESC""")
            rows = cursor.fetchall()

        if export_format == "excel":
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Leave Requests"

            headers = ["Employee", "Leave Type", "From", "To",'Reason', "Status"]
            ws.append(headers)

            for row in rows:
                full_name = f"{row[0]} {row[1]}"
                ws.append([
                    full_name,
                    row[2],
                    row[3].strftime("%d-%m-%Y"),
                    row[4].strftime("%d-%m-%Y"),
                    row[6],
                    row[5]
                ])
            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = f'attachment; filename=LeaveRequests.xlsx'
            wb.save(response)
            return response

        elif export_format == "pdf":
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="LeaveRequests.pdf"'

            doc = SimpleDocTemplate(response, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = [Paragraph("Leave Requests", styles["Title"])]

            table_data = [["Employee", "Leave Type", "From", "To",'Reason', "Status"]]
            for row in rows:
                table_data.append([
                    f"{row[0]} {row[1]}",
                    row[2],
                    row[3].strftime("%d-%m-%Y"),
                    row[4].strftime("%d-%m-%Y"),
                    row[6],
                    row[5]
                ])

            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))

            elements.append(table)
            doc.build(elements)
            return response


class PayrollView(HRAdminRequiredMixin, TemplateView):
    template_name = "hr_admin/payroll.html"

    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            data = self.get_payroll_data(request.user.user_id)
            data["employee_list"] = self.get_employee_list_for_dropdown(request.user.user_id)

            # Filters
            page_number = int(request.GET.get("page", 1))
            page_size = 5

            # Get payroll list
            payslip_list, total_count, start, end = self.get_all_payslips(page_number, page_size, request.user.user_id)
            paginator = Paginator(range(total_count), page_size)
            page_obj = paginator.get_page(page_number)

            data.update({
                "payslip_list": payslip_list,
                "page_obj": page_obj,
                "total_count": total_count,
                "start": start,
                "end": end,
            })

            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
        except Exception as e:
            logger.error("❌ Error fetching payroll data:", exc_info=True)
            data = {}

        return render(request, self.template_name, data)

    def get_payroll_data(self, user_id):
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.first_name, e.middle_name, e.last_name
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE u.user_id = %s
            """, [user_id])
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            cursor.execute("SELECT ISNULL(SUM(salary), 0) FROM payslips WHERE generated_by = %s", [user_id])
            total_payroll = cursor.fetchone()[0]

            cursor.execute("""SELECT COUNT(*) 
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE e.is_deleted = 0 AND u.u_role != 'HR_ADMIN';
                """)
            total_employees = cursor.fetchone()[0]
            
            cursor.execute("""
                SELECT COUNT(*)
                FROM payslips
                WHERE MONTH(period_ending) = 4
                AND YEAR(period_ending) = 2025
                AND generated_by = %s
            """, [user_id])
            payslips_this_month = cursor.fetchone()[0]

            cursor.execute("""
                SELECT ISNULL(SUM(project_bonus + leadership_bonus), 0)
                FROM payslips
                WHERE MONTH(period_ending) = 4
                AND YEAR(period_ending) = 2025
                AND generated_by = %s
            """, [user_id])
            total_bonuses_this_month = cursor.fetchone()[0]
            
            cursor.execute("SELECT profile_image FROM other_documents WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = %s)", [user_id])
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None

        return {
            "user_name": user_name,
            "profile_image": profile_image,
            "total_upcoming_payroll": total_payroll,
            "total_employees": total_employees,
            "total_bonuses_this_month": total_bonuses_this_month,
            "payslips_this_month": payslips_this_month
        }
        
    def get_employee_list_for_dropdown(self, user_id):
        with connection.cursor() as cursor:
            query="""
                SELECT 
                    e.employee_id,
                    CONCAT(e.first_name, ' ', COALESCE(e.middle_name, ''), ' ', e.last_name) AS full_name,
                    od.profile_image,
                    e.designation
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE 
                    e.is_deleted = 0
                    AND u.u_role != 'HR_ADMIN'
                    AND u.user_id != %s
                ORDER BY full_name
                """
            cursor.execute(query, [user_id])
            rows = cursor.fetchall()

        return [{
            "employee_id": row[0],
            "full_name": row[1],
            "profile_image": row[2] or "default.png",
            "designation": row[3]
        } for row in rows]

    def get_all_payslips(self, page, page_size, user_id):
        with connection.cursor() as cursor:
            base_sql = f"""
                SELECT 
                    p.payslip_id,
                    p.employee_id,
                    CONCAT(e.first_name, ' ', COALESCE(e.middle_name, ''), ' ', e.last_name) AS full_name,
                    e.designation,
                    p.salary,
                    (p.project_bonus + p.leadership_bonus) AS bonuses,
                    p.net_pay,
                    p.period_ending,
                    p.pay_date,
                    ISNULL(od.profile_image, 'default.png') AS profile_image
                FROM payslips p
                JOIN employees e ON p.employee_id = e.employee_id
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE p.generated_by = {user_id}
            """

            # ✅ Fix: Wrap with column names for subquery
            count_sql = f"""
                SELECT COUNT(*) FROM (
                    {base_sql}
                ) AS total
            """
            cursor.execute(count_sql)
            total_count = cursor.fetchone()[0]

            # ✅ Main paginated query with ORDER BY + OFFSET
            paginated_sql = base_sql + """
                ORDER BY p.date_generated DESC
                OFFSET %s ROWS FETCH NEXT %s ROWS ONLY
            """
            offset = (page - 1) * page_size
            cursor.execute(paginated_sql, [offset, page_size])
            rows = cursor.fetchall()

        payslip_list = []
        for row in rows:
            payslip_list.append({
                "payslip_id": row[0],
                "employee_id": row[1],
                "name": row[2].strip(),
                "designation": row[3],
                "base_salary": float(row[4]),
                "bonuses": float(row[5]),
                "total": float(row[6]),
                "period": row[7].strftime("%b %Y"),
                "pay_date": row[8].strftime("%d %b %Y"),
                "profile_image": row[9],
            })

        start = (page - 1) * page_size + 1
        end = min(start + len(payslip_list) - 1, total_count)
        return payslip_list, total_count, start, end


class GeneratePayslipsView(HRAdminRequiredMixin, View):
    def post(self, request):
        try:
            data = json.loads(request.body)
            payslips = data.get("payslips", [])
            today = date.today()
            period_end = today.replace(day=28)
            month = today.strftime("%b").upper()
            year = today.year

            emails_to_notify = []
            
            with connection.cursor() as cursor:
                for slip in payslips:
                    employee_id = slip["employee_id"]
                    regular = float(slip["regular_income"])
                    project = float(slip.get("project_bonus", 0))
                    leadership = float(slip.get("leadership_bonus", 0))
                    cpp = float(slip["cpp"])
                    ei = float(slip["ei"])
                    it = float(slip["income_tax"])
                    
                    gross = regular + project + leadership
                    total_deductions = cpp + ei + it
                    net = gross - total_deductions
                    
                    if regular != 0:
                        # 1️⃣ Insert into payslips table (skip computed fields like salary/deductions/net_pay)
                        cursor.execute("""
                            INSERT INTO payslips (
                                employee_id, regular_income, project_bonus, leadership_bonus,
                                cpp, ei, income_tax,
                                period_ending, pay_date, generated_by, emailed
                            )
                            OUTPUT INSERTED.payslip_id
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
                        """, [
                            employee_id, regular, project, leadership,
                            cpp, ei, it,
                            period_end, today, request.user.user_id
                        ])
                        payslip_id = cursor.fetchone()[0]

                        # 2️⃣ Insert into payroll_summary (manual computation needed for gross, net)
                        cursor.execute("""
                            INSERT INTO payroll_summary (
                                employee_id, month_name, year,
                                gross, cpp, ei, income_tax, net, payslip_id
                            )
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, [
                            employee_id, month, year,
                            gross, cpp, ei, it, net, payslip_id
                        ])

                        # 3️⃣ Get employee email (assuming you have an employee table)
                        cursor.execute("""
                            SELECT 
                                CONCAT(e.first_name, ' ', 
                                    ISNULL(e.middle_name + ' ', ''), 
                                    e.last_name) AS full_name,
                                c.current_email
                            FROM employees e
                            JOIN employee_contact_details c ON e.employee_id = c.employee_id
                            WHERE e.employee_id = %s
                            """, [employee_id])
                        result = cursor.fetchone()
                        print(result)
                        if result:
                            full_name, email = result
                            emails_to_notify.append((full_name, email))
                        
            # 4️⃣ Send email notifications
            for name, email in emails_to_notify:
                try:
                    send_mail(
                        subject="Payslip Generated",
                        message=(
                            f"Dear {name},\n\n"
                            f"Your payslip for {month} {year} has been successfully generated. "
                            f"You can now log in to the HRMS portal to download it.\n\n"
                            f"Best regards,\nHR Team"
                        ),
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[email],
                        fail_silently=False,
                    )
                except Exception as mail_err:
                    print(f"⚠️ Failed to send email to {email}: {mail_err}")

            return JsonResponse({"success": True})

        except Exception as e:
            print("❌ Error in generate_payslips:", e)
            return JsonResponse({"success": False, "error": str(e)})


class ExportPayslipsView(HRAdminRequiredMixin, View):
    def get(self, request):
        export_format = request.GET.get("format", "excel")

        with connection.cursor() as cursor:
            cursor.execute(f"""
                SELECT 
                    CONCAT(e.first_name, ' ', COALESCE(e.middle_name, ''), ' ', e.last_name) AS full_name,
                    e.designation,
                    p.salary,
                    (p.project_bonus + p.leadership_bonus) AS bonuses,
                    p.net_pay,
                    p.period_ending,
                    p.pay_date
                FROM payslips p
                JOIN employees e ON p.employee_id = e.employee_id
                WHERE p.generated_by = {request.user.user_id}
                ORDER BY p.date_generated DESC
            """)
            rows = cursor.fetchall()

        # 📄 Excel Export
        if export_format == "excel":
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "Payslips"

            headers = ["Employee", "Designation", "Gross Salary", "Bonuses", "Net Pay", "Period", "Pay Date"]
            ws.append(headers)

            for row in rows:
                ws.append([
                    row[0],  # full name
                    row[1] or "N/A",  # designation
                    float(row[2]),   # salary
                    float(row[3]),   # bonuses
                    float(row[4]),   # net pay
                    row[5].strftime("%b %Y") if row[5] else "",
                    row[6].strftime("%d-%m-%Y") if row[6] else ""
                ])

            response = HttpResponse(
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            response["Content-Disposition"] = 'attachment; filename=PayrollList.xlsx'
            wb.save(response)
            return response

        # 🧾 PDF Export
        elif export_format == "pdf":
            response = HttpResponse(content_type='application/pdf')
            response['Content-Disposition'] = 'attachment; filename="PayrollList.pdf"'

            doc = SimpleDocTemplate(response, pagesize=A4)
            styles = getSampleStyleSheet()
            elements = []

            elements.append(Paragraph("Payroll Summary", styles["Title"]))
            elements.append(Spacer(1, 12))

            table_data = [["Employee", "Designation", "Gross", "Bonus", "Net", "Period", "Pay Date"]]

            for row in rows:
                table_data.append([
                    row[0],
                    row[1] or "N/A",
                    f"${float(row[2]):,.2f}",
                    f"${float(row[3]):,.2f}",
                    f"${float(row[4]):,.2f}",
                    row[5].strftime("%b %Y") if row[5] else "",
                    row[6].strftime("%d-%m-%Y") if row[6] else ""
                ])

            table = Table(table_data, repeatRows=1)
            table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightblue),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ]))

            elements.append(table)
            doc.build(elements)
            return response


class DownloadPayslipPDFView(HRAdminRequiredMixin, TemplateView):
    def post(self, request):
        employee_id = request.POST.get('employee_id')
        payslip_id = request.POST.get('payslip_id')
        with connection.cursor() as cursor:
            cursor.execute("""
                    SELECT user_id
                    FROM employees
                    WHERE employee_id = %s
                """, [employee_id])
            user_id = cursor.fetchone()[0]
        
        if not employee_id:
            return HttpResponseBadRequest("Employee ID is required.")
        
        current_year = date.today().year

        # Fetch employee core info
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT e.employee_id, e.first_name, e.middle_name, e.last_name
                FROM employees e
                WHERE e.user_id = %s
            """, [user_id])
            emp = cursor.fetchone()
            emp_id, first, middle, last = emp
            full_name = f"{first} {middle or ''} {last}".strip()
            emp_code = f"E{emp_id}"

            # Fetch address
            cursor.execute("SELECT current_address FROM employee_contact_details WHERE employee_id = %s", [emp_id])
            address_row = cursor.fetchone()
            address = address_row[0] if address_row else "N/A"

            # Latest payslip (for current month)
            cursor.execute("""
                SELECT regular_income, project_bonus, leadership_bonus,
                       cpp, ei, income_tax, net_pay, pay_date
                FROM payslips
                WHERE employee_id = %s AND YEAR(period_ending) = %s AND payslip_id = %s
                ORDER BY pay_date DESC
            """, [emp_id, current_year, payslip_id])
            latest = cursor.fetchone()
            
            reg, proj, lead, cpp, ei, it, net, pay_date = latest if latest else (0, 0, 0, 0, 0, 0, 0, date.today())

            # 🧮 YTD Deductions from payslips
            cursor.execute("""
                SELECT ISNULL(SUM(cpp), 0), ISNULL(SUM(ei), 0), ISNULL(SUM(income_tax), 0)
                FROM payslips
                WHERE employee_id = %s AND YEAR(period_ending) = %s AND payslip_id = %s
            """, [emp_id, current_year, payslip_id])
            ytd_cpp, ytd_ei, ytd_it = cursor.fetchone()

            # 🧮 YTD Gross, Deductions, Net from payroll_summary
            cursor.execute("""
                SELECT ISNULL(SUM(gross), 0), ISNULL(SUM(cpp + ei + income_tax), 0), ISNULL(SUM(net), 0)
                FROM payroll_summary
                WHERE employee_id = %s AND year = %s AND payslip_id = %s
            """, [emp_id, current_year, payslip_id])
            ytd_gross, ytd_deductions, ytd_net = cursor.fetchone()

            cursor.execute("""
                SELECT month_name, 
                    ISNULL(gross, 0), ISNULL(income_tax, 0), ISNULL(cpp, 0), ISNULL(ei, 0), ISNULL(net, 0)
                FROM payroll_summary
                WHERE employee_id = %s AND year = %s AND payslip_id = %s
            """, [emp_id, current_year, payslip_id])
            monthly_data = cursor.fetchall()

        # Initialize month map
        month_names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]

        month_summary = {m: {"gross": "", "it": "", "cpp": "", "ei": "", "ded": "", "net": ""} for m in month_names}

        # Fill data into dict
        for row in monthly_data:
            mname = row[0].upper()
            gross, it, cpp, ei, net = row[1:]
            if mname in month_summary:
                ded = it + cpp + ei
                month_summary[mname] = {
                    "gross": f"{gross:,.2f}" if gross else "",
                    "it": f"{it:,.2f}" if it else "",
                    "cpp": f"{cpp:,.2f}" if cpp else "",
                    "ei": f"{ei:,.2f}" if ei else "",
                    "ded": f"{ded:,.2f}" if ded else "",
                    "net": f"{net:,.2f}" if net else "",
                }

        # Calculate totals
        total = {"gross": 0, "it": 0, "cpp": 0, "ei": 0, "ded": 0, "net": 0}
        for m in month_summary.values():
            total["gross"] += float(m["gross"].replace(",", "") or 0)
            total["it"] += float(m["it"].replace(",", "") or 0)
            total["cpp"] += float(m["cpp"].replace(",", "") or 0)
            total["ei"] += float(m["ei"].replace(",", "") or 0)
            total["ded"] += float(m["ded"].replace(",", "") or 0)
            total["net"] += float(m["net"].replace(",", "") or 0)

        # 📄 Generate salary history table rows
        page2_rows = ""
        for m in month_names:
            row = month_summary[m]
            page2_rows += f"""
                <tr>
                    <td>{m}</td>
                    <td>{row['gross']}</td>
                    <td>{row['it']}</td>
                    <td>{row['cpp']}</td>
                    <td>{row['ei']}</td>
                    <td>{row['ded']}</td>
                    <td>{row['net']}</td>
                </tr>
            """

        # Final row for totals
        page2_rows += f"""
            <tr style="background-color: yellow;">
                <td>TOTAL</td>
                <td>{total['gross']:,.2f}</td>
                <td>{total['it']:,.2f}</td>
                <td>{total['cpp']:,.2f}</td>
                <td>{total['ei']:,.2f}</td>
                <td>{total['ded']:,.2f}</td>
                <td>{total['net']:,.2f}</td>
            </tr>
        """

        # ✅ Convert logo
        image_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'aureus.png')
        with open(image_path, "rb") as img_file:
            b64_image = base64.b64encode(img_file.read()).decode("utf-8")

        # ✅ Construct HTML
        html_string = f"""
        <!DOCTYPE html>
        <html><head><meta charset="UTF-8" />
        <style>
            body {{ margin: 0; padding: 20px; font-family: Arial; font-size: 14px; }}
            .header {{ display: flex; justify-content: space-between; margin-bottom: -20px; }}
            .logo img {{ height: 80px; margin-top: 50px; }}
            .company-details {{ text-align: right; margin-top: -80px; line-height: 1.5; }}
            .paystub-title {{ background: #444; color: white; text-align: center; padding: 5px; font-weight: bold; margin: 20px 0 5px; }}
            table {{ width: 100%; border-collapse: collapse; margin-top: 10px; text-align: center; }}
            th, td {{ border: 1px solid #ccc; padding: 6px; }}
            th {{ background: #f4f4f4; }}
            .red {{ color: red; font-weight: bold; }}
            .text-left {{ text-align: left; padding-left: 8px; }}
        </style>
        </head><body>

        <div class="header">
            <div class="logo"><img src="data:image/png;base64,{b64_image}" alt="Logo"></div>
            <div class="company-details">
                <strong>Aureus Infotech Inc.</strong><br>
                7250 Keele St. #381<br>
                Vaughan, ON, L4K 1Z8<br>
                <a href="mailto:info@aureusinfotech.com">info@aureusinfotech.com</a><br>
                www.aureusinfotech.com<br>
                Tel: +1-416-890-8380
            </div>
        </div>

        <div class="paystub-title">PAYSTUB</div>
        <div><strong>{full_name.upper()}</strong><br>{address}</div>

        <table>
            <tr class="red">
                <th>EMPLOYEE ID</th><th>PERIOD ENDING</th><th>PAY DATE</th><th>CHEQUE NUMBER</th>
            </tr>
            <tr>
                <td>{emp_code}</td><td>{pay_date.strftime("%d-%m-%y")}</td><td>{pay_date.strftime("%d-%m-%y")}</td><td>Direct Deposit</td>
            </tr>
        </table>

        <table>
            <tr>
                <th>INCOME</th><th>RATE</th><th>HOURS</th><th>CURRENT TOTAL</th>
                <th>DEDUCTIONS</th><th>CURRENT TOTAL</th><th>YTD</th>
            </tr>
            <tr>
                <td class="text-left">REGULAR</td><td></td><td></td><td>{reg:.2f}</td>
                <td class="text-left">CPP</td><td>{cpp:.2f}</td><td>{ytd_cpp:.2f}</td>
            </tr>
            <tr>
                <td class="text-left">PROJECT BONUS</td><td></td><td></td><td>{proj:.2f}</td>
                <td class="text-left">EI</td><td>{ei:.2f}</td><td>{ytd_ei:.2f}</td>
            </tr>
            <tr>
                <td class="text-left">LEADERSHIP BONUS</td><td></td><td></td><td>{lead:.2f}</td>
                <td class="text-left">INCOME TAX</td><td>{it:.2f}</td><td>{ytd_it:.2f}</td>
            </tr>
        </table>

        <table>
            <tr>
                <th>YTD GROSS</th><th>YTD DEDUCTIONS</th><th>YTD NET PAY</th>
                <th>CURRENT TOTAL</th><th>DEDUCTIONS</th><th>NET PAY</th>
            </tr>
            <tr>
                <td>{ytd_gross:.2f}</td><td>{ytd_deductions:.2f}</td><td>{ytd_net:.2f}</td>
                <td>{reg + proj + lead:.2f}</td><td>{cpp + ei + it:.2f}</td><td>{net:.2f}</td>
            </tr>
        </table>
        <div style="page-break-before: always;"></div>
        <h2 style="text-align: center;">Salary History - {current_year}</h2>
        <table border="1" cellspacing="0" cellpadding="6" style="width: 100%; border-collapse: collapse; text-align: center;">
            <thead style="background-color: #ADD8E6;">
                <tr>
                    <th>MONTH</th><th>GROSS</th><th>IT</th><th>CPP</th><th>EI</th><th>TOT DED</th><th>NET</th>
                </tr>
            </thead>
            <tbody>
                {page2_rows}
            </tbody>
        </table>

        </body></html>
        """

        # PDF Generation using pdfkit
        path_to_wkhtmltopdf = r"D:\WKHTMLTOX\wkhtmltopdf\bin\wkhtmltopdf.exe"
        config = pdfkit.configuration(wkhtmltopdf=path_to_wkhtmltopdf)
        pdf_data = pdfkit.from_string(html_string, False, configuration=config)

        response = HttpResponse(pdf_data, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="Payslip.pdf"'
        return response

   
class LogoutView(RedirectView):
    """Logs out the user and clears session data"""
    url = "/login/"  # Redirects to login after logout

    def get(self, request, *args, **kwargs):
        logout(request)
        request.session.flush()  # Completely clear session

        response = super().get(request, *args, **kwargs)
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response


class AccessDeniedView(View):
    """ Custom View to handle 403 Access Denied error """
    def get(self, request):
        return render(request, "hr_admin/403.html", status=403)
