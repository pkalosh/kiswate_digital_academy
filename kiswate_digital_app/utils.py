"""
utils.py — helper functions for notifications, auto-grading, attendance, and reporting.
"""
from django.utils import timezone
from django.db.models import Avg, Count, Q


# ─── AUTO-GRADING ────────────────────────────────────────────────────────────

def auto_grade_attempt(attempt):
    """
    Grade an attempt for MCQ / True-False questions automatically.
    Short answer / essay questions require manual grading.
    Returns the total auto-score.
    """
    from .models import StudentAnswer, Question
    total_score = 0
    auto_gradeable_types = ('mcq', 'true_false')

    for answer in attempt.answers.select_related('question', 'selected_choice'):
        q = answer.question
        if q.question_type in auto_gradeable_types:
            if answer.selected_choice and answer.selected_choice.is_correct:
                answer.marks_awarded = q.marks
                total_score += q.marks
            else:
                answer.marks_awarded = 0
            answer.save(update_fields=['marks_awarded'])

    # Only mark as graded if all questions were auto-gradeable
    all_auto = not attempt.answers.filter(
        question__question_type__in=['short_answer', 'essay']
    ).exists()

    attempt.score = total_score
    attempt.auto_graded = True
    attempt.is_graded = all_auto
    if all_auto:
        attempt.submitted_at = attempt.submitted_at or timezone.now()
    attempt.save(update_fields=['score', 'auto_graded', 'is_graded'])
    return total_score


# ─── ATTENDANCE HELPERS ──────────────────────────────────────────────────────

def record_join_attendance(virtual_class, student_profile):
    """
    Called when a student clicks 'Join Class'.
    Creates or retrieves attendance record (idempotent).
    Returns (record, created).
    """
    from .models import ClassAttendance
    record, created = ClassAttendance.objects.get_or_create(
        virtual_class=virtual_class,
        student=student_profile,
        defaults={
            'joined_at': timezone.now(),
            'is_present': True,
            'marked_by_teacher': False,
        }
    )
    return record, created


def get_attendance_summary(virtual_class):
    """
    Returns a dict: {enrolled_count, present_count, absent_count, rate_pct}
    """
    from .models import Enrollment, ClassAttendance
    enrolled = Enrollment.objects.filter(
        program=virtual_class.program, is_active=True).count()
    present = ClassAttendance.objects.filter(
        virtual_class=virtual_class, is_present=True).count()
    absent = enrolled - present
    rate = round((present / enrolled * 100), 1) if enrolled else 0
    return {
        'enrolled_count': enrolled,
        'present_count': present,
        'absent_count': max(absent, 0),
        'rate_pct': rate,
    }


def get_student_attendance_rate(student_profile, program=None):
    """
    Returns overall attendance % for a student, optionally filtered by program.
    """
    from .models import ClassAttendance, VirtualClass
    qs = ClassAttendance.objects.filter(student=student_profile)
    if program:
        qs = qs.filter(virtual_class__program=program)

    total_classes = qs.count()
    present = qs.filter(is_present=True).count()
    rate = round((present / total_classes * 100), 1) if total_classes else 0
    return {'total': total_classes, 'present': present, 'rate': rate}


# ─── REPORT HELPERS ──────────────────────────────────────────────────────────

def get_program_performance_report(program):
    """
    Returns per-student performance summary for a program.
    """
    from .models import Enrollment, StudentAssessmentAttempt, Assessment
    enrollments = Enrollment.objects.filter(
        program=program, is_active=True
    ).select_related('student__user')

    assessments = Assessment.objects.filter(program=program, results_published=True)
    report = []

    for enr in enrollments:
        student = enr.student
        attempts = StudentAssessmentAttempt.objects.filter(
            student=student, assessment__in=assessments, is_graded=True)
        avg_score = attempts.aggregate(avg=Avg('score'))['avg']
        attendance = get_student_attendance_rate(student, program)

        report.append({
            'student': student,
            'attempts': attempts.count(),
            'avg_score': round(avg_score, 1) if avg_score else None,
            'attendance_rate': attendance['rate'],
            'attendance_present': attendance['present'],
            'attendance_total': attendance['total'],
        })

    return report


