from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator
from decimal import Decimal
import uuid
from django.utils import timezone
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


class ContactMessage(models.Model):
    """
    Model to store contact messages from individuals interested in Smart Shule.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    first_name = models.CharField(max_length=100, help_text="First name of the person contacting.")
    last_name = models.CharField(max_length=100, help_text="Last name of the person contacting.")
    email_address = models.EmailField(help_text="Email address for communication.")
    
    school_name = models.CharField(max_length=255, blank=True, null=True, 
                                   help_text="Name of the school the person represents or is inquiring about.")
    
    message = models.TextField(help_text="The content of the inquiry or message.")
    
    # Metadata
    created_at = models.DateTimeField(default=timezone.now, help_text="Timestamp when the message was received.")
    is_read = models.BooleanField(default=False, help_text="Indicates if the message has been reviewed by an admin.")
    
    class Meta:
        verbose_name = "Contact Message"
        verbose_name_plural = "Contact Messages"
        ordering = ['-created_at'] # Order newest messages first
        indexes = [
            models.Index(fields=['email_address']),
            models.Index(fields=['school_name']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"Message from {self.first_name} {self.last_name} ({self.school_name or 'N/A'}) - {self.created_at.strftime('%Y-%m-%d')}"

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

