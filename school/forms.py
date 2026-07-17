# forms.py in the school app (or relevant app)
from django import forms
import random
import string
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from django.db.models import Q
import uuid
from .models import (
    Grade, Parent, StaffProfile, Student, Subject, SubjectCatalog, Enrollment, Timetable, Lesson,
    Session, Attendance, DisciplineRecord, Notification, SmartID, Payment,
    Assignment, Submission, Role, Invoice, SchoolSubscription, SubscriptionPlan, UploadedFile,
    ContactMessage, Scholarship, ScholarshipApplication, Book, Chapter, LibraryAccess,
    Certificate, Term, School, Streams, TimeSlot, CURRICULUM_CHOICES, Complaint,
    ExamSession, ExamResult, FeeStructure, FeeType, FeeInvoice, AcademicYear,
)
from django.db import transaction


from userauths.models import User
GENDER_CHOICES = [
    ('m', 'Male'),
    ('f', 'Female'),
]

POSITION_CHOICES = [
    ('teacher', 'Teacher'),
    ('hod', 'Head of Department'),
    ('deputy_principal', 'Deputy Principal'),
    ('principal', 'Principal'),
    ('administrator', 'Administrator'),
    ('security', 'Security Staff'),
    ('cook', 'Cook'),
    ('dorm_supervisor', 'Dormitory Supervisor'),
    ('gate_keeper', 'School Gate Keeper'),
    ('trip_coordinator', 'Trip Coordinator'),
    ('moe_policy_maker', 'MoE Policy Maker'),
    ('cleaner', 'Cleaner'),
    ('driver', 'Driver'),
    ('other', 'Other'),
]

ATTENDANCE_STATUS_CHOICES = [
    ('P', 'Present'),
    ('ET', 'Excused Tardy'),
    ('UT', 'Unexcused Tardy'),
    ('EA', 'Excused Absence'),
    ('UA', 'Unexcused Absence'),
    ('IB', 'Inappropriate Behavior'),
    ('18', 'Suspension'),
    ('20', 'Expulsion'),
]

INCIDENT_TYPE_CHOICES = [
    ('late', 'Late Arrival'),
    ('misconduct', 'Misconduct'),
    ('absence', 'Unauthorized Absence'),
    ('suspension', 'Suspension'),
    ('expulsion', 'Expulsion'),
    ('other', 'Other'),
]

SEVERITY_CHOICES = [
    ('minor', 'Minor'),
    ('major', 'Major'),
    ('critical', 'Critical'),
]

ENROLLMENT_STATUS_CHOICES = [
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('dropped', 'Dropped'),
]

PAYMENT_TYPE_CHOICES = [
    ('fees', 'School Fees'),
    ('micro', 'Micro-Payment (e.g., Chapter/Library)'),
    ('scholarship', 'Scholarship Disbursement'),
    ('service', 'Other Services (e.g., Meals, Printing)'),
]

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
]

PLATFORM_CHOICES = [
    ('in_person', 'In-Person'),
    ('zoom', 'Zoom'),
    ('teams', 'Microsoft Teams'),
    ('meet', 'Google Meet'),
    ('other', 'Other'),
]

ASSIGNMENT_TYPE_CHOICES = [
    ('assignment', 'Assignment'),
    ('quiz', 'Quiz'),
    ('assessment', 'Assessment'),
]

REPORT_TYPE_CHOICES = [
    ('class', 'By Class'),
    ('grade', 'By Grade'),
    ('school', 'Whole School'),
]

TERM_CHOICES = [
    ('1', 'Term 1'),
    ('2', 'Term 2'),
    ('3', 'Term 3'),
]

# Subscription/Invoice Choices
PLAN_TYPE_CHOICES = [
    ('basic_school', 'Basic School Plan'),
    ('standard_school', 'Standard School Plan'),
    ('premium_school', 'Premium School Plan'),
    ('custom_school', 'Custom Enterprise Plan'),
]

BILLING_CYCLE_CHOICES = [
    ('monthly', 'Monthly'),
    ('annually', 'Annually'),
    ('quarterly', 'Quarterly'),
]

SUBSCRIPTION_STATUS_CHOICES = [
    ('active', 'Active'),
    ('cancelled', 'Cancelled'),
    ('pending', 'Payment Pending'),
    ('expired', 'Expired'),
    ('trial', 'Trial'),
    ('paused', 'Paused'),
]

INVOICE_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
    ('void', 'Void'),
]
class BaseForm(forms.ModelForm):
    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school

        for name, field in self.fields.items():
            # Apply Bootstrap classes
            css = field.widget.attrs.get('class', '')
            if isinstance(field.widget, (forms.Select, forms.SelectMultiple)):
                field.widget.attrs['class'] = f'{css} form-select'.strip()
            else:
                field.widget.attrs['class'] = f'{css} form-control'.strip()

            # Filter by school if applicable
            if school and hasattr(field, 'queryset'):
                model = field.queryset.model
                if hasattr(model, 'school'):
                    field.queryset = field.queryset.filter(school=school)



