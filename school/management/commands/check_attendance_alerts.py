"""
check_attendance_alerts — daily job that:

1. Flags class teachers who haven't marked roll-call today.
2. Computes each school's attendance rate for the day; if below threshold
   creates an AttendanceAlert and queues a Notification to the principal.
3. Flags students with consecutive absences and notifies parents.

Run once a day (after school hours) via cron:
    0 16 * * 1-5 /path/to/venv/bin/python manage.py check_attendance_alerts >> /var/log/kiswate/alerts.log 2>&1
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Count, Q
from school.models import (
    School, Student, StaffProfile, GradeAttendance, Attendance,
    ClassTeacherAssignment, Streams, Notification, AttendanceAlert, Term,
)


LOW_ATTENDANCE_THRESHOLD = 70  # percent
CONSECUTIVE_ABSENCE_DAYS = 3   # flag after this many missed days


class Command(BaseCommand):
    help = 'Check attendance rates and generate alerts for today.'

    def add_arguments(self, parser):
        parser.add_argument('--date', type=str, default=None,
                            help='Check date YYYY-MM-DD (default: today)')
        parser.add_argument('--threshold', type=int, default=LOW_ATTENDANCE_THRESHOLD,
                            help='Alert threshold percent (default 70)')

    def handle(self, *args, **options):
        check_date = (
            timezone.datetime.strptime(options['date'], '%Y-%m-%d').date()
            if options['date']
            else timezone.now().date()
        )
        threshold = options['threshold']
        self.stdout.write(f'[{check_date}] Running attendance checks...')

        for school in School.objects.filter(is_active=True):
            self._check_school(school, check_date, threshold)

        self.stdout.write(self.style.SUCCESS('Attendance alert check complete.'))

    # ── Per-school checks ─────────────────────────────────────────────────

    def _check_school(self, school, check_date, threshold):
        self._flag_unmarked_class_teachers(school, check_date)
        self._check_school_rate(school, check_date, threshold)
        self._check_consecutive_absences(school, check_date)

    def _flag_unmarked_class_teachers(self, school, check_date):
        """Notify class teachers who haven't submitted roll-call today."""
        assignments = ClassTeacherAssignment.objects.filter(
            school=school
        ).select_related('teacher__user', 'stream')

        for assignment in assignments:
            marked_today = GradeAttendance.objects.filter(
                stream=assignment.stream,
                recorded_at__date=check_date
            ).exists()
            if not marked_today:
                teacher = assignment.teacher
                stream = assignment.stream
                msg = (
                    f"Reminder: Roll-call for {stream.grade.name} {stream.name} "
                    f"has not been submitted for {check_date}. Please mark attendance."
                )
                self._queue_notification(
                    recipient=teacher.user,
                    title='Roll-Call Reminder',
                    message=msg,
                    school=school,
                )
                self.stdout.write(
                    f"  [{school.name}] Unmarked: {stream.grade.name} {stream.name} "
                    f"(teacher: {teacher.user.get_full_name()})"
                )

    def _check_school_rate(self, school, check_date, threshold):
        """Check overall school attendance rate; alert principal if low."""
        total_students = Student.objects.filter(school=school, is_active=True).count()
        if not total_students:
            return

        present_today = GradeAttendance.objects.filter(
            student__school=school,
            recorded_at__date=check_date,
            status='P'
        ).values('student').distinct().count()

        rate = round(present_today / total_students * 100, 1)

        if rate < threshold:
            msg = (
                f"Low attendance alert for {school.name}: "
                f"{rate}% present today ({present_today}/{total_students}). "
                f"Threshold is {threshold}%."
            )
            # Create AttendanceAlert record
            principal_staff = StaffProfile.objects.filter(
                school=school, position__icontains='principal'
            ).first()
            if principal_staff:
                AttendanceAlert.objects.create(
                    school=school,
                    sent_to=principal_staff,
                    message=msg,
                    attendance_rate=rate,
                )
                self._queue_notification(
                    recipient=principal_staff.user,
                    title='Low Attendance Alert',
                    message=msg,
                    school=school,
                )
            self.stdout.write(
                self.style.WARNING(
                    f"  [{school.name}] LOW ATTENDANCE: {rate}% (threshold {threshold}%)"
                )
            )
        else:
            self.stdout.write(
                f"  [{school.name}] Attendance OK: {rate}%"
            )

    def _check_consecutive_absences(self, school, check_date):
        """Flag students with N+ consecutive absences and notify their parents."""
        from datetime import timedelta
        absent_statuses = ['UA', 'EA']
        # Look back CONSECUTIVE_ABSENCE_DAYS school days
        window_start = check_date - timedelta(days=CONSECUTIVE_ABSENCE_DAYS + 2)

        students = Student.objects.filter(school=school, is_active=True).select_related('user')
        for student in students:
            # Use GradeAttendance (roll-call), simpler than lesson-level
            records = GradeAttendance.objects.filter(
                student=student,
                recorded_at__date__range=[window_start, check_date],
            ).order_by('-recorded_at__date')

            # Build consecutive-absence streak from today backwards
            streak = 0
            seen_dates = set()
            for r in records:
                d = r.recorded_at.date()
                if d in seen_dates:
                    continue
                seen_dates.add(d)
                if r.status != 'P':
                    streak += 1
                else:
                    break  # streak broken
                if streak >= CONSECUTIVE_ABSENCE_DAYS:
                    break

            if streak >= CONSECUTIVE_ABSENCE_DAYS:
                for parent in student.parents.all():
                    msg = (
                        f"Dear parent, {student.user.get_full_name()} has been absent "
                        f"for {streak} consecutive school days (up to {check_date}). "
                        f"Please contact {school.name} for assistance."
                    )
                    self._queue_notification(
                        recipient=parent.user,
                        title='Student Absence Alert',
                        message=msg,
                        school=school,
                    )
                self.stdout.write(
                    f"  [{school.name}] Absence streak: {student.user.get_full_name()} — {streak} days"
                )

    # ── Helpers ───────────────────────────────────────────────────────────

    def _queue_notification(self, recipient, title, message, school):
        """Create an in-app Notification (picked up by send_notifications cron)."""
        Notification.objects.create(
            recipient=recipient,
            title=title,
            message=message,
            school=school,
        )
