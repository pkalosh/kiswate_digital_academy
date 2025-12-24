from django import template

register = template.Library()

@register.simple_tag
def get_lessons_for_slot_day(timetable, slot, day):
    """
    Returns all lessons for a given slot and day across all grades.
    Expects:
      - timetable[grade_id][TimeSlot object][date] = lesson
      - slot = TimeSlot object
      - day = date object
    """
    lessons_list = []

    for grade_id, grade_slots in timetable.items():
        slot_lessons = grade_slots.get(slot, {})  # TimeSlot objects as keys
        lesson = slot_lessons.get(day)  # date objects as keys
        if lesson:
            # handle if lesson is already a list
            if isinstance(lesson, (list, tuple)):
                lessons_list.extend(lesson)
            else:
                lessons_list.append(lesson)

    return lessons_list