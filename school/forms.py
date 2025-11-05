# forms.py (in school/forms.py or app-level)
import random
import string
from django import forms
from django.db.models import Q
from userauths.models import User
from .models import Grade, Parent,StaffProfile,Student, SmartID
from django.core.mail import send_mail
from django.core.exceptions import ValidationError
from django.conf import settings

class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['name', 'description', 'code', 'capacity', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter grade name (e.g., Grade 10)'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Optional description'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Unique code (e.g., G10)'}),
            'capacity': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'placeholder': 'Max students'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'name': 'Grade Name',
            'description': 'Description',
            'code': 'Grade Code',
            'capacity': 'Capacity',
            'is_active': 'Active',
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            # Ensure code uniqueness is scoped to school in validation
            self.instance.school = school
        # Custom validation for code uniqueness per school
        if self.instance.pk:
            self.fields['code'].help_text = "Unique within your school."
        else:
            self.fields['code'].help_text = "Must be unique within your school."

    def clean_code(self):
        code = self.cleaned_data.get('code')
        school = self.instance.school
        if code and Grade.objects.filter(school=school, code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("This code is already in use for your school.")
        return code

class ParentCreationForm(forms.Form):
    # User fields
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Parent email address'
        })
    )
    first_name = forms.CharField(
        label="First Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        label="Last Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    phone_number = forms.CharField(
        label="Phone Number",
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique phone number'
        })
    )
    country = forms.CharField(
        label="Country",
        max_length=15,
        required=False,
        initial='KENYA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KENYA'
        })
    )
    send_email = forms.BooleanField(
        label="Send Credentials via Email",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check to email temporary password to the parent."
    )

    # Parent fields
    parent_id = forms.CharField(
        label="Parent ID",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique ID (e.g., P001)'
        })
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    gender = forms.ChoiceField(
        label="Gender",
        choices=Parent.gender.field.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    address = forms.CharField(
        label="Address",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Full address'
        })
    )
    bio = forms.CharField(
        label="Bio",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Short biography'
        })
    )
    profile_picture = forms.ImageField(
        label="Profile Picture",
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_parent_id(self):
        parent_id = self.cleaned_data.get('parent_id')
        if Parent.objects.filter(parent_id=parent_id).exists():
            raise ValidationError("This parent ID is already in use.")
        return parent_id

    def save(self, commit=True):
        # Auto-generate password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        # Create User
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data['phone_number'],
            country=self.cleaned_data['country'],
            password=password,
            is_parent=True,
            is_active=True,
            is_verified=False,
        )

        # Create Parent
        parent = Parent.objects.create(
            user=user,
            parent_id=self.cleaned_data['parent_id'],
            date_of_birth=self.cleaned_data.get('date_of_birth'),
            gender=self.cleaned_data.get('gender'),
            phone=self.cleaned_data['phone_number'],
            address=self.cleaned_data.get('address'),
            bio=self.cleaned_data.get('bio'),
            profile_picture=self.cleaned_data.get('profile_picture'),
            school=self.school,
        )

        # Send email if requested
        if self.cleaned_data['send_email'] and settings.EMAIL_HOST:
            subject = 'Welcome to Kiswate Digital Academy'
            message = f"""
            Dear {user.get_full_name()},
            
            Your account has been created successfully.
            Email: {user.email}
            Temporary Password: {password}
            
            Please log in and change your password.
            Login URL: {settings.FRONTEND_URL or 'https://yourapp.com/login'}
            
            Best regards,
            School Admin
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

        return parent, password  # Return for messages


class ParentEditForm(forms.ModelForm):
    # User fields
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    country = forms.CharField(max_length=15, required=False)
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
        model = Parent
        fields = ['parent_id', 'date_of_birth', 'gender', 'address', 'bio', 'profile_picture']
        widgets = {
            'parent_id': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['phone_number'].initial = self.instance.user.phone_number
            self.fields['country'].initial = self.instance.user.country

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone != self.instance.user.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email != self.instance.user.email and User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def save(self, commit=True):
        parent = super().save(commit=False)

        # Update User
        user = parent.user
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.country = self.cleaned_data.get('country')
        
        password = None
        if self.cleaned_data['reset_password']:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user.set_password(password)

        user.save()
        parent.phone = user.phone_number

        if commit:
            parent.save()

        # Send email if requested
        if (self.cleaned_data['send_email'] or self.cleaned_data['reset_password']) and settings.EMAIL_HOST:
            subject = 'Account Update - Kiswate Digital Academy'
            message = f"""
            Dear {user.get_full_name()},
            
            Your account details have been updated.
            Email: {user.email}
            Temporary Password: {password}
            
            If you did not request this, contact admin.
            Login URL: {settings.FRONTEND_URL or 'https://yourapp.com/login'}
            
            Best regards,
            School Admin
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

        return parent