class TermForm(BaseForm):

    class Meta:
        model = Term
        fields = ["name", "start_date", "end_date", "is_active"]

        widgets = {
            "name": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Enter term name (e.g., Term 1)"
            }),
            "start_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "end_date": forms.DateInput(attrs={
                "class": "form-control",
                "type": "date"
            }),
            "is_active": forms.CheckboxInput(attrs={
                "class": "form-check-input"
            }),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get("start_date")
        end = cleaned_data.get("end_date")
        name = cleaned_data.get("name")

        # Date validation
        if start and end and end < start:
            raise forms.ValidationError("End date cannot be earlier than start date.")

        # Prevent overlapping terms for same school
        if self.instance and self.instance.school:
            school = self.instance.school
            qs = Term.objects.filter(school=school)

            if self.instance.pk:
                qs = qs.exclude(pk=self.instance.pk)

            if start and end:
                if qs.filter(start_date__lte=end, end_date__gte=start).exists():
                    raise forms.ValidationError(
                        "This term overlaps with an existing term for this school."
                    )

        return cleaned_data


class TimeSlotForm(BaseForm):
    class Meta:
        model = TimeSlot
        fields = ["start_time", "end_time", "description"]
        widgets = {
            "start_time": forms.TimeInput(attrs={
                "class": "form-control",
                "type": "time",
                "step": "900"  # 15-minute increments
            }),
            "end_time": forms.TimeInput(attrs={
                "class": "form-control",
                "type": "time",
                "step": "900"
            }),
            "description": forms.TextInput(attrs={
                "class": "form-control",
                "placeholder": "Optional description"
            }),
        }

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        if start_time and end_time and end_time <= start_time:
            raise forms.ValidationError("End time must be after start time.")
        # Optional: Check for overlaps using self.school
        if self.school and self.instance.pk:  # Edit
            overlapping = TimeSlot.objects.filter(
                school=self.school,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exclude(pk=self.instance.pk).exists()
        else:  # Create
            overlapping = TimeSlot.objects.filter(
                school=self.school,
                start_time__lt=end_time,
                end_time__gt=start_time
            ).exists()
        if overlapping:
            raise forms.ValidationError("This time slot overlaps with an existing one.")
        return cleaned_data
# ------------------------------- GRADE FORM -------------------------------
class GradeForm(BaseForm):
    class Meta:
        model = Grade
        fields = ['name', 'description', 'code', 'capacity','is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'code': forms.TextInput(attrs={'placeholder': 'e.g., GRD-001'}),
        }

class GradeUploadForm(forms.ModelForm):
    class Meta:
        model = UploadedFile
        fields = ['file']
        widgets = {
            'file': forms.ClearableFileInput(attrs={'accept': '.xlsx'}),
        }
# ------------------------------- SMARTID FORMS -------------------------------
class SmartIDForm(BaseForm):
    class Meta:
        model = SmartID
        fields = ['profile', 'card_id', 'user_f18_id', 'is_active']
        widgets = {
            'card_id': forms.TextInput(attrs={'placeholder': 'Physical card serial'}),
            'user_f18_id': forms.TextInput(attrs={'placeholder': 'F18 user ID'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, school=school, **kwargs)

        if school:
            # Allow selecting only users belonging to this school (student/staff/parent)
            self.fields['profile'].queryset = User.objects.filter(
                Q(student__school=school) |
                Q(staffprofile__school=school) |
                Q(parent__school=school)
            ).distinct().select_related(
                'student',
                'staffprofile',
                'parent'
            )


# ------------------------------- PARENT FORMS -------------------------------
from .models import Student, Parent, Grade, Streams, GENDER_CHOICES  # noqa: F811

class BaseForm(forms.ModelForm):
    """Base form with common styling."""
    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        # General styling for all fields
        for field in self.fields.values():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-check-input'
            else:
                field.widget.attrs['class'] = 'form-control'

class StudentCreationForm(BaseForm):
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")
    first_name = forms.CharField(max_length=100, label="First name")
    last_name = forms.CharField(max_length=100, label="Last name")
    email = forms.EmailField(required=False, label="Email (optional)")
    phone_number = forms.CharField(max_length=20, required=False, label="Phone (optional)")

    class Meta:
        model = Student
        fields = [
            'student_id', 'date_of_birth', 'gender', 'enrollment_date',
            'grade_level', 'stream', 'bio', 'profile_picture', 'parents'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 2}),
            'parents': forms.SelectMultiple(attrs={'class': 'form-control select2', 'multiple': True}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)  # Pop here to match BaseForm expectation
        super().__init__(*args, **kwargs)
        self.school = school  # Ensure set after BaseForm (which also sets it)
        if self.school:
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.school)
            self.fields['stream'].queryset = Streams.objects.filter(school=self.school)
            self.fields['stream'].required = False
            self.fields['parents'].queryset = Parent.objects.filter(school=self.school)

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def save(self, commit=True):
        temp_password = self.generate_temp_password()
        user = User.objects.create_user(
            email=self.cleaned_data.get('email') or f"{self.cleaned_data['student_id']}@example.com",
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data.get('phone_number', ''),
            password=temp_password,
            is_student=True,
            is_verified=True,
        )
        student = super().save(commit=False)
        student.user = user
        student.school = self.school  # Now self.school is set correctly
        if commit:
            student.save()
            self.save_m2m()
        if self.cleaned_data['send_email']:
            self.send_welcome_email(student, temp_password)
        return student, temp_password

    def send_welcome_email(self, student, password):
        pass  # TODO: Implement

# ParentCreationForm - Already good (pops before super), but add queryset if needed (e.g., for future fields)
class ParentCreationForm(BaseForm):
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    phone_number = forms.CharField(max_length=20, required=True)

    class Meta:
        model = Parent
        fields = [
            'parent_id', 'date_of_birth', 'gender', 'address', 'bio', 'profile_picture'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'bio': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)  # Already pops correctly
        super().__init__(*args, **kwargs)
        self.school = school  # Redundant but safe
        # No queryset needed here, but add if expanding

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def save(self, commit=True):
        password = self.generate_temp_password()
        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data['phone_number'],
            password=password,
            is_parent=True,
            is_verified=True,
        )
        parent = super().save(commit=False)
        parent.user = user
        parent.phone = self.cleaned_data['phone_number']
        parent.school = self.school  # Now guaranteed set
        if commit:
            parent.save()
        if self.cleaned_data['send_email']:
            self.send_welcome_email(parent, password)
        return parent, password

    def send_welcome_email(self, parent, password):
        pass  # TODO: Implement

