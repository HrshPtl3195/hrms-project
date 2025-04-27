from django.conf import settings
from django.conf.urls.static import static
from django.urls import path
from core.views import (
    LoginView, LogoutView, HRAdminDashboardView, OfficeAdminDashboardView,
    EmployeeDashboardView, HybridDashboardView, ResetPasswordView, ResendOTPView,
    HelpPageView, TermsPrivacyView,VerifyOTPAjaxView,
    ForgotPasswordView, ChooseRoleView, HybridEmployeeDashboardView
)

urlpatterns = [
    path('', LoginView.as_view(), name='login'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('choose-role/<str:role>/', ChooseRoleView.as_view(), name='choose_role'),

    path('hr-admin/dashboard/', HRAdminDashboardView.as_view(), name='hr_admin_dashboard'),
    path('office-admin/dashboard/', OfficeAdminDashboardView.as_view(), name='office_admin_dashboard'),
    path('employee/dashboard/', EmployeeDashboardView.as_view(), name='employee_dashboard'),
    path('hybrid/e_dashboard/', HybridEmployeeDashboardView.as_view(), name='hybrid_employee_dashboard'),
    path('hybrid/o_dashboard/', HybridDashboardView.as_view(), name='hybrid_office_admin_dashboard'),
    
    path('verify-otp/', VerifyOTPAjaxView.as_view(), name='verify_otp'),
    path('reset-password/<int:user_idd>/', ResetPasswordView.as_view(), name='reset_password'),
    path('forgot-password/', ForgotPasswordView.as_view(), name='forgot_password'),
    path("resend-otp/<int:user_id>/", ResendOTPView.as_view(), name="resend_otp"),

    path('help/', HelpPageView.as_view(), name='help'),
    path('terms-privacy/', TermsPrivacyView.as_view(), name='terms_privacy'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    

