from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django.utils import timezone
from userauths.models import User
from django.core.exceptions import ValidationError
import os
from django.contrib.auth.models import Group

# KDADTR-Specific Choice Constants 
GENDER_CHOICES = [
    ('m', 'Male'),
    ('f', 'Female'),
]

# Expanded POSITION_CHOICES to cover all stakeholders
POSITION_CHOICES = [
    ('teacher', 'Teacher'),
    ('hod', 'Head of Department'),  # New: For HODs
    ('administrator', 'Administrator'),
    ('class_teacher', 'Class Teacher'),
    ('clerks', 'Clerks'),
    ('finance', 'Finance'),
    ('security', 'Security Staff'),
    ('cook', 'Cook'),  # Kitchen
    ('dorm_supervisor', 'Dormitory Supervisor'),  # New: For dorms
    ('gate_keeper', 'School Gate Keeper'),  # New: For gate
    ('trip_coordinator', 'Trip Coordinator'),  # New: For school trips/games
    ('moe_policy_maker', 'MoE Policy Maker'),  # New: External stakeholders
    ('cleaner', 'Cleaner'),
    ('driver', 'Driver')
]

# New: ATTENDANCE_STATUS_CHOICES matching concept exactly
ATTENDANCE_STATUS_CHOICES = [
    ('P', 'Present'),
    ('ET', 'Excused Tardy'),
    ('UT', 'Unexcused Tardy'),
    ('EA', 'Excused Absence'),
    ('UA', 'Unexcused Absence'),
    ('IB', 'Inappropriate Behavior'),  # Links to DisciplineRecord
    ('18', 'Suspension'),  # Marked by Deputy/Principal
    ('20', 'Expulsion'),  # Marked only by Principal
]

# Expanded INCIDENT_TYPE_CHOICES for discipline
INCIDENT_TYPE_CHOICES = [
    ('late', 'Late Arrival'),
    ('tardy', 'Tardy'),
    ('absence', 'Absence'),
    ('misconduct', 'Misconduct'),
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

ENROLLMENT_STATUS_CHOICES = [
    ('active', 'Active'),
    ('completed', 'Completed'),
    ('dropped', 'Dropped'),
]

PLATFORM_CHOICES = [
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



SEVERITY_CHOICES = [
    ('minor', 'Minor'),
    ('major', 'Major'),
    ('critical', 'Critical'),
]

CERTIFICATE_TYPE_CHOICES = [
    ('provisional', 'Provisional Leaving'),
    ('final', 'Final Leaving'),
]

SCHOLARSHIP_STATUS_CHOICES = [
    ('submitted', 'Submitted'),
    ('under_review', 'Under Review'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

DISBURSEMENT_METHOD_CHOICES = [
    ('smart_id', 'Smart ID'),
    ('bank', 'Bank Account'),
]

WEEKDAY_CHOICES = [
        ("monday", "Monday"),
        ("tuesday", "Tuesday"),
        ("wednesday", "Wednesday"),
        ("thursday", "Thursday"),
        ("friday", "Friday"),
        ("saturday", "Saturday"),
        ("sunday", "Sunday"),
    ]

SCHOOL_CLASSIFICATION_CHOICES = [
    ('C1', 'National'),
    ('C2', 'Extra-County'),
    ('C3', 'County'),
    ('C4', 'Sub-County/Day'),
]

class County(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)

    def __str__(self):
        return self.name
    
class City(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='cities', blank=True, null=True)

    def __str__(self):
        return self.name

class Constituency(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='constituencies', blank=True, null=True)

    def __str__(self):
        return self.name
    
class SubCounty(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    county = models.ForeignKey(County, on_delete=models.CASCADE, related_name='sub_counties', blank=True, null=True)

    def __str__(self):
        return self.name

class Ward(models.Model):
    name = models.CharField(max_length=100, unique=True, blank=True, null=True)
    constituency = models.ForeignKey(Constituency, on_delete=models.CASCADE, related_name='wards', blank=True, null=True)

    def __str__(self):
        return self.name



# School model

class School(models.Model):
    name = models.CharField(max_length=255)
    school_classification = models.CharField(max_length=250, choices=SCHOOL_CLASSIFICATION_CHOICES, blank=True, null=True)  # e.g., public/private, boarding/day
    school_admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='school_admin_profile')
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    logo = models.ImageField(upload_to='school_logos/', blank=True, null=True)
    county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, blank=True)
    constituency = models.ForeignKey(Constituency, on_delete=models.SET_NULL, null=True, blank=True)
    sub_county = models.ForeignKey(SubCounty, on_delete=models.SET_NULL, null=True, blank=True)
    ward = models.ForeignKey(Ward, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

# Grade model
class Grade(models.Model):
    name = models.CharField(max_length=50)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='grades')
    lessons_per_term = models.PositiveIntegerField(default=9)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=50, db_index=True)
    capacity = models.PositiveIntegerField(default=30)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['school', 'code']

    def __str__(self):
        return f"{self.name} - {self.school.name}"

class Pathway(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='pathways')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='pathways')
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.grade.name}"


class Streams(models.Model):
    name = models.CharField(max_length=50)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='streams')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='streams')
    capacity = models.PositiveIntegerField(default=30)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['grade', 'name', 'school']

    def __str__(self):
        return f"{self.name}"

#Role Model for granular permissions
class Role(models.Model):
    name = models.CharField(max_length=50)  # e.g., 'class_teacher', 'mark_suspension'
    description = models.TextField(blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='roles')

    class Meta:
        unique_together = [('name', 'school')]

    def __str__(self):
        return self.name


# Subject
CURRICULUM_CHOICES = [
    ('cbc', 'CBC (Competency-Based)'),
    ('kcse', 'KCSE'),
    ('kcpe', 'KCPE'),
    ('igcse', 'IGCSE'),
    ('other', 'Other'),
]


