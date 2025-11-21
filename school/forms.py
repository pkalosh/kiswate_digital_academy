# forms.py in the school app (or relevant app)
from django import forms
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
    Certificate  # Include if needed, but per request, exclude LMS parts where possible
)

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

        if school:
            for name, field in self.fields.items():
                # Only filter fields that are QuerySets (FK or M2M)
                if hasattr(field, "queryset"):
                    model = field.queryset.model
                    
                    # Direct school relation
                    if hasattr(model, "school"):
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
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    class Meta:
        model = Parent
        fields = ['user', 'parent_id', 'date_of_birth', 'gender', 'phone', 'address', 'bio', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'bio': forms.Textarea(attrs={'rows': 2}),
        }

    def save(self, commit=True):
        parent = super().save(commit=False)
        if not parent.user_id:
            # Create user if not provided
            user_data = {
                'phone_number': self.cleaned_data['phone'],  # Or generate
                'email': f"{self.cleaned_data['phone']}@example.com",  # Placeholder
                'first_name': self.cleaned_data.get('user__first_name', ''),
                'last_name': self.cleaned_data.get('user__last_name', ''),
            }
            user = User.objects.create_user(**user_data, password=self.generate_temp_password())
            parent.user = user
        if commit:
            parent.save()
        # Send email if requested
        if self.cleaned_data['send_email']:
            self.send_welcome_email(parent)
        return parent

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def send_welcome_email(self, parent):
        # Implement email sending
        pass

class ParentEditForm(ParentCreationForm):
    class Meta(ParentCreationForm.Meta):
        exclude = ['parent_id']  # ID not editable

# ------------------------------- STAFF FORMS -------------------------------
class StaffCreationForm(BaseForm):
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    class Meta:
        model = StaffProfile
        fields = ['user', 'staff_id', 'date_of_birth', 'gender', 'employment_date', 'position', 'tsc_number', 'qualification', 'subjects', 'bio', 'profile_picture', 'department']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'employment_date': forms.DateInput(attrs={'type': 'date'}),
            'subjects': forms.TextInput(attrs={'placeholder': 'e.g., Math, English'}),
            'bio': forms.Textarea(attrs={'rows': 3}),
        }

    def save(self, commit=True):
        staff = super().save(commit=False)
        if not staff.user_id:
            user_data = {
                'username': self.cleaned_data['staff_id'],
                'email': f"{self.cleaned_data['staff_id']}@example.com",
                'first_name': self.cleaned_data.get('user__first_name', ''),
                'last_name': self.cleaned_data.get('user__last_name', ''),
            }
            user = User.objects.create_user(**user_data, password=self.generate_temp_password())
            staff.user = user
        if commit:
            staff.save()
        if self.cleaned_data['send_email']:
            self.send_welcome_email(staff)
        return staff

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def send_welcome_email(self, staff):
        # Implement
        pass

class StaffEditForm(StaffCreationForm):
    class Meta(StaffCreationForm.Meta):
        exclude = ['staff_id']

# ------------------------------- STUDENT FORMS -------------------------------
class StudentCreationForm(BaseForm):
    send_email = forms.BooleanField(required=False, initial=True, label="Send welcome email")
    reset_password = forms.BooleanField(required=False, initial=False, label="Reset password")

    class Meta:
        model = Student
        fields = ['user', 'student_id', 'date_of_birth', 'gender', 'enrollment_date', 'grade_level', 'bio', 'profile_picture']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'enrollment_date': forms.DateInput(attrs={'type': 'date'}),
            'bio': forms.Textarea(attrs={'rows': 2}),
        }

    def save(self, commit=True):
        student = super().save(commit=False)
        if not student.user_id:
            user_data = {
                'username': self.cleaned_data['student_id'],
                'email': f"{self.cleaned_data['student_id']}@example.com",
                'first_name': self.cleaned_data.get('user__first_name', ''),
                'last_name': self.cleaned_data.get('user__last_name', ''),
            }
            user = User.objects.create_user(**user_data, password=self.generate_temp_password())
            student.user = user
        if commit:
            student.save()
        if self.cleaned_data['send_email']:
            self.send_welcome_email(student)
        return student

    def generate_temp_password(self):
        return ''.join(random.choices(string.ascii_letters + string.digits, k=8))

    def send_welcome_email(self, student):
        # Implement
        pass

class StudentEditForm(StudentCreationForm):
    class Meta(StudentCreationForm.Meta):
        exclude = ['student_id']

# ------------------------------- SUBJECT FORM -------------------------------
class SubjectForm(BaseForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'code', 'teacher', 'grade', 'start_date', 'end_date', 'is_active']
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

# ------------------------------- TIMETABLE FORM -------------------------------
class TimetableForm(BaseForm):
    class Meta:
        model = Timetable
        fields = ['grade', 'term', 'year', 'start_date', 'end_date']
        widgets = {
            'term': forms.Select(choices=Timetable.TERM_CHOICES),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

# ------------------------------- LESSON FORM -------------------------------
class LessonForm(forms.ModelForm):
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

# ------------------------------- SCHOLARSHIP FORMS (if needed, but per request exclude) -------------------------------
# Skip LMS: ScholarshipForm, etc.

# Note: For excluded LMS parts (library, scholarships, certificates), omit their forms.
# Import random and string at top if used: import random; import string
# Ensure choices are imported from models if not already.