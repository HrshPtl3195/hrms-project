import os, logging, io, pdfkit, base64
from PIL import Image
from datetime import date
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth import logout
from django.views import View
from django.views.generic import TemplateView, RedirectView
from django.db import connection
from django.shortcuts import render, redirect
from django.conf import settings
from django.http import JsonResponse
from django.http import FileResponse, Http404, JsonResponse, HttpResponse
from django.core.paginator import Paginator
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_JUSTIFY
from django.core.mail import send_mail

logger = logging.getLogger(__name__)

class EmployeeRequiredMixin(LoginRequiredMixin):
    """ Custom Mixin to restrict access to HR Admins only """
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('login')

        if str(request.user.u_role).lower() != 'employee':
            return redirect('access_denied')

        return super().dispatch(request, *args, **kwargs)


class EmployeeDashboardView(EmployeeRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
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
        
        
class EmployeeProfileView(EmployeeRequiredMixin, TemplateView):
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

        return render(request, "employee/profile.html", context)
    
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
            return redirect("employee_profile")

        except Exception as e:
            logger.error("❌ Error updating profile info", exc_info=True)
            return JsonResponse({"success": False, "error": "Internal server error."})


class LeaveManagementView(EmployeeRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            # Get pagination parameters
            page_number = int(request.GET.get("page", 1))
            page_size = 5

            # Fetch data
            data = self.get_data(request.user.user_id, page_number, page_size)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "employee/leave_management.html", data)

    def get_data(self, user_id, page_number=1, page_size=5):
        with connection.cursor() as cursor:
            # Fetch user name
            cursor.execute(f"""
                SELECT e.first_name, e.middle_name, e.last_name 
                FROM employees e
                JOIN users u ON e.user_id = u.user_id
                WHERE u.user_id = {user_id};
            """)
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            # Total leaves
            cursor.execute(f"""
                SELECT MAX(total_leaves) 
                FROM leaves 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});
            """)
            total_leaves = cursor.fetchone()[0]
            total_leaves = 15 if total_leaves is None else total_leaves
            
            # Pending requests
            cursor.execute(f"""
                SELECT COUNT(*) 
                FROM leaves 
                WHERE L_status = 'PENDING' 
                AND employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});
            """)
            pending_requests = cursor.fetchone()[0]

            # Leaves left
            cursor.execute(f"""
                SELECT (MAX(total_leaves) - COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)) AS leaves_left
                FROM leaves 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});
            """)
            leaves_left = cursor.fetchone()[0]
            leaves_left = 0 if leaves_left is None else leaves_left
            leaves_taken = total_leaves - leaves_left

            # Profile image
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});
            """)
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            # Fetch leave history using stored procedure
            cursor.execute("EXEC GetEmployeeLeaveHistory @user_id = %s", [user_id])
            leave_history = cursor.fetchall()

            # Pagination logic
            total_count = len(leave_history)
            offset = (page_number - 1) * page_size
            paginated_history = leave_history[offset:offset + page_size]

            start_index = offset + 1 if total_count > 0 else 0
            end_index = min(start_index + page_size - 1, total_count)

            # Convert rows to dict
            leave_list = []
            for row in paginated_history:
                leave_list.append({
                    "leave_id": row[0],
                    "type": row[1],
                    "start": row[2].strftime("%b %d, %Y"),
                    "end": row[3].strftime("%b %d, %Y"),
                    "days": row[4],
                    "status": row[5]
                })

        # Paginator object
        paginator = Paginator(range(total_count), page_size)
        page_obj = paginator.get_page(page_number)

        return {
            "user_name": user_name,
            "profile_image": profile_image,
            "total_leaves": total_leaves,
            "leaves_taken": leaves_taken,
            "leave_left": leaves_left,
            "pending_requests": pending_requests,
            "leave_list": leave_list,
            "page_obj": page_obj,
            "total_count": total_count,
            "start_index": start_index,
            "end_index": end_index,
        }


class DownloadLeavePDFView(EmployeeRequiredMixin, View):
    def get(self, request, leave_id):
        user_id = request.user.user_id

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                SELECT 
                    e.first_name, e.last_name, e.designation,
                    l.leave_type, l.L_start_date, l.L_end_date, l.L_status,
                    l.L_apply_date, l.leave_reason, e.employee_id
                FROM leaves l
                JOIN employees e ON l.employee_id = e.employee_id
                JOIN users u ON u.user_id = e.user_id
                WHERE l.leave_id = %s AND e.user_id = %s
                """, [leave_id, user_id])
                row = cursor.fetchone()

                if not row:
                    raise Http404("Leave not found.")

                # Unpack details
                full_name = f"{row[0]} {row[1]}"
                designation = row[2]
                leave_type = row[3]
                start_date = row[4].strftime("%B %d, %Y")
                end_date = row[5].strftime("%B %d, %Y")
                total_days = (row[5] - row[4]).days + 1
                status = row[6].capitalize()
                apply_date = row[7].strftime("%B %d, %Y")
                reason = row[8]
                employee_id = row[9]

            # Create PDF
            buffer = io.BytesIO()
            doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=50, bottomMargin=50)
            styles = getSampleStyleSheet()
            normal = styles["Normal"]
            justified = ParagraphStyle(name="Justified", parent=normal, alignment=TA_JUSTIFY)
            bold = ParagraphStyle(name='Bold', parent=normal, fontName='Helvetica-Bold')
            spacer = Spacer(1, 12)

            story = []

            # Space to push below header
            story.append(Spacer(1, 90))
            story.append(Paragraph(f"<b>Date:</b> {date.today().strftime('%B %d, %Y')}", normal))
            story.append(Paragraph(f"<b>Leave Application Date:</b> {apply_date}", normal))
            story.append(spacer)

            recipient = [
                "To,",
                f"Name: <b>{full_name}</b>",
                f"ID: <b>{employee_id}</b>",
                f"Dsgn.: <b>{designation}</b>"
            ]

            for line in recipient:
                story.append(Paragraph(line, normal))
            story.append(spacer)

            story.append(Paragraph("<b>Subject: Leave Status Notification</b>", bold))
            story.append(spacer)

            if status.upper() == "CANCELLED":
                body = [
                    f"Dear {full_name},",
                    f"This is to confirm that your leave request from <b>{start_date}</b> to <b>{end_date}</b> "
                    f"(<b>{total_days} day(s)</b>) has been <b>CANCELLED</b> as per your request.",
                    "The request has been withdrawn from the system and will not be processed further.",
                    "",
                    "Sincerely,",
                    "<b>HR Department</b>",
                    "Aureus Infotech India"
                ]
            else:
                body = [
                    f"Dear {full_name},",
                    f"We have received your request for leave from <b>{start_date}</b> to <b>{end_date}</b> "
                    f"(<b>Total: {total_days} day(s)</b>) for the reason: <br/><br/><b>\"{reason}\"</b>",
                f"We are pleased to inform you that your leave has been <b>{status.upper()}</b> by the HR department.",
                "You are kindly advised to ensure proper handover and communication with your reporting manager before proceeding on leave.",
                "If you have any questions, please contact HR at the above details.",
                "We appreciate your continued dedication to <b>Aureus Infotech India</b>.",
                "Sincerely,",
                "<b>HR Department</b>",
                "Aureus Infotech India"
            ]

            for paragraph in body:
                story.append(Paragraph(paragraph, justified))
                story.append(spacer)

            # ✅ Header rendering function
            def draw_header(canvas, doc):
                width, height = A4
                logo_path = os.path.join(settings.BASE_DIR, 'static/images/aureus.png')
                if os.path.exists(logo_path):
                    canvas.drawImage(logo_path, 50, height - 80, width=1.8 * inch, height=0.6 * inch, mask='auto')

                canvas.setFont("Helvetica", 9)
                details = [
                    "Aureus Infotech India",
                    "123 Corporate Avenue, Phase II",
                    "Bangalore, Karnataka – 560001",
                    "Phone: +91-9876543210",
                    "Email: hr@aureusinfotech.com"
                ]
                y = height - 40
                for line in details:
                    canvas.drawRightString(width - 50, y, line)
                    y -= 12

                canvas.line(50, y - 5, width - 50, y - 5)

            # ✅ Build with header
            doc.build(story, onFirstPage=draw_header)

            buffer.seek(0)
            return FileResponse(buffer, as_attachment=True, filename=f"leave_{leave_id}.pdf")

        except Exception as e:
            logger.error("❌ Error generating leave PDF", exc_info=True)
            raise Http404("Unable to generate leave letter.")