class SubjectCatalog(models.Model):
    """Platform-level subject catalog managed by Kiswate admins.
    Schools activate entries from here rather than creating subjects from scratch."""
    name = models.CharField(max_length=255, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    curriculum = models.CharField(max_length=20, choices=CURRICULUM_CHOICES, default='cbc')
    is_core = models.BooleanField(default=True, help_text='Core/mandatory subject')
    is_elective = models.BooleanField(default=False)
    sessions_per_week_default = models.PositiveIntegerField(default=2)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject Catalog'
        verbose_name_plural = 'Subject Catalog'
        indexes = [
            models.Index(fields=['curriculum', 'is_active']),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class Subject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    code = models.CharField(max_length=100, blank=True)

    catalog_ref = models.ForeignKey(
        SubjectCatalog,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='school_subjects',
        help_text='Platform catalog entry this subject was activated from'
    )

    school = models.ForeignKey(School, on_delete=models.CASCADE)
    grade = models.ManyToManyField(Grade, related_name='subjects')
    pathway = models.ForeignKey(
        Pathway,
        on_delete=models.CASCADE,
        related_name='subjects',
        blank=True,
        null=True
    )

    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    sessions_per_week = models.PositiveIntegerField(default=2)

    is_elective = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} ({self.pathway})"



class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=50, unique=True, db_index=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    employment_date = models.DateField(blank=True, null=True)
    position = models.CharField(max_length=100, choices=POSITION_CHOICES)
    tsc_number = models.CharField(max_length=50, unique=True, blank=True, null=True)
    qualification = models.TextField(blank=True, null=True)
    subjects = models.ManyToManyField(Subject, related_name='teachers_subjects', blank=True, null=True)  # Changed(max_length=255, blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='teachers/', blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)    
    # New: department for support services (e.g., 'kitchen', 'security')
    department = models.CharField(max_length=50, blank=True)  # e.g., 'Dining Hall', 'School Gate'
    # New: M2M for permissions
    roles = models.ManyToManyField(Role, blank=True, related_name='staff_members')

    @property
    def is_class_teacher(self):
        """True when the staff member has the school-level 'class_teacher' role."""
        return self.roles.filter(name='class_teacher').exists()

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name}"


