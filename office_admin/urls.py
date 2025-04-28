from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from .views import (
    OfficeAdminDashboardView, OfficeAdminProfileView, EmployeeManagementView,
    LeaveApprovalView, MyPayrollView, AddEmployeeView,LeaveManagementView,
    RequestLeaveView, LogoutView, LeaveActionView, DownloadPayslipPDFView,
    AccessDeniedView, EmployeeSearchView, EmployeeExportView, EmployeeDeleteView,
    LeaveExportView, CancelLeaveRequestView, DownloadLeavePDFView
)

urlpatterns = [
    path('dashboard/', OfficeAdminDashboardView.as_view(), name='office_dashboard'),
    path('profile/', OfficeAdminProfileView.as_view(), name='office_profile'),
    path('employee-management/', EmployeeManagementView.as_view(), name='office_employee_management'),
    path('leave-approval/', LeaveApprovalView.as_view(), name='office_leave_approval'),
    path('mypayroll/', MyPayrollView.as_view(), name='office_my_payroll'),
    path('mypayroll/download/', DownloadPayslipPDFView.as_view(), name='download_my_payslipO'),
    path('add-employee/', AddEmployeeView.as_view(), name='office_add_employee'),
    path('leave-management/', LeaveManagementView.as_view(), name='office_leave_management'),
    path('request-leave/', RequestLeaveView.as_view(), name='office_request_leave'),
    path('access-denied/', AccessDeniedView.as_view(), name='access_denied'),
    path('leave-action/', LeaveActionView.as_view(), name='office_leave_action'),
    path("office-employee-search/", EmployeeSearchView.as_view(), name="office_employee_search"),
    path("office-employee-export/", EmployeeExportView.as_view(), name="office_employee_export"),
    path("employee/delete/<int:employee_id>/", EmployeeDeleteView.as_view(), name="office_delete_employee"),
    path("office-leave-export/", LeaveExportView.as_view(), name="office_leave_export"),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('office-cancel-leave/', CancelLeaveRequestView.as_view(), name='office_cancel_leave_request'),
    path('office-download-leave-pdf/<int:leave_id>/', DownloadLeavePDFView.as_view(), name='office_download_leave_pdf'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)