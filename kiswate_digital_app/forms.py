# forms.py (add School forms)
import secrets
import string
from django.db import transaction
import json
from django import forms
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.conf import settings
from decimal import Decimal
from django.utils.translation import gettext_lazy as _
from school.models import School, Scholarship, SchoolSubscription, SubscriptionPlan, County, City, Constituency, SubCounty, Ward, Streams, Grade, StaffProfile
from userauths.models import User
from django.forms import inlineformset_factory

 
from .models import (
    UserProfile, Guardian, Subject, Program, Enrollment,
    VirtualClass, Lesson, Assignment, AssignmentSubmission,
    Assessment, Question, Choice,
    NotificationTemplate, NotificationLog, TuitionPayment,
    LEVEL_CHOICES, CATEGORY_CHOICES,
)


class SchoolCreationForm(forms.ModelForm):
    # User (admin) fields for creation
    admin_email = forms.EmailField(
        label="Admin Email",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'School admin email'
        })
    )
    admin_first_name = forms.CharField(
        label="Admin First Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Admin first name'
        })
    )
    admin_last_name = forms.CharField(
        label="Admin Last Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Admin last name'
        })
    )
    admin_phone_number = forms.CharField(
        label="Admin Phone Number",
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique admin phone'
        })
    )
    admin_country = forms.CharField(
        label="Admin Country",
        max_length=15,
        required=False,
        initial='KENYA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KENYA'
        })
    )
    send_email = forms.BooleanField(
        label="Send Credentials to Admin via Email",
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Auto-generate password and email to admin."
    )

    class Meta:
        model = School
        fields = ['name', 'code','county','city','constituency','sub_county','ward', 'address', 'contact_email', 'contact_phone']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'School name'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique school code'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
        }

        county = forms.ModelChoiceField(
            queryset=County.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        city = forms.ModelChoiceField(
            queryset=City.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        constituency = forms.ModelChoiceField(
            queryset=Constituency.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        sub_county = forms.ModelChoiceField(
            queryset=SubCounty.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        ward = forms.ModelChoiceField(
            queryset=Ward.objects.all(),
            required=False,
            widget=forms.Select(attrs={'class': 'form-select'})
        )


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def clean_admin_phone_number(self):
        phone = self.cleaned_data.get('admin_phone_number')
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_admin_email(self):
        email = self.cleaned_data.get('admin_email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if School.objects.filter(code=code).exists():
            raise ValidationError("This school code is already in use.")
        return code

    def save(self, commit=True):
        # Auto-generate password for admin
        _alphabet = string.ascii_letters + string.digits
        password = ''.join(secrets.choice(_alphabet) for _ in range(12))

        # Create Admin User
        admin_user = User.objects.create_user(
            email=self.cleaned_data['admin_email'],
            first_name=self.cleaned_data['admin_first_name'],
            last_name=self.cleaned_data['admin_last_name'],
            phone_number=self.cleaned_data['admin_phone_number'],
            country=self.cleaned_data.get('admin_country', 'KENYA'),
            password=password,
            is_staff=True,
            is_superuser=False,
            is_admin=True,  # School admin flag
            is_active=True,
            is_verified=False,
            is_principal=True,
            is_deputy_principal=False,
        )

        # Create School
        school = super().save(commit=False)
        school.school_admin = admin_user
        if commit:
            school.save()

            # Create a StaffProfile for the principal so they can access school views,
            # be assigned lessons, and appear in staff lists.
            staff_id = f"PRIN-{school.code or school.pk}"
            # Ensure uniqueness if school code clashes
            if StaffProfile.objects.filter(staff_id=staff_id).exists():
                staff_id = f"PRIN-{school.pk}-{admin_user.pk}"
            StaffProfile.objects.create(
                user=admin_user,
                staff_id=staff_id,
                school=school,
                position='teacher',
            )

        # Send email if requested
        if self.cleaned_data['send_email'] and getattr(settings, 'EMAIL_HOST', None):
            subject = 'Welcome - Kiswate Digital Academy School Admin'
            message = f"""
            Dear {admin_user.get_full_name()},
            
            Your school admin account has been created for {school.name}.
            Email: {admin_user.email}
            Temporary Password: {password}
            
            Please log in and change your password.
            Login URL: {getattr(settings, 'FRONTEND_URL', 'https://app.kiswate.org/sing-in/')}
            
            Best regards,
            System Admin
            """
            # send_mail(
            #     subject,
            #     message,
            #     settings.DEFAULT_FROM_EMAIL,
            #     [admin_user.email],
            #     fail_silently=False,
            # )

        return school, password  # Return for messages


class SchoolEditForm(forms.ModelForm):
    # Allow editing admin details? For simplicity, focus on school; add admin fields if needed
    admin_email = forms.EmailField(required=True)
    admin_first_name = forms.CharField(max_length=50, required=True)
    admin_last_name = forms.CharField(max_length=50, required=True)
    admin_phone_number = forms.CharField(max_length=15, required=True)
    admin_country = forms.CharField(max_length=15, required=False)
    send_email = forms.BooleanField(
        label="Send Updated Credentials via Email",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    reset_password = forms.BooleanField(
        label="Reset Admin Password (Auto-generate new one)",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = School
        fields = ['name', 'code', 'address', 'contact_email', 'contact_phone', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['admin_email'].initial = self.instance.school_admin.email
            self.fields['admin_first_name'].initial = self.instance.school_admin.first_name
            self.fields['admin_last_name'].initial = self.instance.school_admin.last_name
            self.fields['admin_phone_number'].initial = self.instance.school_admin.phone_number
            self.fields['admin_country'].initial = self.instance.school_admin.country

    def clean_admin_phone_number(self):
        phone = self.cleaned_data.get('admin_phone_number')
        if phone != self.instance.school_admin.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_admin_email(self):
        email = self.cleaned_data.get('admin_email')
        if email != self.instance.school_admin.email and User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code != self.instance.code and School.objects.filter(code=code).exists():
            raise ValidationError("This school code is already in use.")
        return code

    def save(self, commit=True):
        school = super().save(commit=False)

        # Update Admin User
        admin = school.school_admin
        admin.email = self.cleaned_data['admin_email']
        admin.first_name = self.cleaned_data['admin_first_name']
        admin.last_name = self.cleaned_data['admin_last_name']
        admin.phone_number = self.cleaned_data['admin_phone_number']
        admin.country = self.cleaned_data.get('admin_country')
        
        password = None
        if self.cleaned_data['reset_password']:
            _alphabet = string.ascii_letters + string.digits
            password = ''.join(secrets.choice(_alphabet) for _ in range(12))
            admin.set_password(password)

        admin.save()

        if commit:
            school.save()

        # Send email if requested
        # if (self.cleaned_data['send_email'] or self.cleaned_data['reset_password']) and getattr(settings, 'EMAIL_HOST', None):
        #     subject = 'Account Update - Kiswate Digital Academy School Admin'
        #     message = f"""
        #     Dear {admin.get_full_name()},
            
        #     Your school admin account for {school.name} has been updated.
        #     Email: {admin.email}
        #     Temporary Password: {password}
            
        #     If you did not request this, contact support.
        #     Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
        #     Best regards,
        #     System Admin
        #     """
        #     send_mail(
        #         subject,
        #         message,
        #         settings.DEFAULT_FROM_EMAIL,
        #         [admin.email],
        #         fail_silently=False,
        #     )

        return school

class AdminEditForm(forms.ModelForm):
    email = forms.EmailField(
        label="Admin Email",
        widget=forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
        help_text="Admin email cannot be changed.",
        required=True
    )
    send_email = forms.BooleanField(
        label="Send Updated Credentials via Email",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    reset_password = forms.BooleanField(
        label="Reset Password (Auto-generate new one)",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'phone_number', 'country', 'is_active', 'email']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone != self.instance.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)

        password = None
        if self.cleaned_data.get('reset_password'):
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user.set_password(password)

        if commit:
            user.save()

        if (self.cleaned_data.get('send_email') or self.cleaned_data.get('reset_password')) and getattr(settings, 'EMAIL_HOST', None):
            subject = 'Account Update - Admin'
            message = f"""
            Dear {user.get_full_name()},

            Your admin account has been updated.
            Email: {user.email}
            Temporary Password: {password or '(unchanged)'}

            If you did not request this, contact support.
            Login URL: {getattr(settings, 'FRONTEND_URL', 'https://app.kiswate.org/sing-in/')}

            Best regards,
            System Admin
            """
            # send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], fail_silently=False)

        return user
    

class ScholarshipForm(forms.ModelForm):
    class Meta:
        model = Scholarship
        fields = ['title', 'description', 'amount', 'start_date', 'end_date', 'eligibility_criteria', 'is_active']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Scholarship title (e.g., Merit Award 2025)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Detailed description of the scholarship'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': 'e.g., 500.00'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'eligibility_criteria': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Eligibility (e.g., Grade 8+ students with GPA > 3.0)'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title': 'Title',
            'description': 'Description',
            'amount': 'Amount (Currency)',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'eligibility_criteria': 'Eligibility Criteria',
            'is_active': 'Active',
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.instance.created_by = user
        # Add validation for end_date > start_date
        self.fields['end_date'].required = True

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        if start_date and end_date and end_date < start_date:
            raise forms.ValidationError("End date must be after start date.")
        return cleaned_data

class SubscriptionPlanForm(forms.ModelForm):
    class Meta:
        model = SubscriptionPlan
        fields = ['name', 'description', 'base_price', 'price_per_student', 'price_per_bus', 'price_per_parent', 'features_json', 'is_active', 'default_billing_cycle']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 4}),
            'features_json': forms.Textarea(attrs={'rows': 6, 'placeholder': '{"max_students": 500, "max_buses": 5, "sms_notifications": true}'}),
            'default_billing_cycle': forms.Select(choices=SubscriptionPlan.BILLING_CYCLE_CHOICES),
            'name': forms.Select(choices=SubscriptionPlan.PLAN_TYPE_CHOICES),
        }
        labels = {
            'name': 'Plan Name',
            'description': 'Description',
            'base_price': 'Base Price',
            'price_per_student': 'Price per Student',
            'price_per_bus': 'Price per Bus',
            'price_per_parent': 'Price per Parent',
            'features_json': 'Features (JSON)',
            'is_active': 'Active',
            'default_billing_cycle': 'Default Billing Cycle',
        }

    # def clean_features_json(self):
    #     data = self.cleaned_data['features_json']
    #     if data:
    #         try:
    #             import json
    #             json.loads(str(data))  # Validate JSON
    #         except json.JSONDecodeError:
    #             raise ValidationError(_("Invalid JSON format. Please check the features field."))
    #     return data

    def clean_features_json(self):
            data = self.cleaned_data.get('features_json')
            if data:
                try:
                    json.loads(data)  # Validate JSON
                except json.JSONDecodeError:
                    raise ValidationError("Enter a valid JSON.")
            return data

class SchoolSubscriptionForm(forms.ModelForm):
    class Meta:
        model = SchoolSubscription
        fields = ['plan', 'billing_cycle', 'price_charged', 'start_date', 'end_date', 'next_billing_date', 'status', 'payment_method_last4', 'current_students_count', 'current_buses_count', 'current_parents_count', 'parents_to_pay', 'school_to_pay', 'managed_by']
        widgets = {
            'start_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'end_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'next_billing_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'billing_cycle': forms.Select(choices=SchoolSubscription.BILLING_CYCLE_CHOICES),
            'status': forms.Select(choices=SchoolSubscription.STATUS_CHOICES),
        }
        labels = {
            'plan': 'Subscription Plan',
            'billing_cycle': 'Billing Cycle',
            'price_charged': 'Price Charged',
            'start_date': 'Start Date',
            'end_date': 'End Date',
            'next_billing_date': 'Next Billing Date',
            'status': 'Status',
            'payment_method_last4': 'Payment Method Last 4',
            'current_students_count': 'Current Students Count',
            'current_buses_count': 'Current Buses Count',
            'current_parents_count': 'Current Parents Count',
            'parents_to_pay': 'Parents to Pay',
            'school_to_pay': 'School to Pay',
            'managed_by': 'Managed By',
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields['school'].initial = school
            self.fields['school'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        plan = cleaned_data.get('plan')
        current_students_count = cleaned_data.get('current_students_count', 0)
        current_buses_count = cleaned_data.get('current_buses_count', 0)
        current_parents_count = cleaned_data.get('current_parents_count', 0)
        if plan:
            features = plan.features_json or {}
            max_students = features.get('max_students', float('inf'))
            max_buses = features.get('max_buses', float('inf'))
            if current_students_count > max_students:
                raise ValidationError(_("Student count exceeds plan limit."))
            if current_buses_count > max_buses:
                raise ValidationError(_("Bus count exceeds plan limit."))
        return cleaned_data


class StreamForm(forms.ModelForm):
    class Meta:
        model = Streams
        fields = ['name','capacity']
        #filter grades for the school



 
# ─── SHARED WIDGET HELPERS ───────────────────────────────────────────────────
 
INPUT = 'form-control'
SELECT = 'form-select'
CHECK = 'form-check-input'
TEXTAREA = 'form-control'
 
 
def _w(widget_class, **kwargs):
    return widget_class(attrs={'class': INPUT, **kwargs})
 
 
# ─── USER MANAGEMENT FORMS ───────────────────────────────────────────────────
 
class StudentProfileOnlyForm(forms.ModelForm):
    """For logged-in users creating a tuition student profile (no new User needed)."""
    class Meta:
        model = UserProfile
        fields = ['phone', 'date_of_birth', 'gender']
        widgets = {
            'phone': forms.TextInput(attrs={'class': INPUT}),
            'date_of_birth': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'gender': forms.Select(attrs={'class': SELECT}),
        }


class TeacherProfileOnlyForm(forms.ModelForm):
    """For logged-in users creating a tuition teacher profile (no new User needed)."""
    class Meta:
        model = UserProfile
        fields = ['phone', 'date_of_birth', 'gender', 'bio', 'id_number']
        widgets = {
            'phone': forms.TextInput(attrs={'class': INPUT}),
            'date_of_birth': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'gender': forms.Select(attrs={'class': SELECT}),
            'bio': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'id_number': forms.TextInput(attrs={'class': INPUT}),
        }


class StudentRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': INPUT}))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': INPUT}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': INPUT}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT}))

    class Meta:
        model = UserProfile
        fields = ['school', 'phone', 'date_of_birth', 'gender']
        widgets = {
            'school': forms.Select(attrs={'class': SELECT}),
            'phone': forms.TextInput(attrs={'class': INPUT}),
            'date_of_birth': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'gender': forms.Select(attrs={'class': SELECT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].required = False
 
    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
 
    def save(self, commit=True):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        profile = super().save(commit=False)
        profile.user = user
        profile.role = 'student'
        if commit:
            profile.save()
        return profile
 
 
class TeacherRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': INPUT}))
    last_name = forms.CharField(max_length=50, widget=forms.TextInput(attrs={'class': INPUT}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': INPUT}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT}))
    confirm_password = forms.CharField(widget=forms.PasswordInput(attrs={'class': INPUT}))
    subjects = forms.ModelMultipleChoiceField(
        queryset=Subject.objects.all(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': CHECK}),
        required=False
    )

    class Meta:
        model = UserProfile
        fields = ['school', 'phone', 'date_of_birth', 'gender', 'bio', 'id_number']
        widgets = {
            'school': forms.Select(attrs={'class': SELECT}),
            'phone': forms.TextInput(attrs={'class': INPUT}),
            'date_of_birth': forms.DateInput(attrs={'class': INPUT, 'type': 'date'}),
            'gender': forms.Select(attrs={'class': SELECT}),
            'bio': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'id_number': forms.TextInput(attrs={'class': INPUT}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['school'].required = False
 
    def clean(self):
        cleaned = super().clean()
        if cleaned.get('password') != cleaned.get('confirm_password'):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned
 
    def save(self, commit=True):
        data = self.cleaned_data
        user = User.objects.create_user(
            username=data['email'],
            email=data['email'],
            password=data['password'],
            first_name=data['first_name'],
            last_name=data['last_name'],
        )
        profile = super().save(commit=False)
        profile.user = user
        profile.role = 'teacher'
        if commit:
            profile.save()
        return profile
 
 
class GuardianForm(forms.ModelForm):
    class Meta:
        model = Guardian
        fields = ['name', 'relationship', 'phone', 'email', 'is_primary']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT}),
            'relationship': forms.TextInput(attrs={'class': INPUT}),
            'phone': forms.TextInput(attrs={'class': INPUT}),
            'email': forms.EmailInput(attrs={'class': INPUT}),
            'is_primary': forms.CheckboxInput(attrs={'class': CHECK}),
        }
 
 
class VettingForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['vetting_status', 'vetting_notes']
        widgets = {
            'vetting_status': forms.Select(attrs={'class': SELECT}),
            'vetting_notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
        }
 
 
class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'program']
        widgets = {
            'student': forms.Select(attrs={'class': SELECT}),
            'program': forms.Select(attrs={'class': SELECT}),
        }
 
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            self.fields['student'].queryset = UserProfile.objects.filter(
                school=school, role='student', vetting_status='approved')
            self.fields['program'].queryset = Program.objects.filter(school=school, is_active=True)
 
 
# ─── VIRTUAL LEARNING FORMS ──────────────────────────────────────────────────
 
class VirtualClassForm(forms.ModelForm):
    class Meta:
        model = VirtualClass
        fields = [
            'teacher', 'program', 'title', 'description', 'platform', 'meeting_link',
            'meeting_id', 'passcode', 'scheduled_at', 'duration_minutes',
            'is_recurring', 'notes'
        ]
        widgets = {
            'teacher': forms.Select(attrs={'class': SELECT}),
            'program': forms.Select(attrs={'class': SELECT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'platform': forms.Select(attrs={'class': SELECT}),
            'meeting_link': forms.URLInput(attrs={'class': INPUT, 'placeholder': 'https://meet.google.com/...'}),
            'meeting_id': forms.TextInput(attrs={'class': INPUT}),
            'passcode': forms.TextInput(attrs={'class': INPUT}),
            'scheduled_at': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'duration_minutes': forms.NumberInput(attrs={'class': INPUT}),
            'is_recurring': forms.CheckboxInput(attrs={'class': CHECK}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        teacher_profile = kwargs.pop('teacher_profile', None)
        super().__init__(*args, **kwargs)
        if teacher_profile:
            # Teacher mode: hide teacher field (set by view), filter programs
            self.fields.pop('teacher')
            self.fields['program'].queryset = Program.objects.filter(
                teacher=teacher_profile, is_active=True)
        else:
            # Admin mode: show teacher picker
            self.fields['teacher'].queryset = UserProfile.objects.filter(
                role='teacher', vetting_status='approved')
            self.fields['teacher'].required = True
 
 
class RecordingUploadForm(forms.ModelForm):
    class Meta:
        model = VirtualClass
        fields = ['recording_link']
        widgets = {
            'recording_link': forms.URLInput(attrs={'class': INPUT, 'placeholder': 'https://...'}),
        }
 
 
class AttendanceManualForm(forms.Form):
    """Teacher manually marks attendance for a virtual class."""
    present_students = forms.ModelMultipleChoiceField(
        queryset=UserProfile.objects.none(),
        widget=forms.CheckboxSelectMultiple(attrs={'class': CHECK}),
        required=False,
        label="Mark Present"
    )
 
    def __init__(self, *args, **kwargs):
        virtual_class = kwargs.pop('virtual_class')
        super().__init__(*args, **kwargs)
        enrolled = UserProfile.objects.filter(
            enrollments__program=virtual_class.program,
            enrollments__is_active=True,
            role='student'
        )
        self.fields['present_students'].queryset = enrolled
 
 
class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['teacher', 'program', 'title', 'description', 'topic', 'notes_file', 'video_url', 'order', 'is_published']
        widgets = {
            'teacher': forms.Select(attrs={'class': SELECT}),
            'program': forms.Select(attrs={'class': SELECT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'topic': forms.TextInput(attrs={'class': INPUT}),
            'video_url': forms.URLInput(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'is_published': forms.CheckboxInput(attrs={'class': CHECK}),
        }

    def __init__(self, *args, **kwargs):
        teacher_profile = kwargs.pop('teacher_profile', None)
        super().__init__(*args, **kwargs)
        if teacher_profile:
            # Teacher mode: hide teacher field (set by view), filter programs
            self.fields.pop('teacher')
            self.fields['program'].queryset = Program.objects.filter(teacher=teacher_profile, is_active=True)
        else:
            # Admin mode: show teacher picker
            self.fields['teacher'].queryset = UserProfile.objects.filter(role='teacher', vetting_status='approved')
            self.fields['teacher'].required = True
 
 
class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['program', 'lesson', 'title', 'instructions', 'attachment', 'due_date', 'total_marks', 'is_published']
        widgets = {
            'program': forms.Select(attrs={'class': SELECT}),
            'lesson': forms.Select(attrs={'class': SELECT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'instructions': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}),
            'due_date': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'total_marks': forms.NumberInput(attrs={'class': INPUT}),
            'is_published': forms.CheckboxInput(attrs={'class': CHECK}),
        }

    def __init__(self, *args, **kwargs):
        teacher_profile = kwargs.pop('teacher_profile', None)
        super().__init__(*args, **kwargs)
        if teacher_profile:
            self.fields['program'].queryset = Program.objects.filter(teacher=teacher_profile, is_active=True)
 
 
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['file', 'text_answer']
        widgets = {
            'text_answer': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 5}),
        }
 
 
class GradeSubmissionForm(forms.ModelForm):
    class Meta:
        model = AssignmentSubmission
        fields = ['marks_obtained', 'feedback']
        widgets = {
            'marks_obtained': forms.NumberInput(attrs={'class': INPUT}),
            'feedback': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
        }
 
 
# ─── ASSESSMENT FORMS ────────────────────────────────────────────────────────
 
class AssessmentForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = [
            'program', 'title', 'assessment_type', 'instructions',
            'total_marks', 'pass_mark', 'duration_minutes',
            'start_time', 'end_time', 'is_published'
        ]
        widgets = {
            'program': forms.Select(attrs={'class': SELECT}),
            'title': forms.TextInput(attrs={'class': INPUT}),
            'assessment_type': forms.Select(attrs={'class': SELECT}),
            'instructions': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'total_marks': forms.NumberInput(attrs={'class': INPUT}),
            'pass_mark': forms.NumberInput(attrs={'class': INPUT}),
            'duration_minutes': forms.NumberInput(attrs={'class': INPUT}),
            'start_time': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': INPUT, 'type': 'datetime-local'}),
            'is_published': forms.CheckboxInput(attrs={'class': CHECK}),
        }

    def __init__(self, *args, **kwargs):
        teacher_profile = kwargs.pop('teacher_profile', None)
        super().__init__(*args, **kwargs)
        if teacher_profile:
            self.fields['program'].queryset = Program.objects.filter(teacher=teacher_profile, is_active=True)
 
 
class QuestionForm(forms.ModelForm):
    class Meta:
        model = Question
        fields = ['text', 'question_type', 'marks', 'order', 'explanation']
        widgets = {
            'text': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
            'question_type': forms.Select(attrs={'class': SELECT}),
            'marks': forms.NumberInput(attrs={'class': INPUT}),
            'order': forms.NumberInput(attrs={'class': INPUT}),
            'explanation': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
        }
 
 
class ChoiceForm(forms.ModelForm):
    class Meta:
        model = Choice
        fields = ['text', 'is_correct']
        widgets = {
            'text': forms.TextInput(attrs={'class': INPUT}),
            'is_correct': forms.CheckboxInput(attrs={'class': CHECK}),
        }
 
 
ChoiceFormSet = inlineformset_factory(Question, Choice, form=ChoiceForm, extra=4, max_num=6, can_delete=True)
 
 
class PublishResultsForm(forms.ModelForm):
    class Meta:
        model = Assessment
        fields = ['results_published']
        widgets = {
            'results_published': forms.CheckboxInput(attrs={'class': CHECK}),
        }
 
 
# ─── COMMUNICATION FORMS ─────────────────────────────────────────────────────
 
class NotificationTemplateForm(forms.ModelForm):
    class Meta:
        model = NotificationTemplate
        fields = ['name', 'notification_type', 'subject', 'body', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT}),
            'notification_type': forms.Select(attrs={'class': SELECT}),
            'subject': forms.TextInput(attrs={'class': INPUT}),
            'body': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 5,
                                          'placeholder': 'Use {name}, {class_title}, {date}, {link}'}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECK}),
        }
 
 
class BulkNotificationForm(forms.Form):
    RECIPIENT_CHOICES = [
        ('all_students', 'All Students'),
        ('all_teachers', 'All Teachers'),
        ('program', 'Specific Program'),
        ('school', 'Specific School'),
    ]
    notification_type = forms.ChoiceField(
        choices=[('sms', 'SMS'), ('email', 'Email'), ('both', 'Both')],
        widget=forms.Select(attrs={'class': SELECT})
    )
    recipients = forms.ChoiceField(choices=RECIPIENT_CHOICES, widget=forms.Select(attrs={'class': SELECT}))
    program = forms.ModelChoiceField(queryset=Program.objects.all(), required=False,
                                     widget=forms.Select(attrs={'class': SELECT}))
    school = forms.ModelChoiceField(queryset=School.objects.all(), required=False,
                                    widget=forms.Select(attrs={'class': SELECT}))
    subject = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': INPUT}))
    message = forms.CharField(widget=forms.Textarea(attrs={'class': TEXTAREA, 'rows': 4}))


# ─── SUBJECT FORM ────────────────────────────────────────────────────────────

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Mathematics'}),
            'code': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. MATH'}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2, 'placeholder': 'Optional description'}),
        }


# ─── TUITION FORMS ────────────────────────────────────────────────────────────

class TuitionProgramForm(forms.ModelForm):
    class Meta:
        model = Program
        fields = ['name', 'subject', 'teacher', 'description', 'price', 'level', 'category', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. Form 3 Mathematics Remedial'}),
            'subject': forms.Select(attrs={'class': SELECT}),
            'teacher': forms.Select(attrs={'class': SELECT}),
            'description': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 3}),
            'price': forms.NumberInput(attrs={'class': INPUT, 'step': '0.01', 'min': '0', 'placeholder': '0.00'}),
            'level': forms.Select(attrs={'class': SELECT}),
            'category': forms.Select(attrs={'class': SELECT}),
            'is_active': forms.CheckboxInput(attrs={'class': CHECK}),
        }

    def __init__(self, *args, **kwargs):
        teacher_locked = kwargs.pop('teacher_locked', None)
        super().__init__(*args, **kwargs)
        self.fields['teacher'].queryset = UserProfile.objects.filter(
            role='teacher', vetting_status='approved')
        self.fields['teacher'].required = False
        if teacher_locked:
            self.fields['teacher'].widget = forms.HiddenInput()
            self.initial['teacher'] = teacher_locked.pk


class TuitionPaymentForm(forms.ModelForm):
    class Meta:
        model = TuitionPayment
        fields = ['payment_method', 'transaction_id', 'payer_phone', 'notes']
        widgets = {
            'payment_method': forms.Select(attrs={'class': SELECT}),
            'transaction_id': forms.TextInput(attrs={'class': INPUT, 'placeholder': 'e.g. QHX7YBABC1'}),
            'payer_phone': forms.TextInput(attrs={'class': INPUT, 'placeholder': '+254712345678'}),
            'notes': forms.Textarea(attrs={'class': TEXTAREA, 'rows': 2}),
        }


class PrincipalTuitionEnrollForm(forms.Form):
    """Used by principals/deputies to batch-enroll school students in tuition programs."""
    enroll_mode = forms.ChoiceField(
        choices=[('student', 'Per Student'), ('stream', 'By Stream'), ('grade', 'By Grade')],
        widget=forms.HiddenInput(),
        initial='student',
    )
    students = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple(),
        label='Students',
        required=False,
    )
    grade = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': SELECT}),
        label='Grade',
        required=False,
    )
    stream = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': SELECT}),
        label='Stream',
        required=False,
    )
    program = forms.ModelChoiceField(
        queryset=Program.objects.filter(is_tuition=True, is_active=True),
        widget=forms.Select(attrs={'class': SELECT}),
        label='Tuition Program',
    )

    def __init__(self, *args, **kwargs):
        from school.models import Student, Grade, Streams
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        qs = Student.objects.filter(is_active=True).select_related('user', 'grade_level', 'stream').order_by('user__first_name')
        grade_qs = Grade.objects.filter(is_active=True).order_by('name')
        stream_qs = Streams.objects.filter(is_active=True).select_related('grade').order_by('grade__name', 'name')
        if school:
            qs = qs.filter(school=school)
            grade_qs = grade_qs.filter(school=school)
            stream_qs = stream_qs.filter(school=school)
        self.fields['students'].queryset = qs
        self.fields['students'].label_from_instance = lambda s: (
            f"{s.user.get_full_name() or s.user.email}"
            + (f" — {s.grade_level}" if s.grade_level else "")
            + (f" {s.stream}" if s.stream else "")
        )
        self.fields['grade'].queryset = grade_qs
        self.fields['grade'].label_from_instance = lambda g: g.name
        self.fields['stream'].queryset = stream_qs
        self.fields['stream'].label_from_instance = lambda s: f"{s.grade.name} — {s.name}"

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get('enroll_mode', 'student')
        if mode == 'student' and not cleaned.get('students'):
            self.add_error('students', 'Select at least one student.')
        elif mode == 'grade' and not cleaned.get('grade'):
            self.add_error('grade', 'Select a grade.')
        elif mode == 'stream' and not cleaned.get('stream'):
            self.add_error('stream', 'Select a stream.')
        return cleaned

