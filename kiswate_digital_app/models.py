from django.db import models
from django.utils import timezone
from userauths.models import User
from school.models import School


# ─── CHOICES ─────────────────────────────────────────────────────────────────

ROLE_CHOICES = [
    ('student', 'Student'),
    ('teacher', 'Teacher'),
    ('school_admin', 'School Admin'),
    ('super_admin', 'Super Admin'),
]

VETTING_STATUS = [
    ('pending', 'Pending'),
    ('approved', 'Approved'),
    ('rejected', 'Rejected'),
]

PLATFORM_CHOICES = [
    ('google_meet', 'Google Meet'),
    ('ms_teams', 'Microsoft Teams'),
    ('zoom', 'Zoom'),
]

QUIZ_TYPE_CHOICES = [
    ('quiz', 'Quiz'),
    ('cat', 'CAT'),
    ('end_of_topic', 'End of Topic'),
    ('exam', 'Exam'),
]

NOTIFICATION_TYPE = [
    ('sms', 'SMS'),
    ('email', 'Email'),
    ('both', 'Both'),
]

NOTIFICATION_STATUS = [
    ('pending', 'Pending'),
    ('sent', 'Sent'),
    ('failed', 'Failed'),
]


# ─── USER MANAGEMENT ─────────────────────────────────────────────────────────

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='members')
    phone = models.CharField(max_length=20, blank=True)
    id_number = models.CharField(max_length=20, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=10, choices=[('male','Male'),('female','Female'),('other','Other')], blank=True)
    profile_picture = models.ImageField(upload_to='profiles/', null=True, blank=True)
    bio = models.TextField(blank=True)
    vetting_status = models.CharField(max_length=10, choices=VETTING_STATUS, default='pending')
    vetting_notes = models.TextField(blank=True)
    vetted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='vetted_profiles')
    vetted_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_full_name()} ({self.role})"

    @property
    def full_name(self):
        return self.user.get_full_name()


class Guardian(models.Model):
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='guardians',
                                limit_choices_to={'role': 'student'})
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=50)
    phone = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    is_primary = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} → {self.student.full_name}"


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name


LEVEL_CHOICES = [
    ('primary', 'Primary'),
    ('form1', 'Form 1'), ('form2', 'Form 2'), ('form3', 'Form 3'), ('form4', 'Form 4'),
    ('grade1', 'Grade 1'), ('grade2', 'Grade 2'), ('grade3', 'Grade 3'), ('grade4', 'Grade 4'),
    ('grade5', 'Grade 5'), ('grade6', 'Grade 6'), ('grade7', 'Grade 7'), ('grade8', 'Grade 8'),
    ('grade9', 'Grade 9'), ('grade10', 'Grade 10'), ('grade11', 'Grade 11'), ('grade12', 'Grade 12'),
    ('olevel', 'O-Level'), ('alevel', 'A-Level'), ('diploma', 'Diploma'),
    ('certificate', 'Certificate'), ('other', 'Other'),
]

CATEGORY_CHOICES = [
    ('sciences', 'Sciences'), ('mathematics', 'Mathematics'), ('languages', 'Languages'),
    ('humanities', 'Humanities'), ('arts', 'Arts & Creative'), ('technical', 'Technical & Vocational'),
    ('ict', 'ICT & Computing'), ('business', 'Business & Commerce'), ('other', 'Other'),
]


class Program(models.Model):
    """A course/program students enroll into e.g. 'Form 3 Mathematics'. school=None means standalone tuition."""
    name = models.CharField(max_length=200)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='programs')
    school = models.ForeignKey(School, on_delete=models.SET_NULL, null=True, blank=True, related_name='programs')
    teacher = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='teaching_programs', limit_choices_to={'role': 'teacher'})
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    is_tuition = models.BooleanField(default=False)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, blank=True)
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        if self.school:
            return f"{self.name} — {self.school.name}"
        return f"{self.name} (Tuition)"


class Enrollment(models.Model):
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='enrollments',
                                limit_choices_to={'role': 'student'})
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ('student', 'program')

    def __str__(self):
        return f"{self.student.full_name} → {self.program.name}"


# ─── VIRTUAL LEARNING ────────────────────────────────────────────────────────

class VirtualClass(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='virtual_classes')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='hosted_classes', limit_choices_to={'role': 'teacher'})
    platform = models.CharField(max_length=20, choices=PLATFORM_CHOICES, default='google_meet')
    meeting_link = models.URLField()
    meeting_id = models.CharField(max_length=100, blank=True)
    passcode = models.CharField(max_length=50, blank=True)
    scheduled_at = models.DateTimeField()
    duration_minutes = models.PositiveIntegerField(default=60)
    is_recurring = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    recording_link = models.URLField(blank=True)  # post-class upload
    is_cancelled = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-scheduled_at']

    def __str__(self):
        return f"{self.title} ({self.scheduled_at.strftime('%d %b %Y %H:%M')})"

    @property
    def is_upcoming(self):
        return self.scheduled_at > timezone.now()

    @property
    def platform_icon(self):
        icons = {
            'google_meet': 'bi-camera-video-fill',
            'ms_teams': 'bi-microsoft',
            'zoom': 'bi-camera-video',
        }
        return icons.get(self.platform, 'bi-camera-video')


class ClassAttendance(models.Model):
    """
    Recorded when a student clicks 'Join Class'.
    Teacher can also mark attendance manually.
    """
    virtual_class = models.ForeignKey(VirtualClass, on_delete=models.CASCADE, related_name='attendance_records')
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='class_attendances',
                                limit_choices_to={'role': 'student'})
    joined_at = models.DateTimeField(default=timezone.now)
    marked_by_teacher = models.BooleanField(default=False)
    is_present = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ('virtual_class', 'student')

    def __str__(self):
        return f"{self.student.full_name} @ {self.virtual_class.title}"