class StaffCreationForm(forms.Form):
    # User fields
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Staff email address'
        })
    )
    first_name = forms.CharField(
        label="First Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        label="Last Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    phone_number = forms.CharField(
        label="Phone Number",
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique phone number'
        })
    )
    country = forms.CharField(
        label="Country",
        max_length=15,
        required=False,
        initial='KENYA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KENYA'
        })
    )
    send_email = forms.BooleanField(
        label="Send Credentials via Email",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check to email temporary password to the staff member."
    )

    # Staff fields
    staff_id = forms.CharField(
        label="Staff ID",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique ID (e.g., S001)'
        })
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    gender = forms.ChoiceField(
        label="Gender",
        choices=StaffProfile.gender.field.choices,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    employment_date = forms.DateField(
        label="Employment Date",
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    position = forms.ChoiceField(
        label="Position",
        choices=StaffProfile.position.field.choices,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    tsc_number = forms.CharField(
        label="TSC Number",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'For teachers only'
        })
    )
    qualification = forms.CharField(
        label="Qualification",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'e.g., B.Ed, M.Ed'
        })
    )
    subjects = forms.CharField(
        label="Subjects (comma-separated)",
        max_length=255,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Math, English'
        })
    )

    bio = forms.CharField(
        label="Bio",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Short biography'
        })
    )
    profile_picture = forms.ImageField(
        label="Profile Picture",
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_staff_id(self):
        staff_id = self.cleaned_data.get('staff_id')
        if StaffProfile.objects.filter(staff_id=staff_id).exists():
            raise ValidationError("This staff ID is already in use.")
        return staff_id

    def clean_tsc_number(self):
        tsc = self.cleaned_data.get('tsc_number')
        position = self.cleaned_data.get('position')
        if tsc and position != 'teacher':
            raise ValidationError("TSC Number is only required for teachers.")
        if tsc and StaffProfile.objects.filter(tsc_number=tsc).exclude(tsc_number__isnull=True).exists():
            raise ValidationError("This TSC number is already in use.")
        return tsc

    def save(self, commit=True):
        # Auto-generate password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        # Create User
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data['phone_number'],
            country=self.cleaned_data['country'],
            password=password,
            is_staff=True,  # All staff
            school_staff=True,
            is_teacher=(self.cleaned_data['position'] == 'teacher'),  # Flag for teachers
            is_active=True,
            is_verified=False,
        )

        # Create StaffProfile
        staff = StaffProfile.objects.create(
            user=user,
            staff_id=self.cleaned_data['staff_id'],
            date_of_birth=self.cleaned_data.get('date_of_birth'),
            gender=self.cleaned_data.get('gender'),
            employment_date=self.cleaned_data['employment_date'],
            position=self.cleaned_data['position'],
            tsc_number=self.cleaned_data.get('tsc_number'),
            qualification=self.cleaned_data.get('qualification'),
            subjects=self.cleaned_data.get('subjects'),
            bio=self.cleaned_data.get('bio'),
            profile_picture=self.cleaned_data.get('profile_picture'),
            school=self.school,
        )

        # Send email if requested
        # if self.cleaned_data['send_email'] and getattr(settings, 'EMAIL_HOST', None):
        #     subject = 'Welcome to Kiswate Digital Academy - Staff Account'
        #     message = f"""
        #     Dear {user.get_full_name()},
            
        #     Your staff account has been created.
        #     Email: {user.email}
        #     Temporary Password: {password}
        #     Position: {self.cleaned_data['position'].title()}
            
        #     Please log in and change your password.
        #     Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
        #     Best regards,
        #     School Admin
        #     """
        #     send_mail(
        #         subject,
        #         message,
        #         settings.DEFAULT_FROM_EMAIL,
        #         [user.email],
        #         fail_silently=False,
        #     )

        return staff, password