class ClassTeacherAssignment(models.Model):
    """Maps one teacher to one stream as class teacher for a given year."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='class_teacher_assignments')
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='class_teacher_streams')
    stream = models.ForeignKey('Streams', on_delete=models.CASCADE, related_name='class_teacher_assignments')
    assigned_by = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='ct_assignments_made'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [('stream', 'school')]  # one class teacher per stream

    def __str__(self):
        return f"{self.teacher} → {self.stream}"


# Parent
class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    parent_id = models.CharField(max_length=50, unique=True, db_index=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField(max_length=15, unique=True)
    address = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='parents/', blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True)
    roles = models.ManyToManyField(Role, blank=True, related_name='parents')  # New: Optional for parental roles

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name} ({self.parent_id})"

# Student
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=50, unique=True, db_index=True)
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    enrollment_date = models.DateField(blank=True, null=True)

    grade_level = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='students')
    stream = models.ForeignKey(Streams, on_delete=models.CASCADE, related_name='student_stream', blank=True, null=True)

    pathway = models.ForeignKey(
        Pathway,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='students'
    )

    bio = models.TextField(blank=True)
    parents = models.ManyToManyField(Parent, blank=True, related_name='children')
    profile_picture = models.ImageField(upload_to='students/', blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    suspended = models.BooleanField(default=False)  # New: For marking suspensions
    expelled = models.BooleanField(default=False)  # New: For marking expulsions

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id})"


class SubjectEnrollment(models.Model):
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
        related_name='subject_enrollments'
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='enrollments'
    )

    is_elective = models.BooleanField(default=False)
    enrolled_on = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'subject')

    def __str__(self):
        return f"{self.student} → {self.subject}"


class TeacherStreamAssignment(models.Model):
    teacher = models.ForeignKey(
        'StaffProfile',
        on_delete=models.CASCADE,
        related_name='assigned_streams'
    )
    stream = models.ForeignKey(
        'Streams',
        on_delete=models.CASCADE,
        related_name='assigned_teachers'
    )
    school = models.ForeignKey(
        'School',
        on_delete=models.CASCADE,
        related_name='teacher_stream_assignments'
    )
    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['teacher', 'stream', 'school']

    def __str__(self):
        return f"{self.teacher.user.get_full_name()} → {self.stream.name} ({self.school.name})"

# Enrollment
class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    lesson = models.ForeignKey(
        'Lesson',
        on_delete=models.CASCADE,
        related_name="l_enrollments",        blank=True, null=True
    )    
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default='active')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='enrollments')

    class Meta:
        indexes = [
            models.Index(fields=['lesson']),
            models.Index(fields=['student']),
        ]

    def __str__(self):
        return f"{self.student} → {self.lesson.subject if self.lesson else 'No Lesson'}"


class AcademicYear(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    name = models.CharField(max_length=20)  # e.g., "2025-2026"
    start_date = models.DateField()
    end_date = models.DateField()

    def __str__(self):
        return self.school.name + " - " + self.name

class Term(models.Model):
    year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, blank=True, null=True, related_name='terms')
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='terms')
    name = models.CharField(max_length=80)
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)

    class Meta:
        unique_together = ('school', 'name')
    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        return f"{self.name} - {self.school.name}"
    
class TimeSlot(models.Model):
    start_time = models.TimeField()
    end_time = models.TimeField()
    description = models.CharField(max_length=100, blank=True)
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='time_slots')
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey('StaffProfile', on_delete=models.SET_NULL, null=True, related_name='created_time_slots')
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey('StaffProfile', on_delete=models.SET_NULL, null=True, related_name='updated_time_slots')

    class Meta:
        unique_together = ['school', 'start_time', 'end_time']
        ordering = ['start_time']

    def __str__(self):
        return f"{self.start_time.strftime('%H:%M')} - {self.end_time.strftime('%H:%M')} ({self.description})"


class Timetable(models.Model):
    school = models.ForeignKey('School', on_delete=models.CASCADE, related_name='timetables', blank=True, null=True)
    grade = models.ForeignKey('Grade', on_delete=models.CASCADE, related_name='timetables', blank=True, null=True)  
    stream = models.ForeignKey('Streams', on_delete=models.CASCADE, related_name='timetables', blank=True, null=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='term_timetables', blank=True, null=True)
    year = models.PositiveIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['school', 'grade', 'stream', 'term', 'year']

    def __str__(self):
        return f"{self.grade} {self.stream} - {self.term} {self.year}"


WEEKDAY_CHOICES = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]

class Lesson(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='lessons', blank=True, null=True)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='lessons', blank=True, null=True)
    stream = models.ForeignKey('Streams', on_delete=models.CASCADE, related_name='lessons', blank=True, null=True)
    teacher = models.ForeignKey('StaffProfile', on_delete=models.CASCADE, related_name='lessons_taught', blank=True, null=True)
    day_of_week = models.CharField(max_length=10, choices=WEEKDAY_CHOICES, blank=True, null=True)
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE, related_name='lessons', blank=True, null=True)
    room = models.CharField(max_length=50, blank=True)
    is_canceled = models.BooleanField(default=False)
    lesson_date = models.DateField(blank=True, null=True)  # For one-off changes
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['day_of_week','lesson_date', 'time_slot__start_time']
        unique_together = ['timetable', 'subject', 'day_of_week', 'time_slot', 'stream','lesson_date']
        indexes = [
            models.Index(fields=['teacher', 'lesson_date']),
            models.Index(fields=['timetable', 'day_of_week']),
        ]

    def __str__(self):
        if self.time_slot:
            return f"{self.subject} - {self.stream} - {self.day_of_week} {self.time_slot.start_time}-{self.time_slot.end_time}"
        return f"{self.subject} - {self.stream} - {self.day_of_week}"

# VirtualClass 
class Session(models.Model):  # Renamed from VirtualClass for in-person/hybrid
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='sessions')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, null=True, blank=True, related_name='sessions')  # New: Link to physical lesson
    title = models.CharField(max_length=255)
    platform = models.CharField(max_length=50, choices=[('in_person', 'In-Person'), ('zoom', 'Zoom'), ('teams', 'Microsoft Teams'), ('meet', 'Google Meet'), ('other', 'Other')], default='in_person')  # Updated choices
    meeting_link = models.URLField(blank=True, null=True)
    scheduled_at = models.DateTimeField()
    duration = models.DurationField(blank=True, null=True)
    is_live = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='sessions')
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='sessions')

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.scheduled_at}"

# Attendance
def validate_file(file):
    max_size = 5 * 1024 * 1024  # 5MB
    ext = os.path.splitext(value.name)[1].lower()
    if ext not in ['.xls', '.xlsx']:
        raise ValidationError('Only Excel files (.xls, .xlsx) are allowed.')
    if value.size > max_size:
        raise ValidationError('File size must be under 5MB.')

class UploadedFile(models.Model):
    CATEGORY_CHOICES = [
        ('grade', 'Grade'),
        ('users', 'users'),
        ('subjects', 'Subjects'),
        ('timetable', 'timetable'),
        
    ]

    upload_file_category = models.CharField(max_length=20, choices=CATEGORY_CHOICES)
    file = models.FileField(upload_to='uploads/%Y/%m/%d/')
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_size = models.PositiveIntegerField(editable=False)
    file_type = models.CharField(max_length=20, editable=False)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='uploaded_files')

    def save(self, *args, **kwargs):
        self.file_size = self.file.size
        self.file_type = os.path.splitext(self.file.name)[1].lower()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.upload_file_category} - {self.file.name}"

class Attendance(models.Model):
    ATTENDANCE_STATUS_CHOICES = [
        ('P', 'Present'),
        ('ET', 'Excused Tardy'),
        ('UT', 'Unexcused Tardy'),
        ('EA', 'Excused Absence'),
        ('UA', 'Unexcused Absence'),
        ('IB', 'Behavior'),
        ('18', 'Suspension'),
        ('20', 'Expulsion'),
    ]

    enrollment = models.ForeignKey(
        Enrollment,
        on_delete=models.CASCADE,
        related_name='attendances'
    )
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.CASCADE, blank=True, null=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE, blank=True, null=True)
    date = models.DateField()
    status = models.CharField(
        max_length=20,
        choices=ATTENDANCE_STATUS_CHOICES
    )
    remarks = models.TextField(blank=True, null=True)
    marked_by = models.ForeignKey(
        StaffProfile,
        on_delete=models.SET_NULL,
        null=True,
        related_name='marked_attendance'
    )
    marked_at = models.DateTimeField(auto_now_add=True)

    def clean(self):
        # Only certain roles can mark '18'/'20'
        if self.status in ['18', '20'] and self.marked_by.position not in ['deputy_principal', 'principal']:
            raise ValidationError("Suspensions/Expulsions can only be marked by Deputy Principal or Principal.")
        super().clean()

    class Meta:
        indexes = [
            models.Index(fields=['enrollment']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['marked_by', 'date']),
        ]

    def __str__(self):
        return f"{self.enrollment.student} - {self.enrollment.lesson.subject} on {self.date}"



# DisciplineRecord
class DisciplineRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discipline_records')
    linked_attendance = models.ForeignKey(Attendance, on_delete=models.CASCADE, null=True, blank=True, related_name='discipline_links')  # New: For IB during lesson
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='discipline_records')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='discipline_records')
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPE_CHOICES, default='misconduct')
    description = models.TextField()
    date = models.DateField(db_index=True, default=timezone.now)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='minor')
    action_taken = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discipline_reports')
    frequency_count = models.PositiveIntegerField(default=1)  # New: Track repeats for patterns
    resolved = models.BooleanField(default=False)  # New: For follow-up

    class Meta:
        indexes = [models.Index(fields=['student', 'date', 'severity']),models.Index(fields=['teacher', 'date']),
models.Index(fields=['school', 'date']),]
    def __str__(self):
        return f"{self.get_incident_type_display()} - {self.student} ({self.severity})"

# SummaryReport Model
class SummaryReport(models.Model):
    REPORT_TYPE_CHOICES = [('class', 'By Class'), ('grade', 'By Grade'), ('school', 'Whole School')]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='summary_reports')
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name='summary_reports')
    report_type = models.CharField(max_length=10, choices=REPORT_TYPE_CHOICES)
    period_start = models.DateField()
    period_end = models.DateField()
    # JSON for totals: e.g., {'P': 150, 'UA': 10, 'total_sessions': 20, 'present_pct': 95.0}
    data = models.JSONField(default=dict)
    generated_at = models.DateTimeField(auto_now_add=True)
    generated_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True)

    class Meta:
        unique_together = ['school', 'grade', 'report_type', 'period_start', 'period_end']

    def __str__(self):
        return f"{self.get_report_type_display()} Summary {self.period_start} to {self.period_end} - {self.school.name}"

#Notification Model
class Notification(models.Model):
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')  # Parent/Admin/etc.
    title = models.CharField(max_length=255)
    message = models.TextField()
    related_attendance = models.ForeignKey(Attendance, on_delete=models.SET_NULL, null=True, blank=True)
    related_discipline = models.ForeignKey(DisciplineRecord, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    sent_at = models.DateTimeField(auto_now_add=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    # Delivery status tracking (None = not attempted, True = success, False = failed)
    sms_sent = models.BooleanField(null=True, blank=True)
    email_sent = models.BooleanField(null=True, blank=True)
    sms_error = models.CharField(max_length=500, blank=True)
    email_error = models.CharField(max_length=500, blank=True)

    class Meta:
        ordering = ['-sent_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'sent_at']),
        ]

    def __str__(self):
        return f"{self.title} to {self.recipient.get_full_name()}"

# Smart ID model 
class SmartID(models.Model):
    profile = models.OneToOneField(User, on_delete=models.CASCADE)
    id_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    card_id = models.CharField(max_length=100, unique=True, db_index=True)  # Physical card ID
    user_f18_id = models.CharField(max_length=100, unique=True, db_index=True)
    qr_code = models.ImageField(upload_to='smart_ids/', blank=True)  # Generated QR
    is_active = models.BooleanField(default=True)
    biometric_data = models.JSONField(blank=True, null=True)  # Optional biometric hash
    issued_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(blank=True, null=True)  # Last time the ID was used
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='smart_ids')

    def __str__(self):
        return f"Smart ID for {self.id_uuid}"
#School ScanLog model
class ScanLog(models.Model):
    smart_id = models.ForeignKey(SmartID, on_delete=models.CASCADE, related_name='scan_logs')
    scan_id =  models.CharField(max_length=100, unique=True, db_index=True)
    scanned_at = models.DateTimeField(auto_now_add=True)
    location = models.CharField(max_length=255, blank=True)  # e.g., "Main Gate", "Library"
    device_id = models.CharField(max_length=100, blank=True)  # ID of the scanning device
    action = models.CharField(max_length=50, blank=True)  # e.g., "Entry", "Exit"

    def __str__(self):
        return f"ScanLog: {self.smart_id} at {self.scanned_at}"

class GradeAttendance(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='grade_attendance')
    stream = models.ForeignKey(Streams, on_delete=models.CASCADE,blank=True, null=True)
    status = models.CharField(max_length=5, choices=ATTENDANCE_STATUS_CHOICES, default='P')
    recorded_at = models.DateTimeField(auto_now_add=True)
    scan_log = models.ForeignKey(ScanLog, null=True, blank=True, on_delete=models.SET_NULL)

    def __str__(self):
        return f"{self.student.user.get_full_name()} - {self.status}"    

# Payment model
class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)  # Nullable for general payments
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)

    class Meta:
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['school', 'paid_at']),
        ]

    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} for {self.student or 'General'}"


# Assignment/Quiz model 
class Assignment(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='assignments')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='assignments')
    title = models.CharField(max_length=255)
    description = models.TextField()
    due_date = models.DateTimeField()
    assignment_type = models.CharField(max_length=20, choices=ASSIGNMENT_TYPE_CHOICES, default='assignment')
    max_score = models.FloatField(default=100.0)
    file_attachment = models.FileField(upload_to='assignments/', blank=True)

    def __str__(self):
        return f"{self.title} - {self.subject}"

# Submission model 
class Submission(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='submissions')
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='submissions')
    submitted_at = models.DateTimeField(auto_now_add=True)
    score = models.FloatField(blank=True, null=True)
    feedback = models.TextField(blank=True)
    file_submission = models.FileField(upload_to='submissions/', blank=True)

    def __str__(self):
        return f"Submission for {self.enrollment.student} - {self.assignment.title}"


# Certificate model
class Certificate(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    certificate_number = models.CharField(max_length=50, unique=True, db_index=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='certificates')
    certificate_type = models.CharField(max_length=20, choices=CERTIFICATE_TYPE_CHOICES)
    issued_at = models.DateField()
    reason = models.TextField(blank=True)  # e.g., graduation, transfer
    pdf_file = models.FileField(upload_to='certificates/')

    def __str__(self):
        return f"{self.get_certificate_type_display()} for {self.student}"

# Book model for Library
class Book(models.Model):
    title = models.CharField(max_length=255)
    author = models.CharField(max_length=255)
    isbn = models.CharField(max_length=13, unique=True, blank=True, db_index=True)
    description = models.TextField()
    cover_image = models.ImageField(upload_to='books/', blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='books')
    linked_teachers = models.ManyToManyField(StaffProfile, blank=True, related_name='linked_books')  # TSC-linked teachers

    def __str__(self):
        return self.title

# Chapter model
class Chapter(models.Model):
    book = models.ForeignKey(Book, on_delete=models.CASCADE, related_name='chapters')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='chapters')
    title = models.CharField(max_length=255)
    content = models.TextField()  # Or FileField for PDF
    order = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=8, decimal_places=2, default=0.00)  # For micro-payments

    def __str__(self):
        return f"{self.title} - {self.book.title}"

# Library Access model 
class LibraryAccess(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, null=True, blank=True, related_name='accesses')
    accessed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Access to {self.chapter or self.book} by {self.student}"

# Scholarship model
class Scholarship(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    start_date = models.DateField()
    end_date = models.DateField()
    eligibility_criteria = models.TextField(blank=True)  # e.g., "Must be a student in Grade 8 or above"
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_scholarships')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.title
    
# Scholarship Application model
class ScholarshipApplication(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scholarship_applications')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='scholarship_applications')
    scholarship = models.ForeignKey(Scholarship, on_delete=models.CASCADE, related_name='applications', blank=True, null=True)
    documents = models.FileField(upload_to='scholarship_docs/', blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=SCHOLARSHIP_STATUS_CHOICES, default='submitted')
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    review_comments = models.TextField(blank=True, null=True)  # Comments from the reviewer
    date_reviewed = models.DateTimeField(blank=True, null=True)  # When the application was reviewed
    date_updated = models.DateTimeField(auto_now=True)  # Last update time

    def __str__(self):
        return f"{self.title} - {self.student}"

# Scholarship Disbursement (removed redundant student FK)
class ScholarshipDisbursement(models.Model):
    application = models.ForeignKey(ScholarshipApplication, on_delete=models.CASCADE, related_name='disbursement')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='scholarship_disbursements')
    amount_disbursed = models.DecimalField(max_digits=10, decimal_places=2)
    disbursed_at = models.DateTimeField()
    method = models.CharField(max_length=20, choices=DISBURSEMENT_METHOD_CHOICES)
    bank_details = models.TextField(blank=True)  # If bank
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)

    def __str__(self):
        return f"Disbursement for {self.application.title}"


class SubscriptionPlan(models.Model):
    """
    Defines the different subscription plans for the Smart Shule platform.
    These are global plans offered to schools.
    """
    PLAN_TYPE_CHOICES = (
        ('basic_school', 'Basic School Plan'),
        ('standard_school', 'Standard School Plan'),
        ('premium_school', 'Premium School Plan'),
        ('custom_school', 'Custom Enterprise Plan'),
        # Add other plans based on features/student capacity/etc.
    )
    BILLING_CYCLE_CHOICES = (
        ('monthly', 'Monthly'),
        ('annually', 'Annually'),
        ('quarterly', 'Quarterly'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True, choices=PLAN_TYPE_CHOICES,
                            help_text="Name of the subscription plan (e.g., Basic School, Premium School)")
    description = models.TextField(blank=True, help_text="Detailed description of the plan's benefits.")

    # Base pricing for the plan
    base_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.00)],
        help_text="Base price of the plan per billing cycle."
    )
    
    # Example of dynamic pricing: per student, per bus, etc.
    # You could have a separate model for pricing tiers if it gets complex
    price_per_student = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                            help_text="Additional cost per student per month/year.")
    price_per_bus = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                         help_text="Additional cost per bus per month/year.")
    price_per_parent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00,
                                         help_text="Additional cost per parent per month/year.")
    # Features: This is key for dynamic feature unlocking
    # Example: {"max_students": 500, "max_buses": 5, "sms_notifications": True, "whatsapp_integration": False, "realtime_tracking": True}
    features_json = models.JSONField(
        default=dict,
        blank=True,
        help_text="JSON object listing features and limits included in this plan. "
                  "E.g., {'max_students': 500, 'max_buses': 5, 'sms_notifications': True}"
    )

    is_active = models.BooleanField(default=True, help_text="Indicates if the plan is currently available for subscription.")
    default_billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='annually')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Subscription Plan"
        verbose_name_plural = "Subscription Plans"
        ordering = ['base_price']

    def __str__(self):
        return self.name

class SchoolSubscription(models.Model):
    """
    Manages a school's subscription to a specific SubscriptionPlan.
    This links a School (Tenant) to a SubscriptionPlan and payment details.
    """
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('pending', 'Payment Pending'), # For when payment is due but not yet confirmed
        ('expired', 'Expired'),
        ('trial', 'Trial'),
        ('paused', 'Paused'),
    )
    BILLING_CYCLE_CHOICES = (
        ('monthly', 'Monthly'),
        ('annually', 'Annually'),
        ('quarterly', 'Quarterly'),
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.OneToOneField(
        'School', # Reference to the School model from the 'schools' app
        on_delete=models.CASCADE,
        related_name='platform_subscription',
        help_text="The school (tenant) holding this subscription."
    )
    plan = models.ForeignKey(
        SubscriptionPlan,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='school_subscriptions',
        help_text="The subscription plan this school is subscribed to."
    )

    # Actual price charged for this specific subscription (can differ from plan's base_price due to discounts/prorations)
    price_charged = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.00)],
        help_text="The actual price charged for this subscription."
    )
    
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='annually')

    start_date = models.DateTimeField(default=timezone.now, help_text="Date and time when the subscription started.")
    end_date = models.DateTimeField(blank=True, null=True, help_text="Date and time when the subscription is set to end or expired.")
    next_billing_date = models.DateTimeField(blank=True, null=True, help_text="The next date on which the school will be billed.")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='trial', help_text="Current status of the school's subscription.")

    payment_method_last4 = models.CharField(
        max_length=4,
        blank=True,
        null=True,
        help_text="Last 4 digits of the payment method (e.g., card number)."
    )
    
    # Store dynamic quantities that affect pricing for this school's subscription
    current_students_count = models.PositiveIntegerField(default=0, help_text="Current number of active students in the school.")
    current_buses_count = models.PositiveIntegerField(default=0, help_text="Current number of active buses in the school.")
    current_parents_count = models.PositiveIntegerField(default=0, help_text="Current number of active parents in the school.")
    parents_to_pay = models.BooleanField(
        default=False,
        help_text="Indicates if parents are required to pay for the subscription."
    )
    school_to_pay = models.BooleanField(
        default=True,
        help_text="Indicates if the school itself is responsible for paying the subscription."
    )

    # User who manages this subscription (e.g., a school admin) - optional
    managed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_school_subscriptions',
        help_text="The global platform user who manages this school's subscription."
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "School Subscription"
        verbose_name_plural = "School Subscriptions"
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['end_date']),
        ]

    def __str__(self):
        return f"{self.school.name}'s {self.plan.name if self.plan else 'No Plan'} Subscription ({self.status})"

    def calculate_current_cost(self):
        """
        Calculates the current cost of the subscription based on the plan and usage.
        This would be used for invoicing.
        """
        if not self.plan:
            return 0.00
        
        cost = self.plan.base_price
        cost += self.current_students_count * self.plan.price_per_student
        cost += self.current_buses_count * self.plan.price_per_bus
        cost += self.current_parents_count * self.plan.price_per_parent
        # Apply any discounts or adjustments based on the plan's features
        # if self.plan.features_json:
            # Example: If the plan has a discount for a certain number of students
            # if 'student_discount' in self.plan.features_json:
            #     discount = self.plan.features_json['student_discount']
            #     cost -= discount * self.current_students_count
        return cost

    # Add methods like renew, cancel, mark_expired as in the previous example,
    # adapting them for school-level subscription logic.


class Invoice(models.Model):
    """
    Represents an invoice generated for a school's subscription payment.
    """
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('void', 'Void'),
    )

    invoice_id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    school = models.ForeignKey(
        'school', # Link to the School (Tenant)
        on_delete=models.CASCADE,
        related_name='invoices',
        help_text="The school to whom this invoice belongs."
    )
    subscription = models.ForeignKey(
        SchoolSubscription,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices',
        help_text="The subscription this invoice is associated with."
    )

    amount_due = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(0.00)])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, validators=[MinValueValidator(0.00)])
    currency = models.CharField(max_length=3, default='KES', help_text="Currency of the invoice (e.g., KES, USD).")
    parent = models.ForeignKey(
        'Parent', # Link to the Parent model if applicable
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices_paid',
        help_text="The parent responsible for this invoice, if applicable."
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')

    invoice_date = models.DateTimeField(default=timezone.now, help_text="Date when the invoice was generated.")
    due_date = models.DateTimeField(blank=True, null=True, help_text="Date when the invoice payment is due.")
    paid_at = models.DateTimeField(blank=True, null=True, help_text="Date and time when the invoice was successfully paid.")

    # A link to the hosted invoice PDF from the billing platform
    invoice_pdf_url = models.URLField(max_length=500, blank=True, null=True,
                                      help_text="URL to the hosted invoice PDF.")

    # Line items for dynamic invoicing (e.g., base plan, X students, Y buses)
    line_items = models.JSONField(
        default=list,
        blank=True,
        help_text="JSON array of line items in the invoice. "
                  "E.g., [{'description': 'Standard Plan', 'quantity': 1, 'unit_price': 5000, 'total': 5000}, "
                  "{'description': 'Per student fee', 'quantity': 200, 'unit_price': 5, 'total': 1000}]"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Invoice"
        verbose_name_plural = "Invoices"
        ordering = ['-invoice_date']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['invoice_date']),
        ]

    def __str__(self):
        return f"Invoice {self.invoice_id} for {self.school.name} - KES {self.amount_due} ({self.status})"

    # Add methods like mark_as_paid, mark_as_failed, is_overdue



SCHOOL_CLASSIFICATION_CHOICES = [
    ('C1', 'National'),
    ('C2', 'Extra-County'),
    ('C3', 'County'),
    ('C4', 'Sub-County/Day'),
]

LEAD_STATUS = [
    ("new", "New"),
    ("contacted", "Contacted"),
    ("demo_scheduled", "Demo Scheduled"),
    ("converted", "Converted"),
]


class ContactMessage(models.Model):

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Contact person
    first_name = models.CharField(max_length=100, blank=True, null=True)
    last_name = models.CharField(max_length=100, blank=True, null=True)
    email_address = models.EmailField(blank=True, null=True)
    contact_phone = models.CharField(max_length=20, blank=True, null=True)

    # School
    school_name = models.CharField(max_length=255, blank=True, null=True)
    school_category = models.CharField(
        max_length=5,
        choices=SCHOOL_CLASSIFICATION_CHOICES,
        blank=True,
        null=True
    )

    # Location
    county = models.CharField(max_length=100, blank=True, null=True)
    sub_county = models.CharField(max_length=100, blank=True, null=True)
    constituency = models.CharField(max_length=100, blank=True, null=True)
    ward = models.CharField(max_length=100, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    address = models.TextField(blank=True, null=True)

    # Inquiry
    message = models.TextField()

    # Lead tracking
    lead_status = models.CharField(
        max_length=20,
        choices=LEAD_STATUS,
        default="new"
    )

    # Security / tracking
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    # Verification
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    # Metadata
    created_at = models.DateTimeField(default=timezone.now)
    is_read = models.BooleanField(default=False)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email_address']),
            models.Index(fields=['school_name']),
            models.Index(fields=['lead_status']),
            models.Index(fields=['created_at']),
        ]

    def save(self, *args, **kwargs):

        if self.is_verified and not self.verified_at:
            self.verified_at = timezone.now()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.first_name} {self.last_name} - {self.school_name or 'N/A'}"
class MpesaStkPushRequestResponse(models.Model):
    merchant_request_id = models.CharField(max_length=100)
    checkout_request_id = models.CharField(max_length=100)
    response_code = models.CharField(max_length=10)
    response_description = models.CharField(max_length=255)
    customer_message = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    invoice_number = models.CharField(max_length=100, blank=True)
    is_paid = models.BooleanField(default=False)
    reason_not_paid = models.TextField(blank=True)
    amount = models.FloatField(blank=True, null=True)
    order_number = models.CharField(max_length=100, blank=True, null=True)

    def __str__(self):
        return f"STK Request For {self.wallet} Amount:{self.amount}"


class MpesaPayment(models.Model):
    merchant_request_id = models.CharField(max_length=255)
    checkout_request_id = models.CharField(max_length=255)
    result_code = models.IntegerField()
    result_desc = models.CharField(max_length=255)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_receipt_number = models.CharField(max_length=255, unique=True)
    wallet_balance = models.CharField(max_length=255, null=True, blank=True)
    transaction_date = models.BigIntegerField()
    phone_number = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.phone_number} | {self.mpesa_receipt_number} | {self.amount}'
    

class AbstractBaseModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class MpesaResponseBody(AbstractBaseModel):
    body = models.JSONField()

class PolicymakerProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='policymaker_profile')
    county = models.ForeignKey(County, on_delete=models.SET_NULL, null=True, blank=True)  # optional - scope to county
    role = models.CharField(max_length=100, choices=[('county_officer', 'County Officer'), ('national', 'National'), ('other', 'Other')])
    phone = models.CharField(max_length=15, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role}"

# Optional: Alert/Notification model
class AttendanceAlert(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    sent_to = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, related_name='received_alerts')  # principal
    message = models.TextField()
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2)  # e.g. 72.50%
    sent_at = models.DateTimeField(auto_now_add=True)
    is_resolved = models.BooleanField(default=False)

    def __str__(self):
        return f"Alert for {self.school} - {self.attendance_rate}%"


class Upload(models.Model):
    STATUS_CHOICES = [
        ('pending',    'Pending'),
        ('processing', 'Processing'),
        ('done',       'Done'),
        ('failed',     'Failed'),
    ]
    file = models.FileField(upload_to='uploads/')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='uploads', blank=True, null=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    category = models.CharField(max_length=50, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', db_index=True)
    result_json = models.JSONField(default=dict, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Upload #{self.pk} by {self.uploaded_by} ({self.category})"


# ─── AUDIT LOG ───────────────────────────────────────────────────────────────
class AuditLog(models.Model):
    ACTION_CHOICES = [('create', 'Created'), ('update', 'Updated'), ('delete', 'Deleted')]
    school = models.ForeignKey(School, on_delete=models.CASCADE, null=True, blank=True, related_name='audit_logs')
    model_name = models.CharField(max_length=100, db_index=True)
    object_id = models.PositiveIntegerField()
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    description = models.TextField(blank=True)
    changes = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['actor', 'timestamp']),
            models.Index(fields=['school', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.action} {self.model_name}#{self.object_id} by {self.actor} at {self.timestamp}"


# ─── COMPLAINT ───────────────────────────────────────────────────────────────
class Complaint(models.Model):
    STATUS_CHOICES = [
        ('open', 'Open'),
        ('in_review', 'In Review'),
        ('resolved', 'Resolved'),
        ('closed', 'Closed'),
    ]
    CATEGORY_CHOICES = [
        ('academic', 'Academic'),
        ('discipline', 'Discipline'),
        ('fees', 'Fees'),
        ('health', 'Health & Safety'),
        ('bullying', 'Bullying'),
        ('teacher', 'Teacher Conduct'),
        ('facilities', 'Facilities'),
        ('other', 'Other'),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='complaints')
    parent = models.ForeignKey(Parent, on_delete=models.CASCADE, related_name='complaints')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True, related_name='complaints')
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='other')
    subject = models.CharField(max_length=255)
    description = models.TextField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='open')
    response = models.TextField(blank=True)
    responded_by = models.ForeignKey(
        StaffProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='complaint_responses'
    )
    responded_at = models.DateTimeField(null=True, blank=True)
    is_anonymous = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['school', 'status']),
            models.Index(fields=['parent', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_category_display()} - {self.subject} ({self.get_status_display()})"


# ─── ANNOUNCEMENT ─────────────────────────────────────────────────────────────
class Announcement(models.Model):
    AUDIENCE_CHOICES = [
        ('all', 'Everyone'),
        ('students', 'Students Only'),
        ('parents', 'Parents Only'),
        ('staff', 'Staff Only'),
    ]
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='announcements')
    title = models.CharField(max_length=255)
    body = models.TextField()
    audience = models.CharField(max_length=20, choices=AUDIENCE_CHOICES, default='all')
    grade = models.ForeignKey(Grade, on_delete=models.SET_NULL, null=True, blank=True, related_name='announcements')
    is_pinned = models.BooleanField(default=False)
    created_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, related_name='announcements')
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['school', 'audience', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.school.name})"

    @property
    def is_active(self):
        from django.utils import timezone
        if self.expires_at:
            return timezone.now() <= self.expires_at
        return True


# ─── FEE INVOICE ──────────────────────────────────────────────────────────────
class FeeInvoice(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('partial', 'Partially Paid'),
        ('paid', 'Fully Paid'),
        ('waived', 'Waived'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('mpesa', 'M-Pesa STK Push'),
        ('cash', 'Cash'),
        ('cheque', 'Cheque'),
        ('bank', 'Bank Transfer'),
    ]
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fee_invoices')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_invoices')
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True)
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True)
    description = models.CharField(max_length=255, default='School Fees')
    amount_required = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')
    due_date = models.DateField(null=True, blank=True)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, null=True, blank=True)
    cheque_number = models.CharField(max_length=50, blank=True)
    receipt_number = models.CharField(max_length=50, unique=True, blank=True, db_index=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='fee_invoices_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['student', 'status']),
            models.Index(fields=['school', 'term']),
        ]

    def __str__(self):
        return f"{self.student} – {self.description} ({self.status})"

    @property
    def balance(self):
        return self.amount_required - self.amount_paid

    def save(self, *args, **kwargs):
        if not self.receipt_number:
            import uuid
            self.receipt_number = f"RCP-{str(uuid.uuid4()).upper()[:8]}"
        if self.amount_paid >= self.amount_required:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        else:
            self.status = 'pending'
        super().save(*args, **kwargs)


# ─── EXAM MODULE ──────────────────────────────────────────────────────────────

def cbc_grade_band(percentage):
    if percentage >= 75:
        return 'EE'
    elif percentage >= 50:
        return 'ME'
    elif percentage >= 25:
        return 'AE'
    return 'BE'


def kcse_grade(percentage):
    thresholds = [
        (80, 'A'), (75, 'A-'), (70, 'B+'), (65, 'B'), (60, 'B-'),
        (55, 'C+'), (50, 'C'), (45, 'C-'), (40, 'D+'), (35, 'D'),
        (30, 'D-'),
    ]
    for floor, grade in thresholds:
        if percentage >= floor:
            return grade
    return 'E'


class ExamSession(models.Model):
    """One exam period for a grade in a school (e.g., Term 1 End-Term 2025, Grade 7)."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exam_sessions')
    term = models.ForeignKey(Term, on_delete=models.SET_NULL, null=True, blank=True, related_name='exam_sessions')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='exam_sessions')
    name = models.CharField(max_length=150)
    year = models.PositiveIntegerField()
    cat_out_of = models.FloatField(default=30.0)
    assignment_out_of = models.FloatField(default=10.0)
    assessment_out_of = models.FloatField(default=10.0)
    exam_out_of = models.FloatField(default=50.0)
    is_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, related_name='exam_sessions_created')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year', '-created_at']
        indexes = [models.Index(fields=['school', 'year', 'is_published'])]

    def __str__(self):
        return f"{self.name} – {self.grade} ({self.year})"

    @property
    def total_marks(self):
        return self.cat_out_of + self.assignment_out_of + self.assessment_out_of + self.exam_out_of


