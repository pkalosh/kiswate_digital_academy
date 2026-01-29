# your_app/management/commands/check_lessons.py
from django.core.management.base import BaseCommand
from datetime import timedelta
from school.models import Lesson, Subject,Grade, Term,StaffProfile
from collections import defaultdict
import datetime
class Command(BaseCommand):
    help = "Check lessons created for each subject/teacher for the current term"

    def handle(self, *args, **options):
        # Get the current term
        try:
            term = Term.objects.latest('start_date')
        except Term.DoesNotExist:
            self.stdout.write(self.style.ERROR("No Term found."))
            return

        self.stdout.write(f"[TERM] {term}: {term.start_date} → {term.end_date}")
        total_days = (term.end_date - term.start_date).days + 1
        total_weeks = (total_days + 6) // 7
        self.stdout.write(f"Total days: {total_days}, weeks: {total_weeks}\n")

        subjects = Subject.objects.all()
        for subject in subjects:
            teachers = subject.teachers_subjects.all()
            if not teachers:
                self.stdout.write(f"[SUBJECT] {subject.name} - No teacher assigned\n")
                continue

            self.stdout.write(f"[SUBJECT] {subject.name}")
            for teacher in teachers:
                self.stdout.write(f"  👨‍🏫 Teacher: {teacher.user.get_full_name()}")

                # Filter lessons for this subject & teacher in this term by lesson_date
                lessons = Lesson.objects.filter(
                    subject=subject,
                    teacher=teacher,
                    lesson_date__gte=term.start_date,
                    lesson_date__lte=term.end_date
                ).order_by('lesson_date')

                if not lessons.exists():
                    self.stdout.write("    ❌ No lessons created for this teacher.\n")
                    continue

                # Map lessons by week and weekday
                lessons_by_week = {}
                for lesson in lessons:
                    delta_days = (lesson.lesson_date - term.start_date).days
                    week_num = (delta_days // 7) + 1
                    weekday = lesson.lesson_date.strftime("%A")
                    if week_num not in lessons_by_week:
                        lessons_by_week[week_num] = []
                    lessons_by_week[week_num].append(weekday)

                # Print lessons per week
                for week in range(1, total_weeks + 1):
                    days = lessons_by_week.get(week, [])
                    if days:
                        self.stdout.write(f"    Week {week}: {', '.join(days)}")
                    else:
                        self.stdout.write(f"    Week {week}: ❌ No lessons created")

            self.stdout.write("")  # Blank line between subjects

        self.stdout.write(self.style.SUCCESS("Lesson check completed!"))