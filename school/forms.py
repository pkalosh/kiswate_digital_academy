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
    Grade, Parent, StaffProfile, Student, Subject, Enrollment, Timetable, Lesson,
    Session, Attendance, DisciplineRecord, Notification, SmartID, Payment,
    Assignment, Submission, Role, Invoice, SchoolSubscription, SubscriptionPlan,
    ContactMessage, Scholarship, ScholarshipApplication, Book, Chapter, LibraryAccess,
    Certificate,Term  # Include if needed, but per request, exclude LMS parts where possible
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



# ------------------------------- GRADE FORM -------------------------------
class GradeForm(BaseForm):
    class Meta:
        model = Grade
        fields = ['name', 'description', 'code', 'capacity']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'code': forms.TextInput(attrs={'placeholder': 'e.g., GRD-001'}),
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
class ParentCreationForm(BaseForm):
    # Extra admin controls
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    email = forms.EmailField(required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    phone_number = forms.CharField(max_length=20, required=True)
    country = forms.CharField(max_length=50, required=False)

    class Meta:
        model = Parent
        fields = [
            # Parent fields
            'parent_id',
            'date_of_birth',
            'gender',
            'address',
            'bio',
            'profile_picture',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'bio': forms.Textarea(attrs={'rows': 2, 'class': 'form-control'}),
            'parent_id': forms.TextInput(attrs={'class': 'form-control'}),
        }


    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field_name, field in self.fields.items():
            if not isinstance(field.widget, forms.CheckboxInput):
                if 'class' not in field.widget.attrs:
                    field.widget.attrs['class'] = 'form-control'

        # Additional styling
        self.fields['send_email'].widget.attrs['class'] = 'form-check-input'
        self.fields['reset_password'].widget.attrs['class'] = 'form-check-input'


    def save(self, commit=True):
        # Create User object
        password = self.generate_temp_password()
        print(password)

        user = User.objects.create_user(
            email=self.cleaned_data['email'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data['phone_number'],
            country=self.cleaned_data.get('country', ''),
            password=password,
            is_parent=True,
            is_verified=True,  # Assuming parents are verified by default
        )

        # Create Parent object
        parent = super().save(commit=False)
        parent.user = user
        parent.phone = self.cleaned_data['phone_number']
        parent.school = self.school  # Set school if provided

        if commit:
            parent.save()

        # Send welcome email?
        if self.cleaned_data['send_email']:
            self.send_welcome_email(parent, password)

        return parent, password

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def send_welcome_email(self, parent, password):
        # TODO: integrate email system
        pass

class ParentEditForm(ParentCreationForm):

    class Meta(ParentCreationForm.Meta):
        exclude = ['parent_id']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Remove creation-only fields
        creation_fields = ['send_email', 'reset_password', 'email',
                           'first_name', 'last_name', 'phone_number', 'country']

        for field in creation_fields:
            if field in self.fields:
                self.fields.pop(field)

    def save(self, commit=True):
        """
        Edit parent WITHOUT re-running the user creation logic
        present in ParentCreationForm.save().
        """
        # IMPORTANT: use ModelForm save(), not ParentCreationForm.save()
        parent = super(ParentCreationForm, self).save(commit=False)

        # You can update 'phone' or other fields if needed:
        # parent.phone = parent.user.phone_number

        if commit:
            parent.save()

        return parent

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

class StaffEditForm(StaffCreationForm):
    class Meta(StaffCreationForm.Meta):
        exclude = ['staff_id']

# ------------------------------- STUDENT FORMS -------------------------------
class StudentCreationForm(BaseForm):
    # Extra fields (for creating User)
    first_name = forms.CharField(max_length=100, label="First name")
    last_name = forms.CharField(max_length=100, label="Last name")
    email = forms.EmailField(required=False, label="Email (optional)")
    phone_number = forms.CharField(required=False, label="Phone (optional)")

    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    class Meta:
        model = Student
        fields = [
            'first_name', 'last_name', 'email', 'phone_number',
            'student_id', 'date_of_birth', 'gender', 'enrollment_date',
            'grade_level', 'bio', 'profile_picture', 'parents'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 2}),
            'parents': forms.SelectMultiple(),
        }

    def __init__(self, *args, **kwargs):
        # Get school from view
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        # ★ Add Bootstrap classes to all fields
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = f"{existing} form-control".strip()

        # Fix checkboxes (avoid applying form-control)
        for name in ['send_email', 'reset_password']:
            self.fields[name].widget.attrs['class'] = 'form-check-input'

        # Filter queryset fields when school provided
        if self.school:
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.school)
            self.fields['parents'].queryset = Parent.objects.filter(school=self.school)

        # ★ Make parents multi-select work with select2
        self.fields['parents'].widget.attrs.update({
            'class': 'form-control select2',
            'multiple': True,
        })

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def save(self, commit=True):
        temp_password = self.generate_temp_password()
        print(f"Generated temporary password: {temp_password}")

        # Create user for student
        user = User.objects.create_user(
            email=self.cleaned_data.get('email') or f"{self.cleaned_data['student_id']}@example.com",
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            phone_number=self.cleaned_data.get('phone_number', ''),
            password=temp_password,
            is_student=True,
            is_verified=True,  # Assuming students are verified by default
        )

        # Build Student instance
        student = super().save(commit=False)
        student.user = user
        student.school = self.school
        # student.parents = self.cleaned_data.get('parents', [])

        if commit:
            student.save()
            self.save_m2m()  # save parents many-to-many

        # Send welcome email
        if self.cleaned_data['send_email']:
            self.send_welcome_email(student, temp_password)

        return student, temp_password

    def send_welcome_email(self, student, password):
        # Implement email logic
        pass

