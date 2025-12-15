from datetime import timedelta
from django.db import transaction
from django.utils import timezone
from ..models import (
    Timetable, Lesson, Subject, StaffProfile, Student,
    TimeSlot, School, Enrollment
)

# Define working weekdays (school days)
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']


def get_school_time_slots(school):
    """Returns a list of TimeSlot objects ordered by start_time for the given school."""
    return TimeSlot.objects.filter(school=school).order_by('start_time')


def get_school_days_between(start_date, end_date):
    """Return all school days (Mon-Fri) between start_date and end_date (inclusive)."""
    day = start_date
    days = []
    while day <= end_date:
        if day.weekday() < 5:  # Monday=0 to Friday=4
            days.append(day)
        day += timedelta(days=1)
    return days


def choose_teacher_for_subject(subject, school):
    """Return queryset of teachers (StaffProfile) in school that teach the subject."""
    return StaffProfile.objects.filter(school=school, subjects=subject)


def teacher_load_map(lessons_queryset, time_slots):
    """
    Helper: builds busy map from a queryset of lessons.
    Format: teacher_id -> set of (day_of_week, time_slot_index)
    """
    busy = {}
    for lesson in lessons_queryset.select_related('teacher', 'time_slot'):
        if not lesson.teacher_id:
            continue
        tid = lesson.teacher_id
        busy.setdefault(tid, set())
        ts_idx = next((i for i, ts in enumerate(time_slots) if ts.id == lesson.time_slot_id), None)
        if ts_idx is not None:
            busy[tid].add((lesson.day_of_week, ts_idx))
    return busy


def global_teacher_busy_map(school, time_slots, term=None, exclude_timetable=None):
    """
    Build teacher busy map considering ALL lessons in the school (or term),
    excluding the current timetable if we're overwriting it.
    This prevents the same teacher from being double-booked across streams/grades.
    """
    queryset = Lesson.objects.filter(
        timetable__school=school,
        time_slot__school=school
    )
    if term:
        queryset = queryset.filter(timetable__term=term)
    if exclude_timetable:
        queryset = queryset.exclude(timetable=exclude_timetable)

    return teacher_load_map(queryset, time_slots)


@transaction.atomic
def generate_for_stream(timetable: Timetable, overwrite=False):
    """
    Generate lessons for a single Timetable (stream) using dynamic DB time slots.
    Auto-enroll students in the grade for all subjects.
    If overwrite=True, existing lessons for timetable are deleted first.
    Returns list of created Lesson objects.
    """
    if overwrite:
        timetable.lessons.all().delete()

    term = timetable.term
    if not term:
        raise ValueError("Timetable must reference a Term")

    school = timetable.school
    grade = timetable.grade
    stream = timetable.stream

    # Get all time slots for school
    time_slots = list(get_school_time_slots(school))
    if not time_slots:
        raise ValueError("No time slots defined for school")

    # Get all school days within the valid window
    days = get_school_days_between(
        max(term.start_date, timetable.start_date),
        min(term.end_date, timetable.end_date)
    )
    if not days:
        raise ValueError("No valid school days within the timetable/term window")

    created = []

    # Stream-specific occupied slots (different streams can share time slots if teachers/rooms differ)
    stream_occupied = set(
        (lesson.day_of_week, next((i for i, ts in enumerate(time_slots) if ts.id == lesson.time_slot_id), None))
        for lesson in timetable.lessons.all()
        if lesson.time_slot_id is not None
    )

    # CRITICAL FIX: Use GLOBAL teacher availability across the school (and term)
    teacher_busy = global_teacher_busy_map(
        school=school,
        time_slots=time_slots,
        term=term,
        exclude_timetable=timetable if overwrite else None
    )

    # Get active subjects for the grade
    subjects = Subject.objects.filter(grade=grade, is_active=True)
    if not subjects.exists():
        raise ValueError("No subjects defined for grade")

    # Auto-enroll all students in the grade into each subject
    students = Student.objects.filter(grade_level=grade, school=school)
    for subject in subjects:
        Enrollment.objects.bulk_create(
            [
                Enrollment(student=student, subject=subject, school=school, status='active')
                for student in students
                if not Enrollment.objects.filter(student=student, subject=subject, school=school).exists()
            ],
            ignore_conflicts=True
        )

    # Build subject weekly loads
    subject_loads = [(subj, max(1, getattr(subj, 'sessions_per_week', 2))) for subj in subjects]

    # Generate lessons per subject
    for subject, weekly_load in subject_loads:
        teachers = list(choose_teacher_for_subject(subject, school))
        if not teachers:
            raise ValueError(f"No teacher assigned for subject {subject.name} in school {school.name}")

        teacher_ids = [t.id for t in teachers]
        created_count = 0
        teacher_rotate_idx = 0

        # Track dates already assigned for this subject in this timetable (to avoid duplicates)
        subject_dates = set(
            l.lesson_date for l in timetable.lessons.filter(subject=subject)
        )

        # Total sessions needed (based on weeks in term)
        total_sessions = weekly_load * max(1, len(days) // len(WEEKDAYS))
        attempts = 0
        max_attempts = total_sessions * 30  # Increased safety margin

        day_idx = 0
        while created_count < total_sessions and attempts < max_attempts:
            cur_date = days[day_idx % len(days)]
            day_name = WEEKDAYS[cur_date.weekday()]

            # Skip if this date already has this subject in this timetable
            if cur_date in subject_dates:
                day_idx += 1
                attempts += 1
                continue

            # Rotate teacher preference order
            preferred_teacher_ids = teacher_ids[teacher_rotate_idx:] + teacher_ids[:teacher_rotate_idx]

            # Find an available slot and teacher
            slot_idx = None
            chosen_tid = None
            for idx, ts in enumerate(time_slots):
                if (day_name, idx) in stream_occupied:
                    continue  # Slot already used in this stream

                for tid in preferred_teacher_ids:
                    if (day_name, idx) not in teacher_busy.get(tid, set()):
                        slot_idx = idx
                        chosen_tid = tid
                        break
                if slot_idx is not None:
                    break

            if slot_idx is not None:
                teacher_obj = next(t for t in teachers if t.id == chosen_tid)

                lesson = Lesson.objects.create(
                    timetable=timetable,
                    subject=subject,
                    stream=stream,
                    teacher=teacher_obj,
                    day_of_week=day_name,
                    time_slot=time_slots[slot_idx],
                    lesson_date=cur_date,
                    room=f"{grade.name} {stream.name}",
                )
                created.append(lesson)
                created_count += 1

                # Update tracking structures
                subject_dates.add(cur_date)
                stream_occupied.add((day_name, slot_idx))
                teacher_busy.setdefault(teacher_obj.id, set()).add((day_name, slot_idx))

                # Rotate for next placement
                teacher_rotate_idx = (teacher_rotate_idx + 1) % len(teacher_ids)

            day_idx += 1
            attempts += 1

        if created_count < total_sessions:
            raise RuntimeError(
                f"Could not schedule all {total_sessions} sessions for {subject.name}. "
                f"Only scheduled {created_count}. Consider adding more time slots or teachers."
            )

    return created