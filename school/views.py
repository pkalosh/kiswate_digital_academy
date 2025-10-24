from django.shortcuts import render

# Create your views here.
def dashboard(request):
    return render(request, "school/dashboard.html", {})

def school_grades(request):
    return render(request, "school/grade.html", {})

def school_students(request):
    return render(request, "school/student.html", {})

def school_staffs(request):
    return render(request, "school/staff.html", {})

def school_parents(request):
    return render(request, "school/subject.html", {})

def school_subjects(request):
    return render(request, "school/subject.html", {})

def school_virtual_classes(request):
    return render(request, "school/class.html", {})

def school_attendance(request):
    return render(request, "school/attendance.html", {})

def school_enrollment(request):
    return render(request, "school/enrollment.html", {})

def school_student_assignments(request):
    return render(request, "school/assignment.html", {})

def school_exams(request):
    return render(request, "school/exam.html", {})

def school_timetable(request):
    return render(request, "school/timetable.html", {})

def school_students_submissions(request):
    return render(request, "school/submission.html", {})

def school_subscriptions(request):
    return render(request, "school/subscription.html", {})


def school_notifications(request):
    return render(request, "school/notification.html", {})

def school_settings(request):
    return render(request, "school/settings.html", {})

def school_reports(request):
    return render(request, "school/report.html", {})

def school_books(request):
    return render(request, "school/book.html", {})

def school_book_chapters(request):
    return render(request, "school/book_chapter.html", {})

def school_library_access(request):
    return render(request, "school/library.html", {})

def school_calendar(request):
    return render(request, "school/calendar.html", {})

def school_events(request):
    return render(request, "school/event.html", {})

def school_fees(request):
    return render(request, "school/fee.html", {})
def school_finance(request):
    return render(request, "school/finance.html", {})

def school_discipline(request):
    return render(request, "school/discipline.html", {})

def school_certificates(request):
    return render(request, "school/certificate.html", {})

def scholarships(request):
    return render(request, "school/scholarship.html", {})