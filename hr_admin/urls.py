from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import (
    HRAdminDashboardView, HRAdminProfileView, EmployeeManagementView,
    LeaveApprovalView, PayrollView, AddEmployeeView, LogoutView, AccessDeniedView,
    LeaveActionView, EmployeeSearchView, EmployeeExportView, EmployeeDeleteView,
    LeaveExportView, GeneratePayslipsView, ExportPayslipsView
)

urlpatterns = [
    path('dashboard/', HRAdminDashboardView.as_view(), name='hr_dashboard'),
    path('profile/', HRAdminProfileView.as_view(), name='hr_profile'),
    path('employee-management/', EmployeeManagementView.as_view(), name='hr_employee_management'),
    path('leave-approval/', LeaveApprovalView.as_view(), name='hr_leave_approval'),
    path('payroll/', PayrollView.as_view(), name='hr_payroll'),
    path("generate-payslips/", GeneratePayslipsView.as_view(), name="generate_payslipsH"),
    path("payroll/export/", ExportPayslipsView.as_view(), name="export_payslips"),
    path('add-employee/', AddEmployeeView.as_view(), name='hr_add_employee'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('access-denied/', AccessDeniedView.as_view(), name='access_denied'),
    path('leave-action/', LeaveActionView.as_view(), name='hr_leave_action'),
    path("hr-employee-search/", EmployeeSearchView.as_view(), name="hr_employee_search"),
    path("hr-employee-export/", EmployeeExportView.as_view(), name="hr_employee_export"),
    path("employee/delete/<int:employee_id>/", EmployeeDeleteView.as_view(), name="hr_delete_employee"),
    path("hr-leave-export/", LeaveExportView.as_view(), name="hr_leave_export"),
]
 
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)