# ParentStudentCreationForm - Already good (pops before super), minor tweaks for consistency
class ParentStudentCreationForm(BaseForm):
    # Parent fields (as in your code)
    parent_first_name = forms.CharField(max_length=100, required=True, label="Parent First Name")
    parent_last_name = forms.CharField(max_length=100, required=True, label="Parent Last Name")
    parent_email = forms.EmailField(required=False, label="Parent Email")
    parent_phone_number = forms.CharField(max_length=20, required=True, label="Parent Phone")
    parent_id = forms.CharField(max_length=50, required=True)
    parent_dob = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    parent_gender = forms.ChoiceField(choices=GENDER_CHOICES, required=True)
    parent_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    parent_bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    parent_profile_picture = forms.ImageField(required=False)
    # Student fields (as in your code)
    student_first_name = forms.CharField(max_length=100, required=True, label="Student First Name")
    student_last_name = forms.CharField(max_length=100, required=True, label="Student Last Name")
    student_email = forms.EmailField(required=False, label="Student Email")
    student_phone_number = forms.CharField(max_length=20, required=False, label="Student Phone")
    student_id = forms.CharField(max_length=50, required=True)
    student_dob = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    enrollment_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    student_gender = forms.ChoiceField(choices=GENDER_CHOICES, required=True)
    grade_level = forms.ModelChoiceField(queryset=Grade.objects.none(), required=True)
    student_bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    student_profile_picture = forms.ImageField(required=False)
    # Common
    send_email = forms.BooleanField(required=False, initial=True)

    class Meta:
        model = User  # Dummy for form
        fields = []

    def __init__(self, *args, **kwargs):
        school = kwargs.pop('school', None)  # Already good
        super().__init__(*args, **kwargs)
        self.school = school
        if self.school:
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.school)

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    @transaction.atomic
    def save(self, commit=True):
        # Create Parent (as in your code, with school=self.school)
        parent_password = self.generate_temp_password()
        parent_user = User.objects.create_user(
            email=self.cleaned_data.get('parent_email') or f"{self.cleaned_data['parent_id']}@example.com",
            first_name=self.cleaned_data['parent_first_name'],
            last_name=self.cleaned_data['parent_last_name'],
            phone_number=self.cleaned_data['parent_phone_number'],
            password=parent_password,
            is_verified=True,
            is_parent=True,
        )
        parent = Parent.objects.create(
            user=parent_user,
            parent_id=self.cleaned_data['parent_id'],
            date_of_birth=self.cleaned_data['parent_dob'],
            gender=self.cleaned_data['parent_gender'],
            phone=self.cleaned_data['parent_phone_number'],
            address=self.cleaned_data['parent_address'],
            bio=self.cleaned_data['parent_bio'],
            profile_picture=self.cleaned_data.get('parent_profile_picture'),
            school=self.school,  # Guaranteed set
        )
        # Create Student (as in your code)
        student_password = self.generate_temp_password()
        student_user = User.objects.create_user(
            email=self.cleaned_data.get('student_email') or f"{self.cleaned_data['student_id']}@example.com",
            first_name=self.cleaned_data['student_first_name'],
            last_name=self.cleaned_data['student_last_name'],
            phone_number=self.cleaned_data.get('student_phone_number', ''),
            password=student_password,
            is_verified=True,
            is_student=True,
        )
        student = Student.objects.create(
            user=student_user,
            student_id=self.cleaned_data['student_id'],
            date_of_birth=self.cleaned_data['student_dob'],
            enrollment_date=self.cleaned_data['enrollment_date'],
            gender=self.cleaned_data['student_gender'],
            grade_level=self.cleaned_data['grade_level'],
            bio=self.cleaned_data['student_bio'],
            profile_picture=self.cleaned_data.get('student_profile_picture'),
            school=self.school,  # Guaranteed set
        )
        # Link
        student.parents.add(parent)
        # Emails
        if self.cleaned_data['send_email']:
            self.send_welcome_email(parent, parent_password)
            self.send_welcome_email(student, student_password)  # Assuming generic method
        return parent, student, parent_password, student_password

    def send_welcome_email(self, instance, password):
        pass  # TODO: Implement (generic for Parent/Student)