class Lesson(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='lessons', limit_choices_to={'role': 'teacher'})
    topic = models.CharField(max_length=200, blank=True)
    notes_file = models.FileField(upload_to='lesson_notes/', null=True, blank=True)
    video_url = models.URLField(blank=True)
    order = models.PositiveIntegerField(default=0)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', 'created_at']

    def __str__(self):
        return f"{self.title} — {self.program.name}"


class Assignment(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='assignments')
    lesson = models.ForeignKey(Lesson, on_delete=models.SET_NULL, null=True, blank=True, related_name='assignments')
    title = models.CharField(max_length=200)
    instructions = models.TextField()
    attachment = models.FileField(upload_to='assignments/', null=True, blank=True)
    due_date = models.DateTimeField()
    total_marks = models.PositiveIntegerField(default=100)
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} — due {self.due_date.strftime('%d %b %Y')}"


class AssignmentSubmission(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='submissions')
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='submissions')
    file = models.FileField(upload_to='submissions/', null=True, blank=True)
    text_answer = models.TextField(blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    marks_obtained = models.FloatField(null=True, blank=True)
    feedback = models.TextField(blank=True)
    graded_at = models.DateTimeField(null=True, blank=True)
    graded_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True,
                                  related_name='graded_submissions')

    class Meta:
        unique_together = ('assignment', 'student')

    def __str__(self):
        return f"{self.student.full_name} → {self.assignment.title}"


# ─── ASSESSMENT ──────────────────────────────────────────────────────────────

class Assessment(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name='assessments')
    title = models.CharField(max_length=200)
    assessment_type = models.CharField(max_length=20, choices=QUIZ_TYPE_CHOICES, default='quiz')
    instructions = models.TextField(blank=True)
    total_marks = models.PositiveIntegerField(default=100)
    pass_mark = models.PositiveIntegerField(default=50)
    duration_minutes = models.PositiveIntegerField(default=60)
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    results_published = models.BooleanField(default=False)
    created_by = models.ForeignKey(UserProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='created_assessments')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} ({self.get_assessment_type_display()})"


class Question(models.Model):
    QUESTION_TYPE = [
        ('mcq', 'Multiple Choice'),
        ('true_false', 'True / False'),
        ('short_answer', 'Short Answer'),
        ('essay', 'Essay'),
    ]
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    question_type = models.CharField(max_length=20, choices=QUESTION_TYPE, default='mcq')
    marks = models.FloatField(default=1)
    order = models.PositiveIntegerField(default=0)
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"Q{self.order}: {self.text[:60]}"


class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.text


class StudentAssessmentAttempt(models.Model):
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='assessment_attempts')
    started_at = models.DateTimeField(default=timezone.now)
    submitted_at = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    is_graded = models.BooleanField(default=False)
    auto_graded = models.BooleanField(default=False)

    class Meta:
        unique_together = ('assessment', 'student')

    def __str__(self):
        return f"{self.student.full_name} — {self.assessment.title}"

    @property
    def percentage(self):
        if self.score is not None and self.assessment.total_marks:
            return round((self.score / self.assessment.total_marks) * 100, 1)
        return None

    @property
    def passed(self):
        if self.percentage is not None:
            return self.percentage >= self.assessment.pass_mark
        return None


class StudentAnswer(models.Model):
    attempt = models.ForeignKey(StudentAssessmentAttempt, on_delete=models.CASCADE, related_name='answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_choice = models.ForeignKey(Choice, on_delete=models.SET_NULL, null=True, blank=True)
    text_answer = models.TextField(blank=True)
    marks_awarded = models.FloatField(null=True, blank=True)


# ─── COMMUNICATION ───────────────────────────────────────────────────────────

class NotificationTemplate(models.Model):
    name = models.CharField(max_length=100)
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE)
    subject = models.CharField(max_length=200, blank=True)  # for email
    body = models.TextField(help_text="Use {name}, {class_title}, {date}, {link} as placeholders")
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class NotificationLog(models.Model):
    template = models.ForeignKey(NotificationTemplate, on_delete=models.SET_NULL, null=True, blank=True)
    recipient = models.ForeignKey(UserProfile, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPE)
    subject = models.CharField(max_length=200, blank=True)
    message = models.TextField()
    status = models.CharField(max_length=10, choices=NOTIFICATION_STATUS, default='pending')
    sent_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    related_class = models.ForeignKey(VirtualClass, on_delete=models.SET_NULL, null=True, blank=True)
    related_assessment = models.ForeignKey(Assessment, on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.notification_type.upper()} → {self.recipient.full_name} ({self.status})"


# ─── TUITION PAYMENTS ────────────────────────────────────────────────────────

PAYMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('failed', 'Failed'),
    ('refunded', 'Refunded'),
]

PAYMENT_METHOD_CHOICES = [
    ('mpesa', 'M-Pesa'),
    ('cash', 'Cash'),
    ('bank', 'Bank Transfer'),
    ('card', 'Card'),
    ('school', 'School Sponsored'),
]


class TuitionPayment(models.Model):
    enrollment = models.OneToOneField(Enrollment, on_delete=models.CASCADE, related_name='payment')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=10, choices=PAYMENT_METHOD_CHOICES, default='mpesa')
    transaction_id = models.CharField(max_length=100, blank=True)
    payer_phone = models.CharField(max_length=20, blank=True, help_text="M-Pesa or guardian phone")
    status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    paid_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.enrollment} — {self.get_status_display()}"