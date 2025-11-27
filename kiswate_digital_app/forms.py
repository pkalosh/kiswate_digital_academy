# forms.py (add School forms)
import random
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
from school.models import School,Scholarship,SchoolSubscription,SubscriptionPlan,County,City,Constituency,SubCounty,Ward, Streams,Grade
from userauths.models import User


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
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        print(password)

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
        )

        # Create School
        school = super().save(commit=False)
        school.school_admin = admin_user
        if commit:
            school.save()

        # Send email if requested
        if self.cleaned_data['send_email'] and getattr(settings, 'EMAIL_HOST', None):
            subject = 'Welcome - Kiswate Digital Academy School Admin'
            message = f"""
            Dear {admin_user.get_full_name()},
            
            Your school admin account has been created for {school.name}.
            Email: {admin_user.email}
            Temporary Password: {password}
            
            Please log in and change your password.
            Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
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
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            print(password)
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
        fields = ['first_name', 'last_name', 'phone_number', 'country', 'is_active']
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['email'] = forms.EmailField(
                initial=self.instance.email,
                widget=forms.EmailInput(attrs={'class': 'form-control', 'readonly': True}),
                help_text="Admin email cannot be changed."
            )

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone != self.instance.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def save(self, commit=True):
        user = super().save(commit=False)

        password = None
        if self.cleaned_data['reset_password']:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user.set_password(password)

        if commit:
            user.save()

        # Send email if requested
        if (self.cleaned_data['send_email'] or self.cleaned_data['reset_password']) and getattr(settings, 'EMAIL_HOST', None):
            subject = 'Account Update - Kiswate Digital Academy Admin'
            message = f"""
            Dear {user.get_full_name()},
            
            Your admin account has been updated.
            Email: {user.email}
            Temporary Password: {password}
            
            If you did not request this, contact support.
            Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
            Best regards,
            System Admin
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

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