class StaffEditForm(forms.ModelForm):
    # User fields
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    country = forms.CharField(max_length=15, required=False)
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
        model = StaffProfile
        fields = ['staff_id', 'date_of_birth', 'gender', 'employment_date', 'position', 'tsc_number', 'qualification', 'subjects', 'bio', 'profile_picture']
        widgets = {
            'staff_id': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'employment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'tsc_number': forms.TextInput(attrs={'class': 'form-control'}),
            'qualification': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'subjects': forms.TextInput(attrs={'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['phone_number'].initial = self.instance.user.phone_number
            self.fields['country'].initial = self.instance.user.country

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone != self.instance.user.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email != self.instance.user.email and User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_tsc_number(self):
        tsc = self.cleaned_data.get('tsc_number')
        position = self.cleaned_data.get('position')
        if tsc and position != 'teacher':
            raise ValidationError("TSC Number is only applicable for teachers.")
        if tsc and tsc != self.instance.tsc_number and StaffProfile.objects.filter(tsc_number=tsc).exists():
            raise ValidationError("This TSC number is already in use.")
        return tsc

    def save(self, commit=True):
        staff = super().save(commit=False)

        # Update User
        user = staff.user
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.country = self.cleaned_data.get('country')
        
        password = None
        if self.cleaned_data['reset_password']:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user.set_password(password)

        # Update flags based on position
        user.school_staff = True
        user.is_teacher = (self.cleaned_data['position'] == 'teacher')
        user.save()

        if commit:
            staff.save()

        # Send email if requested
        if (self.cleaned_data['send_email'] or self.cleaned_data['reset_password']) and getattr(settings, 'EMAIL_HOST', None):
            subject = 'Account Update - Kiswate Digital Academy'
            message = f"""
            Dear {user.get_full_name()},
            
            Your staff account has been updated.
            Email: {user.email}
            Position: {staff.position.title()}
            Temporary Password: {password}
            
            If you did not request this, contact admin.
            Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
            Best regards,
            School Admin
            """
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                fail_silently=False,
            )

        return staff

class StudentCreationForm(forms.Form):
    # User fields
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'Student email address'
        })
    )
    first_name = forms.CharField(
        label="First Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        })
    )
    last_name = forms.CharField(
        label="Last Name",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        })
    )
    phone_number = forms.CharField(
        label="Phone Number",
        max_length=15,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique phone number'
        })
    )
    country = forms.CharField(
        label="Country",
        max_length=15,
        required=False,
        initial='KENYA',
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., KENYA'
        })
    )
    send_email = forms.BooleanField(
        label="Send Credentials via Email",
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Check to email temporary password to the student/guardian."
    )

    # Student fields
    student_id = forms.CharField(
        label="Student ID",
        max_length=50,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Unique ID (e.g., STU001)'
        })
    )
    date_of_birth = forms.DateField(
        label="Date of Birth",
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    gender = forms.ChoiceField(
        label="Gender",
        choices=Student.gender.field.choices,
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    enrollment_date = forms.DateField(
        label="Enrollment Date",
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    grade_level = forms.ModelChoiceField(
        label="Grade Level",
        queryset=Grade.objects.all(),
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    bio = forms.CharField(
        label="Bio",
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Short bio'
        })
    )
    profile_picture = forms.ImageField(
        label="Profile Picture",
        required=False,
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    # Parent selection (M2M)
    parents = forms.ModelMultipleChoiceField(
        label="Guardian(s)",
        queryset=Parent.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select one or more parents/guardians. Default: Parent ID 2 if none selected."
    )

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.school)
            self.fields['parents'].queryset = Parent.objects.filter(school=self.school)

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def clean_student_id(self):
        student_id = self.cleaned_data.get('student_id')
        if Student.objects.filter(student_id=student_id).exists():
            raise ValidationError("This student ID is already in use.")
        return student_id

    def clean(self):
        cleaned_data = super().clean()
        parents = cleaned_data.get('parents', [])
        if not parents:
            # Default to Parent ID 2 if exists
            default_parent = Parent.objects.filter(id=2).first()
            if default_parent:
                cleaned_data['parents'] = [default_parent]
            else:
                raise ValidationError("At least one parent must be selected or Parent ID 2 must exist.")
        return cleaned_data

    def save(self, commit=True):
        # Auto-generate password
        password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))

        # Create User
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data['phone_number'],
            country=self.cleaned_data['country'],
            password=password,
            is_student=True,
            is_active=True,
            is_verified=False,
        )

        # Create Student
        student = Student.objects.create(
            user=user,
            student_id=self.cleaned_data['student_id'],
            date_of_birth=self.cleaned_data['date_of_birth'],
            gender=self.cleaned_data['gender'],
            enrollment_date=self.cleaned_data['enrollment_date'],
            grade_level=self.cleaned_data['grade_level'],
            bio=self.cleaned_data.get('bio'),
            profile_picture=self.cleaned_data.get('profile_picture'),
            school=self.school,
        )

        # Link parents (M2M)
        student.parent.set(self.cleaned_data['parents'])

        # Send email if requested
        # if self.cleaned_data['send_email'] and getattr(settings, 'EMAIL_HOST', None):
        #     subject = 'Welcome to Kiswate Digital Academy - Student Account'
        #     message = f"""
        #     Dear {user.get_full_name()},
            
        #     Your student account has been created.
        #     Email: {user.email}
        #     Temporary Password: {password}
        #     Grade: {self.cleaned_data['grade_level']}
            
        #     Please log in and change your password.
        #     Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
        #     Best regards,
        #     School Admin
        #     """
        #     send_mail(
        #         subject,
        #         message,
        #         settings.DEFAULT_FROM_EMAIL,
        #         [user.email],
        #         fail_silently=False,
        #     )

        return student, password


