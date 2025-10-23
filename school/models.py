from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from userauths.models import User

# Choice constants (isolated for reuse)
GENDER_CHOICES = [
    ('m', 'Male'),
    ('f', 'Female'),
]

POSITION_CHOICES = [
    ('teacher', 'Teacher'),
    ('administrator', 'Administrator'),
    ('security', 'Security Staff'),
    ('cook', 'Cook'),
    ('cleaner', 'Cleaner'),
    ('driver', 'Driver'),
    ('other', 'Other'),
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

INCIDENT_TYPE_CHOICES = [
    ('late', 'Late Arrival'),
    ('misconduct', 'Misconduct'),
    ('absence', 'Unauthorized Absence'),
    ('other', 'Other'),
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

# School model for multi-tenancy
class School(models.Model):
    name = models.CharField(max_length=255)
    school_admin = models.OneToOneField(User, on_delete=models.CASCADE, related_name='school_admin_profile')
    code = models.CharField(max_length=50, unique=True)
    address = models.TextField(blank=True)
    contact_email = models.EmailField()
    contact_phone = models.CharField(max_length=15)
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

class Grade(models.Model):
    name = models.CharField(max_length=50)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='grades')
    description = models.TextField(blank=True)
    code = models.CharField(max_length=50, db_index=True)
    capacity = models.PositiveIntegerField(default=30)  # Default capacity
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['school', 'code']

    def __str__(self):
        return f"{self.name} - {self.school.name}"

# Teacher/Staff profile
class StaffProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    staff_id = models.CharField(max_length=50, unique=True, db_index=True)  # Unique staff ID
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    employment_date = models.DateField(blank=True, null=True)
    position = models.CharField(max_length=100, choices=POSITION_CHOICES)
    tsc_number = models.CharField(max_length=50, unique=True, blank=True, null=True)  # TSC-certified
    qualification = models.TextField(blank=True, null=True)  # e.g., B.Ed, M.Ed
    subjects = models.CharField(max_length=255, blank=True, null=True)  # Comma-separated
    bio = models.TextField(blank=True, null=True)  # Short biography
    profile_picture = models.ImageField(upload_to='teachers/', blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name}"

# Parent profile
class Parent(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    parent_id = models.CharField(max_length=50, unique=True, db_index=True)  # Unique parent ID
    date_of_birth = models.DateField(blank=True, null=True)
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES, blank=True)
    phone = models.CharField(max_length=15, unique=True)  # Unique phone number
    address = models.TextField(blank=True, null=True)
    bio = models.TextField(blank=True, null=True)  # Short biography
    profile_picture = models.ImageField(upload_to='parents/', blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.school.name} ({self.parent_id})"

# Student profile
class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    student_id = models.CharField(max_length=50, unique=True, db_index=True)  # Unique smart ID
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=10, choices=GENDER_CHOICES)
    enrollment_date = models.DateField()
    grade_level = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='students')
    bio = models.TextField(blank=True)
    parent = models.ManyToManyField(Parent, blank=True, related_name='children')  # Removed null=True as M2M handles empty
    profile_picture = models.ImageField(upload_to='students/', blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.student_id}) - {self.school.name}"

# Smart ID model (linked to student for access and payments)
class SmartID(models.Model):
    student = models.OneToOneField(Student, on_delete=models.CASCADE)
    id_uuid = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)
    qr_code = models.ImageField(upload_to='smart_ids/', blank=True)  # Generated QR
    is_active = models.BooleanField(default=True)
    biometric_data = models.JSONField(blank=True, null=True)  # Optional biometric hash
    issued_at = models.DateTimeField(auto_now_add=True)
    last_used = models.DateTimeField(blank=True, null=True)  # Last time the ID was used
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='smart_ids')

    def __str__(self):
        return f"Smart ID for {self.student}"