class AssignParentStudentForm(forms.Form):
    parent = forms.ModelChoiceField(queryset=Parent.objects.none(), label="Select Parent")
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label="Select Student")

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields['parent'].queryset = Parent.objects.filter(school=self.school)
            self.fields['student'].queryset = Student.objects.filter(school=self.school)
        self.fields['parent'].widget.attrs['class'] = 'form-control select2'
        self.fields['student'].widget.attrs['class'] = 'form-control select2'

# ------------------------------- STAFF FORMS -------------------------------
class StaffCreationForm(BaseForm):
    # Explicit user fields
    first_name = forms.CharField(max_length=100, label="First Name")
    last_name = forms.CharField(max_length=100, label="Last Name")
    email = forms.EmailField(required=False, label="Email (optional)")
    phone_number = forms.CharField(required=False, label="Phone (optional)")

    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    class Meta:
        model = StaffProfile
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',  # user fields
            'staff_id', 'date_of_birth', 'gender', 'employment_date', 'position',
            'tsc_number', 'qualification', 'subjects', 'bio', 'profile_picture', 'department', 'roles'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'employment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'form-select select2'}),
            'bio': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'roles': forms.SelectMultiple(attrs={'class': 'form-select select2'}),
            'position': forms.Select(attrs={'class': 'form-select'}),
            'gender': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school

        # Filter roles by school if provided
        if school and 'roles' in self.fields:
            self.fields['roles'].queryset = Role.objects.filter(school=school)
        if school and 'subjects' in self.fields:
            self.fields['subjects'].queryset = Subject.objects.filter(school=school)


    def generate_temp_password(self):
        """Generate a random temporary password."""
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def save(self, commit=True):
        staff = super().save(commit=False)

        # Generate temp password
        temp_password = self.generate_temp_password()

        # Create User
        user_data = {
            'first_name': self.cleaned_data['first_name'],
            'last_name': self.cleaned_data['last_name'],
            'email': self.cleaned_data.get('email') or f"{self.cleaned_data['staff_id']}@example.com",
            'password': temp_password,
            'is_staff': True,
            'is_verified': True,
            'is_teacher': True,  # Assuming staff are teachers by default
        }
        if hasattr(User, 'phone_number'):
            user_data['phone_number'] = self.cleaned_data.get('phone_number', '')

        user = User.objects.create_user(**user_data)
        staff.user = user

        # Attach school
        if self.school:
            staff.school = self.school

        if commit:
            staff.save()
            self.save_m2m()

        if self.cleaned_data.get('send_email'):
            self.send_welcome_email(staff, temp_password)

        return staff, temp_password

    def send_welcome_email(self, staff, password):
        # Implement your email logic here
        pass



# ------------------------------- SUBJECT FORM -------------------------------
class SubjectForm(BaseForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'code', 'grade','pathway', 'start_date', 'end_date', 'is_active', 'is_elective']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter grades by the school passed from BaseForm
        if self.school is not None:
            self.fields['grade'].queryset = Grade.objects.filter(school=self.school, is_active=True)

class AssignParentStudentForm(forms.Form):
    parent = forms.ModelChoiceField(queryset=Parent.objects.none(), label="Select Parent")
    student = forms.ModelChoiceField(queryset=Student.objects.none(), label="Select Student")

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if self.school:
            self.fields['parent'].queryset = Parent.objects.filter(school=self.school)
            self.fields['student'].queryset = Student.objects.filter(school=self.school)
        self.fields['parent'].widget.attrs['class'] = 'form-control select2'
        self.fields['student'].widget.attrs['class'] = 'form-control select2'

# ------------------------------- ENROLLMENT FORM -------------------------------
class EnrollmentForm(BaseForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'lesson', 'status']
        widgets = {
            'status': forms.Select(choices=ENROLLMENT_STATUS_CHOICES),
        }

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, school=school, **kwargs)
        # Avoid loading 100k+ lessons into a dropdown — scope to today's active lessons
        from django.utils import timezone
        from school.models import Lesson as LessonModel
        if school:
            today = timezone.now().date()
            self.fields['lesson'].queryset = LessonModel.objects.filter(
                timetable__school=school,
                lesson_date__gte=today,
            ).select_related('subject', 'time_slot').order_by('lesson_date', 'time_slot__start_time')[:500]
            self.fields['student'].queryset = self.fields['student'].queryset.filter(
                school=school
            ).select_related('user').order_by('user__last_name')

class TermForm(BaseForm):
    class Meta:
        model = Term
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }


