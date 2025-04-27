from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import (
    HybridDashboardView, HybridProfileView, EmployeeManagementView,
    LeaveApprovalView, PayrollView, MyPayrollView, AddEmployeeView,
    LeaveManagementView, RequestLeaveView, LogoutView, LeaveActionView,
    AccessDeniedView, EmployeeSearchView, EmployeeExportView, EmployeeDeleteView,
    LeaveExportView, CancelLeaveRequestView, DownloadLeavePDFView,
    GeneratePayslipsView, ExportPayslipsView, DownloadPayslipPDFView,
    EmployeeDashboardView
)

urlpatterns = [
    path('o_dashboard/', HybridDashboardView.as_view(), name='hybrid_office_admin_dashboard'),
    path('o_profile/', HybridProfileView.as_view(), name='hybrid_office_admin_profile'),
    path('o_employee-management/', EmployeeManagementView.as_view(), name='hybrid_office_admin_employee_management'),
    path('o_leave-approval/', LeaveApprovalView.as_view(), name='hybrid_office_admin_leave_approval'),
    path('o_payroll/', PayrollView.as_view(), name='hybrid_office_admin_payroll'),
    path("o_generate-payslips/", GeneratePayslipsView.as_view(), name="generate_payslipsHb"),
    path('o_mypayroll/', MyPayrollView.as_view(), name='hybrid_office_admin_my_payroll'),
    path("o_payroll/export/", ExportPayslipsView.as_view(), name="export_payslips"),
    path('o_mypayroll/download/', DownloadPayslipPDFView.as_view(), name='download_my_payslip'),
    path('o_add-employee/', AddEmployeeView.as_view(), name='hybrid_office_admin_add_employee'),
    path('o_leave-management/', LeaveManagementView.as_view(), name='hybrid_office_admin_leave_management'),
    path('o_request-leave/', RequestLeaveView.as_view(), name='hybrid_office_admin_request_leave'),
    path('o_access-denied/', AccessDeniedView.as_view(), name='access_denied'),
    path('o_leave-action/', LeaveActionView.as_view(), name='hybrid_office_admin_leave_action'),
    path("o_office-employee-search/", EmployeeSearchView.as_view(), name="hybrid_office_admin_employee_search"),
    path("o_office-employee-export/", EmployeeExportView.as_view(), name="hybrid_office_admin_employee_export"),
    path("o_employee/delete/<int:employee_id>/", EmployeeDeleteView.as_view(), name="hybrid_office_admin_delete_employee"),
    path("o_office-leave-export/", LeaveExportView.as_view(), name="hybrid_office_admin_leave_export"),
    path('o_logout/', LogoutView.as_view(), name='logout'),
    path('o_office-cancel-leave/', CancelLeaveRequestView.as_view(), name='hybrid_office_admin_cancel_leave_request'),
    path('o_office-download-leave-pdf/<int:leave_id>/', DownloadLeavePDFView.as_view(), name='hybrid_office_admin_download_leave_pdf'),
    
    
    path('e_dashboard/', EmployeeDashboardView.as_view(), name='hybrid_employee_dashboard'),
    path('e_profile/', HybridProfileView.as_view(), name='hybrid_employee_profile'),
    path('e_leave-management/', LeaveManagementView.as_view(), name='hybrid_employee_leave_management'),
    path('e_request-leave/', RequestLeaveView.as_view(), name='hybrid_employee_request_leave'),
    path('e_payroll/', MyPayrollView.as_view(), name='hybrid_employee_payroll'),
    path('e_mypayroll/download/', DownloadPayslipPDFView.as_view(), name='download_my_payslipE'),
    path('e_logout/', LogoutView.as_view(), name='logout'),
    path('e_cancel-leave/', CancelLeaveRequestView.as_view(), name='cancel_leave_request'),
    path('e_download-leave-pdf/<int:leave_id>/', DownloadLeavePDFView.as_view(), name='download_leave_pdf'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)