class StudentEditForm(forms.ModelForm):
    # User fields
    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=50, required=True)
    last_name = forms.CharField(max_length=50, required=True)
    phone_number = forms.CharField(max_length=15, required=True)
    country = forms.CharField(max_length=15, required=False)
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
    # Parent selection for edit
    parents = forms.ModelMultipleChoiceField(
        queryset=Parent.objects.all(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        help_text="Select guardians (multiple allowed)."
    )

    class Meta:
        model = Student
        fields = ['student_id', 'date_of_birth', 'gender', 'enrollment_date', 'grade_level', 'bio', 'profile_picture']
        widgets = {
            'student_id': forms.TextInput(attrs={'class': 'form-control'}),
            'date_of_birth': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
            'grade_level': forms.Select(attrs={'class': 'form-select'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.instance = kwargs.get('instance')
        super().__init__(*args, **kwargs)
        if self.instance:
            self.fields['email'].initial = self.instance.user.email
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['phone_number'].initial = self.instance.user.phone_number
            self.fields['country'].initial = self.instance.user.country
            self.fields['parents'].queryset = Parent.objects.filter(school=self.instance.school)
            self.fields['parents'].initial = self.instance.parent.all()
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.instance.school)

    def clean_phone_number(self):
        phone = self.cleaned_data.get('phone_number')
        if phone != self.instance.user.phone_number and User.objects.filter(phone_number=phone).exists():
            raise ValidationError("This phone number is already in use.")
        return phone

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email != self.instance.user.email and User.objects.filter(email=email).exists():
            raise ValidationError("This email is already in use.")
        return email

    def save(self, commit=True):
        student = super().save(commit=False)

        # Update User
        user = student.user
        user.email = self.cleaned_data['email']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.phone_number = self.cleaned_data['phone_number']
        user.country = self.cleaned_data.get('country')
        
        password = None
        if self.cleaned_data['reset_password']:
            password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
            user.set_password(password)

        user.save()

        if commit:
            student.save()
            # Update M2M parents
            student.parent.set(self.cleaned_data['parents'])

        # Send email if requested
        # if (self.cleaned_data['send_email'] or self.cleaned_data['reset_password']) and getattr(settings, 'EMAIL_HOST', None):
        #     subject = 'Account Update - Kiswate Digital Academy'
        #     message = f"""
        #     Dear {user.get_full_name()},
            
        #     Your student account has been updated.
        #     Email: {user.email}
        #     Grade: {student.grade_level}
        #     Temporary Password: {password}
            
        #     If you did not request this, contact admin.
        #     Login URL: {getattr(settings, 'FRONTEND_URL', 'https://yourapp.com/login')}
            
        #     Best regards,
        #     School Admin
        #     """
        #     send_mail(
        #         subject,
        #         message,
        #         settings.DEFAULT_FROM_EMAIL,
        #         [user.email],
        #         fail_silently=False,
        #     )

        return student


class SmartIDForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            queryset = User.objects.filter(
                Q(student__school=school) | Q(staffprofile__school=school)
            ).select_related('student', 'staffprofile').distinct().order_by('last_name', 'first_name')
            self.fields['profile'].queryset = queryset
            # Custom label for choices to distinguish Student vs Staff
            self.fields['profile'].label_from_instance = self.label_from_instance

    def label_from_instance(self, obj):
        if hasattr(obj, 'student') and obj.student:
            return f"Student: {obj.get_full_name()} ({obj.student.student_id})"
        elif hasattr(obj, 'staffprofile') and obj.staffprofile:
            return f"Staff: {obj.get_full_name()} ({obj.staffprofile.staff_id})"
        return str(obj)

    class Meta:
        model = SmartID
        fields = ['profile', 'card_id', 'user_f18_id', 'is_active']
        widgets = {
            'profile': forms.Select(attrs={'class': 'form-select'}),
            'card_id': forms.TextInput(attrs={'class': 'form-control'}),
            'user_f18_id': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }