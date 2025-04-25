class HRAdminDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        if not hasattr(request.user, "user_id"):
            return redirect("login")

        try:
            logger.info(f"🔹 Fetching data for user ID: {request.user.user_id}")
            data = self.get_dashboard_data(request.user.user_id)
            
            if data.get("profile_image"):
                data["profile_image"] = data["profile_image"].replace("\\", "/")
            # logger.debug(data)
            # print()
            
        except Exception as e:
            logger.error("❌ Error fetching data:", exc_info=True)
            data = {}

        return render(request, "hr_admin/dashboard.html", data)

    def get_dashboard_data(self, user_id):
        """ Fetch HR dashboard statistics using raw SQL queries """
        with connection.cursor() as cursor:
            
            # Total number of employees
            cursor.execute("SELECT COUNT(*) FROM employees WHERE is_deleted = 0")
            total_employees = cursor.fetchone()[0]

            # Total number of pending leaves
            cursor.execute("SELECT COUNT(*) FROM leaves WHERE L_status = 'PENDING'")
            total_pending_leaves = cursor.fetchone()[0]

            # Total upcoming payroll (Sum of salaries)
            cursor.execute("SELECT ISNULL(SUM(salary), 0) FROM payslips")
            total_upcoming_payroll = cursor.fetchone()[0]

            # Number of unique designations (departments)
            cursor.execute("SELECT COUNT(DISTINCT designation) FROM employees WHERE is_deleted = 0")
            total_departments = cursor.fetchone()[0]

            # Total number of leaves applied
            cursor.execute("SELECT COUNT(*) FROM leaves")
            total_leaves = cursor.fetchone()[0]

            # Get Profile Image (First Available)
            cursor.execute(f"""
                SELECT profile_image 
                FROM other_documents 
                WHERE employee_id = (SELECT employee_id FROM employees WHERE user_id = 4)
            """)
            profile_image = cursor.fetchone()
            profile_image = profile_image[0] if profile_image else None
            
            # Total number of approved leaves
            cursor.execute("SELECT COUNT(*) FROM leaves WHERE L_status = 'APPROVED'")
            total_approved_leaves = cursor.fetchone()[0]

            # Total number of rejected leaves
            cursor.execute("SELECT COUNT(*) FROM leaves WHERE L_status = 'REJECTED'")
            total_rejected_leaves = cursor.fetchone()[0]

        return {
            "total_employees": total_employees,
            "total_pending_leaves": total_pending_leaves,
            "total_upcoming_payroll": total_upcoming_payroll,
            "total_departments": total_departments,
            "total_leaves": total_leaves,
            "profile_image": profile_image,
            "total_approved_leaves": total_approved_leaves,
            "total_rejected_leaves": total_rejected_leaves
        }