class ExamResult(models.Model):
    """Per-student, per-subject score for an ExamSession."""
    session = models.ForeignKey(ExamSession, on_delete=models.CASCADE, related_name='results')
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='exam_results')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='exam_results')
    stream = models.ForeignKey(Streams, on_delete=models.CASCADE, related_name='exam_results', null=True, blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='exam_results')
    cat_score = models.FloatField(null=True, blank=True)
    assignment_score = models.FloatField(null=True, blank=True)
    assessment_score = models.FloatField(null=True, blank=True)
    exam_score = models.FloatField(null=True, blank=True)
    entered_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, related_name='exam_results_entered')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('session', 'student', 'subject')
        ordering = ['student__user__last_name', 'student__user__first_name']
        indexes = [
            models.Index(fields=['session', 'stream']),
            models.Index(fields=['session', 'subject']),
            models.Index(fields=['student', 'session']),
        ]

    def __str__(self):
        return f"{self.student} – {self.subject} – {self.session}"

    @property
    def total(self):
        scores = [s for s in [self.cat_score, self.assignment_score, self.assessment_score, self.exam_score] if s is not None]
        return round(sum(scores), 2) if scores else None

    @property
    def percentage(self):
        t = self.total
        max_t = self.session.total_marks
        if t is not None and max_t:
            return round((t / max_t) * 100, 1)
        return None

    @property
    def grade_band(self):
        pct = self.percentage
        return cbc_grade_band(pct) if pct is not None else '–'

    @property
    def kcse_grade_label(self):
        pct = self.percentage
        return kcse_grade(pct) if pct is not None else '–'