class GenerateTimetableForm(forms.Form):
    SCOPE_CHOICES = [
        ('school', 'Whole School'),
        ('grade', 'Specific Grade'),
        ('stream', 'Specific Stream'),
    ]

    scope = forms.ChoiceField(
        choices=SCOPE_CHOICES,
        widget=forms.RadioSelect,
        required=True
    )

    school = forms.ModelChoiceField(
        queryset=School.objects.none(),  # Will set in __init__
        required=True,
        widget=forms.HiddenInput()  # always the logged-in user's school
    )

    grade = forms.ModelChoiceField(
        queryset=Grade.objects.none(),
        required=False
    )

    stream = forms.ModelChoiceField(
        queryset=Streams.objects.none(),
        required=False
    )

    overwrite = forms.BooleanField(
        required=False,
        initial=False,
        help_text="If checked, existing lessons in timetable will be deleted and regenerated."
    )

    def __init__(self, *args, **kwargs):
        # Expect 'school' argument from view
        school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)
        if school:
            # Set school to logged-in user's school
            self.fields['school'].queryset = School.objects.filter(pk=school.pk)
            self.fields['school'].initial = school

            # Limit grades and streams to that school
            self.fields['grade'].queryset = Grade.objects.filter(school=school, is_active=True)
            self.fields['stream'].queryset = Streams.objects.filter(grade__school=school, is_active=True)


class TimetableForm(BaseForm):
    class Meta:
        model = Timetable
        fields = ['grade', 'term', 'year', 'start_date', 'end_date']
        widgets = {
            'term': forms.Select(),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }
    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['term'].queryset = Term.objects.filter(school=school)

# ------------------------------- LESSON FORM -------------------------------
class LessonForm(BaseForm):
    class Meta:
        model = Lesson
        fields = ['timetable', 'stream','subject', 'teacher', 'day_of_week', 'time_slot', 'room', 'is_canceled', 'notes']
        widgets = {
            'time_slot': forms.Select(),
            'day_of_week': forms.Select(),
        }

    def clean(self):
        cleaned_data = super().clean()
        day_of_week = cleaned_data.get('day_of_week')
        time_slot = cleaned_data.get('time_slot')
        teacher = cleaned_data.get('teacher')
        stream = cleaned_data.get('stream')
        timetable = cleaned_data.get('timetable')
        lesson_date = cleaned_data.get('lesson_date')
        instance = self.instance

        if day_of_week and time_slot and teacher and timetable:
            exclude_id = instance.id if instance and instance.id else None

            # Conflict check
            conflicts = Lesson.objects.filter(
                teacher=teacher,
                day_of_week=day_of_week,
                time_slot=time_slot,
                timetable=timetable,  # restrict to same timetable
            ).exclude(id=exclude_id)

            # If lesson_date is set, only conflict with same date or null
            if lesson_date:
                conflicts = conflicts.filter(Q(lesson_date=lesson_date) | Q(lesson_date__isnull=True))
            else:
                # For lessons without specific date, conflict only with other lessons with no date
                conflicts = conflicts.filter(lesson_date__isnull=True)

            if conflicts.exists():
                conflict_details = conflicts.values_list('id', 'stream__name', 'subject__name')
                raise ValidationError(
                    f"Teacher conflict on {day_of_week}: Already scheduled for {list(conflict_details)}."
                )

        return cleaned_data

# ------------------------------- SESSION FORM (Virtual/Hybrid) -------------------------------
class SessionForm(BaseForm):
    class Meta:
        model = Session
        fields = ['subject', 'lesson', 'title', 'platform', 'meeting_link', 'scheduled_at', 'duration', 'is_live', 'recording_url']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g., Math Session 1'}),
            'platform': forms.Select(choices=PLATFORM_CHOICES),
            'meeting_link': forms.URLInput(attrs={'placeholder': 'https://zoom.us/j/123456789'}),
            'scheduled_at': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'duration': forms.TextInput(attrs={'placeholder': 'e.g., 01:00:00'}),  # Fixed: Use TextInput for DurationField
            'is_live': forms.CheckboxInput(),
            'recording_url': forms.URLInput(attrs={'placeholder': 'Recording link'}),
        }
    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['subject'].queryset = Subject.objects.filter(school=school)
            self.fields['lesson'].queryset = Lesson.objects.filter(timetable__school=school)

# ------------------------------- ATTENDANCE FORM -------------------------------
from django import forms
from .models import Attendance, ATTENDANCE_STATUS_CHOICES