def get_teacher_activity_report(teacher_profile):
    """
    Returns summary of a teacher's activity — classes hosted, lessons created, assignments set.
    """
    from .models import VirtualClass, Lesson, Assignment
    classes = VirtualClass.objects.filter(teacher=teacher_profile)
    lessons = Lesson.objects.filter(teacher=teacher_profile)
    assignments = Assignment.objects.filter(program__teacher=teacher_profile)

    return {
        'teacher': teacher_profile,
        'classes_hosted': classes.count(),
        'upcoming_classes': classes.filter(scheduled_at__gt=timezone.now()).count(),
        'lessons_created': lessons.count(),
        'published_lessons': lessons.filter(is_published=True).count(),
        'assignments_set': assignments.count(),
    }


def get_school_utilization_report(school):
    """
    Returns school-level usage summary.
    """
    from .models import UserProfile, Program, VirtualClass, Enrollment
    students = UserProfile.objects.filter(school=school, role='student')
    teachers = UserProfile.objects.filter(school=school, role='teacher')
    programs = Program.objects.filter(school=school, is_active=True)
    classes = VirtualClass.objects.filter(program__school=school)

    return {
        'school': school,
        'student_count': students.count(),
        'teacher_count': teachers.count(),
        'program_count': programs.count(),
        'total_classes': classes.count(),
        'upcoming_classes': classes.filter(scheduled_at__gt=timezone.now()).count(),
        'total_enrollments': Enrollment.objects.filter(program__school=school).count(),
    }


# ─── NOTIFICATION HELPERS ────────────────────────────────────────────────────

def send_notification(recipient_profile, message, subject='', notification_type='email',
                      related_class=None, related_assessment=None):
    """
    Logs a notification. In production, wire up Africa's Talking SMS / Django email here.
    """
    from .models import NotificationLog
    log = NotificationLog.objects.create(
        recipient=recipient_profile,
        notification_type=notification_type,
        subject=subject,
        message=message,
        status='pending',
        related_class=related_class,
        related_assessment=related_assessment,
    )
    # --- TODO: replace stubs with real senders ---
    try:
        if notification_type in ('email', 'both'):
            _send_email(recipient_profile, subject, message)
        if notification_type in ('sms', 'both'):
            _send_sms(recipient_profile, message)
        log.status = 'sent'
        log.sent_at = timezone.now()
    except Exception as exc:
        log.status = 'failed'
        log.error_message = str(exc)
    log.save(update_fields=['status', 'sent_at', 'error_message'])
    return log


def _send_email(profile, subject, body):
    """Stub — wire to Django's send_mail or SendGrid."""
    from django.core.mail import send_mail
    from django.conf import settings
    if profile.user.email:
        send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [profile.user.email], fail_silently=False)


def _send_sms(profile, message):
    """Stub — wire to Africa's Talking SDK."""
    # import africastalking
    # africastalking.initialize(settings.AT_USERNAME, settings.AT_API_KEY)
    # sms = africastalking.SMS
    # sms.send(message, [profile.phone])
    pass


def notify_class_reminder(virtual_class):
    """
    Sends a class reminder to all enrolled students and the teacher.
    """
    from .models import Enrollment
    enrollments = Enrollment.objects.filter(
        program=virtual_class.program, is_active=True
    ).select_related('student__user')

    for enr in enrollments:
        msg = (
            f"Hi {enr.student.full_name}, reminder: "
            f"'{virtual_class.title}' starts at "
            f"{virtual_class.scheduled_at.strftime('%d %b %Y at %H:%M')}. "
            f"Join: {virtual_class.meeting_link}"
        )
        send_notification(
            enr.student, msg,
            subject=f"Class Reminder: {virtual_class.title}",
            notification_type='both',
            related_class=virtual_class,
        )


def notify_assignment_due(assignment):
    """Notifies enrolled students about an assignment deadline."""
    from .models import Enrollment
    enrollments = Enrollment.objects.filter(
        program=assignment.program, is_active=True
    ).select_related('student')

    for enr in enrollments:
        msg = (
            f"Hi {enr.student.full_name}, assignment '{assignment.title}' is due on "
            f"{assignment.due_date.strftime('%d %b %Y at %H:%M')}."
        )
        send_notification(
            enr.student, msg,
            subject=f"Assignment Due: {assignment.title}",
            notification_type='both',
        )