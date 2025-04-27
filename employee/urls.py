from django.urls import path
from .views import (
    EmployeeDashboardView, EmployeeProfileView, LeaveManagementView,
    RequestLeaveView, MyPayrollView, LogoutView, CancelLeaveRequestView,
    DownloadLeavePDFView, DownloadPayslipPDFView
)

urlpatterns = [
    path('dashboard/', EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('profile/', EmployeeProfileView.as_view(), name='employee_profile'),
    path('leave-management/', LeaveManagementView.as_view(), name='employee_leave_management'),
    path('request-leave/', RequestLeaveView.as_view(), name='employee_request_leave'),
    path('payroll/', MyPayrollView.as_view(), name='employee_payroll'),
    path('mypayroll/download/', DownloadPayslipPDFView.as_view(), name='e_download_my_payslip'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('cancel-leave/', CancelLeaveRequestView.as_view(), name='cancel_leave_request'),
    path('download-leave-pdf/<int:leave_id>/', DownloadLeavePDFView.as_view(), name='e_download_leave_pdf'),
]




