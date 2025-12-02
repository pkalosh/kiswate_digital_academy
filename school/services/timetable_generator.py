# school/services/timetable_generator.py

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
    """
    Returns a list of TimeSlot objects ordered by start_time for the given school.
    """
    return TimeSlot.objects.filter(school=school).order_by('start_time')


def get_school_days_between(start_date, end_date):
    """
    Return all school days (Mon-Fri) between start_date and end_date.
    """
    day = start_date
    days = []
    while day <= end_date:
        if day.weekday() < 5:  # Monday=0, Friday=4
            days.append(day)
        day += timedelta(days=1)
    return days


def choose_teacher_for_subject(subject, school):
    """
    Return queryset of teachers (StaffProfile) in school that teach the subject.
    """
    return StaffProfile.objects.filter(school=school, subjects=subject)


def teacher_load_map(timetable, time_slots):
    """
    Returns dict of teacher_id -> set of (day_of_week, time_slot_index)
    representing busy slots for this timetable.
    """
    busy = {}
    for lesson in timetable.lessons.select_related('teacher', 'time_slot').all():
        tid = lesson.teacher_id
        if tid not in busy:
            busy[tid] = set()
        ts_idx = next((i for i, ts in enumerate(time_slots) if ts.id == lesson.time_slot_id), None)
        busy[tid].add((lesson.day_of_week, ts_idx))
    return busy


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

    # get all time slots for school
    time_slots = list(get_school_time_slots(school))
    if not time_slots:
        raise ValueError("No time slots defined for school")

    # get all school days within timetable-term window
    days = get_school_days_between(max(term.start_date, timetable.start_date),
                                   min(term.end_date, timetable.end_date))
    if not days:
        raise ValueError("No valid school days within the timetable/term window")

    created = []
    stream_occupied = set(
        (lesson.day_of_week, next((i for i, ts in enumerate(time_slots) if ts.id == lesson.time_slot_id), None))
        for lesson in timetable.lessons.all()
    )
    teacher_busy = teacher_load_map(timetable, time_slots)

    subjects = Subject.objects.filter(grade=grade, is_active=True)
    if not subjects.exists():
        raise ValueError("No subjects defined for grade")

    # Auto-enroll all students in the grade into each subject
    students = Student.objects.filter(grade_level=grade, school=school)
    for subject in subjects:
        for student in students:
            Enrollment.objects.get_or_create(
                student=student,
                subject=subject,
                school=school,
                defaults={'status': 'active'}
            )

    # Build subject weekly loads
    subject_loads = [(subj, max(1, getattr(subj, 'sessions_per_week', 2))) for subj in subjects]

    # iterate subjects
    for subject, weekly_load in subject_loads:
        teachers = list(choose_teacher_for_subject(subject, school))
        if not teachers:
            raise ValueError(f"No teacher assigned for subject {subject.name} in school {school.name}")
        teacher_ids = [t.id for t in teachers]

        created_count = 0
        teacher_rotate_idx = 0
        subject_dates = set(l.lesson_date for l in timetable.lessons.filter(subject=subject))

        day_idx = 0
        attempts = 0
        total_sessions = weekly_load * max(1, len(days) // len(WEEKDAYS))
        max_attempts = total_sessions * 20

        while created_count < total_sessions and attempts < max_attempts:
            cur_date = days[day_idx % len(days)]
            day_name = WEEKDAYS[cur_date.weekday()]

            if cur_date in subject_dates:
                day_idx += 1
                attempts += 1
                continue

            preferred_teacher_ids = teacher_ids[teacher_rotate_idx:] + teacher_ids[:teacher_rotate_idx]

            # find available time slot
            slot_idx = None
            chosen_tid = None
            for idx, ts in enumerate(time_slots):
                if (day_name, idx) in stream_occupied:
                    continue
                for tid in preferred_teacher_ids:
                    busy = teacher_busy.get(tid, set())
                    if (day_name, idx) not in busy:
                        slot_idx = idx
                        chosen_tid = tid
                        break
                if slot_idx is not None:
                    break

            if slot_idx is not None:
                teacher_obj = next((t for t in teachers if t.id == chosen_tid), teachers[0])
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
                subject_dates.add(cur_date)
                stream_occupied.add((day_name, slot_idx))
                teacher_busy.setdefault(teacher_obj.id, set()).add((day_name, slot_idx))
                teacher_rotate_idx = (teacher_rotate_idx + 1) % len(teacher_ids)

            day_idx += 1
            attempts += 1

    return created
