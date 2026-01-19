import datetime
from datetime import timedelta
from collections import defaultdict
from itertools import cycle
from django.db import transaction
from ..models import (
    Timetable, Lesson, Subject, StaffProfile,
    Student, TimeSlot, Enrollment
)
# ---------------- CONFIG ---------------- #
WEEKDAYS = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday']
PRIORITY_SUBJECTS = ['Mathematics', 'English']
MAX_SUBJECTS_PER_DAY = 2
MAX_TEACHER_PER_DAY = 3
MAX_CONSECUTIVE = 2
MAX_RETRY_PASSES = 3

# ---------------- HELPERS ---------------- #
def get_school_time_slots(school):
    return list(TimeSlot.objects.filter(school=school).order_by('start_time'))

def get_school_days_between(start_date, end_date):
    days = []
    d = start_date
    while d <= end_date:
        if d.weekday() < 5:  # Monday=0, Friday=4
            days.append(d)
        d += timedelta(days=1)
    return days

def stream_occupied_map(timetable, time_slots):
    occupied = set()
    for l in timetable.lessons.select_related('time_slot'):
        idx = next(i for i, ts in enumerate(time_slots) if ts.id == l.time_slot_id)
        occupied.add((l.day_of_week, idx))
    return occupied

def global_teacher_load(school, start_date, end_date, time_slots):
    busy = {}
    daily = {}
    lessons = Lesson.objects.filter(
        timetable__school=school,
        lesson_date__range=(start_date, end_date)
    ).select_related('time_slot')
    for l in lessons:
        tid = l.teacher_id
        day = l.day_of_week
        idx = next(i for i, ts in enumerate(time_slots) if ts.id == l.time_slot_id)
        busy.setdefault(tid, set()).add((day, idx))
        daily.setdefault(tid, {}).setdefault(day, 0)
        daily[tid][day] += 1
    return busy, daily

def has_three_consecutive(tid, day, idx, teacher_busy):
    busy = teacher_busy.get(tid, set())
    return (day, idx - 1) in busy and (day, idx - 2) in busy

def subject_daily_load(timetable):
    load = {}
    for l in timetable.lessons.all():
        key = (l.subject_id, l.day_of_week)
        load[key] = load.get(key, 0) + 1
    return load

def subject_weekly_load(timetable):
    load = {}
    for l in timetable.lessons.all():
        load[l.subject_id] = load.get(l.subject_id, 0) + 1
    return load

# ---------------- MAIN GENERATOR ---------------- #
@transaction.atomic
def generate_for_stream(timetable: Timetable, overwrite=False):
    print(f"[DEBUG] Starting generation for timetable {timetable.id} (overwrite={overwrite})")

    if overwrite:
        timetable.lessons.all().delete()

    term = timetable.term
    school = timetable.school
    grade = timetable.grade
    stream = timetable.stream
    time_slots = get_school_time_slots(school)

    if not time_slots:
        raise ValueError("No time slots defined")

    days = get_school_days_between(
        max(term.start_date, timetable.start_date),
        min(term.end_date, timetable.end_date)
    )

    # Only subjects assigned to this grade
    subjects = Subject.objects.filter(grade=grade)
    if not subjects.exists():
        raise ValueError("No subjects found for this grade")

    # Prioritize Mathematics and English
    priority_order = {n: i for i, n in enumerate(PRIORITY_SUBJECTS)}
    subjects = sorted(subjects, key=lambda s: priority_order.get(s.name, 99))

    # All students in this grade & stream
    students = Student.objects.filter(
        grade_level=grade,
        stream=stream,
        school=school
    )
    print(f"[DEBUG] Students found: {students.count()}")

    # Map of subject → eligible teachers
    teacher_map = {
        s.id: list(StaffProfile.objects.filter(school=school, subjects=s))
        for s in subjects
    }

    stream_occupied = stream_occupied_map(timetable, time_slots)
    teacher_busy, teacher_daily = global_teacher_load(
        school, term.start_date, term.end_date, time_slots
    )
    subject_daily = subject_daily_load(timetable)
    subject_weekly = subject_weekly_load(timetable)

    conflicts = []
    created_lessons = []
    enrollments_created = 0

    # Target sessions per subject per week
    weeks = max(1, len(days) // 5)
    weekly_targets = {s.id: weeks * getattr(s, "sessions_per_week", 2) for s in subjects}

    for pass_no in range(1, MAX_RETRY_PASSES + 1):
        relax_soft = pass_no > 1

        for subject in subjects:
            teachers = teacher_map.get(subject.id, [])
            if not teachers:
                conflicts.append({"type": "NO_TEACHER", "subject": subject.name})
                continue

            target = weekly_targets[subject.id]
            current = subject_weekly.get(subject.id, 0)

            while current < target:
                placed = False
                for day in days:
                    day_name = WEEKDAYS[day.weekday()]
                    if subject_daily.get((subject.id, day_name), 0) >= MAX_SUBJECTS_PER_DAY:
                        continue

                    for idx, slot in enumerate(time_slots):
                        if (day_name, idx) in stream_occupied:
                            continue

                        for teacher in teachers:
                            tid = teacher.id

                            if (day_name, idx) in teacher_busy.get(tid, set()):
                                continue
                            if teacher_daily.get(tid, {}).get(day_name, 0) >= MAX_TEACHER_PER_DAY:
                                continue
                            if has_three_consecutive(tid, day_name, idx, teacher_busy):
                                continue

                            # ---- CREATE LESSON ---- #
                            lesson = Lesson.objects.create(
                                timetable=timetable,
                                subject=subject,
                                stream=stream,
                                teacher=teacher,
                                day_of_week=day_name,
                                time_slot=slot,
                                lesson_date=day,
                                room=f"{grade.name} {stream.name}"
                            )
                            created_lessons.append(lesson)

                            # ---- ENROLL STUDENTS INTO THIS LESSON ---- #
                            for student in students:
                                Enrollment.objects.get_or_create(
                                    student=student,
                                    lesson=lesson,
                                    school=school,
                                    defaults={"status": "active"}
                                )
                                enrollments_created += 1

                            # Update tracking maps
                            stream_occupied.add((day_name, idx))
                            teacher_busy.setdefault(tid, set()).add((day_name, idx))
                            teacher_daily.setdefault(tid, {}).setdefault(day_name, 0)
                            teacher_daily[tid][day_name] += 1
                            subject_daily[(subject.id, day_name)] = subject_daily.get((subject.id, day_name), 0) + 1
                            subject_weekly[subject.id] = current + 1
                            current += 1
                            placed = True
                            break
                        if placed:
                            break
                    if placed:
                        break

                if not placed:
                    conflicts.append({
                        "type": "WEEKLY_TARGET_NOT_MET",
                        "subject": subject.name,
                        "pass": pass_no
                    })
                    break

    print(
        f"[DEBUG] Generation complete: "
        f"{len(created_lessons)} lessons, "
        f"{enrollments_created} enrollments, "
        f"{len(conflicts)} conflicts"
    )

    return {
        "lessons": created_lessons,
        "enrollments_created": enrollments_created,
        "conflicts": conflicts,
        "total_in_db": Lesson.objects.filter(timetable=timetable).count()
    }