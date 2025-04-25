# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class AcademicDetails(models.Model):
    academic_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Employees', models.DO_NOTHING, blank=True, null=True)
    degree = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    institution = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    year_of_passing = models.CharField(max_length=10, db_collation='SQL_Latin1_General_CP1_CI_AS')
    grade = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'academic_details'


class DrivingDetails(models.Model):
    driving_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Employees', models.DO_NOTHING, blank=True, null=True)
    driving_license_number = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    driving_license_issue_date = models.DateField(blank=True, null=True)
    driving_license_expiry_date = models.DateField(blank=True, null=True)
    driving_license_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'driving_details'


class EmployeeContactDetails(models.Model):
    employee_contact_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Employees', models.DO_NOTHING, blank=True, null=True)
    current_address = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    permanent_address = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    current_email = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    permanent_email = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    current_phone = models.CharField(max_length=15, db_collation='SQL_Latin1_General_CP1_CI_AS')
    permanent_phone = models.CharField(max_length=15, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'employee_contact_details'


class EmployeeReferences(models.Model):
    reference_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey('Employees', models.DO_NOTHING, blank=True, null=True)
    reference_name = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    reference_contact = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    reference_email = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    relationship = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'employee_references'


class Employees(models.Model):
    employee_id = models.AutoField(primary_key=True)
    user = models.OneToOneField('Users', models.DO_NOTHING, blank=True, null=True)
    first_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    middle_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    last_name = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    gender = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    date_of_birth = models.DateField()
    place_of_birth = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    nationality = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    criminal_record_check = models.CharField(max_length=10, db_collation='SQL_Latin1_General_CP1_CI_AS')
    date_of_joining = models.DateField()
    designation = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    is_deleted = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'employees'


class EmploymentHistory(models.Model):
    history_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    company_name = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    job_title = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    eh_start_date = models.DateField(db_column='EH_start_date', blank=True, null=True)  # Field name made lowercase.
    eh_end_date = models.DateField(db_column='EH_end_date', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        managed = False
        db_table = 'employment_history'


class Leaves(models.Model):
    leave_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    leave_type = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    l_apply_date = models.DateField(db_column='L_apply_date')  # Field name made lowercase.
    l_start_date = models.DateField(db_column='L_start_date')  # Field name made lowercase.
    l_end_date = models.DateField(db_column='L_end_date')  # Field name made lowercase.
    leave_reason = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    l_status = models.CharField(db_column='L_status', max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS')  # Field name made lowercase.
    approved_by = models.ForeignKey('Users', models.DO_NOTHING, db_column='approved_by', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'leaves'


class OtherDocuments(models.Model):
    document_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    offer_letter_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    contract_letter_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    profile_image = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'other_documents'


class PassportDetails(models.Model):
    passport_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    passport_number = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    passport_issue_date = models.DateField(blank=True, null=True)
    passport_expiry_date = models.DateField(blank=True, null=True)
    passport_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'passport_details'


class Payslips(models.Model):
    payslip_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    salary = models.DecimalField(max_digits=10, decimal_places=2)
    deductions = models.DecimalField(max_digits=10, decimal_places=2)
    net_pay = models.DecimalField(max_digits=10, decimal_places=2)
    generated_by = models.ForeignKey('Users', models.DO_NOTHING, db_column='generated_by', blank=True, null=True)
    date_generated = models.DateField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'payslips'


class SinDetails(models.Model):
    sin_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    sin_number = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    sin_issue_date = models.DateField(blank=True, null=True)
    sin_expiry_date = models.DateField(blank=True, null=True)
    sin_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'sin_details'


class Users(models.Model):
    user_id = models.AutoField(primary_key=True)
    email = models.CharField(unique=True, max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    password_hash = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    u_role = models.CharField(max_length=20, db_collation='SQL_Latin1_General_CP1_CI_AS')
    created_at = models.DateTimeField(blank=True, null=True)
    last_login = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'users'


class WorkPermitDetails(models.Model):
    work_permit_id = models.AutoField(primary_key=True)
    employee = models.ForeignKey(Employees, models.DO_NOTHING, blank=True, null=True)
    work_permit_number = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    work_permit_issue_date = models.DateField(blank=True, null=True)
    work_permit_expiry_date = models.DateField(blank=True, null=True)
    work_permit_document = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'work_permit_details'