class CancelLeaveRequestView(EmployeeRequiredMixin, View):
    def post(self, request):
        leave_id = request.POST.get("leave_id")
        user_id = request.user.user_id

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT l.leave_id 
                    FROM leaves l
                    INNER JOIN employees e ON l.employee_id = e.employee_id
                    WHERE l.leave_id = %s AND l.L_status = 'PENDING' AND e.user_id = %s
                """, [leave_id, user_id])
                record = cursor.fetchone()

                if not record:
                    response = redirect("employee_leave_management")
                    response.set_cookie("leaveCancelStatus", "error", max_age=5)
                    return response

                cursor.execute("""
                    UPDATE leaves 
                    SET L_status = 'CANCELLED' 
                    WHERE leave_id = %s
                """, [leave_id])

                response = redirect("employee_leave_management")
                response.set_cookie("leaveCancelStatus", "success", max_age=5)
                return response

        except Exception as e:
            logger.error("❌ Error cancelling leave request", exc_info=True)
            response = redirect("employee_leave_management")
            response.set_cookie("leaveCancelStatus", "error", max_age=5)
            return response


class RequestLeaveView(EmployeeRequiredMixin, TemplateView):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            data = self.get_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
        except Exception as e:
            logger.error("\n❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "employee/request_leave.html", data)

    def get_data(self, user_id):
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT e.first_name, e.middle_name, e.last_name \
                FROM employees e\
                JOIN users u ON e.user_id = u.user_id\
                WHERE u.user_id = {user_id};")
            user = cursor.fetchone()
            user_name = user[0] + " " + user[2]

            cursor.execute(f"SELECT MAX(total_leaves) FROM leaves WHERE \
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            total_leaves = cursor.fetchone()[0]
            total_leaves = 15 if total_leaves == None else total_leaves
            
            cursor.execute(f"SELECT COUNT(*) FROM leaves WHERE L_status = 'PENDING' and\
                employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})")
            pending_requests = cursor.fetchone()[0]

            cursor.execute(f"SELECT (MAX(total_leaves) - COUNT(CASE WHEN L_status = 'APPROVED' THEN 1 END)) AS leaves_left\
            FROM leaves WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id});")
            leaves_taken = cursor.fetchone()[0]
            leaves_taken = 0 if leaves_taken == None else leaves_taken
            
            leaves_left = total_leaves - leaves_taken          
            
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = {user_id})""") # change 4 to variable for user id
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
        return {
            "user_name": user_name,
            "profile_image": profile_image,
            "total_leaves": total_leaves,
            "leaves_taken": leaves_taken,
            "leave_left": leaves_left,
            "pending_requests": pending_requests,
        }

    def post(self, request):
        user_id = request.user.user_id

        leave_type = request.POST.get("leaveType")
        start_date = request.POST.get("startDate")
        end_date = request.POST.get("endDate")
        reason = request.POST.get("reason")
        
        if not all([leave_type, start_date, end_date, reason]):
            return JsonResponse({"success": False, "error": "Missing required fields."})

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT employee_id, first_name, middle_name, last_name FROM employees WHERE user_id = %s", [user_id])
                result = cursor.fetchone()

                if not result:
                    return JsonResponse({"success": False, "error": "Employee not found."})

                employee_id, first_name, middle_name, last_name = result
                full_name = f"{first_name} {middle_name} {last_name}".strip()
                apply_date = date.today()
                status = 'PENDING'

                # Insert leave record
                cursor.execute("""
                    INSERT INTO leaves (
                        employee_id, leave_type, L_apply_date, 
                        L_start_date, L_end_date, leave_reason, L_status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, [
                    employee_id,
                    leave_type,
                    apply_date,
                    start_date,
                    end_date,
                    reason,
                    status
                ])

            # Email HR Admin
            subject = f"📝 New Leave Request from {full_name}"
            message = f"""
Dear HR Admin,

A new leave request has been submitted by the following employee:

👤 Name: {full_name}
📅 Leave Type: {leave_type}
📆 Start Date: {start_date}
📆 End Date: {end_date}
📝 Reason: {reason}
📤 Applied On: {apply_date}

Please review and take appropriate action in the HRMS portal.

Regards,  
HRMS System
            """
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[settings.HR_ADMIN_EMAIL],
                fail_silently=False,
            )

            return JsonResponse({"success": True})

        except Exception as e:
            logger.error("❌ Error submitting leave request", exc_info=True)
            return JsonResponse({"success": False, "error": "Something went wrong."})


class MyPayrollView(EmployeeRequiredMixin, TemplateView):
    template_name = 'employee/mypayroll.html'

    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        with connection.cursor() as cursor:
            # Get employee ID
            cursor.execute("SELECT employee_id FROM employees WHERE user_id = %s", [request.user.user_id])
            row = cursor.fetchone()
            employee_id = row[0] if row else None
                    
            # Fetch profile and name
            cursor.execute("""
                SELECT e.first_name, e.middle_name, e.last_name, od.profile_image
                FROM employees e
                LEFT JOIN other_documents od ON e.employee_id = od.employee_id
                WHERE e.employee_id = %s
            """, [employee_id])
            emp = cursor.fetchone()
            user_name = f"{emp[0]} {emp[2]}"
            profile_image = emp[3] if emp[3] else "default.png"

            # Current month data
            today = date.today()
            cursor.execute("""
                SELECT regular_income, project_bonus, leadership_bonus, cpp, ei, income_tax
                FROM payslips
                WHERE MONTH(period_ending) = %s AND YEAR(period_ending) = %s AND employee_id = %s
            """, [today.month, today.year, employee_id])
            current = cursor.fetchone()
            
            current_salary = current[0] if current else 0
            total_bonus = (current[1] + current[2]) if current else 0
            deductions = (current[3] + current[4] + current[5]) if current else 0

            # Payslip count
            cursor.execute("SELECT COUNT(*) FROM payslips WHERE employee_id = %s", [employee_id])
            payslip_count = cursor.fetchone()[0]

            # Salary History
            cursor.execute("""
                SELECT 
                    period_ending, regular_income, 
                    project_bonus + leadership_bonus AS bonus,
                    cpp + ei + income_tax AS deductions,
                    net_pay
                FROM payslips
                WHERE employee_id = %s
                ORDER BY period_ending DESC
            """, [employee_id])
            rows = cursor.fetchall()

            history = [{
                "month": row[0].strftime("%B %Y"),
                "salary": f"${float(row[1]):,.2f}",
                "bonus": f"${float(row[2]):,.2f}",
                "deductions": f"${float(row[3]):,.2f}",
                "net": f"${float(row[4]):,.2f}",
            } for row in rows]
            
        return render(request, self.template_name, {
            "user_name": user_name,
            "profile_image": profile_image,
            "current_salary": f"${current_salary:,.2f}",
            "total_bonus": f"${total_bonus:,.2f}",
            "deductions": f"${deductions:,.2f}",
            "payslip_count": payslip_count,
            "salary_history": history
        })


class DownloadPayslipPDFView(EmployeeRequiredMixin, TemplateView):
    def get(self, request):
        user_id = request.user.user_id
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
                WHERE employee_id = %s AND YEAR(period_ending) = %s
                ORDER BY pay_date DESC
            """, [emp_id, current_year])
            latest = cursor.fetchone()

            reg, proj, lead, cpp, ei, it, net, pay_date = latest if latest else (0, 0, 0, 0, 0, 0, 0, date.today())

            # 🧮 YTD Deductions from payslips
            cursor.execute("""
                SELECT ISNULL(SUM(cpp), 0), ISNULL(SUM(ei), 0), ISNULL(SUM(income_tax), 0)
                FROM payslips
                WHERE employee_id = %s AND YEAR(period_ending) = %s
            """, [emp_id, current_year])
            ytd_cpp, ytd_ei, ytd_it = cursor.fetchone()

            # 🧮 YTD Gross, Deductions, Net from payroll_summary
            cursor.execute("""
                SELECT ISNULL(SUM(gross), 0), ISNULL(SUM(cpp + ei + income_tax), 0), ISNULL(SUM(net), 0)
                FROM payroll_summary
                WHERE employee_id = %s AND year = %s
            """, [emp_id, current_year])
            ytd_gross, ytd_deductions, ytd_net = cursor.fetchone()

            cursor.execute("""
                SELECT month_name, 
                    ISNULL(gross, 0), ISNULL(income_tax, 0), ISNULL(cpp, 0), ISNULL(ei, 0), ISNULL(net, 0)
                FROM payroll_summary
                WHERE employee_id = %s AND year = %s
            """, [emp_id, current_year])
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
