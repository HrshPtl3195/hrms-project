from django.db import models
from django.utils import timezone
from datetime import timedelta

class PasswordResetOTP(models.Model):
    user_id = models.IntegerField()  # FK manually managed (to 'users' table)
    otp = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)

    class Meta:
        db_table = "password_reset_otp"  # Custom table name

    def is_expired(self):
        return timezone.now() > self.created_at + timedelta(minutes=5)

    def __str__(self):
        return f"User ID: {self.user_id} | OTP: {self.otp} | Used: {self.is_used}"


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


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


class AuthUser(models.Model):
    password = models.CharField(max_length=128, db_collation='SQL_Latin1_General_CP1_CI_AS')
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.BooleanField()
    username = models.CharField(unique=True, max_length=150, db_collation='SQL_Latin1_General_CP1_CI_AS')
    first_name = models.CharField(max_length=150, db_collation='SQL_Latin1_General_CP1_CI_AS')
    last_name = models.CharField(max_length=150, db_collation='SQL_Latin1_General_CP1_CI_AS')
    email = models.CharField(max_length=254, db_collation='SQL_Latin1_General_CP1_CI_AS')
    is_staff = models.BooleanField()
    is_active = models.BooleanField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'


class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user', 'group'),)


class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(db_collation='SQL_Latin1_General_CP1_CI_AS', blank=True, null=True)
    object_repr = models.CharField(max_length=200, db_collation='SQL_Latin1_General_CP1_CI_AS')
    action_flag = models.SmallIntegerField()
    change_message = models.TextField(db_collation='SQL_Latin1_General_CP1_CI_AS')
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AuthUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    model = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    name = models.CharField(max_length=255, db_collation='SQL_Latin1_General_CP1_CI_AS')
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40, db_collation='SQL_Latin1_General_CP1_CI_AS')
    session_data = models.TextField(db_collation='SQL_Latin1_General_CP1_CI_AS')
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


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
    employee = models.ForeignKey('Employees', models.DO_NOTHING)
    reference_name = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    reference_contact = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')
    reference_email = models.CharField(max_length=100, db_collation='SQL_Latin1_General_CP1_CI_AS')
    relationship = models.CharField(max_length=50, db_collation='SQL_Latin1_General_CP1_CI_AS')

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
    total_leaves = models.IntegerField()
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

    def __str__(self):
        return f"{self.email} - {self.u_role}"
    
    @property
    def is_authenticated(self):
        """Always return True for active authenticated Users."""
        return True



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