class AttendanceForm(forms.ModelForm):
    class Meta:
        model = Attendance
        fields = ['status', 'remarks']
        widgets = {
            'status': forms.RadioSelect(choices=ATTENDANCE_STATUS_CHOICES),
            'remarks': forms.Textarea(attrs={
                'rows': 2,
                'class': 'form-control',
                'placeholder': 'Optional remarks...'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Optional: make status required visually
        self.fields['status'].required = True

# ------------------------------- DISCIPLINE FORM -------------------------------
class DisciplineRecordForm(BaseForm):
    class Meta:
        model = DisciplineRecord
        fields = ['student', 'incident_type', 'description', 'severity', 'action_taken']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'action_taken': forms.Textarea(attrs={'rows': 2}),
            'incident_type': forms.Select(choices=INCIDENT_TYPE_CHOICES),
            'severity': forms.Select(choices=SEVERITY_CHOICES),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Prefill default value for severity
        self.fields['severity'].initial = 'minor'

# ------------------------------- NOTIFICATION FORM -------------------------------
class NotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['recipient', 'title', 'message']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g., Attendance Alert'}),
            'message': forms.Textarea(attrs={'rows': 4}),
        }

# ------------------------------- PAYMENT FORM -------------------------------
class PaymentForm(BaseForm):
    class Meta:
        model = Payment
        fields = ['student', 'amount', 'payment_type', 'description', 'status']
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01'}),
            'payment_type': forms.Select(choices=PAYMENT_TYPE_CHOICES),
            'status': forms.Select(choices=PAYMENT_STATUS_CHOICES),
            'description': forms.Textarea(attrs={'rows': 2}),
        }

# ------------------------------- ASSIGNMENT FORM -------------------------------
class AssignmentForm(BaseForm):
    class Meta:
        model = Assignment
        fields = ['subject', 'title', 'description', 'due_date', 'assignment_type', 'max_score', 'file_attachment']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g., Homework #1'}),
            'description': forms.Textarea(attrs={'rows': 4}),
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'assignment_type': forms.Select(choices=ASSIGNMENT_TYPE_CHOICES),
        }

# ------------------------------- SUBMISSION FORM -------------------------------
class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ['file_submission', 'score', 'feedback']  # Score/feedback for grading
        widgets = {
            'feedback': forms.Textarea(attrs={'rows': 3}),
        }