# ─── FINANCE MODULE ───────────────────────────────────────────────────────────

FEE_TYPE_CHOICES = [
    ('tuition', 'Tuition Fee'),
    ('development', 'Development Levy'),
    ('activity', 'Activity Fee'),
    ('boarding', 'Boarding Fee'),
    ('transport', 'Transport Fee'),
    ('uniform', 'Uniform Fee'),
    ('exam', 'Exam Fee'),
    ('other', 'Other'),
]


class FeeType(models.Model):
    """School-defined fee type names (replaces hardcoded FEE_TYPE_CHOICES)."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_types')
    name = models.CharField(max_length=100)

    class Meta:
        unique_together = ('school', 'name')
        ordering = ['name']

    def __str__(self):
        return self.name


class FeeStructure(models.Model):
    """Defines the fee charged for a grade (optionally a specific stream) per term."""
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='fee_structures')
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='fee_structures')
    stream = models.ForeignKey(
        Streams, on_delete=models.CASCADE, related_name='fee_structures',
        null=True, blank=True, help_text='Leave blank to apply to all streams in the grade'
    )
    term = models.ForeignKey(Term, on_delete=models.CASCADE, related_name='fee_structures')
    academic_year = models.ForeignKey(AcademicYear, on_delete=models.SET_NULL, null=True, blank=True, related_name='fee_structures')
    fee_type = models.ForeignKey(FeeType, on_delete=models.PROTECT, related_name='fee_structures', null=True, blank=True)
    description = models.CharField(max_length=255, default='School Fees')
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(StaffProfile, on_delete=models.SET_NULL, null=True, related_name='fee_structures_created')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['grade__name', 'fee_type__name']
        unique_together = ('school', 'grade', 'stream', 'term', 'fee_type')
        indexes = [models.Index(fields=['school', 'term', 'is_active'])]

    def __str__(self):
        stream_label = f' – {self.stream.name}' if self.stream else ''
        fee_label = self.fee_type.name if self.fee_type else 'Unknown'
        return f"{fee_label} | {self.grade.name}{stream_label} | {self.term.name} | KES {self.amount}"


class ExamUploadJob(models.Model):
    STATUS_PENDING    = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_DONE       = 'done'
    STATUS_FAILED     = 'failed'
    STATUS_CHOICES = [
        (STATUS_PENDING,    'Pending'),
        (STATUS_PROCESSING, 'Processing'),
        (STATUS_DONE,       'Done'),
        (STATUS_FAILED,     'Failed'),
    ]

    id           = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session      = models.ForeignKey('ExamSession', on_delete=models.CASCADE, related_name='upload_jobs')
    school       = models.ForeignKey('School', on_delete=models.CASCADE, related_name='exam_upload_jobs')
    stream       = models.ForeignKey('Streams', on_delete=models.SET_NULL, null=True, related_name='exam_upload_jobs')
    subject      = models.ForeignKey('Subject', on_delete=models.SET_NULL, null=True, related_name='exam_upload_jobs')
    uploaded_by  = models.ForeignKey('userauths.User', on_delete=models.SET_NULL, null=True)
    file_path    = models.CharField(max_length=500)
    status       = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    total_rows   = models.PositiveIntegerField(default=0)
    processed    = models.PositiveIntegerField(default=0)
    saved        = models.PositiveIntegerField(default=0)
    skipped      = models.PositiveIntegerField(default=0)
    error        = models.TextField(blank=True)
    created_at   = models.DateTimeField(auto_now_add=True)
    finished_at  = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    @property
    def progress_pct(self):
        if self.total_rows:
            return min(100, int(self.processed / self.total_rows * 100))
        return 0