class StudentEditForm(StudentCreationForm):
    class Meta(StudentCreationForm.Meta):
        exclude = ['student_id']

# ------------------------------- SUBJECT FORM -------------------------------
class SubjectForm(BaseForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'code', 'grade', 'start_date', 'end_date', 'is_active']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

# ------------------------------- ENROLLMENT FORM -------------------------------
class EnrollmentForm(BaseForm):
    class Meta:
        model = Enrollment
        fields = ['student', 'subject', 'status']
        widgets = {
            'status': forms.Select(choices=ENROLLMENT_STATUS_CHOICES),
        }

class TermForm(BaseForm):
    class Meta:
        model = Term
        fields = ['name', 'start_date', 'end_date']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

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
        fields = ['timetable', 'subject', 'teacher', 'date', 'start_time','day_of_week', 'end_time', 'room', 'is_canceled', 'notes']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        date = cleaned_data.get('date')
        day_of_week = cleaned_data.get('day_of_week')
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')
        teacher = cleaned_data.get('teacher')
        timetable = cleaned_data.get('timetable')
        instance = self.instance  # For edits

        if date and start_time and end_time and teacher:
            # Validate against timetable dates
            if date < timetable.start_date or date > timetable.end_date:
                raise ValidationError("Lesson date must be within the timetable term.")

            # Check teacher conflicts (core logic)
            exclude_id = instance.id if instance else None
            conflicts = Lesson.objects.filter(
                teacher=teacher,
                date=date,
                day_of_week=day_of_week,
                # Overlap query: Adapt to TimeField (use django.db.models.TimeField)
                start_time__lt=end_time,  # existing_start < proposed_end
                end_time__gt=start_time,  # existing_end > proposed_start
            ).exclude(id=exclude_id)

            if conflicts.exists():
                conflict_details = conflicts.values_list('id', 'timetable__grade__name', 'subject__name')
                raise ValidationError(
                    f"Teacher conflict on {date}: Already scheduled for {list(conflict_details)}."
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
class AttendanceForm(BaseForm):
    class Meta:
        model = Attendance
        fields = ['status', 'notes']
        widgets = {
            'status': forms.Select(choices=ATTENDANCE_STATUS_CHOICES),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Reason for absence/tardy'}),
        }

    def __init__(self, *args, lesson=None, **kwargs):
        super().__init__(*args, **kwargs)
        if lesson:
            self.instance.lesson = lesson

# For bulk attendance, use formset
from django.forms import formset_factory
AttendanceFormSet = formset_factory(AttendanceForm, extra=0, can_delete=False)

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


class ParentStudentCreationForm(forms.ModelForm):
    # Common User fields for parent and student
    parent_first_name = forms.CharField(max_length=100, required=True, label="Parent First Name")
    parent_last_name = forms.CharField(max_length=100, required=True, label="Parent Last Name")
    parent_email = forms.EmailField(required=False, label="Parent Email")
    parent_phone_number = forms.CharField(max_length=20, required=True, label="Parent Phone")

    student_first_name = forms.CharField(max_length=100, required=True, label="Student First Name")
    student_last_name = forms.CharField(max_length=100, required=True, label="Student Last Name")
    student_email = forms.EmailField(required=False, label="Student Email")
    student_phone_number = forms.CharField(max_length=20, required=False, label="Student Phone")

    # Extra options
    send_email = forms.BooleanField(required=False, initial=True)
    reset_password = forms.BooleanField(required=False, initial=False)

    # Parent-specific fields
    parent_id = forms.CharField(max_length=50, required=True)
    parent_dob = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    parent_gender = forms.ChoiceField(choices=GENDER_CHOICES, required=True)
    parent_address = forms.CharField(widget=forms.Textarea(attrs={'rows': 3}), required=False)
    parent_bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    parent_profile_picture = forms.ImageField(required=False)

    # Student-specific fields
    student_id = forms.CharField(max_length=50, required=True)
    student_dob = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    enrollment_date = forms.DateField(required=True, widget=forms.DateInput(attrs={'type': 'date'}))
    student_gender = forms.ChoiceField(choices=GENDER_CHOICES, required=True)
    grade_level = forms.ModelChoiceField(queryset=Grade.objects.none(), required=True)
    student_bio = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    student_profile_picture = forms.ImageField(required=False)
    # student_parents = forms.ModelMultipleChoiceField(queryset=Parent.objects.none(), required=False)

    class Meta:
        model = User  # We are creating related Parent and Student
        fields = []

    def __init__(self, *args, **kwargs):
        self.school = kwargs.pop('school', None)
        super().__init__(*args, **kwargs)

        # Bootstrap styling
        for field in self.fields.values():
            if not isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs['class'] = 'form-control'
        for name in ['send_email', 'reset_password']:
            self.fields[name].widget.attrs['class'] = 'form-check-input'

        # Set queryset for related fields
        if self.school:
            self.fields['grade_level'].queryset = Grade.objects.filter(school=self.school)
            # self.fields['student_parents'].queryset = Parent.objects.filter(school=self.school)
            # self.fields['student_parents'].widget.attrs.update({'class': 'form-control select2', 'multiple': True})

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    @transaction.atomic
    def save(self, commit=True):
        # ----- CREATE PARENT USER -----
        parent_temp_password = self.generate_temp_password()
        parent_user = User.objects.create_user(
            email=self.cleaned_data.get('parent_email') or f"{self.cleaned_data['parent_id']}@example.com",
            first_name=self.cleaned_data['parent_first_name'],
            last_name=self.cleaned_data['parent_last_name'],
            phone_number=self.cleaned_data['parent_phone_number'],
            password=parent_temp_password,
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
            profile_picture=self.cleaned_data['parent_profile_picture'],
            school=self.school,
        )

        # ----- CREATE STUDENT USER -----
        student_temp_password = self.generate_temp_password()
        student_user = User.objects.create_user(
            email=self.cleaned_data.get('student_email') or f"{self.cleaned_data['student_id']}@example.com",
            first_name=self.cleaned_data['student_first_name'],
            last_name=self.cleaned_data['student_last_name'],
            phone_number=self.cleaned_data.get('student_phone_number', ''),
            password=student_temp_password,
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
            profile_picture=self.cleaned_data['student_profile_picture'],
            school=self.school,
        )

        # Link student to parent
        student.parents.add(parent)

        # Send welcome email if needed
        if self.cleaned_data['send_email']:
            self.send_welcome_email(parent, parent_temp_password)
            self.send_welcome_email(student, student_temp_password)

        return parent, student, parent_temp_password, student_temp_password

    def send_welcome_email(self, instance, password):
        # TODO: Implement email logic
        pass

# ------------------------------- SCHOLARSHIP FORMS (if needed, but per request exclude) -------------------------------
# Skip LMS: ScholarshipForm, etc.

# Note: For excluded LMS parts (library, scholarships, certificates), omit their forms.
# Import random and string at top if used: import random; import string
# Ensure choices are imported from models if not already.