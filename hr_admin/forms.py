from django import forms
from .models import Employees

class EmployeeForm(forms.ModelForm):
    passport_document = forms.FileField(required=False)
    work_permit_document = forms.FileField(required=False)
    sin_document = forms.FileField(required=False)
    driving_license_document = forms.FileField(required=False)
    other_documents = forms.FileField(required=False)

    class Meta:
        model = Employees
        fields = [
            'first_name', 'middle_name', 'last_name', 'current_address', 'permanent_address',
            'current_email', 'permanent_email', 'current_phone', 'permanent_phone',
            'date_of_birth', 'nationality', 'passport_number', 'passport_issue_date',
            'passport_expiry_date', 'work_permit_number', 'work_permit_issue_date', 'work_permit_expiry_date',
            'sin_number', 'sin_issue_date', 'sin_expiry_date', 'driving_license_number',
            'driving_license_issue_date', 'driving_license_expiry_date', 'criminal_record_check',
            'date_of_joining', 'designation',
            'passport_document', 'work_permit_document', 'sin_document', 'driving_license_document', 'other_documents'
        ]

    def clean_current_email(self):
        email = self.cleaned_data.get('current_email')
        if Employees.objects.filter(current_email=email).exists():
            raise forms.ValidationError("This email is already in use.")
        return email
    
    def clean_current_phone(self):
        phone = self.cleaned_data.get('current_phone')
        if Employees.objects.filter(current_phone=phone).exists():
            raise forms.ValidationError("This phone number is already in use.")
        return phone