# Payment model (for fees, micro-payments, scholarships)
class Payment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, null=True, blank=True)  # Nullable for general payments
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='pending')
    transaction_id = models.CharField(max_length=100, unique=True, blank=True, db_index=True)
    paid_at = models.DateTimeField(blank=True, null=True)
    description = models.TextField(blank=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE)

    def __str__(self):
        return f"{self.get_payment_type_display()} - {self.amount} for {self.student or 'General'}"

class Subject(models.Model):
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)  # Moved description here, removed redundant 'subject'
    code = models.CharField(max_length=100, blank=True)  # Renamed from 'subject' to 'code'
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='subjects_taught')
    school = models.ForeignKey(School, on_delete=models.CASCADE)
    grade = models.ForeignKey(Grade, on_delete=models.CASCADE, related_name='subjects')
    start_date = models.DateField()
    end_date = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - {self.teacher}"

# Enrollment model
class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=ENROLLMENT_STATUS_CHOICES, default='active')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='enrollments')

    def __str__(self):
        return f"{self.student} enrolled in {self.subject} - {self.get_status_display()}"

# Virtual Class/Session model
class VirtualClass(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='virtual_classes')
    title = models.CharField(max_length=255)
    platform = models.CharField(max_length=50, choices=PLATFORM_CHOICES)
    meeting_link = models.URLField()
    scheduled_at = models.DateTimeField()  # Made required
    duration = models.DurationField(blank=True, null=True)
    is_live = models.BooleanField(default=False)
    recording_url = models.URLField(blank=True, null=True)
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='virtual_classes')
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='virtual_classes')

    def save(self, *args, **kwargs):
        # Removed faulty is_live logic; set via signal or manual
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} - {self.scheduled_at}"

# Attendance model (removed redundant FKs)
class Attendance(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='attendance')
    virtual_class = models.ForeignKey(VirtualClass, on_delete=models.CASCADE, null=True, blank=True, related_name='attendance')
    session_date = models.DateField(db_index=True)
    is_present = models.BooleanField(default=False)
    participation_score = models.FloatField(default=0.0, blank=True, null=True)  # 0-100

    def __str__(self):
        return f"Attendance for {self.enrollment.student} on {self.session_date}"

# Assignment/Quiz model (removed student FK, now per subject)
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

# Submission model (removed redundant student FK)
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

# Discipline Record model (removed duplicate school FK)
class DisciplineRecord(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    teacher = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='discipline_records')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='discipline_records')
    incident_type = models.CharField(max_length=20, choices=INCIDENT_TYPE_CHOICES)
    description = models.TextField()
    date = models.DateField(db_index=True)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='minor')
    action_taken = models.TextField(blank=True)
    reported_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='discipline_reports')

    def __str__(self):
        return f"{self.get_incident_type_display()} - {self.student}"

# Certificate model (removed duplicate school FK)
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

# Library Access model (removed duplicate chapter FKs)
class LibraryAccess(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE, null=True, blank=True)
    chapter = models.ForeignKey(Chapter, on_delete=models.CASCADE, null=True, blank=True, related_name='accesses')
    accessed_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f"Access to {self.chapter or self.book} by {self.student}"

# Scholarship Application model
class ScholarshipApplication(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='scholarship_applications')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='scholarship_applications')
    title = models.CharField(max_length=255)  # e.g., "Merit Scholarship 2025"
    amount_requested = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField()
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
    application = models.OneToOneField(ScholarshipApplication, on_delete=models.CASCADE, related_name='disbursement')
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name='scholarship_disbursements')
    amount_disbursed = models.DecimalField(max_digits=10, decimal_places=2)
    disbursed_at = models.DateTimeField()
    method = models.CharField(max_length=20, choices=DISBURSEMENT_METHOD_CHOICES)
    bank_details = models.TextField(blank=True)  # If bank
    transaction_id = models.CharField(max_length=100, blank=True, db_index=True)

    def __str__(self):
        return f"Disbursement for {self.application.title}"