# ------------------------------- ROLE FORM (Permissions) -------------------------------
class RoleForm(BaseForm):
    class Meta:
        model = Role
        fields = ['name', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

# ------------------------------- SCHOOL SUBSCRIPTION FORM -------------------------------
class SchoolSubscriptionForm(BaseForm):
    class Meta:
        model = SchoolSubscription
        fields = ['plan', 'billing_cycle', 'status']
        widgets = {
            'billing_cycle': forms.Select(choices=BILLING_CYCLE_CHOICES),
            'status': forms.Select(choices=SchoolSubscription.STATUS_CHOICES),
        }

# ------------------------------- INVOICE FORM -------------------------------
class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['amount_due', 'status', 'due_date', 'parent']
        widgets = {
            'amount_due': forms.NumberInput(attrs={'step': '0.01'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(choices=Invoice.STATUS_CHOICES),
        }

# ------------------------------- CONTACT MESSAGE FORM -------------------------------
class ContactMessageForm(forms.ModelForm):
    class Meta:
        model = ContactMessage
        fields = ['first_name', 'last_name', 'email_address', 'school_name', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 5}),
        }


class StudentUpdateForm(StudentCreationForm):
    """Update form for Student - excludes creation-specific fields like send_email if not needed."""
    class Meta(StudentCreationForm.Meta):
        exclude = ['student_id']  # Assume ID not editable; adjust as needed

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Hide or remove temp password fields for update
        self.fields.pop('send_email', None)
        self.fields.pop('reset_password', None)

    def save(self, commit=True):
        # No temp password generation for update
        student = super().save(commit=commit)
        # Update user fields if needed (e.g., first_name on user)
        if hasattr(self.instance, 'user'):
            self.instance.user.first_name = self.cleaned_data.get('first_name', self.instance.user.first_name)
            self.instance.user.last_name = self.cleaned_data.get('last_name', self.instance.user.last_name)
            self.instance.user.email = self.cleaned_data.get('email', self.instance.user.email)
            self.instance.user.phone_number = self.cleaned_data.get('phone_number', self.instance.user.phone_number)
            self.instance.user.save()
        return student

class ParentUpdateForm(ParentCreationForm):
    """Update form for Parent."""
    class Meta(ParentCreationForm.Meta):
        exclude = ['parent_id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('send_email', None)
        self.fields.pop('reset_password', None)

    def save(self, commit=True):
        parent = super().save(commit=commit)
        if hasattr(self.instance, 'user'):
            self.instance.user.first_name = self.cleaned_data.get('first_name', self.instance.user.first_name)
            self.instance.user.last_name = self.cleaned_data.get('last_name', self.instance.user.last_name)
            self.instance.user.email = self.cleaned_data.get('email', self.instance.user.email)
            self.instance.user.phone_number = self.cleaned_data.get('phone_number', self.instance.user.phone_number)
            self.instance.user.save()
        return parent

class StaffUpdateForm(StaffCreationForm):  # Assuming StaffCreationForm exists, similar structure
    """Update form for Staff."""
    class Meta:
        model = StaffProfile
        fields = '__all__'  # Adjust to exclude non-editable

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields.pop('send_email', None)
        self.fields.pop('reset_password', None)

    def save(self, commit=True):
        staff = super().save(commit=commit)
        if hasattr(self.instance, 'user'):
            # Update user fields similarly
            pass
        return staff


# ------------------------------- SUBJECT CATALOG FORM (Kiswate admin) --------
class SubjectCatalogForm(forms.ModelForm):
    class Meta:
        model = SubjectCatalog
        fields = ['name', 'code', 'description', 'curriculum', 'is_core', 'is_elective',
                  'sessions_per_week_default', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Mathematics'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., MATH'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'curriculum': forms.Select(attrs={'class': 'form-select'}),
            'sessions_per_week_default': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
            'is_core': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_elective': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


# ------------------------------- SUBJECT ACTIVATION FORM (principal) ---------
class SubjectActivationForm(forms.Form):
    """Used by principals to activate catalog subjects for their school."""
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        help_text='Activation start date (defaults to today)',
    )
    catalog_ids = forms.ModelMultipleChoiceField(
        queryset=SubjectCatalog.objects.filter(is_active=True),
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='',
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.school = school
        if school:
            already_active = Subject.objects.filter(
                school=school, catalog_ref__isnull=False
            ).values_list('catalog_ref_id', flat=True)
            self.fields['catalog_ids'].queryset = SubjectCatalog.objects.filter(
                is_active=True
            ).exclude(id__in=already_active)

    def activate(self, school):
        """Create Subject instances for each selected catalog entry."""
        created = []
        start_date = self.cleaned_data['start_date']
        for cat in self.cleaned_data['catalog_ids']:
            subj, new = Subject.objects.get_or_create(
                school=school,
                catalog_ref=cat,
                defaults={
                    'name': cat.name,
                    'code': cat.code,
                    'description': cat.description,
                    'is_elective': cat.is_elective,
                    'sessions_per_week': cat.sessions_per_week_default,
                    'start_date': start_date,
                    'is_active': True,
                }
            )
            if new:
                created.append(subj)
        return created


# ─── COMPLAINT FORM (parent self-service) ────────────────────────────────────

class ComplaintForm(forms.ModelForm):
    class Meta:
        model = Complaint
        fields = ['student', 'category', 'subject', 'description', 'is_anonymous']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief summary'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                 'placeholder': 'Describe the issue in detail…'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'student': forms.Select(attrs={'class': 'form-select'}),
            'is_anonymous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, parent=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent = parent
        if parent:
            self.fields['student'].queryset = parent.children.select_related('user', 'grade_level')
            self.fields['student'].required = False
            self.fields['student'].label = 'Regarding child (optional)'
            self.fields['student'].empty_label = '— All children / General —'


class StaffComplaintForm(forms.ModelForm):
    """Used by teachers and principals filing a complaint."""
    class Meta:
        model = Complaint
        fields = ['category', 'subject', 'description', 'is_anonymous']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief summary of the issue'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                  'placeholder': 'Describe the issue in detail…'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
            'is_anonymous': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class StudentComplaintForm(forms.ModelForm):
    """Used by students filing a complaint to school administration."""
    class Meta:
        model = Complaint
        fields = ['category', 'subject', 'description']
        widgets = {
            'subject': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Brief summary of the issue'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 4,
                                                  'placeholder': 'Describe the issue in detail…'}),
            'category': forms.Select(attrs={'class': 'form-select'}),
        }


# ─── BULK SUBJECT UPLOAD FORM ────────────────────────────────────────────────

class BulkSubjectUploadForm(forms.Form):
    file = forms.FileField(
        help_text='Excel (.xlsx) with columns: name, code, curriculum, is_core, is_elective, sessions_per_week_default, description',
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
    )

    def clean_file(self):
        f = self.cleaned_data['file']
        ext = f.name.rsplit('.', 1)[-1].lower()
        if ext not in ('xlsx', 'xls'):
            raise forms.ValidationError('Only .xlsx / .xls files are accepted.')
        if f.size > 5 * 1024 * 1024:
            raise forms.ValidationError('File must be under 5 MB.')
        return f


# ─── BULK NOTIFICATION FORM ───────────────────────────────────────────────────

class BulkNotificationForm(forms.Form):
    AUDIENCE_CHOICES = [
        ('all_parents',     'All Parents'),
        ('all_students',    'All Students'),
        ('all_staff',       'All Staff'),
        ('all',             'Everyone (parents, students, staff)'),
        ('grade_parents',   'Parents of a Grade'),
        ('grade_students',  'Students in a Grade'),
        ('stream_parents',  'Parents of a Stream'),
        ('stream_students', 'Students in a Stream'),
    ]

    title = forms.CharField(
        max_length=160,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Notification title / SMS header',
        }),
    )
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 'rows': 4,
            'placeholder': 'Type the message…',
            'id': 'id_bulk_message',
        }),
    )
    audience = forms.ChoiceField(
        choices=AUDIENCE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_audience'}),
    )
    grade = forms.ModelChoiceField(
        queryset=Grade.objects.none(),
        required=False,
        empty_label='— Select grade —',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    stream = forms.ModelChoiceField(
        queryset=Grade.objects.none(),
        required=False,
        empty_label='— Select stream —',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    channel_inapp = forms.BooleanField(
        required=False, initial=True, label='In-App (web)',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    channel_email = forms.BooleanField(
        required=False, label='Email',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )
    channel_sms = forms.BooleanField(
        required=False, label='SMS',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
    )

    def __init__(self, *args, school=None, **kwargs):
        super().__init__(*args, **kwargs)
        if school:
            self.fields['grade'].queryset = Grade.objects.filter(school=school)
            self.fields['stream'].queryset = Streams.objects.filter(school=school)

    def clean(self):
        cleaned = super().clean()
        audience = cleaned.get('audience', '')
        if 'grade' in audience and not cleaned.get('grade'):
            raise forms.ValidationError('Please select a grade for this audience.')
        if 'stream' in audience and not cleaned.get('stream'):
            raise forms.ValidationError('Please select a stream for this audience.')
        if not any([cleaned.get('channel_inapp'), cleaned.get('channel_email'), cleaned.get('channel_sms')]):
            raise forms.ValidationError('Select at least one delivery channel.')
        return cleaned


# ─── EXAM MODULE FORMS ────────────────────────────────────────────────────────

class ExamSessionForm(forms.ModelForm):
    class Meta:
        model = ExamSession
        fields = ['name', 'grade', 'term', 'year', 'cat_out_of', 'assignment_out_of', 'assessment_out_of', 'exam_out_of']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Term 1 End-Term Exams 2025'}),
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'year': forms.NumberInput(attrs={'class': 'form-control', 'min': 2020, 'max': 2100}),
            'cat_out_of': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'assignment_out_of': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'assessment_out_of': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
            'exam_out_of': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.5'}),
        }

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].queryset = Grade.objects.filter(school=school, is_active=True)
        self.fields['term'].queryset = Term.objects.filter(school=school).order_by('-start_date')
        self.fields['term'].required = False


class ExamResultForm(forms.ModelForm):
    class Meta:
        model = ExamResult
        fields = ['cat_score', 'assignment_score', 'assessment_score', 'exam_score']
        widgets = {
            'cat_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm score-input', 'step': '0.5', 'min': '0'}),
            'assignment_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm score-input', 'step': '0.5', 'min': '0'}),
            'assessment_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm score-input', 'step': '0.5', 'min': '0'}),
            'exam_score': forms.NumberInput(attrs={'class': 'form-control form-control-sm score-input', 'step': '0.5', 'min': '0'}),
        }


class ExamUploadForm(forms.Form):
    stream = forms.ModelChoiceField(
        queryset=Streams.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Select the stream this file covers',
    )
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
        help_text='Excel file: columns student_id, cat, assignment, assessment, exam',
    )

    def __init__(self, session, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['stream'].queryset = Streams.objects.filter(grade=session.grade, school=session.school)
        self.fields['subject'].queryset = Subject.objects.filter(school=session.school, grade=session.grade)


# ─── FINANCE MODULE FORMS ─────────────────────────────────────────────────────

class FeeStructureForm(forms.ModelForm):
    """Used for single-record edit only. Bulk create handled in the view directly."""
    class Meta:
        model = FeeStructure
        fields = ['grade', 'stream', 'term', 'academic_year', 'fee_type', 'description', 'amount']
        widgets = {
            'grade': forms.Select(attrs={'class': 'form-select'}),
            'stream': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'fee_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['grade'].queryset = Grade.objects.filter(school=school, is_active=True)
        self.fields['stream'].queryset = Streams.objects.filter(school=school)
        self.fields['stream'].required = False
        self.fields['term'].queryset = Term.objects.filter(school=school).order_by('-start_date')
        self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
        self.fields['academic_year'].required = False
        self.fields['fee_type'].queryset = FeeType.objects.filter(school=school)


class BulkInvoiceGenerateForm(forms.Form):
    fee_structures = forms.ModelMultipleChoiceField(
        queryset=FeeStructure.objects.none(),
        widget=forms.CheckboxSelectMultiple(),
        label='Fee Structures to Invoice',
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        required=False,
        label='Due Date (optional)',
    )
    overwrite_existing = forms.BooleanField(required=False, label='Re-generate if invoice already exists')

    def __init__(self, school, term, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['fee_structures'].queryset = FeeStructure.objects.filter(
            school=school, term=term, is_active=True
        ).select_related('grade', 'stream')


class FeePaymentUploadForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=Term.objects.none(),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    file = forms.FileField(
        widget=forms.ClearableFileInput(attrs={'class': 'form-control', 'accept': '.xlsx,.xls'}),
        help_text='Excel: columns student_id, amount, payment_method (cash/mpesa/cheque/bank), notes',
    )

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = Term.objects.filter(school=school).order_by('-start_date')


class FeeInvoiceForm(forms.ModelForm):
    class Meta:
        model = FeeInvoice
        fields = ['student', 'term', 'academic_year', 'description', 'amount_required', 'due_date', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.TextInput(attrs={'class': 'form-control'}),
            'amount_required': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'due_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, school, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.filter(school=school, is_active=True).select_related('user')
        self.fields['term'].queryset = Term.objects.filter(school=school).order_by('-start_date')
        self.fields['academic_year'].queryset = AcademicYear.objects.filter(school=school).order_by('-start_date')
        self.fields['academic_year'].required = False
        self.fields['due_date'].required = False
