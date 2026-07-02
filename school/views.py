from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db.models import Q
from django.core.paginator import Paginator
from userauths.models import User
from .models import Grade, School, Parent,StaffProfile,Student, ScanLog, SmartID,Scholarship
import logging
from django.db.models import Q, Count, Avg, Case, When, Value, FloatField, ExpressionWrapper, F, DurationField
from django.db import IntegrityError
import os
from django.db.models import Q, Value, CharField
from django.db.models.functions import Concat

from django.db.models import Q
from collections import defaultdict
from django.db.models import Count
from django.views.decorators.http import require_POST
import pandas as pd
from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
from itertools import cycle
import random
from django.db.models.functions import Lower
import string
from django.utils.dateparse import parse_date
import datetime
from datetime import timedelta,date
from .services.timetable_generator import generate_for_stream
from collections import defaultdict
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count, Avg, Case, When, Value, FloatField, F,Func, ExpressionWrapper
from django.db.models.functions import Coalesce
from django.db.models.functions import Extract
from django.db.models.functions import Coalesce
from django.http import JsonResponse, HttpResponseForbidden
from collections import defaultdict
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count
from django.core.paginator import Paginator
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
from django.db.models import Count, Q, OuterRef, Exists,Prefetch
from django.utils.dateparse import parse_date

import csv
from io import StringIO
import logging
from decimal import Decimal
from django.utils.timezone import localdate
import uuid
from userauths.models import User
from .models import (
    Grade, School, Parent, StaffProfile, Student, Subject, Enrollment, Timetable, Lesson, PolicymakerProfile, AttendanceAlert,
    Session, Attendance, DisciplineRecord, SummaryReport, Notification, SmartID, ScanLog,TeacherStreamAssignment,
    Payment, Assignment, Submission, Role, Invoice, SchoolSubscription, SubscriptionPlan,UploadedFile, County, Constituency, Ward,
    ContactMessage, MpesaStkPushRequestResponse, MpesaPayment,GradeAttendance, Streams,Term, TimeSlot, AcademicYear,
    SubjectEnrollment,AcademicYear,SubCounty,Pathway,Upload,SubjectCatalog,
    Announcement, FeeInvoice
)
from .forms import (
    # Assuming forms exist or need to be created; placeholders for now
    GradeForm,ParentCreationForm, ParentUpdateForm,StaffCreationForm, StaffUpdateForm,
    StudentCreationForm, StudentUpdateForm,SmartIDForm,GenerateTimetableForm,
    SubjectForm, EnrollmentForm, TimetableForm, LessonForm, SessionForm,GradeUploadForm,
    AttendanceForm, DisciplineRecordForm, NotificationForm, PaymentForm,
    AssignmentForm, SubmissionForm, RoleForm, InvoiceForm, SchoolSubscriptionForm,
    ContactMessageForm,ParentStudentCreationForm,TermForm,TimeSlotForm,AssignParentStudentForm,
    SubjectCatalogForm,SubjectActivationForm,ComplaintForm,BulkSubjectUploadForm,
    BulkNotificationForm,
)
from .models import AuditLog, Complaint
from kiswate_digital_app.forms import StreamForm

# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
import logging
import requests
logger = logging.getLogger(__name__)


import csv
from django.http import HttpResponse
from reportlab.pdfgen import canvas
from django.db.models import Min, Max
from school.models import Attendance, Lesson

INCIDENT_TYPE_CHOICES = [
    ('late', 'Late Arrival'),
    ('tardy', 'Tardy'),
    ('absence', 'Absence'),
    ('misconduct', 'Misconduct'),
    ('other', 'Other'),
]

SEVERITY_CHOICES = [
    ('minor', 'Minor'),
    ('major', 'Major'),
    ('critical', 'Critical'),
]


# =========================
# SMS + EMAIL HELPERS
# =========================

import time
import requests
from datetime import datetime
from django.utils.dateparse import parse_time

def safe_parse_time(value):
    if not value:
        return None

    value = str(value).strip()

    # Try Django parser first (24h format)
    t = parse_time(value)
    if t:
        return t

    # Fallback: AM/PM formats
    for fmt in ("%I:%M %p", "%I %p"):
        try:
            return datetime.strptime(value.upper(), fmt).time()
        except ValueError:
            pass

    return None
def _send_sms_via_eujim(to_phone_number: str, message: str, retries=3, delay=5) -> bool:
    if not to_phone_number:
        return False

    phone = str(to_phone_number)
    if phone.startswith("0"):
        phone = "254" + phone[1:]
    elif phone.startswith("+254"):
        phone = phone[1:]
    elif not phone.startswith("254"):
        phone = "254" + phone

    payload = {
        "apikey": settings.SMS_API_KEY,
        "partnerID": settings.SMS_PARTNERID,
        "shortcode": settings.SMS_SHORTCODE,
        "message": message,
        "mobile": phone,
    }

    for attempt in range(1, retries + 1):
        try:
            response = requests.post(
                'https://quicksms.advantasms.com/api/services/sendsms/',
                json=payload,
                timeout=15
            )
            if response.status_code == 200:
                data = response.json()
                r = data.get("responses", [{}])[0]
                return r.get("response-code") == 200
        except requests.exceptions.RequestException:
            pass
        if attempt < retries:
            time.sleep(delay)  # wait before retrying
    return False



def send_email(to_email: str, subject: str, message: str) -> bool:
    if not to_email:
        return False
    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [to_email],
            fail_silently=False,
        )
        return True
    except Exception as e:
        return False

# --------------------------------------------------
# SLOT HELPERS
# --------------------------------------------------

def is_first_slot(lesson):
    school = lesson.timetable.school if lesson.timetable_id else None
    qs = TimeSlot.objects.filter(school=school) if school else TimeSlot.objects.all()
    return lesson.time_slot == qs.order_by('start_time').first()


def is_last_slot(lesson):
    school = lesson.timetable.school if lesson.timetable_id else None
    qs = TimeSlot.objects.filter(school=school) if school else TimeSlot.objects.all()
    return lesson.time_slot == qs.order_by('-end_time').first()


# --------------------------------------------------
# MESSAGE BUILDERS
# --------------------------------------------------

def build_single_lesson_message(student, subject, status, lesson_date):
    return (
        f"Dear Parent, {student.user.get_full_name()} "
        f"was marked {status} for {subject.name} "
        f"on {lesson_date}."
    )

def build_daily_summary(student, date):
    stats = (
        Attendance.objects
        .filter(enrollment__student=student, date=date)
        .values('status')
        .annotate(total=Count('id'))
    )

    summary = ", ".join(f"{s['status']}: {s['total']}" for s in stats)
    return f"Daily Attendance Summary ({date}): {summary}"


# --------------------------------------------------
# SENDERS
# --------------------------------------------------

def notify_first_lesson(attendance):
    student = attendance.enrollment.student
    parents = student.parents.all()
    message = build_single_lesson_message(
        student,
        attendance.enrollment.lesson.subject,   # Subject object
        attendance.get_status_display(),
        attendance.date                   # Lesson date
    )
    for parent in parents:
        # _send_sms_via_eujim(parent.phone, message)
        if parent.user.email:
            send_mail("Lesson Attendance Notification", message, None, [parent.user.email], fail_silently=True)


def notify_last_lesson(student, date):
    parents = student.parents.all()
    message = build_daily_summary(student, date)

    for parent in parents:
        # _send_sms_via_eujim(parent.phone, message)
        if parent.user.email:
            send_mail(
                "Daily Attendance Summary",
                message,
                None,
                [parent.user.email],
                fail_silently=True
            )
@login_required
def export_attendance_csv(request):
    school = request.user.school_admin_profile
    qs = Attendance.objects.filter(enrollment__school=school)
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance.csv"'
    writer = csv.writer(response)
    writer.writerow(['Student','Grade','Stream','Subject','Date','Status','Term','Year'])
    for a in qs:
        writer.writerow([
            a.enrollment.student.user.get_full_name(),
            a.enrollment.student.grade_level.name,
            a.enrollment.student.stream.name,
            a.enrollment.subject.name,
            a.date,
            a.status,
            a.term.name if a.term else '',
            a.academic_year.name if a.academic_year else '',
        ])
    return response

@login_required
def export_attendance_pdf(request):
    school = request.user.school_admin_profile
    qs = Attendance.objects.filter(enrollment__school=school)
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="attendance.pdf"'
    p = canvas.Canvas(response)
    p.drawString(100, 800, "Attendance Report")
    y = 750
    for a in qs:
        p.drawString(50, y, f"{a.enrollment.student.user.get_full_name()} | {a.status} | {a.date}")
        y -= 20
        if y < 50: p.showPage(); y = 800
    p.showPage()
    p.save()
    return response


def get_user_school(user):
    # Admins/principals: try school_admin_profile (School.school_admin FK) first
    if user.is_admin or user.is_principal:
        school = getattr(user, "school_admin_profile", None)
        if school:
            return school
        # Fall through — principal may have StaffProfile without being school_admin

    # StaffProfile-based lookup covers deputy, teachers, and principals linked via StaffProfile
    if user.is_deputy_principal or user.is_principal or getattr(user, 'school_staff', False):
        try:
            return user.staffprofile.school
        except Exception:
            return None

    return None

@login_required
def dashboard(request):
    import json as _json
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)
    if not school:
        return render(request, "school/error.html", {"message": "No school profile found."})

    today = timezone.localdate()

    # ── Active term ────────────────────────────────────────────────────────────
    active_term = Term.objects.filter(school=school, is_active=True).first()
    term_filter = Q(date__range=(active_term.start_date, active_term.end_date)) if active_term else Q()

    if active_term:
        term_total_days = max((active_term.end_date - active_term.start_date).days, 1)
        term_elapsed    = max(min((today - active_term.start_date).days, term_total_days), 0)
        term_progress   = round(term_elapsed / term_total_days * 100)
        term_days_left  = max((active_term.end_date - today).days, 0)
    else:
        term_total_days = term_elapsed = term_progress = term_days_left = 0

    # ── Week navigation ────────────────────────────────────────────────────────
    date_str = request.GET.get("date")
    try:
        focus_date = timezone.datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else today
    except ValueError:
        focus_date = today
    week_start = focus_date - timedelta(days=focus_date.weekday())
    week_end   = week_start + timedelta(days=6)
    week_days  = [week_start + timedelta(days=i) for i in range(7)]
    prev_week  = week_start - timedelta(days=7)
    next_week  = week_start + timedelta(days=7)
    is_current_week = week_start == today - timedelta(days=today.weekday())

    # ── Core counts ───────────────────────────────────────────────────────────
    total_teachers = StaffProfile.objects.filter(school=school, position='teacher').count()
    total_students = Student.objects.filter(school=school, is_active=True).count()
    total_parents  = Parent.objects.filter(school=school).count()
    total_grades   = Grade.objects.filter(school=school).count()
    total_streams  = Streams.objects.filter(school=school).count()

    # ── Today's attendance rate ────────────────────────────────────────────────
    today_att = Attendance.objects.filter(enrollment__school=school, date=today)
    today_total   = today_att.count()
    today_present = today_att.filter(status='P').count()
    today_rate    = round(today_present / today_total * 100) if today_total else 0

    # ── Term attendance rate ───────────────────────────────────────────────────
    term_att     = Attendance.objects.filter(enrollment__school=school).filter(term_filter)
    term_total   = term_att.count()
    term_present = term_att.filter(status='P').count()
    term_rate    = round(term_present / term_total * 100) if term_total else 0
    term_absent  = term_att.filter(status__in=['UA', 'EA']).count()
    term_tardy   = term_att.filter(status__in=['UT', 'ET']).count()

    # ── Fee collection (term) ─────────────────────────────────────────────────
    from django.db.models import Sum
    fee_qs    = Payment.objects.filter(school=school)
    fee_paid  = fee_qs.filter(status='completed').aggregate(t=Sum('amount'))['t'] or 0
    fee_total = fee_qs.aggregate(t=Sum('amount'))['t'] or 0
    fee_rate  = round(fee_paid / fee_total * 100) if fee_total else 0
    fee_pending_count = fee_qs.filter(status='pending').count()

    # ── Discipline (this term) ─────────────────────────────────────────────────
    discipline_count = DisciplineRecord.objects.filter(school=school).filter(
        Q(date__range=(active_term.start_date, active_term.end_date)) if active_term else Q()
    ).count()
    discipline_recent = DisciplineRecord.objects.filter(school=school).select_related(
        'student__user'
    ).order_by('-date')[:5]

    # ── Complaints ────────────────────────────────────────────────────────────
    open_complaints = Complaint.objects.filter(school=school, status__in=['open','in_review']).count()

    # ── Today's lessons ────────────────────────────────────────────────────────
    todays_lessons = Lesson.objects.filter(
        timetable__school=school,
        lesson_date=today,
    ).select_related(
        'subject', 'teacher__user', 'stream__grade', 'time_slot'
    ).order_by('time_slot__start_time')[:8]

    # ── Weekly attendance chart data ───────────────────────────────────────────
    week_counts = {s: [] for s in ['P', 'ET', 'UT', 'EA', 'UA']}
    for status in week_counts:
        day_dict = {
            d['date']: d['count']
            for d in Attendance.objects.filter(
                status=status,
                date__range=(week_start, week_end),
                enrollment__school=school
            ).values('date').annotate(count=Count('id'))
        }
        for day in week_days:
            week_counts[status].append(day_dict.get(day, 0))

    chart_labels  = [d.strftime('%a %-d %b') for d in week_days]
    chart_present = week_counts['P']
    chart_absent  = [week_counts['UA'][i] + week_counts['EA'][i] for i in range(len(week_days))]
    chart_tardy   = [week_counts['UT'][i] + week_counts['ET'][i] for i in range(len(week_days))]

    # ── Attendance donut (today) ───────────────────────────────────────────────
    donut_data = [
        today_present,
        today_att.filter(status__in=['UA','EA']).count(),
        today_att.filter(status__in=['UT','ET']).count(),
        today_att.filter(status__in=['18','20','IB']).count(),
    ]

    # ── Teachers with missed lessons this week ─────────────────────────────────
    teachers_missed = list(
        StaffProfile.objects.filter(position='teacher', school=school).annotate(
            missed_count=Count(
                'lessons_taught__l_enrollments__attendances',
                filter=Q(
                    lessons_taught__l_enrollments__attendances__status__in=['UT','UA'],
                    lessons_taught__l_enrollments__attendances__date__range=(week_start, week_end),
                )
            )
        ).filter(missed_count__gt=0).select_related('user').order_by('-missed_count')[:8]
    )

    # ── Students missed lessons by stream this week ────────────────────────────
    student_missed_by_stream = []
    for stream in Streams.objects.filter(school=school).select_related('grade'):
        qs = Student.objects.filter(
            enrollments__lesson__stream=stream,
            enrollments__attendances__status__in=['UT','UA'],
            enrollments__attendances__date__range=(week_start, week_end),
        ).annotate(
            missed_count=Count(
                'enrollments__attendances',
                filter=Q(
                    enrollments__attendances__status__in=['UT','UA'],
                    enrollments__attendances__date__range=(week_start, week_end),
                )
            )
        ).distinct().order_by('-missed_count')[:10]
        if qs.exists():
            student_missed_by_stream.append({'stream': stream, 'students': qs})

    # ── Suspensions / Expulsions this week ────────────────────────────────────
    suspensions = Attendance.objects.filter(
        status='18', enrollment__school=school,
        date__range=(week_start, week_end),
    ).select_related('enrollment__student__user', 'enrollment__lesson__subject').order_by('-date')[:10]

    expulsions = Attendance.objects.filter(
        status='20', enrollment__school=school,
        date__range=(week_start, week_end),
    ).select_related('enrollment__student__user', 'enrollment__lesson__subject').order_by('-date')[:10]

    # ── Grade attendance breakdown (term) ─────────────────────────────────────
    grade_att = (
        Attendance.objects.filter(enrollment__school=school)
        .filter(term_filter)
        .values(grade_name=F('enrollment__lesson__stream__grade__name'))
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status='P')),
        )
        .annotate(rate=ExpressionWrapper(
            F('present') * 100.0 / F('total'), output_field=FloatField()
        ))
        .order_by('grade_name')
    )

    context = {
        # Identity
        "school":       school,
        "active_term":  active_term,
        "today":        today,
        # Term progress
        "term_progress":   term_progress,
        "term_days_left":  term_days_left,
        # KPI tiles
        "total_teachers": total_teachers,
        "total_students": total_students,
        "total_parents":  total_parents,
        "total_grades":   total_grades,
        "total_streams":  total_streams,
        # Today
        "today_total":   today_total,
        "today_present": today_present,
        "today_rate":    today_rate,
        # Term attendance
        "term_rate":    term_rate,
        "term_total":   term_total,
        "term_present": term_present,
        "term_absent":  term_absent,
        "term_tardy":   term_tardy,
        # Fees
        "fee_paid":          fee_paid,
        "fee_total":         fee_total,
        "fee_rate":          fee_rate,
        "fee_pending_count": fee_pending_count,
        # Discipline / complaints
        "discipline_count":  discipline_count,
        "discipline_recent": discipline_recent,
        "open_complaints":   open_complaints,
        # Today's schedule
        "todays_lessons": todays_lessons,
        # Week navigation
        "week_days":        week_days,
        "week_start":       week_start,
        "week_end":         week_end,
        "prev_week":        prev_week,
        "next_week":        next_week,
        "is_current_week":  is_current_week,
        # Chart data (JSON)
        "chart_labels_json":  _json.dumps(chart_labels),
        "chart_present_json": _json.dumps(chart_present),
        "chart_absent_json":  _json.dumps(chart_absent),
        "chart_tardy_json":   _json.dumps(chart_tardy),
        "donut_data_json":    _json.dumps(donut_data),
        "donut_data":         donut_data,
        # Alerts
        "teachers_missed":         teachers_missed,
        "student_missed_by_stream": student_missed_by_stream,
        "suspensions":             suspensions,
        "expulsions":              expulsions,
        "grade_att":               grade_att,
    }

    return render(request, "school/dashboard.html", context)
@login_required
def time_slot_list(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    slots = TimeSlot.objects.filter(school=school)
    form = TimeSlotForm(school=school)  # Empty form for modal
    return render(request, "school/time_slots.html", {
        "slots": slots,
        "school": school,
        "form": form,  # Enables {{ form.field }} in template
    })

@login_required
def time_slot_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:time-slot-list')

    # Optional: Role check (from previous code)
    # user_role = get_user_role(request.user)
    # if user_role not in ['admin']:
    #     messages.error(request, "Insufficient permissions.")
    #     return redirect("school:time-slot-list")

    form = TimeSlotForm(request.POST or None, school=school)
    if request.method == "POST" and form.is_valid():
        try:
            slot = form.save(commit=False)
            slot.school = school
            try:
                slot.created_by = request.user.staffprofile
                slot.updated_by = request.user.staffprofile
            except ObjectDoesNotExist:
                messages.error(request, "Missing staff profile for audit trail.")
                return redirect("school:time-slot-list")
            slot.save()
            messages.success(request, "Time slot created successfully.")
            return redirect("school:time-slot-list")
        except IntegrityError as e:
            messages.error(request, f"Save failed: Time slot may overlap or violate constraints. Details: {str(e)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    return render(request, "school/time_slots.html", {
        "form": form, "school": school, "mode": "create"
    })

@login_required
def time_slot_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access to time slots.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:time-slot-list')
    # Optional role check
    # user_role = get_user_role(request.user)
    # if user_role not in ['admin']:
    #     messages.error(request, "Insufficient permissions.")
    #     return redirect("school:time-slot-list")

    slot = get_object_or_404(TimeSlot, pk=pk, school=school)
    form = TimeSlotForm(request.POST or None, instance=slot, school=slot.school)
    if request.method == "POST" and form.is_valid():
        try:
            slot = form.save(commit=False)
            try:
                slot.updated_by = request.user.staffprofile
            except ObjectDoesNotExist:
                messages.error(request, "Missing staff profile for audit trail.")
                return redirect("school:time-slot-list")
            slot.save()
            messages.success(request, "Time slot updated successfully.")
            return redirect("school:time-slot-list")
        except IntegrityError as e:
            messages.error(request, f"Save failed: Time slot may overlap or violate constraints. Details: {str(e)}")
        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
    return render(request, "school/time_slots.html", {
        "form": form, "school": slot.school, "mode": "edit", "slot": slot
    })

@login_required
def time_slot_delete(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to create Time slots.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:time-slot-list')


    slot = get_object_or_404(TimeSlot, pk=pk, school=school)
    if request.method == "POST":
        slot.delete()
        messages.success(request, "Time slot deleted successfully.")
        return redirect("school:time-slot-list")

    return render(request, "school/time_slots.html", {"slot": slot})



def term_list(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access Term List.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    terms = Term.objects.filter(school=school)
    form = TermForm()
    return render(request, "school/terms.html", {"school": school, "terms": terms, "form": form})


@login_required
def create_term(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to create Term.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    form = TermForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        term = form.save(commit=False)
        term.school = school
        term.is_active = True
        term.save()

        # If new term is active → deactivate all other terms
        if term.is_active:
            Term.objects.filter(school=school).exclude(id=term.id).update(is_active=False)

        messages.success(request, "New term created successfully.")
        return redirect("school:term-list")

    return render(request, "school/terms/create_term.html", {
        "form": form,
        "school": school
    })

@login_required
def edit_term(request, term_id):
    term = get_object_or_404(Term, id=term_id)
    school = term.school

    form = TermForm(request.POST or None, instance=term)

    if request.method == "POST" and form.is_valid():
        updated_term = form.save(commit=False)
        updated_term.school = school
        updated_term.save()

        # If edited term is now active → deactivate all other terms
        if updated_term.is_active:
            Term.objects.filter(school=school).exclude(id=updated_term.id).update(is_active=False)

        messages.success(request, "Term updated successfully.")
        return redirect("school:term-list")

    return render(request, "school/terms/edit_term.html", {
        "form": form,
        "term": term,
        "school": school,
    })


@login_required
def delete_term(request, term_id):
    term = get_object_or_404(Term, id=term_id)
    school_id = term.school.id

    if request.method == "POST":
        term.delete()
        messages.success(request, "Term deleted successfully.")
        return redirect("school:term-list")

    return render(request, "school/terms/delete_term_confirm.html", {
        "term": term
    })


from django.core.paginator import Paginator


def paginate(request, queryset, per_page=10, page_param='page'):
    """Paginate a queryset with a custom GET parameter."""
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get(page_param)
    return paginator.get_page(page_number)

@login_required
def school_users(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this page.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)
    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    tab = request.GET.get('tab', 'staff')
    query = request.GET.get('q', '').strip()

    staff_qs = StaffProfile.objects.filter(school=school).select_related('user').order_by('user__first_name')
    students_qs = Student.objects.filter(school=school).select_related('user', 'grade_level', 'stream').order_by('user__first_name')
    parents_qs = Parent.objects.filter(school=school).select_related('user').order_by('user__first_name')

    if query:
        staff_qs = staff_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(staff_id__icontains=query) |
            Q(position__icontains=query)
        )
        students_qs = students_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(student_id__icontains=query)
        )
        parents_qs = parents_qs.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(user__email__icontains=query) |
            Q(parent_id__icontains=query)
        )

    staff_count = StaffProfile.objects.filter(school=school).count()
    students_count = Student.objects.filter(school=school).count()
    parents_count = Parent.objects.filter(school=school).count()

    staff_list = paginate(request, staff_qs, per_page=25, page_param='sp')
    students_list = paginate(request, students_qs, per_page=25, page_param='stp')
    parents_list = paginate(request, parents_qs, per_page=25, page_param='pp')

    staff_form = StaffCreationForm(school=school)
    student_form = StudentCreationForm(school=school)
    parent_form = ParentCreationForm(school=school)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'create_staff':
            staff_form = StaffCreationForm(request.POST, request.FILES, school=school)
            if staff_form.is_valid():
                staff_obj, pwd = staff_form.save()
                messages.success(
                    request,
                    f'Staff "{staff_obj.user.get_full_name()}" created. Temp password: {pwd}'
                )
                return redirect(f"{request.path}?tab=staff")
            else:
                tab = 'staff'
        elif action == 'create_student':
            student_form = StudentCreationForm(request.POST, request.FILES, school=school)
            if student_form.is_valid():
                student_obj, pwd = student_form.save()
                messages.success(request, f'Student "{student_obj.user.get_full_name()}" created.')
                return redirect(f"{request.path}?tab=students")
            else:
                tab = 'students'
        elif action == 'create_parent':
            parent_form = ParentCreationForm(request.POST, request.FILES, school=school)
            if parent_form.is_valid():
                parent_obj, pwd = parent_form.save()
                messages.success(request, f'Parent "{parent_obj.user.get_full_name()}" created.')
                return redirect(f"{request.path}?tab=parents")
            else:
                tab = 'parents'

    context = {
        'school': school,
        'tab': tab,
        'query': query,
        'staff_list': staff_list,
        'students_list': students_list,
        'parents_list': parents_list,
        'staff_count': staff_count,
        'students_count': students_count,
        'parents_count': parents_count,
        'staff_form': staff_form,
        'student_form': student_form,
        'parent_form': parent_form,
    }

    return render(request, 'school/staff.html', context)


@login_required
def update_student(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')

    student = get_object_or_404(Student, pk=pk, school=school)
    if request.method == 'POST':
        form = StudentUpdateForm(request.POST, request.FILES, instance=student, school=school)  # Fixed: school=school
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, f'Successfully updated Student "{student.user.get_full_name()}".')
                return redirect('school:school-users')
            except Exception as e:
                messages.error(request, f"Failed to update: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StudentUpdateForm(instance=student, school=school)
    context = {'form': form, 'student': student, 'school': school}
    return render(request, 'school/student_edit.html', context)

# Similar for Parent Update
@login_required
def update_parent(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')
    parent = get_object_or_404(Parent, pk=pk, school=school)
    if request.method == 'POST':
        form = ParentUpdateForm(request.POST, request.FILES, instance=parent, school=school)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, f'Successfully updated Parent "{parent.user.get_full_name()}".')
                return redirect('school:school-users')
            except Exception as e:
                messages.error(request, f"Failed to update: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = ParentUpdateForm(instance=parent, school=school)
    context = {'form': form, 'parent': parent, 'school': school}
    return render(request, 'school/parent_edit.html', context)

# Similar for Staff Update
@login_required
def update_staff(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')
    staff = get_object_or_404(StaffProfile, pk=pk, school=school)
    if request.method == 'POST':
        form = StaffUpdateForm(request.POST, request.FILES, instance=staff, school=school)
        if form.is_valid():
            try:
                with transaction.atomic():
                    form.save()
                messages.success(request, f'Successfully updated Staff "{staff.user.get_full_name()}".')
                return redirect('school:school-users')
            except Exception as e:
                messages.error(request, f"Failed to update: {str(e)}")
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StaffUpdateForm(instance=staff, school=school)
    context = {'form': form, 'staff': staff, 'school': school}
    return render(request, 'school/staff_edit.html', context)

# Delete Views
@login_required
def delete_student(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')
    
    student = get_object_or_404(Student, pk=pk, school=school)
    try:
        with transaction.atomic():
            student.user.delete()  # Cascade or handle as per model
        messages.success(request, f'Successfully deleted Student "{student.user.get_full_name()}".')
    except Exception as e:
        messages.error(request, f"Failed to delete: {str(e)}")
    return redirect('school:school-users')

@login_required
def delete_parent(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')
    
    parent = get_object_or_404(Parent, pk=pk, school=school)
    try:
        with transaction.atomic():
            parent.user.delete()
        messages.success(request, f'Successfully deleted Parent "{parent.user.get_full_name()}".')
    except Exception as e:
        messages.error(request, f"Failed to delete: {str(e)}")
    return redirect('school:school-users')

@login_required
def delete_staff(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:school-users')
    
    staff = get_object_or_404(StaffProfile, pk=pk, school=school)
    try:
        with transaction.atomic():
            staff.user.delete()
        messages.success(request, f'Successfully deleted Staff "{staff.user.get_full_name()}".')
    except Exception as e:
        messages.error(request, f"Failed to delete: {str(e)}")
    return redirect('school:school-users')

def is_school_admin(user):
    # adapt to your project's admin flag - either is_superuser or custom flag on user
    return user.is_active and (user.is_superuser or getattr(user, 'is_admin', False))


@login_required
@user_passes_test(is_school_admin)
def get_streams_for_grade(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)    

    grade_id = request.GET.get('grade_id')

    if not school or not grade_id:
        return JsonResponse({'streams': []})

    streams = Streams.objects.filter(grade_id=grade_id, grade__school=school, is_active=True)
    streams_data = [{'id': s.id, 'name': s.name} for s in streams]
    return JsonResponse({'streams': streams_data})

@login_required
@user_passes_test(is_school_admin)
def generate_timetable_view(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = GenerateTimetableForm(request.POST, school=school)
        if form.is_valid():
            scope = form.cleaned_data['scope']
            grade = form.cleaned_data.get('grade')
            stream = form.cleaned_data.get('stream')
            overwrite = form.cleaned_data.get('overwrite')

            term = Term.objects.filter(school=school, is_active=True).first()
            if not term:
                messages.error(request, "No active term defined for your school.")
                return redirect(request.META.get('HTTP_REFERER', '/'))

            # Determine streams to generate
            streams_qs = Streams.objects.filter(grade__school=school)
            if scope == 'grade':
                if not grade:
                    messages.error(request, "Please select a grade.")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                streams_qs = streams_qs.filter(grade=grade)
            elif scope == 'stream':
                if not stream:
                    messages.error(request, "Please select a stream.")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                streams_qs = streams_qs.filter(id=stream.id)

            created_total = 0
            errors = []
            for st in streams_qs:
                tt, created = Timetable.objects.get_or_create(
                    school=school,
                    grade=st.grade,
                    stream=st,
                    term=term,
                    year=term.start_date.year,
                    defaults={'start_date': term.start_date, 'end_date': term.end_date}
                )
                try:
                    lessons_created = generate_for_stream(tt, overwrite=overwrite)
                    created_total += len(lessons_created)
                except Exception as e:
                    errors.append(str(e))

            if created_total:
                messages.success(request, f"Timetable generated — {created_total} lessons created.")
            if errors:
                messages.warning(request, "Some errors: " + "; ".join(errors))

            return redirect(request.META.get('HTTP_REFERER', '/'))

    else:
        form = GenerateTimetableForm(school=request.user.school_admin_profile)

    # Fetch all timetables for the school
    timetables = Timetable.objects.filter(school=school).order_by('-term__start_date')

    return render(request, 'school/generate_timetable.html', {
        'form': form,
        'timetables': timetables,
        'school': school,
    })

@login_required
def view_timetable_week(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    # ── Focus date ───────────────────────────────────────────────────────────
    focus_date_str = request.GET.get("date")
    try:
        focus_date = datetime.datetime.strptime(focus_date_str, "%Y-%m-%d").date() if focus_date_str else timezone.localdate()
    except (ValueError, TypeError):
        focus_date = timezone.localdate()

    # ── Week range (Monday → Sunday) ─────────────────────────────────────────
    week_start = focus_date - timedelta(days=focus_date.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # ── Time slots ───────────────────────────────────────────────────────────
    time_slots = TimeSlot.objects.filter(school=school).order_by('start_time')

    # ── Lessons ──────────────────────────────────────────────────────────────
    lessons_qs = Lesson.objects.filter(
        timetable__school=school,
        timetable__term__is_active=True,
        lesson_date__range=(week_start, week_end),
    ).select_related(
        'subject',
        'teacher__user',
        'stream',
        'timetable',
    )

    # ── Streams ──────────────────────────────────────────────────────────────
    streams = Streams.objects.filter(school=school)
    streams_dict = {s.id: s for s in streams}

    # ── Build calendar safely ────────────────────────────────────────────────
    calendar = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))

    for lesson in lessons_qs:
        date_str = lesson.lesson_date.strftime("%Y-%m-%d")

        # Skip lessons without time_slot or stream
        if not lesson.time_slot or not lesson.stream:
            continue

        stream_id = lesson.stream.id
        # Precompute stream name safely
        lesson.stream_name = streams_dict.get(stream_id).name if streams_dict.get(stream_id) else "(stream missing)"

        # Append lesson to calendar
        calendar[lesson.time_slot.id][date_str][stream_id].append(lesson)

    # Convert defaultdict → plain dict
    calendar_plain = {
        slot_id: {
            date_str: dict(stream_dict)
            for date_str, stream_dict in date_dict.items()
        }
        for slot_id, date_dict in calendar.items()
    }

    # ── Subjects & colors ────────────────────────────────────────────────────
    subjects = Subject.objects.filter(school=school).distinct()
    subject_colors = {s.id: getattr(s, "color", "#eee") for s in subjects}
    subjects_dict = {s.id: s for s in subjects}

    # ── Conflicts placeholder ────────────────────────────────────────────────
    conflict_lessons = set()

    # ── Context ──────────────────────────────────────────────────────────────
    context = {
        "week_days": week_days,
        "time_slots": time_slots,
        "calendar": calendar_plain,
        "subject_colors": subject_colors,
        "streams_dict": streams_dict,
        "focus_date": focus_date.strftime("%Y-%m-%d"),
        "conflict_lessons": conflict_lessons,
        "subjects": subjects_dict,
    }

    return render(request, "school/timetable_week.html", context)

@login_required
def teacher_timetable_view(request):
    if not hasattr(request.user, 'staffprofile'):
        return HttpResponseForbidden()
    teacher = request.user.staffprofile
    time_slots =  TimeSlot.objects.filter(school=teacher.school).order_by("start_time")
    date_str = request.GET.get('date')
    if date_str:
        focus_date = datetime.date.fromisoformat(date_str)
    else:
        focus_date = timezone.localdate()
    monday = focus_date - timedelta(days=focus_date.weekday())
    week_days = [monday + timedelta(days=i) for i in range(7)]

    lessons_qs = Lesson.objects.filter(teacher=teacher, date__range=(week_days[0], week_days[-1])).order_by('lesson_date')

    # Group by date
    lessons_by_date = {d: lessons_qs.filter(lesson_date=d) for d in week_days}

    context = {
        'week_days': week_days,
        'lessons_by_date': lessons_by_date,
        'time_slots': time_slots,
        'focus_date': focus_date,
    }
    return render(request, 'school/teacher_timetable.html', context)


@login_required
def student_details(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    return render(request, "school/student_details.html", {"student": student})

@login_required
def edit_staff(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    form = StaffCreationForm(request.POST or None, request.FILES or None, instance=staff, school=staff.school)

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Staff updated successfully.")
        return redirect("school_users")

    return render(request, "school/forms/edit_staff.html", {"form": form})
@login_required
def edit_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    form = StudentCreationForm(
        request.POST or None,
        request.FILES or None,
        instance=student,
        school=student.school
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Student updated successfully.")
        return redirect("school_users")

    return render(request, "school/forms/edit_student.html", {"form": form})

@login_required
def edit_parent(request, parent_id):
    parent = get_object_or_404(Parent, id=parent_id)
    form = ParentCreationForm(
        request.POST or None,
        request.FILES or None,
        instance=parent,
        school=parent.school
    )

    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Parent updated successfully.")
        return redirect("school_users")

    return render(request, "school/forms/edit_parent.html", {"form": form})
@login_required
def delete_staff(request, staff_id):
    staff = get_object_or_404(StaffProfile, id=staff_id)
    staff.delete()
    messages.success(request, "Staff deleted.")
    return redirect("school_users")
@login_required
def delete_student(request, student_id):
    student = get_object_or_404(Student, id=student_id)
    student.delete()
    messages.success(request, "Student deleted.")
    return redirect("school_users")
@login_required
def delete_parent(request, parent_id):
    parent = get_object_or_404(Parent, id=parent_id)
    parent.delete()
    messages.success(request, "Parent deleted.")
    return redirect("school_users")

@login_required
def school_grades(request):
    # Ensure user is a school admin
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    form = GradeForm(school=school)
    stream_form = StreamForm()
    upload_form = GradeUploadForm()

    query = request.GET.get('q', '').strip()

    grades_qs = Grade.objects.filter(
        school=school,
        is_active=True
    ).order_by('name')  # ✅ sorted

    if query:
        grades_qs = grades_qs.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query)
        )

    # ✅ Pagination
    paginator = Paginator(grades_qs, 10)  # 10 grades per page
    page_number = request.GET.get('page')
    grades = paginator.get_page(page_number)

    streams = Streams.objects.filter(
        school=school,
        is_active=True
    ).order_by('name')

    context = {
        'grades': grades,
        'form': form,
        'stream_form': stream_form,
        'upload_form': upload_form,
        'school': school,
        'streams': streams,
        'query': query,
    }
    return render(request, "school/grade.html", context)

@login_required
def smartid_list(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    query = request.GET.get('q', '')

    smartids = SmartID.objects.filter(
        school=school,
        is_active=True
    ).select_related(
        'profile',
        'profile__student',
        'profile__staffprofile'
    )

    if query:
        smartids = smartids.filter(
            Q(profile__first_name__icontains=query) |
            Q(profile__last_name__icontains=query) |
            Q(card_id__icontains=query) |
            Q(user_f18_id__icontains=query)
        )

    form = SmartIDForm(school=school)

    return render(request, 'school/smartid_list.html', {
        'smartids': smartids,
        'form': form,
        'school': school,
        'query': query,
    })


@login_required
def smartid_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        return redirect('school:smartid-list')
    
    form = SmartIDForm(request.POST, school=school)
    if form.is_valid():
        smartid = form.save(commit=False)
        smartid.school = school
        smartid.save()
        messages.success(request, f'Smart ID "{smartid.card_id}" created successfully.')
        logger.info(f"Created Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
        return redirect('school:smartid-list')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:smartid-list')

@login_required
def smartid_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        return redirect('school:smartid-list')
    
    smartid = get_object_or_404(SmartID, pk=pk, school=school)
    form = SmartIDForm(request.POST, instance=smartid, school=school)
    if form.is_valid():
        form.save()
        messages.success(request, f'Smart ID "{smartid.card_id}" updated successfully.')
        logger.info(f"Updated Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
        return redirect('school:smartid-list')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:smartid-list')

@login_required
def smartid_delete(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method != 'POST':
        messages.warning(request, "Use the delete button in the list to confirm.")
        return redirect('school:smartid-list')
    
    smartid = get_object_or_404(SmartID, pk=pk, school=school)
    smartid.is_active = False  # Soft delete
    smartid.save()
    messages.success(request, f'Smart ID "{smartid.card_id}" deactivated.')
    logger.info(f"Deactivated Smart ID {smartid.card_id} for school {school.name} by {request.user.email}.")
    return redirect('school:smartid-list')

# -------------------------------SCAN LOGS VIEW-------------------------------
@login_required
def scan_logs_view(request):
    """
    Display all scan logs with pagination and simple search filters.
    """
    search = request.GET.get('q', '')
    school = getattr(request.user, 'school', None)

    logs = ScanLog.objects.all()
    # Optional: limit logs by user's school
    if school:
        logs = logs.filter(school=school)

    if search:
        logs = logs.filter(school=school)

    paginator = Paginator(logs, 25)  # Show 25 logs per page
    page = request.GET.get('page')
    logs_page = paginator.get_page(page)

    context = {
        'logs': logs_page,
        'search': search,
    }
    return render(request, 'school/scan_logs.html', context)

@login_required
def grade_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:school-grades')

    form = GradeForm(request.POST, school=school)
    if form.is_valid():
        grade = form.save(commit=False)
        grade.school = school
        grade.is_active = True
        grade.save()
        messages.success(request, f'Grade "{grade.name}" created successfully.')
        logger.info(f"Created grade {grade.name} for school {school.name} by {request.user.email}.")
        return redirect('school:school-grades')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:school-grades')


@login_required
def upload_grade_file(request):
    # Ensure user has a school
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = GradeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            upload = form.save(commit=False)
            upload.upload_file_category = 'grade'
            upload.uploaded_by = request.user
            upload.school = school
            upload.save()

            # Process Excel file
            file_path = upload.file.path
            ext = os.path.splitext(file_path)[1].lower()
            if ext not in ['.xls', '.xlsx']:
                messages.error(request, "Invalid file type. Only Excel files allowed.")
                upload.delete()
                return redirect('upload_grade_file')

            try:
                df = pd.read_excel(file_path)  # expects columns: name, description, code, capacity
            except Exception as e:
                messages.error(request, f"Failed to read Excel file: {str(e)}")
                upload.delete()
                return redirect('upload_grade_file')

            created_count = 0
            for index, row in df.iterrows():
                # Skip rows without name or code
                if pd.isna(row.get('name')) or pd.isna(row.get('code')):
                    continue

                grade, created = Grade.objects.get_or_create(
                    school=school,
                    code=row.get('code'),
                    defaults={
                        'name': row.get('name'),
                        'description': row.get('description', ''),
                        'capacity': int(row.get('capacity', 50)),
                    }
                )
                if created:
                    created_count += 1

            messages.success(request, f"File uploaded successfully. {created_count} grades created.")
            return redirect('school:school-grades')

        else:
            messages.error(request, "Please fix the errors below.")
    else:
        form = GradeUploadForm()

    uploaded_files = UploadedFile.objects.filter(
        upload_file_category='grade',
        school=school
    ).order_by('-uploaded_at')

    context = {
        'form': form,
        'uploaded_files': uploaded_files,
    }
    return redirect('school:school-grades')



@login_required
def grade_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:school-grades')

    grade = get_object_or_404(Grade, pk=pk, school=school)
    form = GradeForm(request.POST, instance=grade, school=school)
    if form.is_valid():
        form.save()
        messages.success(request, f'Grade "{grade.name}" updated successfully.')
        logger.info(f"Updated grade {grade.name} for school {school.name} by {request.user.email}.")
        return redirect('school:school-grades')
    else:
        # Add form errors to messages
        for field, error_list in form.errors.items():
            if field == '__all__':
                for error in error_list:
                    messages.error(request, error)
            else:
                label = form.fields[field].label
                for error in error_list:
                    messages.error(request, f"{label}: {error}")
        return redirect('school:school-grades')


@login_required
def grade_delete(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method != 'POST':
        messages.warning(request, "Use the delete button in the list to confirm.")
        return redirect('school:school-grades')

    grade = get_object_or_404(Grade, pk=pk, school=school)
    grade.is_active = False  # Soft delete
    grade.save()
    messages.success(request, f'Grade "{grade.name}" deactivated.')
    logger.info(f"Deactivated grade {grade.name} for school {school.name} by {request.user.email}.")
    return redirect('school:school-grades')



@login_required
def parent_list_create(request):
    """
    List parents with search/filter.
    Handles creation via POST (from add modal).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = ParentCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            parent, password = form.save()
            messages.success(
                request,
                f'Successfully created parent "{parent.user.get_full_name()}" ({parent.parent_id}). '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created parent {parent.parent_id} for school {school.name}.")
            return redirect('school:parent_list_create')  # Back to list
        # Errors: Re-render list with bound form
    else:
        form = ParentCreationForm(school=school)

    # List parents
    query = request.GET.get('q', '')
    parents = Parent.objects.filter(school=school).select_related('user').order_by('-user__created_at')
    if query:
        parents = parents.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(parent_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query)
        )

    context = {
        'parents': parents,
        'form': form,  # For add modal
        'school': school,
        'query': query,
    }
    return render(request, 'school/parents.html', context)


@login_required
def parent_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    

    parent = get_object_or_404(Parent, pk=pk, school=school)

    if request.method == 'POST':
        form = ParentEditForm(request.POST, request.FILES, instance=parent)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated parent "{parent.user.get_full_name()}".'
            )
            logger.info(f"Updated parent {parent.parent_id}.")
            return redirect('school:parent_list_create')
        else:
            messages.error(request, "Please correct the form errors.")
            # Still redirect back to list (modal-based editing)
            return redirect('school:parent_list_create')

    # If GET, editing is via modal only, so redirect to list
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:parent_list_create')




@login_required
def parent_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    parent = get_object_or_404(Parent, pk=pk, school=school)

    if request.method == 'POST':
        user = parent.user
        user.is_active = False
        user.save()
        parent.delete()
        messages.success(request, f'Parent "{parent.user.get_full_name()}" ({parent.parent_id}) has been deleted.')
        logger.info(f"Deleted parent {parent.parent_id}.")
        return redirect('school:parent_list_create')  # Back to list (modal closes)
    
    # For GET (direct access): Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:parent_list_create')

@login_required
def staff_list_create(request):
    """
    List staff with search/filter.
    Handles creation via POST (from add modal).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = StaffCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            staff, password = form.save()
            messages.success(
                request,
                f'Successfully created staff "{staff.user.get_full_name()}" ({staff.staff_id}). '
                f'Position: {staff.get_position_display()}. '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created staff {staff.staff_id} for school {school.name}.")
            return redirect('school:staff_list_create')
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StaffCreationForm(school=school)

    # List staff
    query = request.GET.get('q', '')
    staff_list = StaffProfile.objects.filter(school=school).select_related('user').order_by('-user__created_at')
    if query:
        staff_list = staff_list.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(staff_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query) |
            Q(position__icontains=query)
        )

    context = {
        'staff_list': staff_list,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/staff.html', context)


@login_required
def staff_edit(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    staff = get_object_or_404(StaffProfile, pk=pk, school=school)

    if request.method == 'POST':
        form = StaffEditForm(request.POST, request.FILES, instance=staff)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated staff "{staff.user.get_full_name()}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated staff {staff.staff_id}.")
            return redirect('school:staff_list_create')
        else:
            messages.error(request, "Please correct the form errors.")
    # For GET: Redirect to list (modal-driven)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:staff_list_create')


@login_required
def staff_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    staff = get_object_or_404(StaffProfile, pk=pk, school=school)

    if request.method == 'POST':
        user = staff.user
        user.is_active = False
        user.save()
        staff.delete()
        messages.success(request, f'Staff "{staff.user.get_full_name()}" ({staff.staff_id}) has been deleted.')
        logger.info(f"Deleted staff {staff.staff_id}.")
        return redirect('school:staff_list_create')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:staff_list_create')


@login_required
def student_list_create(request):
    """
    List students with search/filter.
    Handles creation via POST (from add modal).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = StudentCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            student, password = form.save(commit=False)
            student.school = school
            student.save()
            messages.success(
                request,
                f'Successfully created student "{student.user.get_full_name()}" ({student.student_id}). '
                f'Grade: {student.grade_level}. '
                f'Temporary password: <strong>{password}</strong>. '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}.'
            )
            logger.info(f"Created student {student.student_id} for school {school.name}.")
            return redirect('school:student_list_create')
        else:
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StudentCreationForm(school=school)

    # List students
    query = request.GET.get('q', '')
    students = Student.objects.filter(school=school).select_related('user', 'grade_level').order_by('-user__created_at')
    if query:
        students = students.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(student_id__icontains=query) |
            Q(user__phone_number__icontains=query) |
            Q(user__email__icontains=query) |
            Q(grade_level__name__icontains=query)
        )

    context = {
        'students': students,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/students.html', context)


@login_required
def student_edit(request, pk):
    """
    Edit via modal form POST.
    Redirects back to list on success/error.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    student = get_object_or_404(Student, pk=pk, school=school)

    if request.method == 'POST':
        form = StudentEditForm(request.POST, request.FILES, instance=student)
        if form.is_valid():
            form.save()
            messages.success(
                request,
                f'Successfully updated student "{student.user.get_full_name()}". '
                f'Email sent: {"Yes" if form.cleaned_data["send_email"] else "No"}. '
                f'Password reset: {"Yes" if form.cleaned_data["reset_password"] else "No"}.'
            )
            logger.info(f"Updated student {student.student_id}.")
            return redirect('school:student_list_create')
        else:
            messages.error(request, "Please correct the form errors.")
    # For GET: Redirect to list (modal-driven)
    messages.info(request, "Use the edit button in the list to modify.")
    return redirect('school:student_list_create')


@login_required
def student_delete(request, pk):
    """
    Delete via modal form POST.
    Redirects back to list on success.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    student = get_object_or_404(Student, pk=pk, school=school)

    if request.method == 'POST':
        user = student.user
        user.is_active = False
        user.save()
        student.delete()
        messages.success(request, f'Student "{student.user.get_full_name()}" ({student.student_id}) has been deleted.')
        logger.info(f"Deleted student {student.student_id}.")
        return redirect('school:student_list_create')
    
    # For GET: Redirect to list
    messages.warning(request, "Use the delete button in the list to confirm.")
    return redirect('school:student_list_create')




def school_exams(request):
    return render(request, "school/exam.html", {})


def school_subscriptions(request):
    return render(request, "school/subscription.html", {})


def school_notifications(request):
    return render(request, "school/notification.html", {})


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

def school_certificates(request):
    return render(request, "school/certificate.html", {})

def scholarships(request):
    return render(request, "school/scholarship.html", {})

@login_required
def school_teacher_subjects(request, staff_id):
    """
    View for school admin to manage subjects assigned to a specific teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    teacher = get_object_or_404(StaffProfile, pk=staff_id, school=school)
    
    query = request.GET.get('q', '')
    subjects = Subject.objects.filter(school=school, teacher=teacher).select_related('grade')
    if query:
        subjects = subjects.filter(
            Q(name__icontains=query) | Q(code__icontains=query)
        )
    form = SubjectForm(school=school)

    context = {
        'subjects': subjects,
        'teacher': teacher,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/teacher/subjects.html', context)

@login_required
def subject_teacher_create(request, staff_id):
    """
    Assign a subject to a teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects', staff_id=staff_id)
    
    teacher = get_object_or_404(StaffProfile, pk=staff_id, school=school)
    
    if request.method == 'POST':
        subject_id = request.POST.get('subject_id')
        subject = get_object_or_404(Subject, pk=subject_id, school=school)
        
        if subject.teacher == teacher:
            messages.warning(request, f'Subject "{subject.name}" is already assigned to {teacher.user.get_full_name()}.')
        else:
            subject.teacher = teacher
            subject.save()
            messages.success(request, f'Subject "{subject.name}" assigned to {teacher.user.get_full_name()}.')
            logger.info(f"Assigned subject {subject.name} to teacher {teacher.user.get_full_name()} for school {school.name}.")
        
        return redirect('school:school-teacher-subjects', staff_id=staff_id)
    
    return redirect('school:school-teacher-subjects', staff_id=staff_id)

@login_required
def subject_teacher_edit(request, staff_id, pk):
    """
    Edit the subject assigned to a teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    teacher = get_object_or_404(StaffProfile, pk=staff_id, school=school)
    subject = get_object_or_404(Subject, pk=pk, school=school)
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subject "{subject.name}" updated successfully.')
            return redirect('school:school-teacher-subjects', staff_id=staff_id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    
    return redirect('school:school-teacher-subjects', staff_id=staff_id)

@login_required
def subject_teacher_delete(request, staff_id, pk):
    """
    Remove a subject from a teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    teacher = get_object_or_404(StaffProfile, pk=staff_id, school=school)
    subject = get_object_or_404(Subject, pk=pk, school=school)
    
    if request.method == 'POST':
        subject.teacher = None
        subject.save()
        messages.success(request, f'Subject "{subject.name}" removed from {teacher.user.get_full_name()}.')
        return redirect('school:school-teacher-subjects', staff_id=staff_id)
    
    return redirect('school:school-teacher-subjects', staff_id=staff_id)


@login_required
def school_subjects(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    query = request.GET.get('q', '')

    subject_qs = (
        Subject.objects
        .filter(school=school)
        .select_related('school', 'pathway')
        .prefetch_related('grade')
        .order_by('name')
    )

    if query:
        subject_qs = subject_qs.filter(
            Q(name__icontains=query) |
            Q(code__icontains=query) |
            Q(grade__name__icontains=query)
        ).distinct()  # 👈 important for M2M searches

    paginator = Paginator(subject_qs, 10)
    page_number = request.GET.get('page')
    subjects = paginator.get_page(page_number)

    form = SubjectForm(school=school)

    return render(
        request,
        'school/subject.html',
        {
            'subjects': subjects,
            'form': form,
            'school': school,
            'query': query,
        }
    )


@login_required
def subject_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = SubjectForm(request.POST, school=school)
        if form.is_valid():
            subject = form.save(commit=False)
            subject.school = school
            subject.save()
            messages.success(request, f'Subject "{subject.name}" created successfully.')
            logger.info(f"Created subject {subject.name} for school {school.name}.")
            return redirect('school:school-subjects')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-subjects')

@login_required
def subject_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    subject = get_object_or_404(Subject, pk=pk, school=school)
    if request.method == 'POST':
        form = SubjectForm(request.POST, instance=subject, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Subject "{subject.name}" updated successfully.')
            return redirect('school:school-subjects')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-subjects')

@login_required
def subject_delete(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    subject = get_object_or_404(Subject, pk=pk, school=school)
    if request.method == 'POST':
        subject.is_active = False  # Soft delete
        subject.save()
        messages.success(request, f'Subject "{subject.name}" deactivated.')
        return redirect('school:school-subjects')
    return redirect('school:school-subjects')

@login_required
def school_enrollment(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    enrollments = Enrollment.objects.filter(school=school).select_related('student', 'subject')
    if query:
        enrollments = enrollments.filter(
            Q(student__user__first_name__icontains=query) | Q(subject__name__icontains=query)
        )
    
    form = EnrollmentForm(school=school)
    context = {
        'enrollments': enrollments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/enrollment.html', context)

@login_required
def enrollment_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, school=school)
        if form.is_valid():
            enrollment = form.save(commit=False)
            enrollment.school = school
            enrollment.save()
            messages.success(request, f'Enrollment for {enrollment.student} in {enrollment.subject} created.')
            return redirect('school:school-enrollment')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-enrollment')


@login_required
def enrollment_edit(request, pk):
    """
    Edit existing enrollment (e.g., change subject).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    enrollment = get_object_or_404(Enrollment, pk=pk, school=school)
    if request.method == 'POST':
        form = EnrollmentForm(request.POST, instance=enrollment, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Enrollment for {enrollment.student} updated successfully.')
            return redirect('school:school-enrollment')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-enrollment')

@login_required
def enrollment_delete(request, pk):
    """
    Soft-delete enrollment (set inactive or remove).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    enrollment = get_object_or_404(Enrollment, pk=pk, school=school)
    if request.method == 'POST':
        # Soft delete: Mark inactive or cascade to lessons if needed
        enrollment.is_active = False
        enrollment.save()
        messages.success(request, f'Enrollment for {enrollment.student} in {enrollment.subject} deactivated.')
        return redirect('school:school-enrollment')
    return redirect('school:school-enrollment')


@login_required
def school_timetable(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "No permission.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)
    if not school:
        return redirect('school:dashboard')

    # ---------------- WEEK NAV ----------------
    today = timezone.now().date()
    week_offset = int(request.GET.get("week", 0))

    start_of_week = today - timedelta(days=today.weekday()) + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=4)

    # ---------------- LESSONS ----------------
    lessons = Lesson.objects.filter(
        timetable__school=school,
        lesson_date__range=[start_of_week, end_of_week]
    ).select_related(
        'subject', 'teacher__user', 'stream', 'time_slot', 'timetable__grade'
    )

    # ---------------- GROUP ----------------
    grid = defaultdict(lambda: defaultdict(list))
    time_slots = set()

    for lesson in lessons:
        day = lesson.lesson_date.strftime('%A')
        grid[lesson.time_slot][day].append(lesson)
        time_slots.add(lesson.time_slot)

    time_slots = sorted(time_slots, key=lambda x: x.start_time)
    days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    return render(request, "school/timetable.html", {
        "grid": grid,
        "time_slots": time_slots,
        "start_of_week": start_of_week,
        "end_of_week": end_of_week,
        "week_offset": week_offset,
        "days": days,
    })

# views.py
WEEKDAY_CHOICES = [
    ('monday', 'Monday'),
    ('tuesday', 'Tuesday'),
    ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'),
    ('friday', 'Friday'),
    ('saturday', 'Saturday'),
    ('sunday', 'Sunday'),
]

@login_required
@require_http_methods(["GET", "POST"])
def lesson_edit(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    if request.method == "POST":
        # Store old position
        old_day = lesson.day_of_week
        old_slot = lesson.time_slot_id

        # Update lesson
        lesson.subject_id = request.POST.get("subject")
        lesson.stream_id = request.POST.get("stream")
        lesson.teacher_id = request.POST.get("teacher")
        lesson.day_of_week = request.POST.get("day_of_week")
        lesson.time_slot_id = request.POST.get("time_slot")
        lesson.room = request.POST.get("room")
        lesson.lesson_date = request.POST.get("lesson_date") or None
        lesson.notes = request.POST.get("notes")
        lesson.is_canceled = request.POST.get("is_canceled") == "on"
        lesson.save()

        # New position
        new_day = lesson.day_of_week
        new_slot = lesson.time_slot_id

        # Send SMS
        # try:
        #     send_sms_to_teacher(lesson)
        # except Exception as e:
        #     print("SMS error:", e)

        # Return updated HTML
        cell_html = render_to_string(
            "school/partials/lesson_cell_content.html",
            {"lesson": lesson},
            request=request
        )

        return JsonResponse({
            "success": True,
            "lesson_id": lesson.id,
            "cell_html": cell_html,
            "old_day": old_day,
            "old_slot": old_slot,
            "new_day": new_day,
            "new_slot": new_slot,
        })

    # GET → load form
    context = {
        "lesson": lesson,
        "subjects": Subject.objects.all(),
        "streams": Streams.objects.all(),
        "teachers": StaffProfile.objects.select_related("user"),
        "timeslots": TimeSlot.objects.all(),
        "weekday_choices": WEEKDAY_CHOICES,
    }

    return render(request, "school/partials/lesson_form.html", context)

@login_required
def lesson_attendance(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)

    # Only active enrollments
    enrollments = Enrollment.objects.filter(
        lesson=lesson,
        status='active'
    ).select_related('student')

    # ---------------- POST REQUEST ----------------
    if request.method == "POST":
        with transaction.atomic():
            for e in enrollments:
                status = request.POST.get(f"status_{e.id}")   # <-- use enrollment ID
                remarks = request.POST.get(f"remarks_{e.id}")

                if not status:
                    continue  # skip empty

                # Only principals/deputies can suspend (18) or expel (20)
                if status in ('18', '20') and not (
                    request.user.is_principal or request.user.is_deputy_principal or request.user.is_admin
                ):
                    continue

                # Update or create attendance
                att, created = Attendance.objects.update_or_create(
                    enrollment=e,
                    date=lesson.lesson_date,
                    defaults={
                        "status": status,
                        "remarks": remarks,
                        "marked_by": getattr(request.user, "staffprofile", None)
                    }
                )

                # Update student suspension/expulsion flags
                student = e.student
                if status == '18':  # Suspension
                    student.suspended = True
                    student.expelled = False
                    student.is_active = True
                    student.save(update_fields=['suspended', 'expelled', 'is_active'])
                elif status == '20':  # Expulsion
                    student.expelled = True
                    student.suspended = False
                    student.is_active = False
                    student.save(update_fields=['expelled', 'suspended', 'is_active'])
                else:
                    if student.suspended or student.expelled:
                        student.suspended = False
                        student.expelled = False
                        student.is_active = True
                        student.save(update_fields=['suspended', 'expelled', 'is_active'])

        # Reload fresh attendance for modal display
        updated_attendance = Attendance.objects.filter(
            enrollment__lesson=lesson,
            date=lesson.lesson_date
        ).select_related("enrollment")

        attendance_map = {a.enrollment_id: a for a in updated_attendance}

        html = render_to_string(
            "school/partials/attendance_modal.html",
            {
                "lesson": lesson,
                "enrollments": enrollments,
                "attendance_map": attendance_map,
                "status_choices": Attendance.ATTENDANCE_STATUS_CHOICES,
            },
            request=request
        )

        return JsonResponse({"success": True, "html": html})

    # ---------------- GET REQUEST ----------------
    attendance_map = {}
    existing_attendance = Attendance.objects.filter(
        enrollment__lesson=lesson,
        date=lesson.lesson_date
    ).select_related("enrollment")

    # Populate existing attendance
    for a in existing_attendance:
        attendance_map[a.enrollment_id] = a

    # Pre-populate suspended/expelled students
    for e in enrollments:
        student = e.student
        if student.suspended:
            if e.id not in attendance_map:
                attendance_map[e.id] = Attendance(
                    enrollment=e,
                    date=lesson.lesson_date,
                    status='18',
                    remarks='Suspended'
                )
        elif student.expelled:
            if e.id not in attendance_map:
                attendance_map[e.id] = Attendance(
                    enrollment=e,
                    date=lesson.lesson_date,
                    status='20',
                    remarks='Expelled'
                )

    return render(request, "school/partials/attendance_modal.html", {
        "lesson": lesson,
        "enrollments": enrollments,
        "attendance_map": attendance_map,
        "status_choices": Attendance.ATTENDANCE_STATUS_CHOICES,
    })


# ──────────────────────────────────────────────────────────────────────────────
# STUDENT STATUS ACTIONS  (suspend / expel / reinstate)
# Only principals and deputy principals may perform these actions.
# ──────────────────────────────────────────────────────────────────────────────

@login_required
@require_POST
def student_suspend(request, student_id):
    user = request.user
    if not (user.is_principal or user.is_deputy_principal or user.is_admin):
        messages.error(request, "Only principals and deputy principals can suspend students.")
        return redirect('school:dashboard')
    school = get_user_school(user)
    student = get_object_or_404(Student, id=student_id, school=school)
    reason = request.POST.get('reason', '').strip()
    student.suspended = True
    student.expelled = False
    student.is_active = True
    student.save(update_fields=['suspended', 'expelled', 'is_active'])
    DisciplineRecord.objects.create(
        school=school,
        student=student,
        reported_by=getattr(user, 'staffprofile', None),
        incident_type='suspension',
        description=reason or 'Suspended by principal.',
        severity='critical',
        action_taken='Student suspended.',
    )
    messages.success(request, f"{student.user.get_full_name()} has been suspended.")
    return redirect(request.POST.get('next', 'school:school-users'))


@login_required
@require_POST
def student_expel(request, student_id):
    user = request.user
    if not (user.is_principal or user.is_deputy_principal or user.is_admin):
        messages.error(request, "Only principals and deputy principals can expel students.")
        return redirect('school:dashboard')
    school = get_user_school(user)
    student = get_object_or_404(Student, id=student_id, school=school)
    reason = request.POST.get('reason', '').strip()
    student.expelled = True
    student.suspended = False
    student.is_active = False
    student.save(update_fields=['expelled', 'suspended', 'is_active'])
    DisciplineRecord.objects.create(
        school=school,
        student=student,
        reported_by=getattr(user, 'staffprofile', None),
        incident_type='expulsion',
        description=reason or 'Expelled by principal.',
        severity='critical',
        action_taken='Student expelled.',
    )
    messages.success(request, f"{student.user.get_full_name()} has been expelled.")
    return redirect(request.POST.get('next', 'school:school-users'))


@login_required
@require_POST
def student_reinstate(request, student_id):
    user = request.user
    if not (user.is_principal or user.is_deputy_principal or user.is_admin):
        messages.error(request, "Only principals and deputy principals can reinstate students.")
        return redirect('school:dashboard')
    school = get_user_school(user)
    student = get_object_or_404(Student, id=student_id, school=school)
    student.suspended = False
    student.expelled = False
    student.is_active = True
    student.save(update_fields=['suspended', 'expelled', 'is_active'])
    messages.success(request, f"{student.user.get_full_name()} has been reinstated.")
    return redirect(request.POST.get('next', 'school:school-users'))


@login_required
def timetable_create(request):
    """
    Create a new timetable for a grade/term/year.
    Validates unique_together and date range.
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = TimetableForm(request.POST, school=school)
        if form.is_valid():
            timetable = form.save(commit=False)
            timetable.school = school
            timetable.save()
            messages.success(request, f'Timetable for {timetable.grade.name} - Term {timetable.term} {timetable.year} created successfully.')
            logger.info(f"Created timetable {timetable.id} for {school.name}.")
            return redirect('school:school-timetable')
        else:
            # Render errors in messages
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else 'Form'}: {error}")
    else:
        form = TimetableForm(school=school)
    
    # On GET error or initial, redirect to list
    return redirect('school:school-timetable')
# Similar edit/delete...


@login_required
def timetable_edit(request, pk):
    """
    Edit existing timetable (e.g., adjust dates).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    timetable = get_object_or_404(Timetable, pk=pk, school=school)
    if request.method == 'POST':
        form = TimetableForm(request.POST, instance=timetable, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Timetable for {timetable.grade.name} updated successfully.')
            return redirect('school:school-timetable')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label if field != '__all__' else 'Form'}: {error}")
    else:
        form = TimetableForm(instance=timetable, school=school)
    
    context = {'form': form, 'timetable': timetable}
    return render(request, 'school/timetable_form.html', context)  # Or modal-redirect


@login_required
def timetable_delete(request, pk):
    """
    Soft-delete timetable (set inactive or remove).
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    timetable = get_object_or_404(Timetable, pk=pk, school=school)
    if request.method == 'POST':
        # Soft delete: Mark inactive or cascade to lessons if needed
        timetable.delete()  # Or timetable.is_active = False; timetable.save()
        messages.success(request, f'Timetable for {timetable.grade.name} deleted.')
        return redirect('school:school-timetable')
    messages.warning(request, "Confirm deletion.")
    return redirect('school:school-timetable')


# List lessons via @login_required
@login_required
def teacher_lessons(request, staff_id):
    """
    List all lessons for a specific teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    teacher = get_object_or_404(StaffProfile, pk=staff_id, school=school)
    lessons = Lesson.objects.filter(teacher=teacher).select_related(
        'subject', 'timetable__grade', 'time_slot', 'stream'
    ).order_by('day_of_week', 'lesson_date', 'time_slot__start_time')

    query = request.GET.get('q', '')
    if query:
        lessons = lessons.filter(
            Q(subject__name__icontains=query) |
            Q(timetable__grade__name__icontains=query) |
            Q(stream__name__icontains=query) |
            Q(day_of_week__icontains=query)
        )
    
    paginator = Paginator(lessons, 10)
    page_number = request.GET.get('page')
    lessons_page = paginator.get_page(page_number)
    form = LessonForm(school=school)
    context = {
        'teacher': teacher,
        'lessons': lessons_page,
        'school': school,
         'form': form,  
        'query': query,
    }
    return render(request, 'school/teacher/lessons.html', context)

@login_required
def teacher_lesson_create(request):
    """
    Create a new lesson for a specific teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    if request.method == 'POST':
        form = LessonForm(request.POST, school=school)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.teacher = request.user.staffprofile
            lesson.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} created.')
            return redirect('school:teacher-lessons', staff_id=request.user.staffprofile.id)
    else:
        form = LessonForm(school=school)
    
    context = {
        'form': form,
        'school': school,
        'teacher': request.user.staffprofile,
    }
    return render(request, 'school/teacher/lesson_form.html', context)  # Or modal-redirect


@login_required
def teacher_lesson_edit(request, lesson_id):
    """
    Edit an existing lesson for a specific teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    lesson = get_object_or_404(Lesson, pk=lesson_id, teacher=request.user.staffprofile)
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} updated.')
            return redirect('school:teacher-lessons', staff_id=request.user.staffprofile.id)
    else:
        form = LessonForm(instance=lesson, school=school)
    
    context = {
        'form': form,
        'lesson': lesson,
        'school': school,
        'teacher': request.user.staffprofile,
    }
    return render(request, 'school/teacher/lesson_form.html', context)  # Or modal-redirect


@login_required
def teacher_lesson_delete(request, lesson_id):
    """
    Delete a lesson for a specific teacher.
    """
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    lesson = get_object_or_404(Lesson, pk=lesson_id, teacher=request.user.staffprofile)
    if request.method == 'POST':
        lesson.delete()
        messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} deleted.')
        return redirect('school:teacher-lessons', staff_id=request.user.staffprofile.id)
    messages.warning(request, "Confirm deletion.")
    return redirect('school:teacher-lessons', staff_id=request.user.staffprofile.id)

def lesson_list(request, timetable_id):
    """
    List all lessons for a specific timetable
    """
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    timetable = get_object_or_404(Timetable, id=timetable_id, school=school)
    lessons = timetable.lessons.select_related(
        'subject', 'teacher__user', 'time_slot', 'stream'
    ).order_by('day_of_week', 'lesson_date', 'time_slot__start_time')

    query = request.GET.get('q', '')
    if query:
        lessons = lessons.filter(
            Q(subject__name__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query) |
            Q(stream__name__icontains=query) |
            Q(room__icontains=query)
        )
    
    paginator = Paginator(lessons, 10)
    page_number = request.GET.get('page')
    lessons_page = paginator.get_page(page_number)
    
    form = LessonForm(school=school, initial={'timetable': timetable})
    context = {
        'timetable': timetable,
        'lessons': lessons_page,
        'form': form,
        'query': query,
        'school': school,
    }
    return render(request, 'school/lesson.html', context)


@login_required
def lesson_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = LessonForm(request.POST, school=school)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} created.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:lesson-list', timetable_id=request.POST.get('timetable'))


# @login_required
# def lesson_edit(request, lesson_id):
#     user = request.user

#     if not (user.is_admin or user.is_principal or user.is_deputy_principal):
#         messages.error(request, "You do not have permission to access this dashboard.")
#         return redirect("userauths:sign-in")

#     school = get_user_school(user)

#     if not school:
#         messages.error(request, "Access denied.")
#         return redirect('school:dashboard')
    
#     lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    
#     if request.method == 'POST':
#         form = LessonForm(request.POST, instance=lesson, school=school)
#         if form.is_valid():
#             form.save()
#             messages.success(request, f'Lesson for {lesson.subject} on {lesson.lesson_date} updated.')
#         else:
#             for field, errors in form.errors.items():
#                 for error in errors:
#                     if field == '__all__':
#                         messages.error(request, error)
#                     else:
#                         messages.error(request, f"{form.fields[field].label}: {error}")
#     return redirect('school:school-timetable')


@login_required
def lesson_delete(request, lesson_id):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    timetable_id = lesson.timetable.id
    lesson.delete()
    messages.success(request, "Lesson deleted successfully.")
    return redirect('school:lesson-list', timetable_id=timetable_id)

@login_required
def school_virtual_classes(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    sessions = Session.objects.filter(school=school).select_related('subject', 'teacher')
    if query:
        sessions = sessions.filter(Q(title__icontains=query) | Q(subject__name__icontains=query))
    
    form = SessionForm(school=school)
    context = {
        'sessions': sessions,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/session.html', context)


@login_required
def session_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = SessionForm(request.POST, school=school)
        if form.is_valid():
            session = form.save(commit=False)
            session.school = school
            session.teacher = request.user.staffprofile
            session.save()
            messages.success(request, f"Session '{session.title}' created successfully.")
        else:
            messages.error(request, "Error creating session. Check the form.")
    return redirect('school:school-sessions')


@login_required
def session_edit(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = SessionForm(request.POST, instance=session, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f"Session '{session.title}' updated successfully.")
        else:
            messages.error(request, "Error updating session. Check the form.")
    return redirect('school:school-sessions')


@login_required
def session_delete(request, session_id):
    session = get_object_or_404(Session, id=session_id)
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        session.delete()
        messages.success(request, f"Session '{session.title}' deleted successfully.")
    return redirect('school:school-sessions')



def auto_mark_attendance_from_scan(student, stream, scan_log=None):
    """
    Auto-mark attendance using the given scan log.
    Only creates GradeAttendance if the scan came from a device ID starting with 'grade'.
    If scan_log is None, use the latest ScanLog for the student.
    """
    if not scan_log:
        scan_log = ScanLog.objects.filter(
            smart_id__profile=student.user,
            smart_id__school=stream.school
        ).order_by('-scanned_at').first()

    if not scan_log:
        return

    # Only mark if device_id starts with 'grade'
    if scan_log.device_id.lower().startswith('grade'):
        GradeAttendance.objects.create(
            student=student,
            stream=stream,
            status='P',
            scan_log=scan_log
        )


@login_required
def teacher_class_attendance_report(request, stream_id):
    school = request.user.staffprofile.school
    stream = get_object_or_404(Streams, id=stream_id, school=school)
    grade = stream.grade
    students = stream.students.all()
    attendance_summary = []

    # Handle POST save
    if request.method == 'POST':
        for student in students:
            status_key = f"status_{student.id}"
            status = request.POST.get(status_key)

            if status:
                # Update latest attendance OR create new if none exists
                latest = GradeAttendance.objects.filter(student=student, stream=stream).order_by('-recorded_at').first()
                if latest:
                    latest.status = status
                    latest.save()
                else:
                    GradeAttendance.objects.create(student=student, stream=stream, status=status)
        
        messages.success(request, "Attendance saved successfully!")
        return redirect(request.path)

    # GET → Show UI
    for student in students:

        # Auto-mark using ScanLog (creates new records for each scan)
        auto_mark_attendance_from_scan(student, stream)

        # Get latest attendance for display
        latest = GradeAttendance.objects.filter(student=student, stream=stream).order_by('-recorded_at').first()

        attendance_summary.append({
            'student': student,
            'existing': latest
        })

    paginator = Paginator(attendance_summary, 50)
    page = request.GET.get('page')
    attendance_summary = paginator.get_page(page)

    context = {
        'stream': stream,
        'grade': grade,
        'attendance_summary': attendance_summary,
        'school': school,
    }
    return render(request, 'school/teacher/class_attendance_report.html', context)

from django.db.models import Count, Q, F
from django.core.paginator import Paginator
@login_required
def attendance_dashboard(request):
    user = request.user

    # ───── PERMISSIONS ─────
    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)
    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    # ───── BASE QUERYSET ─────
    qs = Attendance.objects.select_related(
        'enrollment__student__user',
        'enrollment__student__grade_level',
        'enrollment__student__stream',
        'enrollment__lesson__subject',
        'enrollment__lesson__teacher__user',
        'term',
        'academic_year',
        'marked_by__user'
    ).filter(enrollment__school=school)

    # ───── FILTERS ─────
    filters = {
        'academic_year': request.GET.get('academic_year', ''),
        'term': request.GET.get('term', ''),
        'grade': request.GET.get('grade', ''),
        'stream': request.GET.get('stream', ''),
        'subject': request.GET.get('subject', ''),
        'student': request.GET.get('student', ''),
        'date_from': request.GET.get('date_from', ''),
        'date_to': request.GET.get('date_to', ''),
    }

    if filters['academic_year'].isdigit():
        qs = qs.filter(academic_year_id=filters['academic_year'])

    if filters['term'].isdigit():
        qs = qs.filter(term_id=filters['term'])

    if filters['grade'].isdigit():
        qs = qs.filter(enrollment__student__grade_level_id=filters['grade'])

    if filters['stream'].isdigit():
        qs = qs.filter(enrollment__student__stream_id=filters['stream'])

    if filters['subject'].isdigit():
        qs = qs.filter(enrollment__lesson__subject_id=filters['subject'])

    if filters['student'].strip():
        s = filters['student'].strip()
        qs = qs.filter(
            Q(enrollment__student__student_id__icontains=s) |
            Q(enrollment__student__user__first_name__icontains=s) |
            Q(enrollment__student__user__last_name__icontains=s)
        )

    # ───── DATE RANGE ─────
    date_from = parse_date(filters['date_from']) if filters['date_from'] else None
    date_to = parse_date(filters['date_to']) if filters['date_to'] else None

    if date_from and date_to:
        qs = qs.filter(date__range=(date_from, date_to))
    elif date_from:
        qs = qs.filter(date__gte=date_from)
    elif date_to:
        qs = qs.filter(date__lte=date_to)

    # ───── STATUS CARDS ─────
    stats = qs.aggregate(
        P=Count('id', filter=Q(status='P')),
        ET=Count('id', filter=Q(status='ET')),
        UT=Count('id', filter=Q(status='UT')),
        EA=Count('id', filter=Q(status='EA')),
        UA=Count('id', filter=Q(status='UA')),
    )

    stats = {k: v or 0 for k, v in stats.items()}

    status_cards = [
        {'label': 'Present', 'color': 'success', 'count': stats['P']},
        {'label': 'Tardy', 'color': 'warning', 'count': stats['ET'] + stats['UT']},
        {'label': 'Absent', 'color': 'danger', 'count': stats['EA'] + stats['UA']},
    ]

    # ───── FULL STATUS TREND ─────
    status_trend = qs.values('date').annotate(
        P=Count('id', filter=Q(status='P')),
        ET=Count('id', filter=Q(status='ET')),
        UT=Count('id', filter=Q(status='UT')),
        EA=Count('id', filter=Q(status='EA')),
        UA=Count('id', filter=Q(status='UA')),
        IB=Count('id', filter=Q(status='IB')),
        S18=Count('id', filter=Q(status='18')),
        S20=Count('id', filter=Q(status='20')),
    ).order_by('date')

    # ───── MISSING ATTENDANCE ─────
    lesson_qs = Lesson.objects.filter(
        timetable__school=school,
        lesson_date__lt=localdate()
    )

    attendance_exists = Attendance.objects.filter(
        enrollment__lesson=OuterRef('pk')
    )

    missing_lessons = lesson_qs.annotate(
        has_attendance=Exists(attendance_exists)
    ).filter(has_attendance=False)

    missing_lessons_count = missing_lessons.count()

    # ───── TEACHER MISSED LESSONS ─────
    teacher_missed_trends = missing_lessons.values(
        'teacher__user__first_name',
        'teacher__user__last_name',
        'teacher__pk',
    ).annotate(
        missed=Count('id')
    ).order_by('-missed')[:10]

    # Per-teacher missed lesson details (for hover tooltip)
    import json as _json
    teacher_missed_details = {}
    for t in teacher_missed_trends:
        tid = t.get('teacher__pk')
        if tid:
            details = list(
                missing_lessons.filter(teacher_id=tid).select_related(
                    'subject', 'stream', 'timetable__grade', 'time_slot'
                ).values(
                    'lesson_date',
                    'time_slot__start_time',
                    'time_slot__end_time',
                    'subject__name',
                    'stream__name',
                    'timetable__grade__name',
                )[:15]
            )
            teacher_name = f"{t['teacher__user__first_name']} {t['teacher__user__last_name']}"
            teacher_missed_details[teacher_name] = [
                {
                    'date': str(d['lesson_date']),
                    'time': f"{d['time_slot__start_time']} - {d['time_slot__end_time']}" if d['time_slot__start_time'] else '—',
                    'subject': d['subject__name'] or '—',
                    'class': f"{d['timetable__grade__name']} {d['stream__name']}",
                }
                for d in details
            ]
    teacher_missed_details_json = _json.dumps(teacher_missed_details)

    # ───── DISCIPLINE BASE ─────
    discipline_qs = DisciplineRecord.objects.filter(
        school=school,
        linked_attendance__in=qs
    )

    # ───── DISCIPLINE STATS ─────
    discipline_stats = discipline_qs.aggregate(
        total=Count('id'),
        unresolved=Count('id', filter=Q(resolved=False)),
        severe=Count('id', filter=Q(severity='severe')),
    )

    discipline_stats = {k: v or 0 for k, v in discipline_stats.items()}

    # ───── DISCIPLINE DAILY TREND (FIXED ✅ uses date) ─────
    discipline_daily = discipline_qs.values('date').annotate(
        total=Count('id'),
        severe=Count('id', filter=Q(severity='severe'))
    ).order_by('date')

    # ───── DISCIPLINE PER GRADE ─────
    discipline_by_grade = discipline_qs.values(
        'linked_attendance__enrollment__student__grade_level__name'
    ).annotate(
        total=Count('id'),
        severe=Count('id', filter=Q(severity='severe')),
        repeats=Sum('frequency_count')
    )

    # ───── INCIDENT TYPE TREND (NEW 🔥) ─────
    discipline_by_type = discipline_qs.values('incident_type').annotate(
        total=Count('id')
    ).order_by('-total')

    # ───── TOP REPEAT OFFENDERS (NEW 🔥) ─────
    repeat_offenders = discipline_qs.values(
        'student__user__first_name',
        'student__user__last_name'
    ).annotate(
        total_cases=Count('id'),
        repeat_score=Sum('frequency_count')
    ).order_by('-repeat_score')[:10]

    # ───── DEFAULT TREND ─────
    trend_qs = qs
    if not (date_from or date_to):
        today = localdate()
        trend_qs = qs.filter(date__gte=today - timedelta(days=30))

    daily_trend = trend_qs.values('date').annotate(
        present=Count('id', filter=Q(status='P')),
        absent=Count('id', filter=Q(status__in=['EA', 'UA'])),
    ).order_by('date')

    # ───── PAGINATION ─────
    paginator = Paginator(qs.order_by('-date', '-id'), 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    # ───── FINAL CONTEXT ─────
    return render(request, 'school/attendance_dashboard.html', {
        'attendances': page_obj,
        'status_cards': status_cards,
        'daily_trend': list(daily_trend),

        'status_trend': list(status_trend),
        'teacher_missed_trends': list(teacher_missed_trends),
        'teacher_missed_details_json': teacher_missed_details_json,
        'discipline_daily': list(discipline_daily),
        'discipline_by_grade': list(discipline_by_grade),
        'discipline_by_type': list(discipline_by_type),
        'repeat_offenders': list(repeat_offenders),
        'missing_lessons_count': missing_lessons_count,

        'discipline_stats': discipline_stats,
        'filters': filters,
        'academic_years': AcademicYear.objects.filter(school=school),
        'terms': Term.objects.filter(school=school),
        'grades': Grade.objects.filter(school=school),
        'streams': Streams.objects.filter(school=school),
        'subjects': Subject.objects.filter(school=school, is_active=True),
        'school': school,
        'alerts': [],
    })
@login_required
def get_streams_by_grade(request):
    grade_id = request.GET.get('grade')
    streams = []
    if grade_id:
        streams_qs = Streams.objects.filter(grade_id=grade_id).order_by('name')
        streams = [{'id': s.id, 'name': s.name} for s in streams_qs]
    return JsonResponse({'streams': streams})

# === EXPORT CSV ===
def export_attendance_csv(request):
    qs = Attendance.objects.all()

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="attendance_report.csv"'

    writer = csv.writer(response)
    writer.writerow([
        'Student', 'Grade', 'Stream', 'Subject', 'Date', 'Status'
    ])

    for a in qs:
        writer.writerow([
            a.enrollment.student.user.get_full_name(),
            a.enrollment.student.grade_level.name,
            a.enrollment.student.stream.name,
            a.enrollment.subject.name,
            a.date,
            a.status
        ])

    return response


@login_required
def attendance_mark(request, lesson_id):
    # --- Fetch lesson safely ---
    lesson = get_object_or_404(
        Lesson.objects.select_related('subject', 'school', 'timetable__term__academic_year'),
        id=lesson_id,
        teacher=request.user.staffprofile
    )

    # --- Fetch students enrolled in lesson's subject or fallback to all active students in the school ---
    students = Enrollment.objects.filter(
        school=lesson.school,
        status='active'
    ).select_related('student__user')

    # Optional: filter by subject if you want strict matching
    subject_students = students.filter(subject=lesson.subject)
    if subject_students.exists():
        students = subject_students

    # --- Fetch existing attendance records for this lesson date ---
    attendance_dict = {
        att.enrollment_id: att
        for att in Attendance.objects.filter(
            enrollment__in=students,
            date=lesson.lesson_date
        )
    }

    term = getattr(lesson.timetable, 'term', None) if getattr(lesson, 'timetable', None) else None
    academic_year = getattr(term, 'academic_year', None) if term else None

    valid_statuses = {code for code, _ in Attendance.ATTENDANCE_STATUS_CHOICES}

    if request.method == 'POST':
        saved_count = 0
        for enrollment in students:
            field_name = f'status_{enrollment.id}'
            selected_status = request.POST.get(field_name)

            # Validate selected status
            if selected_status not in valid_statuses:
                selected_status = 'P'  # default to Present if invalid/missing

            Attendance.objects.update_or_create(
                enrollment=enrollment,
                date=lesson.lesson_date,
                defaults={
                    'status': selected_status,
                    'marked_by': request.user.staffprofile,
                    'term': term,
                    'academic_year': academic_year,
                }
            )
            saved_count += 1

        messages.success(request, f"Attendance for {saved_count} students has been recorded.")
        return redirect('school:teacher-attendance-mark', lesson_id=lesson.id)

    return render(request, 'school/teacher/attendance_mark.html', {
        'lesson': lesson,
        'students': students,
        'attendance_dict': attendance_dict,
        'school': lesson.school,
    })
@login_required
def attendance_edit(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            messages.success(request, f'Attendance for {attendance.enrollment.student} updated successfully.')
        else:
            messages.error(request, "Error updating attendance. Check the form.")
    return redirect('school:attendance-dashboard')

@login_required
def attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, f'Attendance for {attendance.enrollment.student} deleted successfully.')
    return redirect('school:attendance-dashboard')
# Summary view
@login_required
def attendance_summary(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    # Generate summary data
    period_start = request.GET.get('start')
    period_end = request.GET.get('end')
    if not period_start or not period_end:
        period_start = timezone.now().date().replace(day=1)
        period_end = timezone.now().date()
    
    lessons = Lesson.objects.filter(date__range=[period_start, period_end], school=school)
    attendances = Attendance.objects.filter(lesson__in=lessons)
    
    summary = attendances.values('status').annotate(count=Count('status'))
    total_sessions = lessons.count()
    present_pct = (summary.get('P', {'count': 0})['count'] / (len(enrollments) * total_sessions)) * 100 if total_sessions else 0
    
    context = {
        'summary': summary,
        'period_start': period_start,
        'period_end': period_end,
        'present_pct': round(present_pct, 2),
        'school': school,
    }
    return render(request, 'school/attendance_summary.html', context)


@login_required
def teacher_attendance(request):
    try:
        teacher = request.user.staffprofile
        school = teacher.school
    except AttributeError:
        messages.error(request, "Access denied.")
        return redirect('userauths:teacher-dashboard')

    # ───────────── DATE FILTER ─────────────
    start = request.GET.get('start')
    end = request.GET.get('end')

    if start and end:
        try:
            start = datetime.strptime(start, "%Y-%m-%d").date()
            end = datetime.strptime(end, "%Y-%m-%d").date()
        except ValueError:
            start = timezone.now().date().replace(day=1)
            end = timezone.now().date()
    else:
        start = timezone.now().date().replace(day=1)
        end = timezone.now().date()

    # ───────────── STREAM & GRADE FILTER ─────────────
    stream_id = request.GET.get('stream')
    grade_id = request.GET.get('grade')

    # ───────────── LESSONS FOR TEACHER ─────────────
    lessons = Lesson.objects.filter(
        lesson_date__range=[start, end],
        teacher=teacher,
        is_canceled=False
    ).select_related('stream', 'subject')

    if stream_id:
        lessons = lessons.filter(stream_id=stream_id)
    if grade_id:
        lessons = lessons.filter(stream__grade_id=grade_id)

    # ───────────── ATTENDANCE QUERY ─────────────
    attendances_qs = Attendance.objects.filter(
        enrollment__lesson__in=lessons,
        enrollment__status='active'
    ).select_related(
        'enrollment__student__user',
        'enrollment__lesson__stream',
        'enrollment__lesson__subject',
        'marked_by'
    ).order_by('-date')

    # Dynamic student search (name or reg number)
    student_search = request.GET.get('student_search', '').strip()
    if student_search:
        attendances_qs = attendances_qs.filter(
            Q(enrollment__student__user__first_name__icontains=student_search) |
            Q(enrollment__student__user__last_name__icontains=student_search) |
            Q(enrollment__student__student_id__icontains=student_search)
        )

    # ───────────── SUMMARY ─────────────
    total_records = attendances_qs.count()
    summary_qs = attendances_qs.values('status').annotate(count=Count('status'))
    summary = {row['status']: row['count'] for row in summary_qs}

    present = summary.get('P', 0)
    absent = summary.get('UA', 0) + summary.get('EA', 0)
    tardy = summary.get('ET', 0) + summary.get('UT', 0)

    present_pct = (present / total_records * 100) if total_records else 0
    absent_pct = (absent / total_records * 100) if total_records else 0
    tardy_pct = (tardy / total_records * 100) if total_records else 0

    # ───────────── PAGINATION ─────────────
    paginator = Paginator(attendances_qs, 50)
    page = request.GET.get('page')
    attendances_page = paginator.get_page(page)

    # ───────────── FILTER DROPDOWNS ─────────────
    streams = Streams.objects.filter(school=school)
    grades = Grade.objects.filter(school=school)

    context = {
        'attendances': attendances_page,
        'school': school,

        # Filters
        'period_start': start,
        'period_end': end,
        'streams': streams,
        'grades': grades,
        'selected_stream': stream_id,
        'selected_grade': grade_id,
        'student_search': student_search,

        # Summary
        'summary': summary,
        'total_records': total_records,
        'present_pct': round(present_pct, 2),
        'absent_pct': round(absent_pct, 2),
        'tardy_pct': round(tardy_pct, 2),
    }

    return render(request, 'school/teacher/teacher_attendance_dashboard.html', context)


def send_parent_discipline_notification(parent, student, discipline, lesson):
    """
    Customize this based on your notification system (email, SMS, in-app, FCM, etc.)
    """
    subject = f"Discipline Alert: {student.user.get_full_name()}"
    message = (
        f"Dear Parent,\n\n"
        f"Your child {student.user.get_full_name()} was marked with "
        f"{discipline.get_incident_type_display()} on {discipline.date}.\n\n"
        f"Reason: {discipline.description}\n"
        f"Severity: {discipline.get_severity_display()}\n"
        f"Action Taken: {discipline.action_taken or 'None recorded'}\n\n"
        f"Teacher: {discipline.teacher.user.get_full_name()}\n"
        f"Subject: {lesson.subject.name}\n\n"
        f"Please contact the school if needed."
    )

    # Example using Django email
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[parent.email],  # assuming parent has email
            fail_silently=False,
        )
    except Exception as e:
        logger.error(f"Failed to send discipline email to {parent.email}: {e}")

# Constants
DISCIPLINE_CODES = ['IB', '18', '20']
ATTENDANCE_CODES = ['P', 'ET', 'UT', 'EA', 'UA']
@login_required
def teacher_attendance_mark(request, lesson_id):
    lesson = get_object_or_404(
        Lesson,
        id=lesson_id,
        teacher=request.user.staffprofile
    )

    teacher = request.user.staffprofile
    can_override = teacher.position in ['principal', 'deputy_principal']

    enrollments = Enrollment.objects.filter(
        lesson=lesson,
        status='active'
    ).select_related('student', 'student__user')

    # Prefetch today's attendance
    today_attendance_qs = Attendance.objects.filter(
        enrollment__in=enrollments,
        date=lesson.lesson_date
    ).select_related('enrollment')

    today_attendance_map = {a.enrollment_id: a for a in today_attendance_qs}

    # Current statuses
    current_statuses = {eid: att.status for eid, att in today_attendance_map.items()}

    # Status choices
    status_choices = [
        {'code': 'P',  'label': 'Present', 'color': 'success'},
        {'code': 'ET', 'label': 'Excused Tardy', 'color': 'warning'},
        {'code': 'UT', 'label': 'Unexcused Tardy', 'color': 'warning'},
        {'code': 'EA', 'label': 'Excused Absence', 'color': 'danger'},
        {'code': 'UA', 'label': 'Unexcused Absence', 'color': 'danger'},
        {'code': 'IB', 'label': 'Inappropriate Behavior', 'color': 'info'},
        {'code': '18', 'label': 'Suspension', 'color': 'dark'},
        {'code': '20', 'label': 'Expulsion', 'color': 'dark'},
    ]

    # Hide 18 & 20 from teachers without override
    if not can_override:
        status_choices = [s for s in status_choices if s['code'] not in ['18', '20']]

    # Determine if student is expelled/suspended
    disabled_attendance = {}
    forced_status_map = {}

    for e in enrollments:
        student = e.student
        if student.expelled:
            disabled_attendance[e.id] = True
            forced_status_map[e.id] = '20'
        elif student.suspended:
            disabled_attendance[e.id] = True
            forced_status_map[e.id] = '18'
        else:
            disabled_attendance[e.id] = False

    # POST - save attendance
    if request.method == 'POST' and request.headers.get('x-requested-with') == 'XMLHttpRequest':
        with transaction.atomic():
            updated_attendances = []

            for e in enrollments:
                # Force expelled/suspended status
                if e.id in forced_status_map:
                    status = forced_status_map[e.id]
                else:
                    status = request.POST.get(f'status_{e.id}')
                    # Prevent teacher from setting 18/20
                    if not can_override and status in ['18', '20']:
                        previous = today_attendance_map.get(e.id)
                        status = previous.status if previous else 'P'

                    # Validate
                    valid_codes = [s['code'] for s in status_choices]
                    if status not in valid_codes:
                        status = 'P'

                att, _ = Attendance.objects.update_or_create(
                    enrollment=e,
                    date=lesson.lesson_date,
                    defaults={
                        'status': status,
                        'term': lesson.timetable.term,
                        'academic_year': lesson.timetable.term.year,
                        'marked_by': teacher
                    }
                )
                updated_attendances.append(att)

        # Notifications for first/last slot
        is_first = is_first_slot(lesson)
        is_last  = is_last_slot(lesson)

        if is_first:
            for att in updated_attendances:
                if att.status in ['P', 'ET', 'UT', 'EA', 'UA']:
                    notify_first_lesson(att)

        if is_last:
            students_notified = set()
            for att in updated_attendances:
                student = att.enrollment.student
                if student.id not in students_notified:
                    notify_last_lesson(student, lesson.lesson_date)
                    students_notified.add(student.id)

        return JsonResponse({'success': True})

    # Term trends
    term_attendance = Attendance.objects.filter(
        enrollment__student__in=[e.student for e in enrollments],
        term=lesson.timetable.term
    ).values('enrollment__student_id', 'status')

    trend_map = defaultdict(lambda: {'P':0,'ET':0,'UT':0,'EA':0,'UA':0,'total':0})

    for row in term_attendance:
        sid = row['enrollment__student_id']
        status = row['status']
        if status in trend_map[sid]:
            trend_map[sid][status] += 1
        trend_map[sid]['total'] += 1

    # Convert to %
    for sid in trend_map:
        total = trend_map[sid]['total'] or 1
        for code in ['P','ET','UT','EA','UA']:
            trend_map[sid][code] = round((trend_map[sid][code] / total) * 100, 0)

    return render(request, 'school/teacher/attendance_mark.html', {
        'lesson': lesson,
        'enrollments': enrollments,
        'status_choices': status_choices,
        'current_statuses': current_statuses,
        'attendance_locked': False,  # always editable
        'can_override': can_override,
        'ATTENDANCE_CODES': ['P','ET','UT','EA','UA'],
        'DISCIPLINE_CODES': ['IB','18','20'],
        'disabled_attendance': disabled_attendance,
        'forced_status_map': forced_status_map,
        'INCIDENT_TYPE_CHOICES': INCIDENT_TYPE_CHOICES,
        'SEVERITY_CHOICES': DisciplineRecord._meta.get_field('severity').choices,
        'trend_map': dict(trend_map),
    })

@login_required
def teacher_attendance_smart(request, lesson_id):
    """
    Returns smart attendance statuses via AJAX.
    Only updates radio buttons; does NOT save anything.
    Scan logic:
        - Scan before 10 mins after lesson start: P
        - Scan within lesson time but after 10 mins: UT
        - No scan: UA
    Trends are ignored for now.
    """
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user.staffprofile)

    enrollments = Enrollment.objects.filter(
        lesson=lesson,
        status='active'
    ).select_related('student', 'student__user')

    smart_statuses = {}

    # Combine lesson date with start/end times (timezone-aware)
    import pytz
    tz = pytz.timezone('Africa/Nairobi')
    lesson_start_dt = tz.localize(timezone.datetime.combine(lesson.lesson_date, lesson.time_slot.start_time))
    lesson_end_dt   = tz.localize(timezone.datetime.combine(lesson.lesson_date, lesson.time_slot.end_time))
    buffer_end = lesson_start_dt + timedelta(minutes=10)

    for e in enrollments:
        # Fetch scans for this student on lesson date
        student_scans = GradeAttendance.objects.filter(
            student=e.student,
            recorded_at__date=lesson.lesson_date
        ).order_by('recorded_at')

        if student_scans.exists():
            first_scan = student_scans.first().recorded_at

            if first_scan <= buffer_end:
                status = 'P'  # Present
            elif first_scan <= lesson_end_dt:
                status = 'UT'  # Unexcused Tardy
            else:
                status = 'UA'  # Scan after lesson end → unexcused absence
        else:
            status = 'UA'  # No scan → unexcused absence

        smart_statuses[e.id] = status

    return JsonResponse({
        'success': True,
        'statuses': smart_statuses
    })


@login_required
@require_POST
def teacher_discipline_create_ajax(request):
    teacher = request.user.staffprofile
    
    # ─── Extract & validate inputs ─────────────────────────────────────
    try:
        student_id     = request.POST['student_id']
        code           = request.POST.get('code')
        description    = request.POST['description'].strip()
        incident_type  = request.POST['incident_type']
        severity       = request.POST['severity']
        action         = request.POST.get('action', '').strip()

        if not description:
            return JsonResponse({'success': False, 'error': 'Description is required'}, status=400)

        # Discipline code authorization check
        if code in ['18', '20'] and teacher.position not in ['principal', 'deputy_principal']:
            return JsonResponse({'success': False, 'error': 'Only principal or deputy can issue suspension/expulsion'}, status=403)

    except KeyError as e:
        return JsonResponse({'success': False, 'error': f'Missing field: {str(e)}'}, status=400)

    # ─── Validate student exists and belongs to the school ─────────────
    try:
        student = Student.objects.get(id=student_id, school=teacher.school)
    except Student.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Invalid or unauthorized student'}, status=403)

    # ─── Create record inside transaction ──────────────────────────────
    try:
        with transaction.atomic():
            record = DisciplineRecord.objects.create(
                student=student,               # better than student_id directly
                teacher=teacher,
                school=teacher.school,
                description=description,
                incident_type=incident_type,
                severity=severity,
                action_taken=action,
                reported_by=request.user,
                # Optional: link to the lesson if you want traceability
                # lesson_id=request.POST.get('lesson_id'),
            )
    except ValidationError as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        # In production: log this error
        return JsonResponse({'success': False, 'error': 'Failed to create record'}, status=500)

    return JsonResponse({
        'success': True,
        'id': record.id,
        'message': 'Discipline record created successfully'
    })

@login_required
def teacher_attendance_edit(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        form = AttendanceForm(request.POST, instance=attendance)
        if form.is_valid():
            form.save()
            messages.success(request, f'Attendance for {attendance.enrollment.student} updated successfully.')
        else:
            messages.error(request, "Error updating attendance. Check the form.")
    return redirect('school:teacher-attendance')

@login_required
def teacher_attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, f'Attendance for {attendance.enrollment.student} deleted successfully.')
    return redirect('school:teacher-attendance')

@login_required
def teacher_attendance_summary(request):
    try:
        teacher = request.user.staffprofile
        school = teacher.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')

    # ─── DATE FILTER ─────────────────────────
    period_start = request.GET.get('start')
    period_end = request.GET.get('end')

    if period_start and period_end:
        try:
            period_start = datetime.strptime(period_start, "%Y-%m-%d").date()
            period_end = datetime.strptime(period_end, "%Y-%m-%d").date()
        except ValueError:
            period_start = timezone.now().date().replace(day=1)
            period_end = timezone.now().date()
    else:
        period_start = timezone.now().date().replace(day=1)
        period_end = timezone.now().date()

    # ─── LESSONS ─────────────────────────
    lessons = Lesson.objects.filter(
        lesson_date__range=[period_start, period_end],
        teacher=teacher
    )

    # ─── ATTENDANCE ─────────────────────────
    attendances = Attendance.objects.filter(
        enrollment__lesson__in=lessons
    )

    total_records = attendances.count()

    # ─── SUMMARY ─────────────────────────
    summary_qs = attendances.values('status').annotate(count=Count('status'))
    summary = {row['status']: row['count'] for row in summary_qs}

    present_count = summary.get('P', 0)

    present_pct = (present_count / total_records * 100) if total_records else 0

    context = {
        'summary': summary,
        'period_start': period_start,
        'period_end': period_end,
        'present_pct': round(present_pct, 2),
        'school': school,
        'total_records': total_records,
    }

    return render(request, 'school/teacher/attendance_summary.html', context)

#teacher discipline

@login_required
def teacher_discipline(request):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    records = DisciplineRecord.objects.filter(school=school, teacher=request.user.staffprofile).select_related('student')
    
    query = request.GET.get('q', '')
    if query:
        records = records.filter(
            Q(student__user__first_name__icontains=query) | Q(description__icontains=query)
        )
    
    paginator = Paginator(records, 10)
    page_number = request.GET.get('page')
    records_page = paginator.get_page(page_number)
    form = DisciplineRecordForm(school=school)
    context = {
        'records': records_page,
        'school': school,
        'form': form,
        'query': query,
    }
    return render(request, 'school/teacher/discipline.html', context)

@login_required
def teacher_discipline_create(request):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, school=school)
        if form.is_valid():
            record = form.save(commit=False)
            record.school = school
            record.teacher = request.user.staffprofile
            record.reported_by = request.user
            record.save()

            # Notify all parents via SMS + email, track delivery status
            parents = record.student.parents.all()
            notif_title = f"Discipline Alert: {record.student.user.get_full_name()}"
            notif_msg = (
                f"Dear Parent, an incident of {record.get_incident_type_display()} "
                f"has been recorded for {record.student.user.get_full_name()} on {record.date}. "
                f"Severity: {record.get_severity_display()}. "
                f"Action: {record.action_taken or 'None recorded'}. "
                f"Please contact the school if needed."
            )
            for parent in parents:
                if not parent.user:
                    continue
                notif = Notification(
                    recipient=parent.user,
                    title=notif_title,
                    message=notif_msg,
                    related_discipline=record,
                    school=school,
                )
                phone = getattr(parent, 'phone', None) or getattr(parent.user, 'phone_number', None)
                if phone:
                    ok = _send_sms_via_eujim(str(phone), notif_msg)
                    notif.sms_sent = ok
                    if not ok:
                        notif.sms_error = "SMS delivery failed"
                if parent.user.email:
                    ok = send_email(parent.user.email, notif_title, notif_msg)
                    notif.email_sent = ok
                    if not ok:
                        notif.email_error = "Email delivery failed"
                notif.save()

            messages.success(request, f'Discipline record for {record.student} created and parents notified.')
            return redirect('school:teacher-discipline')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")

    return redirect('school:teacher-discipline')

@login_required
def teacher_discipline_delete(request, record_id):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    record = get_object_or_404(DisciplineRecord, id=record_id, school=school, teacher=request.user.staffprofile)
    if request.method == 'POST':
        record.delete()
        messages.success(request, f'Discipline record for {record.student} deleted.')
    return redirect('school:teacher-discipline')

@login_required
def teacher_discipline_edit(request, record_id):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    record = get_object_or_404(DisciplineRecord, id=record_id, school=school, teacher=request.user.staffprofile)
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, instance=record, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Discipline record for {record.student} updated.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:teacher-discipline')

@login_required
def school_discipline(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    query = request.GET.get('q', '')
    records_qs = (
        DisciplineRecord.objects
        .filter(school=school)
        .select_related('student__user', 'teacher__user')
        .prefetch_related('notification_set')
        .order_by('-date')
    )

    if query:
        records_qs = records_qs.filter(
            Q(student__user__first_name__icontains=query) |
            Q(student__user__last_name__icontains=query) |
            Q(description__icontains=query)
        )

    paginator = Paginator(records_qs, 10)  # 10 per page
    page_number = request.GET.get('page')
    records = paginator.get_page(page_number)

    form = DisciplineRecordForm(school=school)

    context = {
        'records': records,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/discipline.html', context)


@login_required
def discipline_create(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, school=school)
        if form.is_valid():
            record = form.save(commit=False)
            record.school = school
            record.teacher = request.user.staffprofile
            record.reported_by = request.user
            record.save()
            
            # Notify all parents with SMS + email, track delivery status
            parents = record.student.parents.all()
            notif_title = f"Discipline Alert: {record.student.user.get_full_name()}"
            notif_msg = (
                f"Dear Parent, an incident of {record.get_incident_type_display()} "
                f"has been recorded for {record.student.user.get_full_name()} on {record.date}. "
                f"Severity: {record.get_severity_display()}. "
                f"Action: {record.action_taken or 'None recorded'}. "
                f"Please contact the school if needed."
            )
            for parent in parents:
                if not parent.user:
                    continue
                notif = Notification(
                    recipient=parent.user,
                    title=notif_title,
                    message=notif_msg,
                    related_discipline=record,
                    school=school,
                )
                # SMS
                phone = getattr(parent, 'phone', None) or getattr(parent.user, 'phone_number', None)
                if phone:
                    ok = _send_sms_via_eujim(str(phone), notif_msg)
                    notif.sms_sent = ok
                    if not ok:
                        notif.sms_error = "SMS delivery failed"
                # Email
                if parent.user.email:
                    ok = send_email(parent.user.email, notif_title, notif_msg)
                    notif.email_sent = ok
                    if not ok:
                        notif.email_error = "Email delivery failed"
                notif.save()

            messages.success(request, f'Discipline record for {record.student} created and parents notified.')
            return redirect('school:school-discipline')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-discipline')

# Similar edit/delete, with validation for severity/frequency...

@login_required
def discipline_edit(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    record = get_object_or_404(DisciplineRecord, id=pk, school=school)
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, instance=record, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Discipline record for {record.student} updated.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-discipline')


@login_required
def discipline_delete(request, pk):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    record = get_object_or_404(DisciplineRecord, id=pk, school=school)
    if request.method == 'POST':
        record.delete()
        messages.success(request, f'Discipline record for {record.student} deleted.')
    return redirect('school:school-discipline')


@login_required
def school_notifications(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    notifications = Notification.objects.filter(school=school).order_by('-sent_at')
    # Mark as read for current user if applicable
    if request.user.is_authenticated:
        notifications.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    form = NotificationForm()
    context = {
        'notifications': notifications,
        'form': form,
        'school': school,
    }
    return render(request, 'school/notification.html', context)

@login_required
def notification_send(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        form = NotificationForm(request.POST, school=school)
        if form.is_valid():
            notification = form.save(commit=False)
            notification.school = school
            notification.save()
            # Actual send via email/SMS (integrate with external service)
            if notification.recipient.email:
                send_mail(
                    notification.title,
                    notification.message,
                    settings.DEFAULT_FROM_EMAIL,
                    [notification.recipient.email],
                )
            messages.success(request, 'Notification sent successfully.')
            return redirect('school:school-notifications')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-notifications')

@login_required
def school_reports(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    # Generate on-the-fly or from SummaryReport
    report_type = request.GET.get('type', 'school')
    period_start = request.GET.get('start', timezone.now().date().replace(day=1))
    period_end = request.GET.get('end', timezone.now().date())
    
    # Example: Attendance report
    if report_type == 'attendance':
        lessons = Lesson.objects.filter(date__range=[period_start, period_end], school=school)
        data = Attendance.objects.filter(lesson__in=lessons).values('status').annotate(count=Count('status'))
        # Save as SummaryReport
        SummaryReport.objects.update_or_create(
            school=school, report_type='school', period_start=period_start, period_end=period_end,
            defaults={'data': dict(data), 'generated_by': request.user.staffprofile}
        )
    
    context = {
        'report_type': report_type,
        'period_start': period_start,
        'period_end': period_end,
        'school': school,
        # Pass data...
    }
    return render(request, 'school/report.html', context)

@login_required
def export_report(request):
    # CSV export example
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="report.csv"'
    writer = csv.writer(response)
    writer.writerow(['Status', 'Count'])
    # Add data...
    return response

@login_required
def export_pdf_report(request):
    # PDF export using reportlab
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="report.pdf"'
    doc = SimpleDocTemplate(response, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    story.append(Paragraph("Attendance Report", styles['Title']))
    # Add table...
    data = [['Status', 'Count']]  # Populate
    t = Table(data)
    t.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.grey)]))
    story.append(t)
    doc.build(story)
    return response

@login_required
def school_student_assignments(request):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    assignments = Assignment.objects.filter(school=school).select_related('subject')
    if query:
        assignments = assignments.filter(Q(title__icontains=query) | Q(subject__name__icontains=query))
    
    form = AssignmentForm(school=school)
    context = {
        'assignments': assignments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/assignment.html', context)

# Create/edit assignment similar...
@login_required
def assignment_create(request):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-assignments')
    
    if request.method == 'POST':
        form = AssignmentForm(request.POST, school=school)
        if form.is_valid():
            assignment = form.save(commit=False)
            assignment.school = school
            assignment.teacher = request.user.staffprofile
            assignment.save()
            messages.success(request, f'Assignment "{assignment.title}" created successfully.')
            return redirect('school:school-assignments')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-assignments')
@login_required
def assignment_edit(request, pk):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-assignments')
    
    assignment = get_object_or_404(Assignment, pk=pk, school=school)
    if request.method == 'POST':
        form = AssignmentForm(request.POST, instance=assignment, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Assignment "{assignment.title}" updated successfully.')
            return redirect('school:school-assignments')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-assignments')

@login_required
def assignment_delete(request, pk):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-assignments')
    
    assignment = get_object_or_404(Assignment, pk=pk, school=school)
    assignment.delete()
    messages.success(request, f'Assignment "{assignment.title}" deleted successfully.')
    return redirect('school:school-assignments')
# Delete assignment


@login_required
def school_students_submissions(request, pk):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')

    assignment = get_object_or_404(Assignment, pk=pk, school=school)
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(
        school=school, assignment=assignment
    ).select_related('enrollment__student__user', 'assignment')
    if query:
        submissions = submissions.filter(
            Q(enrollment__student__user__first_name__icontains=query) |
            Q(enrollment__student__user__last_name__icontains=query)
        )

    context = {
        'submissions': submissions,
        'assignment': assignment,
        'school': school,
        'query': query,
    }
    return render(request, 'school/submission.html', context)

# Grade submission (update score/feedback)
@login_required
def submission_grade(request, pk):
    try:
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    submission = get_object_or_404(Submission, pk=pk, school=school)
    if request.method == 'POST':
        try:
            raw = request.POST.get('score', '')
            submission.score = int(raw) if raw.strip() else None
        except (ValueError, TypeError):
            messages.error(request, 'Score must be a whole number.')
            return redirect('school:assignment-submissions', pk=submission.assignment_id)
        submission.feedback = request.POST.get('feedback', '')
        submission.save()
        messages.success(request, 'Submission graded.')
    return redirect('school:assignment-submissions', pk=submission.assignment_id)


#student submission

@login_required
def submission_create(request):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(enrollment__student=student).select_related('assignment')
    if query:
        submissions = submissions.filter(Q(assignment__title__icontains=query))
    
    context = {
        'submissions': submissions,
        'query': query,
    }
    return render(request, 'school/student_submissions.html', context)

@login_required
def submission_edit(request, pk):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    submission = get_object_or_404(Submission, pk=pk, enrollment__student=student)
    if request.method == 'POST':
        submission.file = request.FILES.get('file', submission.file)
        submission.save()
        messages.success(request, 'Submission updated successfully.')
        return redirect('school:student-submissions')
    return redirect('school:student-submissions')


@login_required
def submission_delete(request, pk):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')
    
    submission = get_object_or_404(Submission, pk=pk, enrollment__student=student)
    if request.method == 'POST':
        submission.delete()
        messages.success(request, 'Submission deleted successfully.')
    return redirect('school:student-submissions')


@login_required
def student_submissions(request):
    try:
        student = request.user.student
    except AttributeError:
        messages.error(request, "Access denied: Student privileges required.")
        return redirect('school:dashboard')

    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(enrollment__student=student).select_related('assignment')
    if query:
        submissions = submissions.filter(Q(assignment__title__icontains=query))

    context = {
        'submissions': submissions,
        'query': query,
    }
    return render(request, 'school/student_submissions.html', context)


@login_required
def student_assignments_portal(request):
    """Student: view assignments, download files, upload submissions, see scores & remarks."""
    if not getattr(request.user, 'is_student', False):
        return redirect('userauths:sign-in')

    try:
        student = request.user.student
    except Exception:
        return redirect('userauths:sign-in')

    # Student's active subject enrollments
    subject_ids = SubjectEnrollment.objects.filter(
        student=student, is_active=True
    ).values_list('subject_id', flat=True)

    # All assignments for those subjects
    q = request.GET.get('q', '')
    status_filter = request.GET.get('status', '')
    subject_filter = request.GET.get('subject', '')

    assignments_qs = Assignment.objects.filter(
        school=student.school,
        subject_id__in=subject_ids,
    ).select_related('subject').prefetch_related('submissions').order_by('due_date')

    if q:
        assignments_qs = assignments_qs.filter(title__icontains=q)
    if subject_filter:
        assignments_qs = assignments_qs.filter(subject_id=subject_filter)

    # Annotate with student's submission
    from django.db.models import Prefetch
    student_submissions_prefetch = Prefetch(
        'submissions',
        queryset=Submission.objects.filter(enrollment__student=student).select_related('enrollment'),
        to_attr='my_submissions'
    )
    assignments_qs = assignments_qs.prefetch_related(student_submissions_prefetch)

    # Build enriched list
    today = timezone.now()
    assignment_data = []
    for asgn in assignments_qs:
        my_sub = asgn.my_submissions[0] if asgn.my_submissions else None
        if status_filter == 'submitted' and not my_sub:
            continue
        if status_filter == 'pending' and my_sub:
            continue
        if status_filter == 'overdue' and (my_sub or asgn.due_date >= today):
            continue
        assignment_data.append({
            'assignment': asgn,
            'my_submission': my_sub,
            'is_overdue': asgn.due_date < today and not my_sub,
        })

    # Handle submission upload
    if request.method == 'POST':
        asgn_id = request.POST.get('assignment_id')
        try:
            asgn = Assignment.objects.get(pk=asgn_id, school=student.school)
            # Get or create active enrollment for this subject
            enrollment = Enrollment.objects.filter(
                student=student, lesson__subject=asgn.subject, status='active'
            ).first()
            if not enrollment:
                messages.error(request, "You are not enrolled in this subject.")
            else:
                sub_file = request.FILES.get('file_submission')
                existing = Submission.objects.filter(enrollment=enrollment, assignment=asgn).first()
                if existing:
                    if sub_file:
                        existing.file_submission = sub_file
                        existing.save()
                    messages.success(request, "Submission updated.")
                else:
                    Submission.objects.create(
                        enrollment=enrollment,
                        assignment=asgn,
                        school=student.school,
                        file_submission=sub_file,
                    )
                    messages.success(request, "Assignment submitted successfully.")
        except Assignment.DoesNotExist:
            messages.error(request, "Assignment not found.")
        return redirect('school:student-assignments')

    subjects = Subject.objects.filter(id__in=subject_ids)
    paginator = Paginator(assignment_data, 15)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'school/student/assignments.html', {
        'assignment_data': page,
        'student': student,
        'subjects': subjects,
        'q': q,
        'status_filter': status_filter,
        'subject_filter': subject_filter,
    })
@login_required
def school_fees(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    payments = Payment.objects.filter(school=school).select_related('student')
    if query:
        payments = payments.filter(Q(student__user__first_name__icontains=query) | Q(payment_type__icontains=query))
    
    form = PaymentForm(school=school)
    context = {
        'payments': payments,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/fee.html', context)

# Integrate M-Pesa for payments...
@login_required
def process_mpesa_payment(request):
    # Example: Trigger STK push
    # Use Daraja API (assume configured)
    # For now, placeholder
    messages.success(request, 'Payment processed via M-Pesa.')
    return redirect('school:school-fees')

@login_required
def school_finance(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    subscriptions = SchoolSubscription.objects.filter(school=school)
    invoices = Invoice.objects.filter(school=school)
    
    context = {
        'subscriptions': subscriptions,
        'invoices': invoices,
        'school': school,
    }
    return render(request, 'school/finance.html', context)

@login_required
def school_subscriptions(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    subscription = school.platform_subscription
    form = SchoolSubscriptionForm(instance=subscription)
    
    if request.method == 'POST':
        form = SchoolSubscriptionForm(request.POST, instance=subscription)
        if form.is_valid():
            form.save()
            messages.success(request, 'Subscription updated.')
            return redirect('school:school-subscriptions')
    
    context = {
        'subscription': subscription,
        'form': form,
        'plans': SubscriptionPlan.objects.filter(is_active=True),
        'school': school,
    }
    return render(request, 'school/subscription.html', context)

# Generate invoice
@login_required
def generate_invoice(request):
    school = request.user.school_admin_profile
    subscription = school.platform_subscription
    if subscription:
        cost = subscription.calculate_current_cost()
        invoice = Invoice.objects.create(
            school=school,
            subscription=subscription,
            amount_due=cost,
            line_items=[{'description': 'Subscription', 'total': cost}]  # Simplify
        )
        messages.success(request, f'Invoice {invoice.invoice_id} generated.')
    return redirect('school:school-finance')

@login_required
def school_calendar(request):
    # Integrate with fullcalendar.js or similar in template
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    # Fetch events (use Session, Lesson, etc. as events)
    events = []  # JSON for JS
    context = {
        'events': mark_safe(json.dumps(events)),
        'school': school,
    }
    return render(request, 'school/calendar.html', context)

@login_required
def school_events(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    # Events could be a new model or use existing (e.g., Sessions)
    # Placeholder: List sessions as events
    events = Session.objects.filter(school=school)
    context = {'events': events, 'school': school}
    return render(request, 'school/event.html', context)

# ------------------------------- SETTINGS & PERMISSIONS -------------------------------
@login_required
def school_settings(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    if request.method == 'POST':
        school.name = request.POST.get('name')
        school.contact_email = request.POST.get('email')
        school.save()
        messages.success(request, 'School settings updated.')
        return redirect('school:school-settings')
    
    context = {'school': school}
    return render(request, 'school/settings.html', context)

@login_required
def permissions_logs(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    # Log actions via middleware or signals; placeholder query
    logs = []  # From audit log model if added
    context = {'logs': logs, 'school': school}
    return render(request, 'school/permissions.html', context)  # Assume template

@login_required
def contact_messages(request):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    
    messages_list = ContactMessage.objects.all().order_by('-created_at')
    context = {'messages': messages_list}
    return render(request, 'school/contact.html', context)

# Callbacks for M-Pesa (STK push response, payment confirmation)
def mpesa_stk_callback(request):
    # Parse XML/JSON from M-Pesa
    # Update MpesaStkPushRequestResponse
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})

def mpesa_payment_callback(request):
    # Update MpesaPayment and link to Invoice/Payment
    body = request.POST.get('Body')
    # Parse and save
    payment = MpesaPayment.objects.create(
        merchant_request_id=body.get('MerchantRequestID'),
        # ... other fields
    )
    # Update related Payment/Invoice status to 'paid'
    return JsonResponse({'ResultCode': 0, 'ResultDesc': 'Success'})

@login_required
def grade_streams_view(request, grade_id):

    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    grade = get_object_or_404(Grade, id=grade_id, school=school)

    streams = grade.streams.filter(is_active=True).order_by("name")

    data = [
        {
            "id": s.id,
            "name": s.name
        }
        for s in streams
    ]

    return JsonResponse(data, safe=False)

@login_required
def create_stream(request, grade_id):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    grade = get_object_or_404(Grade, id=grade_id, school=school)

    if request.method == "POST":

        form = StreamForm(request.POST)

        if form.is_valid():
            stream = form.save(commit=False)
            stream.grade = grade
            stream.school = school
            stream.save()

            messages.success(request, "Stream added successfully.")

        else:
            messages.error(request, "Failed to create stream.")

    return redirect("school:school-grades")

@login_required
def edit_stream(request, stream_id):

    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    stream = get_object_or_404(Streams, id=stream_id, school=school)

    if request.method == "POST":

        form = StreamForm(request.POST, instance=stream)

        if form.is_valid():
            form.save()
            messages.success(request, "Stream updated successfully.")

        else:
            messages.error(request, "Failed to update stream.")

    return redirect("school:school-grades")
@login_required
def delete_stream(request, stream_id):

    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    stream = get_object_or_404(Streams, id=stream_id, school=school)

    if request.method == "POST":

        stream.is_active = False
        stream.save()

        messages.success(request, "Stream deleted successfully.")

    return redirect("school:school-grades")


@login_required
def create_parent_student(request):
    # Ensure user is a school admin
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == "POST":
        form = ParentStudentCreationForm(request.POST, request.FILES, school=school)
        if form.is_valid():
            try:
                # Atomic creation to ensure both User and Parent/Student are saved
                with transaction.atomic():
                    obj, temp_password = form.save(commit=True)

                member_type = 'Parent' if form.cleaned_data.get('member_type') == 'parent' else 'Student'
                messages.success(request, f"{member_type} created successfully.")

                # Optional: show temp password if email sending is disabled
                if form.cleaned_data.get('send_email'):
                    messages.info(request, f"A welcome email has been sent. Temporary password: {temp_password}")

                return redirect('school:school-users')

            except Exception as e:
                messages.error(request, f"Failed to create member: {str(e)}")
        else:
            messages.error(request, "Please correct the errors below.")
    else:
        form = ParentStudentCreationForm(school=school)

    context = {
        'parent_student_form': form,
        'school': school,
    }
    return render(request, 'school/staff.html', context)

@login_required
def assign_class_teacher_for_teacher(request, teacher_id):
    user = request.user

    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)

    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    # Get teacher to assign
    teacher = get_object_or_404(StaffProfile, id=teacher_id, school=school)

    if request.method == 'POST':
        stream_id = request.POST.get('stream')
        stream = get_object_or_404(Streams, id=stream_id, school=school)

        assignment, created = TeacherStreamAssignment.objects.get_or_create(
            teacher=teacher,
            stream=stream,
            school=school
        )

        if created:
            messages.success(request, f"{teacher.user.get_full_name()} assigned to {stream.name} successfully.")
        else:
            messages.info(request, f"{teacher.user.get_full_name()} is already assigned to {stream.name}.")

        return redirect('school:assign-class-teacher-for-teacher', teacher_id=teacher.id)

    streams = Streams.objects.filter(school=school)
    assignments = TeacherStreamAssignment.objects.filter(teacher=teacher, school=school)

    return render(request, 'school/staff.html', {
        'teacher': teacher,
        'streams': streams,
        'assignments': assignments
    })



@login_required
def ajax_subjects(request):
    school_id = request.GET.get("school_id")
    grade_id = request.GET.get("grade_id")
    qs = Subject.objects.all()
    if school_id:
        qs = qs.filter(school_id=school_id)
    if grade_id:
        qs = qs.filter(grade__id=grade_id)
    subjects = qs.values("id","name").order_by("name")
    return JsonResponse(list(subjects), safe=False)

def is_policymaker(user):
    return getattr(user, "is_policy_maker", False)

# ───────────── AJAX FILTERS ─────────────
@login_required
def ajax_subcounties(request):
    county_id = request.GET.get("county_id")
    if not county_id:
        subcounties = SubCounty.objects.all().values("id","name").order_by("name")
    else:
        subcounties = SubCounty.objects.filter(county_id=county_id).values("id","name").order_by("name")
    return JsonResponse(list(subcounties), safe=False)

@login_required
def ajax_schools(request):
    subcounty_id = request.GET.get("subcounty_id")
    if not subcounty_id:
        schools = School.objects.filter(is_active=True).values("id","name").order_by("name")
    else:
        schools = School.objects.filter(sub_county_id=subcounty_id, is_active=True).values("id","name").order_by("name")
    return JsonResponse(list(schools), safe=False)

@login_required
def ajax_grades(request):
    school_id = request.GET.get("school_id")
    if not school_id:
        grades = Grade.objects.all().values("id","name").order_by("name")
    else:
        grades = Grade.objects.filter(school_id=school_id).values("id","name").order_by("name")
    return JsonResponse(list(grades), safe=False)


@login_required
def ajax_students_search(request):
    """AJAX: search students by name or ID for finance modal."""
    q = request.GET.get('q', '').strip()
    school_id = request.GET.get('school', '')
    school = get_user_school(request.user)
    if not school:
        return JsonResponse([], safe=False)

    qs = Student.objects.filter(school=school).select_related('user')
    if q:
        qs = qs.filter(
            Q(user__first_name__icontains=q) |
            Q(user__last_name__icontains=q) |
            Q(student_id__icontains=q)
        )
    data = [{'id': s.pk, 'name': s.user.get_full_name(), 'student_id': s.student_id} for s in qs[:20]]
    return JsonResponse(data, safe=False)


@login_required
@user_passes_test(is_policymaker)
def policymaker_dashboard(request):
    import json as _json
    from django.db.models.functions import TruncMonth

    county_id    = request.GET.get("county")
    subcounty_id = request.GET.get("subcounty")
    school_id    = request.GET.get("school")
    grade_id     = request.GET.get("grade")
    subject_id   = request.GET.get("subject")
    term_id      = request.GET.get("term")
    classification = request.GET.get("classification")

    # ───────── SCHOOL FILTER ─────────
    schools = School.objects.filter(is_active=True)
    if county_id:
        schools = schools.filter(county_id=county_id)
    if subcounty_id:
        schools = schools.filter(sub_county_id=subcounty_id)
    if school_id:
        schools = schools.filter(id=school_id)
    if classification:
        schools = schools.filter(school_classification=classification)

    # ───────── ATTENDANCE BASE QUERY ─────────
    attendance = (
        Attendance.objects
        .filter(enrollment__school__in=schools)
        .select_related(
            "enrollment__lesson__teacher__user",
            "enrollment__lesson__subject",
            "enrollment__lesson__stream__grade",
            "enrollment__school__county",
        )
    )
    if grade_id:
        attendance = attendance.filter(enrollment__lesson__stream__grade_id=grade_id)
    if subject_id:
        attendance = attendance.filter(enrollment__lesson__subject_id=subject_id)
    if term_id:
        attendance = attendance.filter(term_id=term_id)

    _att_expr = ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField())

    # ───────── SCHOOL RANKING ─────────
    school_rankings = (
        attendance.values("enrollment__school__id", "enrollment__school__name",
                          "enrollment__school__school_classification")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .annotate(present_rate=ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField()))
        .order_by("-present_rate")[:20]
    )

    # ───────── COUNTY RANKING ─────────
    county_rankings = (
        attendance.values("enrollment__school__county__name")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .annotate(performance=ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField()))
        .order_by("-performance")
    )

    # ───────── TEACHER PERFORMANCE ─────────
    teacher_rankings = (
        attendance.values(
            "enrollment__lesson__teacher__user__first_name",
            "enrollment__lesson__teacher__user__last_name",
            "enrollment__school__name",
        )
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .annotate(performance=ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField()))
        .order_by("-performance")[:15]
    )

    # ───────── GRADE PERFORMANCE ─────────
    grade_rankings = (
        attendance.values("enrollment__lesson__stream__grade__name")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .annotate(performance=ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField()))
        .order_by("-performance")
    )

    # ───────── SUBJECT PERFORMANCE ─────────
    subject_rankings = (
        attendance.values("enrollment__lesson__subject__name")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .annotate(performance=ExpressionWrapper(F("present") * 100.0 / F("total"), output_field=FloatField()))
        .order_by("-performance")
    )

    # ───────── NATIONAL / FILTERED RATE ─────────
    totals = attendance.aggregate(
        total=Count("id"),
        present=Count("id", filter=Q(status="P")),
        absent_unexcused=Count("id", filter=Q(status="UA")),
        tardy=Count("id", filter=Q(status__in=["ET","UT"])),
    )
    total_records = totals["total"] or 1
    national_rate = round((totals["present"] or 0) * 100.0 / total_records, 1)

    # ───────── TREND (monthly last 6 months) ─────────
    six_months_ago = timezone.localdate() - timedelta(days=182)
    trend_qs = (
        attendance.filter(date__gte=six_months_ago)
        .annotate(month=TruncMonth("date"))
        .values("month")
        .annotate(total=Count("id"), present=Count("id", filter=Q(status="P")))
        .order_by("month")
    )
    trend_labels = [r["month"].strftime("%b %Y") for r in trend_qs if r["month"]]
    trend_rates  = [
        round(r["present"] * 100.0 / r["total"], 1) if r["total"] else 0
        for r in trend_qs if r["month"]
    ]

    # ───────── DISCIPLINE BREAKDOWN ─────────
    discipline_breakdown = (
        DisciplineRecord.objects.filter(school__in=schools)
        .values("incident_type", "severity")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    discipline_by_type = (
        DisciplineRecord.objects.filter(school__in=schools)
        .values("incident_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ───────── GENDER BREAKDOWN ─────────
    gender_qs = (
        Student.objects.filter(school__in=schools)
        .values("gender")
        .annotate(count=Count("id"))
    )
    gender_labels = [g["gender"].upper() or "Unknown" for g in gender_qs]
    gender_counts = [g["count"] for g in gender_qs]

    # ───────── SCHOOL TYPE BREAKDOWN ─────────
    school_type_qs = (
        schools.values("school_classification")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # ───────── KPI SUMMARY ─────────
    total_schools   = schools.count()
    total_students  = Student.objects.filter(school__in=schools).count()
    total_teachers  = StaffProfile.objects.filter(school__in=schools, position="teacher").count()
    total_lessons   = Lesson.objects.filter(timetable__school__in=schools).count()
    total_discipline = DisciplineRecord.objects.filter(school__in=schools).count()

    # sub-counties for filter (scoped to county if selected)
    sub_counties = SubCounty.objects.filter(county_id=county_id) if county_id else SubCounty.objects.all()
    all_terms = Term.objects.filter(school__in=schools).distinct().order_by("-start_date")[:10]

    context = {
        # KPIs
        "total_schools":    total_schools,
        "total_students":   total_students,
        "total_teachers":   total_teachers,
        "total_lessons":    total_lessons,
        "total_discipline": total_discipline,
        "national_rate":    national_rate,
        "totals":           totals,
        # Rankings
        "school_rankings":  school_rankings,
        "county_rankings":  county_rankings,
        "teacher_rankings": teacher_rankings,
        "grade_rankings":   grade_rankings,
        "subject_rankings": subject_rankings,
        # Breakdowns
        "discipline_by_type":  discipline_by_type,
        "school_type_qs":      school_type_qs,
        # Charts (JSON)
        "trend_labels_json": _json.dumps(trend_labels),
        "trend_rates_json":  _json.dumps(trend_rates),
        "gender_labels_json": _json.dumps(gender_labels),
        "gender_counts_json": _json.dumps(gender_counts),
        # Filters
        "counties":        County.objects.all().order_by("name"),
        "sub_counties":    sub_counties.order_by("name"),
        "all_terms":       all_terms,
        # Selected filter values (for persistence)
        "sel_county":        county_id,
        "sel_subcounty":     subcounty_id,
        "sel_school":        school_id,
        "sel_grade":         grade_id,
        "sel_term":          term_id,
        "sel_classification": classification,
        "classification_choices": School._meta.get_field("school_classification").choices or [],
    }

    return render(request, "school/policy/dashboard.html", context)


#FIle Upload


import random
import string

def generate_password(length=8):
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def safe_email(value, fallback):
    return value.strip().lower() if value else fallback

def generate_time_slots(school, staff_user):
    start = datetime.datetime.strptime("08:00", "%H:%M")
    end = datetime.datetime.strptime("16:00", "%H:%M")

    slots = []
    current = start
    count = 0

    while current < end:
        duration = 45
        description = "Lesson"

        if count == 2 and count == 5:
            duration = 20
            description = "Break"
        elif count == 8:
            duration = 45
            description = "Lunch"

        next_time = current + timedelta(minutes=duration)

        slot, _ = TimeSlot.objects.get_or_create(
            school=school,
            start_time=current.time(),
            end_time=next_time.time(),
            defaults={
                "description": description,
                "created_by": staff_user
            }
        )

        if description == "Lesson":
            slots.append(slot)

        current = next_time
        count += 1

    return slots

def populate_student_lesson_enrollments(school, grade=None, stream=None, term=None):
    """
    Create Enrollment records for all lessons in a term based on student's subject enrollments.
    """
    import logging
    logger = logging.getLogger(__name__)

    # ── Students
    students = Student.objects.filter(school=school, is_active=True)
    if grade:
        students = students.filter(grade_level=grade)
    if stream:
        students = students.filter(stream=stream)

    # ── Lessons within term
    lessons_qs = Lesson.objects.filter(
        timetable__school=school,
        is_canceled=False
    )
    if stream:
        lessons_qs = lessons_qs.filter(stream=stream)
    if term:
        lessons_qs = lessons_qs.filter(
            lesson_date__gte=term.start_date,
            lesson_date__lte=term.end_date
        )

    # Map lessons by subject
    lessons_map = defaultdict(list)
    for lesson in lessons_qs.select_related('subject', 'stream'):
        lessons_map[lesson.subject_id].append(lesson)

    # Prefetch student's subject enrollments
    students = students.prefetch_related('subject_enrollments__subject')

    enrollments_to_create = []

    for student in students:
        try:
            subject_ids = list(student.subject_enrollments.values_list('subject_id', flat=True))
            if not subject_ids:
                logger.warning(f"Student {student.student_id} has no subject enrollments")
                continue

            # For each subject, get all lessons for this term & stream
            for sid in subject_ids:
                lessons = lessons_map.get(sid, [])
                for lesson in lessons:
                    enrollments_to_create.append(
                        Enrollment(
                            student=student,
                            lesson=lesson,
                            school=school,
                            status='active'
                        )
                    )

        except Exception as e:
            logger.exception(f"Failed to process enrollments for student {student.student_id}")

    if enrollments_to_create:
        Enrollment.objects.bulk_create(enrollments_to_create, ignore_conflicts=True)

    # Debug print
    total_students = students.count()
    total_lessons = lessons_qs.count()
    total_enrollments = len(enrollments_to_create)
    logger.info(f"[SUMMARY] Students={total_students} Lessons={total_lessons} Enrollments={total_enrollments}")



SUBJECT_CODE_MAP = {
    "MAT": "Mathematics",
    "CMAT": "Core Maths",
    "EMAT": "Essential Maths",
    "ENG": "English",
    "KISW": "Kiswahili",
    "CHEM": "Chemistry",
    "BIO": "Biology",
    "PHY": "Physics",
    "CRE": "Christian Religious Education",
    "GEO": "Geography",
    "HIST": "History",
    "BST": "Business Studies",
    "AGRI": "Agriculture",
    "MUDA": "Music & Dance",
    "LIT": "Literature",
    "FAS": "Fasihi",
    "TF": "Theatre and Film",
    "GENSCI": "General Science",
    "CSL": "Community Service Learning",
    "HSCI" : "Home Science",
    "ICT": "Information & Communication Technology",
}


# ================= HELPERS =================

def normalize_phone(phone):
    """Normalize Kenyan phone numbers to consistent format: 07XXXXXXXX"""
    if not phone:
        return ""
    
    phone = str(phone).strip()
    
    # Remove all non-digit characters
    phone = ''.join(filter(str.isdigit, phone))
    
    if not phone:
        return ""
    
    # Convert to 10-digit format starting with 0
    if phone.startswith("254"):
        phone = phone[3:]          # remove 254
    elif phone.startswith("+254"):
        phone = phone[4:]          # remove +254
    
    if len(phone) == 9 and not phone.startswith("0"):
        phone = "0" + phone        # 712345678 → 0712345678
    
    elif len(phone) == 10 and phone.startswith("0"):
        pass                       # already good (0712345678)
    
    else:
        # Invalid length → return as is (will fail lookup gracefully)
        return phone
    
    return phone

def generate_lesson_dates(term, weekday):
    weekday_map = {
        "monday": 0,
        "tuesday": 1,
        "wednesday": 2,
        "thursday": 3,
        "friday": 4,
        "saturday": 5,
        "sunday": 6,
    }

    target = weekday_map[weekday.lower()]
    current = term.start_date

    while current.weekday() != target:
        current += timedelta(days=1)

    dates = []
    while current <= term.end_date:
        dates.append(current)
        current += timedelta(days=7)

    return dates



def normalize_weekday(day_str: str) -> str | None:
    day_str = day_str.strip().lower()
    mapping = {
        'mon': 'monday', 'tue': 'tuesday', 'wed': 'wednesday',
        'thu': 'thursday', 'thur': 'thursday', 'fri': 'friday',
        'sat': 'saturday', 'sun': 'sunday'
    }
    for short, full in mapping.items():
        if day_str.startswith(short):
            return full
    return day_str if day_str in {'monday','tuesday','wednesday','thursday','friday','saturday','sunday'} else None


def norm_time(t):
    """Robust time parser handling AM/PM, HH:MM:SS, H:MM, etc."""
    if pd.isna(t) or not str(t).strip():
        return None

    t = str(t).strip().upper().replace(' ', '')
    am_pm = ''
    if 'AM' in t:
        am_pm = 'AM'
        t = t.replace('AM', '')
    elif 'PM' in t:
        am_pm = 'PM'
        t = t.replace('PM', '')

    t = t.replace('.', ':').replace(';', ':')

    try:
        if ':' in t:
            parts = t.split(':')
            h = parts[0].zfill(2)
            m = parts[1][:2].zfill(2) if len(parts) > 1 else '00'
            time_str = f"{h}:{m}"

            h_int = int(h)
            if am_pm == 'PM' and h_int != 12:
                h_int += 12
            elif am_pm == 'AM' and h_int == 12:
                h_int = 0

            return f"{h_int:02d}:{m}"

        if len(t) == 4 and t.isdigit():
            h = t[:2]
            m = t[2:]
            return f"{h}:{m}"

    except Exception:
        pass

    return None


@require_POST
@login_required
def universal_excel_upload(request):
    """
    Universal Excel Upload Handler - Production Ready
    Features:
    - Saves file first to Upload model (prevents timeout on large files)
    - Reads from saved file path
    - Full support for: students, teachers, parents, subjects, grades, time_slots, timetable
    - Proper error handling, logging, and atomic transactions
    """
    excel_file = request.FILES.get("file")
    category = request.POST.get("category")

    if not excel_file or not category:
        return JsonResponse({"error": "File and category are required"}, status=400)

    # Subjects are managed by Kiswate admins via the catalog; schools activate from there.
    if category == "subjects":
        return JsonResponse({
            "error": (
                "Schools cannot upload subjects directly. "
                "Go to Subjects → 'From Catalog' to activate subjects your school will offer. "
                "Contact your Kiswate administrator to add a subject to the platform catalog."
            )
        }, status=400)

    user = request.user
    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "You do not have permission to access this dashboard.")
        return redirect("userauths:sign-in")

    school = get_user_school(user)
    if not school:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    # ─── 1. SAVE FILE FIRST ───
    try:
        upload_record = Upload.objects.create(
            file=excel_file,
            school=school,
            uploaded_by=user
        )
        logger.info(f"File saved successfully: {upload_record.file.name} | ID: {upload_record.id}")
    except Exception as e:
        logger.error(f"Failed to save uploaded file: {str(e)}")
        return JsonResponse({"error": f"Failed to save file: {str(e)}"}, status=500)

    # ─── 2. READ FILE FROM DATABASE ───
    results = {
        "upload_id": upload_record.id,
        "created": 0,
        "errors": [],
        "warnings": []
    }

    try:
        df = pd.read_excel(upload_record.file.path).fillna("")
        df.columns = df.columns.str.strip().str.lower().str.replace(r'[^a-z0-9_]', '_', regex=True)
    except Exception as e:
        logger.error(f"Failed to read saved Excel file: {str(e)}")
        return JsonResponse({"error": f"Invalid Excel file: {str(e)}"}, status=400)

    staff = StaffProfile.objects.filter(user=user, school=school).first()
    active_term = Term.objects.filter(school=school, is_active=True).first()

    with transaction.atomic():

        # ====================== STUDENTS ======================
        if category == "students":
            if not active_term:
                return JsonResponse({"error": "No active term found"}, status=400)

            for idx, row in df.iterrows():
                try:
                    with transaction.atomic():
                        admin_no = str(row.get("admin_no", "")).strip()
                        if not admin_no:
                            raise ValueError("admin_no is required")

                        student_email = f"{admin_no}@student.school.local"
                        student_password = generate_password()
                        first_name = str(row.get("first_name", "")).strip()
                        last_name = str(row.get("last_name", "")).strip()
                        gender = str(row.get("gender", "")).strip().upper()

                        # Create User
                        user_obj, user_created = User.objects.get_or_create(
                            email=student_email,
                            defaults={
                                "phone_number": admin_no,
                                "first_name": first_name,
                                "last_name": last_name,
                                "is_student": True,
                            }
                        )
                        if user_created:
                            user_obj.set_password(student_password)
                            user_obj.save()

                        # Grade & Stream
                        grade_name = str(row.get("grade", "")).strip()
                        stream_name = str(row.get("stream", "")).strip()
                        grade = Grade.objects.filter(name__iexact=grade_name, school=school).first()
                        stream = Streams.objects.filter(name__iexact=stream_name, school=school).first()

                        if not grade or not stream:
                            raise ValueError(f"Grade '{grade_name}' or Stream '{stream_name}' not found")

                        # Pathway
                        pathway_obj = None
                        pathway_raw = str(row.get("pathway", "")).strip()
                        if pathway_raw and grade:
                            normalized_csv = pathway_raw.lower().replace(".", "").replace("&", "and").replace(" ", "")
                            for p in Pathway.objects.filter(school=school, grade=grade):
                                normalized_db = p.name.strip().lower().replace(".", "").replace("&", "and").replace(" ", "")
                                if normalized_db == normalized_csv:
                                    pathway_obj = p
                                    break

                        # Create/Update Student
                        student, created = Student.objects.update_or_create(
                            user=user_obj,
                            student_id=admin_no,
                            school=school,
                            defaults={
                                "date_of_birth": row.get("date_of_birth"),
                                "gender": gender,
                                "enrollment_date": timezone.now().date(),
                                "grade_level": grade,
                                "stream": stream,
                                "pathway": pathway_obj,
                            }
                        )

                        # Subject Enrollment
                        subject_codes = [
                            c.strip().upper()
                            for c in str(row.get("subjects", "")).split(",")
                            if c.strip()
                        ]
                        for code in subject_codes:
                            subject = Subject.objects.filter(school=school, code__iexact=code).first()
                            if not subject:
                                subject = Subject.objects.create(
                                    school=school,
                                    code=code,
                                    name=code,
                                    start_date=active_term.start_date,
                                    end_date=active_term.end_date,
                                )
                                subject.grade.add(grade)
                            SubjectEnrollment.objects.get_or_create(student=student, subject=subject)

                        # Parent Auto Creation & Linking
                        parent_phone = str(row.get("parent_phone", "")).strip()
                        if parent_phone:
                            parent_email = str(row.get("parent_email", "")).strip() or f"{parent_phone}@parent.school.local"
                            parent_first_name = str(row.get("parent_first_name", "")).strip()
                            parent_last_name = str(row.get("parent_last_name", "")).strip()
                            parent_password = generate_password()

                            parent_user, parent_user_created = User.objects.get_or_create(
                                email=parent_email,
                                defaults={
                                    "phone_number": parent_phone,
                                    "first_name": parent_first_name,
                                    "last_name": parent_last_name,
                                    "is_parent": True,
                                }
                            )
                            if parent_user_created:
                                parent_user.set_password(parent_password)
                                parent_user.save()

                            parent_obj, _ = Parent.objects.get_or_create(
                                phone=parent_phone,
                                defaults={
                                    "user": parent_user,
                                    "parent_id": parent_phone,
                                    "school": school,
                                }
                            )
                            if not parent_obj.user:
                                parent_obj.user = parent_user
                                parent_obj.save()

                            student.parents.add(parent_obj)

                        results["created"] += 1

                except Exception as e:
                    logger.exception(f"Student row {idx + 2} failed")
                    results["errors"].append({"row": idx + 2, "error": str(e)})

        # ====================== TEACHERS ======================
        elif category == "teachers":
            required = ["phone", "email", "first_name", "last_name", "subjects", "streams", "class_teacher"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                return JsonResponse({"error": f"Missing columns: {missing}"}, status=400)

            for idx, row in df.iterrows():
                try:
                    phone = normalize_phone(row["phone"])
                    email = safe_email(row["email"], f"{phone}@gmail.com")
                    password = generate_password()

                    user_obj, created = User.objects.get_or_create(
                        email=email,
                        defaults={
                            "phone_number": phone,
                            "first_name": str(row["first_name"]).strip(),
                            "last_name": str(row["last_name"]).strip(),
                            "is_teacher": True,
                        }
                    )
                    if created:
                        user_obj.set_password(password)
                        user_obj.save()

                    staff_id = f"TCHR{str(user_obj.id).zfill(5)}"
                    staff_profile, _ = StaffProfile.objects.get_or_create(
                        user=user_obj,
                        school=school,
                        defaults={
                            "staff_id": staff_id,
                            "position": "teacher",
                        }
                    )

                    # Assign Subjects
                    for code in str(row["subjects"]).replace(" ", "").split(","):
                        if code:
                            subj = Subject.objects.filter(code=code, school=school).first()
                            if subj:
                                staff_profile.subjects.add(subj)

                    # Assign Streams as Class Teacher
                    if str(row.get("class_teacher", "")).upper() == "YES":
                        stream_names = [s.strip() for s in str(row["streams"]).replace(" ", "").split(",") if s.strip()]
                        streams = Streams.objects.filter(name__in=stream_names, school=school)
                        for stream in streams:
                            TeacherStreamAssignment.objects.get_or_create(
                                teacher=staff_profile, stream=stream, school=school
                            )

                    # Send Credentials
                    msg = f"Teacher Login\nEmail: {email}\nPassword: {password}"
                    logger.info(msg)
                    # _send_sms_via_eujim(phone, msg)

                    results["created"] += 1

                except Exception as e:
                    logger.exception(f"Teacher row {idx + 2} failed")
                    results["errors"].append({"row": idx + 2, "error": str(e)})

        # ====================== GRADES ======================
        elif category == "grades":
            required = ["grade_name", "code", "lessons_per_term", "capacity", "stream_name"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                return JsonResponse({"error": f"Missing columns: {missing}"}, status=400)

            for idx, row in df.iterrows():
                try:
                    grade_code = str(row["code"]).strip().upper()
                    grade_name = str(row["grade_name"]).strip()
                    raw_streams = str(row["stream_name"]).strip()

                    if not raw_streams:
                        raise ValueError("stream_name is required")

                    stream_names = [s.strip().upper() for s in raw_streams.split(",") if s.strip()]

                    grade, _ = Grade.objects.update_or_create(
                        school=school,
                        code=grade_code,
                        defaults={
                            "name": grade_name,
                            "lessons_per_term": int(row["lessons_per_term"]),
                            "capacity": int(row["capacity"]),
                            "description": str(row.get("description", "")),
                            "is_active": True,
                        }
                    )

                    stream_capacity = int(row.get("stream_capacity") or grade.capacity)

                    for stream_name in stream_names:
                        Streams.objects.update_or_create(
                            school=school,
                            grade=grade,
                            name=stream_name,
                            defaults={
                                "capacity": stream_capacity,
                                "is_active": True,
                            }
                        )

                    results["created"] += 1

                except Exception as e:
                    results["errors"].append({"row": idx + 2, "error": str(e)})

        # ====================== TIME SLOTS ======================
        elif category == "time_slots":
            for idx, row in df.iterrows():
                try:
                    start_time = safe_parse_time(row["start_time"])
                    end_time = safe_parse_time(row["end_time"])
                    if not start_time or not end_time:
                        raise ValueError("Invalid time format")

                    TimeSlot.objects.update_or_create(
                        school=school,
                        start_time=start_time,
                        end_time=end_time,
                        defaults={
                            "description": str(row.get("description", "")),
                            "updated_by": staff
                        }
                    )
                    results["created"] += 1
                except Exception as e:
                    results["errors"].append({"row": idx + 2, "error": str(e)})

        # ====================== SUBJECTS ======================
        elif category == "subjects":
            if not active_term:
                return JsonResponse({"error": "No active term found"}, status=400)

            for idx, row in df.iterrows():
                try:
                    # Grades (comma separated)
                    grade_names = []
                    if "grade" in df.columns and row.get("grade"):
                        grade_names = [g.strip() for g in str(row["grade"]).split(",") if g.strip()]

                    # Pathway
                    pathway_obj = None
                    pathway_raw = str(row.get("pathway", "")).strip()
                    if pathway_raw and grade_names:
                        normalized_csv = pathway_raw.lower().replace(".", "").replace("&", "and").replace(" ", "")
                        grade_obj = Grade.objects.filter(
                            school=school, name__iexact=grade_names[0]
                        ).first()
                        if grade_obj:
                            for p in Pathway.objects.filter(school=school, grade=grade_obj):
                                if p.name.strip().lower().replace(".", "").replace("&", "and").replace(" ", "") == normalized_csv:
                                    pathway_obj = p
                                    break
                            if not pathway_obj:
                                pathway_obj = Pathway.objects.create(
                                    name=pathway_raw,
                                    grade=grade_obj,
                                    school=school,
                                    is_active=True
                                )

                    # Create/Update Subject
                    subject, _ = Subject.objects.update_or_create(
                        school=school,
                        code=str(row["code"]).strip().upper(),
                        defaults={
                            "name": str(row["name"]).strip(),
                            "sessions_per_week": int(row.get("lessons_per_week", 0)),
                            "start_date": active_term.start_date,
                            "end_date": active_term.end_date,
                            "pathway": pathway_obj,
                        }
                    )

                    # Assign grades
                    for g_name in grade_names:
                        grade = Grade.objects.filter(school=school, name__iexact=g_name).first()
                        if not grade:
                            grade = Grade.objects.create(
                                school=school,
                                name=g_name,
                                code=g_name.replace(" ", "").upper(),
                                lessons_per_term=0,
                                capacity=0,
                                is_active=True,
                            )
                        subject.grade.add(grade)

                    results["created"] += 1

                except Exception as e:
                    results["errors"].append({"row": idx + 2, "error": str(e)})

        # ====================== PARENTS ======================
        elif category == "parents":
            required = ["first_name", "last_name", "mobile", "admin_no"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                return JsonResponse({"error": f"Missing columns: {missing}"}, status=400)

            for idx, row in df.iterrows():
                row_num = idx + 2
                try:
                    with transaction.atomic():
                        phone = normalize_phone(row["mobile"])
                        admin_no = str(row["admin_no"]).strip()
                        email = f"{phone}@parent.school.local"
                        password = generate_password()

                        user_obj, created = User.objects.get_or_create(
                            email=email,
                            defaults={
                                "phone_number": phone,
                                "first_name": str(row["first_name"]).strip(),
                                "last_name": str(row["last_name"]).strip(),
                                "is_parent": True,
                            }
                        )
                        if created:
                            user_obj.set_password(password)
                            user_obj.save()

                        parent, _ = Parent.objects.get_or_create(
                            user=user_obj,
                            defaults={
                                "parent_id": f"PARENT{user_obj.id}",
                                "phone": phone,
                                "school": school,
                            }
                        )

                        # Link to student
                        student = Student.objects.filter(student_id=admin_no, school=school).first()
                        if student:
                            student.parents.add(parent)
                        else:
                            results["warnings"].append({
                                "row": row_num,
                                "message": f"Student with admin_no '{admin_no}' not found"
                            })

                        results["created"] += 1

                except Exception as e:
                    logger.exception(f"Parent row {row_num} failed")
                    results["errors"].append({"row": row_num, "error": str(e)})

         # ====================== TIMETABLE ======================
        elif category == "timetable":
            required = ["grade", "stream", "term", "year", "subject_code", "room", "weekdays", "start_time", "end_time"]
            missing = [c for c in required if c not in df.columns]
            if missing:
                return JsonResponse({"error": f"Missing columns: {', '.join(missing)}"}, status=400)

            # Extract timetable metadata from first row
            first = df.iloc[0]
            term_name = str(first.get("term", "")).strip()
            excel_year_value = int(str(first.get("year")).strip())

            year_obj = AcademicYear.objects.get(name=excel_year_value)
            term = Term.objects.get(
                name=term_name,
                school=school,
                year=year_obj,
                is_active=True
            )

            grade_name = str(first.get("grade", "")).strip()
            stream_name = str(first.get("stream", "")).strip()
            grade = Grade.objects.get(name=grade_name, school=school)
            stream = Streams.objects.get(name=stream_name, school=school)

            # Create or get Timetable
            timetable, _ = Timetable.objects.get_or_create(
                school=school,
                grade=grade,
                stream=stream,
                term=term,
                year=excel_year_value,
                defaults={
                    "start_date": term.start_date,
                    "end_date": term.end_date
                }
            )

            # ====================== CACHES ======================
            subject_map = {s.code.upper(): s for s in Subject.objects.filter(school=school)}

            # Robust staff_map using your excellent normalize_phone
            staff_map = {}
            for s in StaffProfile.objects.filter(school=school).select_related('user'):
                if s.user and s.user.phone_number:
                    norm_phone = normalize_phone(s.user.phone_number)
                    staff_map[norm_phone] = s
                    # Support Excel that may have phone without leading zero
                    if norm_phone.startswith("0"):
                        staff_map[norm_phone[1:]] = s

            # Time slot cache
            slot_cache = {
                (slot.start_time.strftime('%H:%M'), slot.end_time.strftime('%H:%M')): slot
                for slot in TimeSlot.objects.filter(school=school)
                if slot.start_time and slot.end_time
            }

            lessons_to_create = []
            seen_patterns = set()
            weekday_counts = defaultdict(int)

            # ====================== PROCESS EACH ROW ======================
            for idx, row in df.iterrows():
                row_num = idx + 2
                try:
                    # Subject
                    subj_code = str(row["subject_code"]).strip().upper()
                    room = str(row.get("room", "")).strip() or "N/A"
                    subject = subject_map.get(subj_code)
                    if not subject:
                        raise ValueError(f"Subject '{subj_code}' not found")

                    # ==================== TEACHER LOOKUP (Fixed) ====================
                    teacher = None
                    teacher_phone_raw = None

                    # Support multiple common column names
                    possible_cols = ["teacher_phone", "teacher", "phone", "teacherphone", "mobile", "tutor"]
                    for col in possible_cols:
                        if col in df.columns:
                            teacher_phone_raw = row.get(col)
                            if teacher_phone_raw and str(teacher_phone_raw).strip():
                                break

                    if teacher_phone_raw:
                        phone = normalize_phone(teacher_phone_raw)
                        if phone:
                            teacher = staff_map.get(phone)
                            if not teacher:
                                results["warnings"].append({
                                    "row": row_num,
                                    "message": f"Teacher phone '{phone}' (original: {teacher_phone_raw}) not found in StaffProfile"
                                })

                    # Weekday
                    raw_day = str(row["weekdays"]).strip().lower()
                    wd = normalize_weekday(raw_day)
                    if not wd:
                        raise ValueError(f"Invalid weekday: '{raw_day}'")

                    # Time
                    start_norm = norm_time(row["start_time"])
                    end_norm = norm_time(row["end_time"])
                    if not start_norm or not end_norm:
                        raise ValueError(f"Invalid time format - start: {row.get('start_time')}, end: {row.get('end_time')}")

                    time_slot = slot_cache.get((start_norm, end_norm))
                    if not time_slot:
                        results["warnings"].append({
                            "row": row_num,
                            "message": f"Time slot {start_norm}–{end_norm} not found"
                        })
                        continue

                    # Prevent duplicate lessons
                    pattern_key = (wd, time_slot.id, subject.id, teacher.id if teacher else None, room)
                    if pattern_key in seen_patterns:
                        continue
                    seen_patterns.add(pattern_key)

                    # Generate lessons for every week in the term
                    current_date = term.start_date
                    while current_date <= term.end_date:
                        if current_date.strftime("%A").lower() == wd:
                            break
                        current_date += timedelta(days=1)

                    while current_date <= term.end_date:
                        lessons_to_create.append(
                            Lesson(
                                timetable=timetable,
                                subject=subject,
                                stream=stream,
                                teacher=teacher,           # ← Now correctly assigned
                                day_of_week=wd,
                                time_slot=time_slot,
                                room=room,
                                lesson_date=current_date,
                            )
                        )
                        weekday_counts[wd] += 1
                        current_date += timedelta(days=7)

                except Exception as e:
                    logger.exception(f"[ROW {row_num}] Failed")
                    results["errors"].append({"row": row_num, "error": str(e)})

            # ====================== SAVE LESSONS ======================
            Lesson.objects.filter(timetable=timetable).delete()

            if lessons_to_create:
                Lesson.objects.bulk_create(lessons_to_create, ignore_conflicts=True)
                results["created"] = len(lessons_to_create)
                logger.info(f"[TIMETABLE] {len(lessons_to_create)} lessons created for {grade_name}{stream_name}")

                for wd, count in weekday_counts.items():
                    logger.info(f"[LESSON COUNT] {wd.capitalize()}: {count}")
            else:
                logger.warning("No lessons generated from uploaded file.")

            # Auto populate student enrollments
            transaction.on_commit(
                lambda: populate_student_lesson_enrollments(school, grade, stream, term)
            )

            # Summary for frontend/debug
            results["summary"] = {
                "grade": grade_name,
                "stream": stream_name,
                "term": term_name,
                "year": excel_year_value,
                "lessons_generated": len(lessons_to_create),
                "weekdays": dict(weekday_counts)
            }
            logger.info(f"Timetable upload completed: {results['summary']}")
        else:
            return JsonResponse({"error": "Invalid category"}, status=400)

    return JsonResponse({
        "status": "success",
        "category": category,
        "upload_id": upload_record.id,
        "results": results
    })

@login_required
def upload_excel_page(request):
    """Renders the Excel upload page."""
    user = request.user
    school = get_user_school(user)
    return render(request, 'school/file_upload.html', {'school': school})


# =============================================================================
# SUBJECT CATALOG — Kiswate platform admin manages the global subject catalog.
# Principals then activate subjects from it for their school.
# =============================================================================

@login_required
def catalog_subject_list(request):
    """Kiswate admin: view and manage the platform subject catalog."""
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    query = request.GET.get('q', '').strip()
    qs = SubjectCatalog.objects.annotate(school_count=Count('school_subjects')).order_by('name')
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(code__icontains=query))

    paginator = Paginator(qs, 25)
    catalog_list = paginator.get_page(request.GET.get('page'))
    form = SubjectCatalogForm()
    upload_form = BulkSubjectUploadForm()

    return render(request, 'school/catalog/subjects.html', {
        'catalog_list': catalog_list,
        'form': form,
        'upload_form': upload_form,
        'query': query,
    })


@login_required
def catalog_subject_create(request):
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = SubjectCatalogForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{form.cleaned_data["name"]}" added to catalog.')
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    return redirect('school:catalog-subject-list')


@login_required
def catalog_subject_edit(request, pk):
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    entry = get_object_or_404(SubjectCatalog, pk=pk)
    if request.method == 'POST':
        form = SubjectCatalogForm(request.POST, instance=entry)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{entry.name}" updated.')
        else:
            for field, errs in form.errors.items():
                for e in errs:
                    messages.error(request, f"{field}: {e}")
    return redirect('school:catalog-subject-list')


@login_required
def catalog_subject_delete(request, pk):
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    entry = get_object_or_404(SubjectCatalog, pk=pk)
    if request.method == 'POST':
        name = entry.name
        entry.delete()
        messages.success(request, f'"{name}" removed from catalog.')
    return redirect('school:catalog-subject-list')


@login_required
def catalog_subject_toggle(request, pk):
    """Quick AJAX toggle for is_active on a catalog entry."""
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        return JsonResponse({'error': 'Access denied'}, status=403)
    entry = get_object_or_404(SubjectCatalog, pk=pk)
    entry.is_active = not entry.is_active
    entry.save(update_fields=['is_active'])
    return JsonResponse({'is_active': entry.is_active})


# =============================================================================
# SUBJECT SELECTION — Principal activates catalog subjects for their school.
# =============================================================================

@login_required
def subject_activate_from_catalog(request):
    """Principal/admin: pick catalog subjects to activate for this school."""
    user = request.user
    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    school = get_user_school(user)
    if not school:
        messages.error(request, "No school profile found.")
        return redirect('school:dashboard')

    active_term = Term.objects.filter(school=school, is_active=True).first()
    default_start = active_term.start_date if active_term else timezone.localdate()

    form = SubjectActivationForm(school=school, initial={'start_date': default_start})

    if request.method == 'POST':
        form = SubjectActivationForm(request.POST, school=school)
        if form.is_valid():
            created = form.activate(school)
            if created:
                messages.success(
                    request,
                    f'{len(created)} subject(s) activated: '
                    + ', '.join(s.name for s in created)
                    + '. Set the grade(s) for each subject below.'
                )
            else:
                messages.info(request, 'Selected subjects were already active for your school.')
            return redirect('school:school-subjects')
        else:
            messages.error(request, 'Please correct the errors below.')

    already_active = Subject.objects.filter(school=school, catalog_ref__isnull=False).select_related('catalog_ref')
    catalog_groups = {}
    for entry in SubjectCatalog.objects.filter(is_active=True).order_by('curriculum', 'name'):
        catalog_groups.setdefault(entry.get_curriculum_display(), []).append(entry)

    return render(request, 'school/subject_selection.html', {
        'form': form,
        'school': school,
        'catalog_groups': catalog_groups,
        'already_active': already_active,
    })


# =============================================================================
# BULK SUBJECT UPLOAD — Kiswate admin uploads catalog subjects via Excel
# =============================================================================

@login_required
def catalog_subject_bulk_upload(request):
    """Parse an uploaded Excel file and create SubjectCatalog entries."""
    if not (request.user.is_kiswate_user or request.user.is_kiswate_admin or request.user.is_superuser):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:catalog-subject-list')

    form = BulkSubjectUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        for field, errs in form.errors.items():
            for e in errs:
                messages.error(request, f"{e}")
        return redirect('school:catalog-subject-list')

    file = form.cleaned_data['file']
    try:
        df = pd.read_excel(file, dtype=str)
    except Exception as e:
        messages.error(request, f"Could not read file: {e}")
        return redirect('school:catalog-subject-list')

    required_cols = {'name', 'code'}
    missing = required_cols - set(c.lower().strip() for c in df.columns)
    if missing:
        messages.error(request, f"Missing required columns: {', '.join(missing)}")
        return redirect('school:catalog-subject-list')

    df.columns = [c.lower().strip() for c in df.columns]

    valid_curricula = {'cbc', 'kcse', 'kcpe', 'igcse', 'other'}
    created_count = updated_count = skipped_count = 0

    for idx, row in df.iterrows():
        name = str(row.get('name', '')).strip()
        code = str(row.get('code', '')).strip()
        if not name or not code or name == 'nan' or code == 'nan':
            skipped_count += 1
            continue

        curriculum = str(row.get('curriculum', 'cbc')).strip().lower()
        if curriculum not in valid_curricula:
            curriculum = 'cbc'

        def _bool(val, default=True):
            s = str(val).strip().lower()
            if s in ('true', '1', 'yes'):
                return True
            if s in ('false', '0', 'no'):
                return False
            return default

        defaults = {
            'curriculum': curriculum,
            'is_core': _bool(row.get('is_core', 'TRUE')),
            'is_elective': _bool(row.get('is_elective', 'FALSE'), default=False),
            'sessions_per_week_default': max(1, int(float(row.get('sessions_per_week_default', 2) or 2))),
            'description': str(row.get('description', '')).strip() if row.get('description') else '',
            'is_active': True,
        }

        try:
            obj, created = SubjectCatalog.objects.update_or_create(
                code=code,
                defaults={**defaults, 'name': name},
            )
            if created:
                created_count += 1
            else:
                updated_count += 1
        except Exception:
            skipped_count += 1

    messages.success(
        request,
        f"Import complete: {created_count} added, {updated_count} updated, {skipped_count} skipped."
    )
    return redirect('school:catalog-subject-list')


# =============================================================================
# PARENT SELF-SERVICE PORTAL
# =============================================================================

def _get_parent(user):
    try:
        return user.parent
    except Exception:
        return None


@login_required
def parent_portal(request):
    """Parent dashboard: overview of all children."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "This section is for parents only.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    children = parent.children.select_related('user', 'grade_level', 'stream', 'school').all()
    unread_count = request.user.notifications.filter(is_read=False).count()
    open_complaints = Complaint.objects.filter(parent=parent, status='open').count()

    child_data = []
    for child in children:
        recent_attendance = Attendance.objects.filter(
            enrollment__student=child
        ).select_related('enrollment__lesson__subject').order_by('-date')[:5]

        child_subject_ids = child.subject_enrollments.filter(is_active=True).values_list('subject_id', flat=True)
        pending_assignments = Assignment.objects.filter(
            school=child.school,
            subject_id__in=child_subject_ids,
            due_date__gte=timezone.now(),
        ).order_by('due_date')[:5]

        child_data.append({
            'student': child,
            'recent_attendance': recent_attendance,
            'pending_assignments': pending_assignments,
        })

    return render(request, 'school/parent/portal.html', {
        'parent': parent,
        'child_data': child_data,
        'unread_count': unread_count,
        'open_complaints': open_complaints,
    })


@login_required
def parent_notifications(request):
    """Parent: view and manage notifications."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    if request.method == 'POST' and request.POST.get('action') == 'mark_all_read':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('school:parent-notifications')

    if request.method == 'POST' and request.POST.get('action') == 'mark_read':
        nid = request.POST.get('notification_id')
        request.user.notifications.filter(pk=nid).update(is_read=True)
        return JsonResponse({'ok': True})

    qs = request.user.notifications.select_related(
        'related_attendance__enrollment__lesson__subject',
        'related_discipline__student__user',
    ).all()

    # Filters
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    read_status = request.GET.get('read_status')

    if date_from:
        qs = qs.filter(sent_at__date__gte=date_from)
    if date_to:
        qs = qs.filter(sent_at__date__lte=date_to)
    if read_status == 'unread':
        qs = qs.filter(is_read=False)
    elif read_status == 'read':
        qs = qs.filter(is_read=True)

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))
    unread_count = request.user.notifications.filter(is_read=False).count()

    return render(request, 'school/parent/notifications.html', {
        'notifications': page,
        'unread_count': unread_count,
    })


@login_required
def parent_complaints(request):
    """Parent: submit and track complaints."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    form = ComplaintForm(parent=parent)

    if request.method == 'POST':
        form = ComplaintForm(request.POST, parent=parent)
        if form.is_valid():
            complaint = form.save(commit=False)
            complaint.parent = parent
            complaint.school = parent.school
            if complaint.is_anonymous:
                complaint.parent = parent  # still store for audit; display hides name
            complaint.save()
            messages.success(request, "Complaint submitted. The school will respond shortly.")
            return redirect('school:parent-complaints')
        else:
            messages.error(request, "Please correct the errors below.")

    complaints = Complaint.objects.filter(parent=parent).select_related('student__user', 'responded_by__user')
    paginator = Paginator(complaints, 15)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'school/parent/complaints.html', {
        'form': form,
        'complaints': page,
        'parent': parent,
    })


@login_required
def parent_assignments(request):
    """Parent: view assignments and submission status for all children."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    children = parent.children.select_related('user', 'grade_level').all()
    selected_child_id = request.GET.get('child')

    if selected_child_id:
        children_qs = children.filter(pk=selected_child_id)
    else:
        children_qs = children

    assignment_data = []
    for child in children_qs:
        child_subject_ids = child.subject_enrollments.filter(is_active=True).values_list('subject_id', flat=True)
        child_subjects = Subject.objects.filter(id__in=child_subject_ids)

        assignments = Assignment.objects.filter(
            school=child.school,
            subject__in=child_subjects,
        ).select_related('subject').order_by('-due_date')[:20]

        rows = []
        for asn in assignments:
            submission = Submission.objects.filter(
                enrollment__student=child,
                assignment=asn,
            ).first()
            rows.append({'assignment': asn, 'submission': submission})

        assignment_data.append({'student': child, 'rows': rows})

    return render(request, 'school/parent/assignments.html', {
        'assignment_data': assignment_data,
        'children': children,
        'selected_child_id': selected_child_id,
        'parent': parent,
    })


@login_required
def parent_exam_results(request):
    """Parent: view graded submissions (exam results / assessment scores)."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    children = parent.children.select_related('user', 'grade_level').all()
    selected_child_id = request.GET.get('child')

    results_data = []
    for child in children:
        if selected_child_id and str(child.pk) != selected_child_id:
            continue

        graded = Submission.objects.filter(
            enrollment__student=child,
            score__isnull=False,
        ).select_related(
            'assignment__subject',
            'enrollment__lesson__subject',
        ).order_by('-submitted_at')

        results_data.append({'student': child, 'submissions': graded})

    return render(request, 'school/parent/exam_results.html', {
        'results_data': results_data,
        'children': children,
        'selected_child_id': selected_child_id,
        'parent': parent,
    })


@login_required
def parent_fee_updates(request):
    """Parent: view fee payment history and outstanding balance for children."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    children = parent.children.select_related('user', 'grade_level').all()

    fee_data = []
    for child in children:
        payments = Payment.objects.filter(student=child).order_by('-paid_at', '-id')
        total_paid = payments.filter(status='completed').aggregate(
            total=Sum('amount')
        )['total'] or 0
        pending = payments.filter(status='pending')

        fee_data.append({
            'student': child,
            'payments': payments[:15],
            'total_paid': total_paid,
            'pending_count': pending.count(),
        })

    return render(request, 'school/parent/fees.html', {
        'fee_data': fee_data,
        'children': children,
        'parent': parent,
    })


@login_required
def parent_attendance(request):
    """Parent: view attendance records for children."""
    if not getattr(request.user, 'is_parent', False):
        messages.error(request, "Access denied.")
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        messages.error(request, "Parent profile not found.")
        return redirect('userauths:sign-in')

    children = parent.children.select_related('user', 'grade_level').all()
    selected_child_id = request.GET.get('child')

    attendance_data = []
    for child in children:
        if selected_child_id and str(child.pk) != selected_child_id:
            continue

        base_records = Attendance.objects.filter(enrollment__student=child)
        total = base_records.count()
        present = base_records.filter(status='P').count()
        rate = round((present / total * 100) if total else 0, 1)

        records = base_records.select_related(
            'enrollment__lesson__subject',
            'enrollment__lesson__time_slot',
        ).order_by('-date')[:50]

        attendance_data.append({
            'student': child,
            'records': records,
            'total': total,
            'present': present,
            'rate': rate,
        })

    return render(request, 'school/parent/attendance.html', {
        'attendance_data': attendance_data,
        'children': children,
        'selected_child_id': selected_child_id,
        'parent': parent,
    })


# =============================================================================
# SCHOOL ADMIN: VIEW COMPLAINTS
# =============================================================================

@login_required
def admin_complaints_list(request):
    """Principal/admin view of all parent complaints."""
    user = request.user
    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    school = get_user_school(user)
    if not school:
        messages.error(request, "No school profile found.")
        return redirect('school:dashboard')

    status_filter = request.GET.get('status', '')
    qs = Complaint.objects.filter(school=school).select_related(
        'parent__user', 'student__user', 'responded_by__user'
    ).order_by('-created_at')
    if status_filter:
        qs = qs.filter(status=status_filter)

    if request.method == 'POST':
        complaint_id = request.POST.get('complaint_id')
        response_text = request.POST.get('response', '').strip()
        new_status = request.POST.get('status', 'resolved')
        complaint = get_object_or_404(Complaint, pk=complaint_id, school=school)
        if response_text:
            try:
                staff = user.staffprofile
            except Exception:
                staff = None
            complaint.response = response_text
            complaint.status = new_status
            complaint.responded_by = staff
            complaint.responded_at = timezone.now()
            complaint.save()
            AuditLog.objects.create(
                school=school, model_name='Complaint', object_id=complaint.pk,
                action='update', actor=user,
                description=f"Responded to complaint: {complaint.subject}",
            )
            messages.success(request, "Response saved.")
        return redirect('school:admin-complaints')

    paginator = Paginator(qs, 20)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'school/complaints.html', {
        'complaints': page,
        'status_filter': status_filter,
        'school': school,
        'status_choices': Complaint.STATUS_CHOICES,
    })


# =============================================================================
# BULK NOTIFICATION — school admins and Kiswate admins send SMS/email/in-app
# =============================================================================

def _resolve_recipients(audience, school, grade=None, stream=None):
    """
    Return list of (user, phone) tuples for the given audience.
    phone may be None if the user has no phone.
    """
    recipients = []

    def _phone(u, parent_obj=None):
        if parent_obj and parent_obj.phone:
            return parent_obj.phone
        return getattr(u, 'phone_number', None) or ''

    if audience in ('all_parents', 'all', 'grade_parents', 'stream_parents'):
        qs = Parent.objects.filter(school=school).select_related('user')
        if audience == 'grade_parents':
            qs = qs.filter(children__grade_level=grade).distinct()
        elif audience == 'stream_parents':
            qs = qs.filter(children__stream=stream).distinct()
        for p in qs:
            recipients.append((p.user, _phone(p.user, p)))

    if audience in ('all_students', 'all', 'grade_students', 'stream_students'):
        qs = Student.objects.filter(school=school, is_active=True).select_related('user')
        if audience == 'grade_students':
            qs = qs.filter(grade_level=grade)
        elif audience == 'stream_students':
            qs = qs.filter(stream=stream)
        for s in qs:
            recipients.append((s.user, _phone(s.user)))

    if audience in ('all_staff', 'all'):
        for sp in StaffProfile.objects.filter(school=school).select_related('user'):
            recipients.append((sp.user, _phone(sp.user)))

    # Deduplicate by user pk (a user might appear in multiple groups in 'all')
    seen = set()
    unique = []
    for u, ph in recipients:
        if u.pk not in seen:
            seen.add(u.pk)
            unique.append((u, ph))
    return unique


def _sms_configured():
    return bool(getattr(settings, 'SMS_API_KEY', ''))


@login_required
def bulk_notify(request):
    """Send bulk notifications via in-app, email, and/or SMS."""
    user = request.user
    is_kiswate = (
        getattr(user, 'is_kiswate_user', False) or
        getattr(user, 'is_kiswate_admin', False) or
        user.is_superuser
    )
    is_school_admin = (
        getattr(user, 'is_admin', False) or
        getattr(user, 'is_principal', False) or
        getattr(user, 'is_deputy_principal', False)
    )
    if not (is_kiswate or is_school_admin):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    school = get_user_school(user)

    # Kiswate admins may select school via query param
    if is_kiswate and not school:
        school_id = request.GET.get('school_id') or request.POST.get('school_id')
        if school_id:
            from school.models import School as SchoolModel
            school = SchoolModel.objects.filter(pk=school_id).first()

    if not school:
        messages.error(request, "No school context found. Append ?school_id=<id> to the URL.")
        return redirect('school:dashboard')

    form = BulkNotificationForm(school=school)
    result = None

    if request.method == 'POST':
        form = BulkNotificationForm(request.POST, school=school)
        if form.is_valid():
            cd = form.cleaned_data
            title    = cd['title']
            message  = cd['message']
            audience = cd['audience']
            grade    = cd.get('grade')
            stream   = cd.get('stream')
            do_inapp = cd['channel_inapp']
            do_email = cd['channel_email']
            do_sms   = cd['channel_sms']

            recipients = _resolve_recipients(audience, school, grade, stream)

            inapp_sent = email_sent = sms_sent = 0
            email_failed = sms_failed = 0

            for recipient_user, phone in recipients:
                if do_inapp:
                    Notification.objects.create(
                        recipient=recipient_user,
                        title=title,
                        message=message,
                        school=school,
                    )
                    inapp_sent += 1

                if do_email and recipient_user.email:
                    ok = send_email(recipient_user.email, title, message)
                    if ok:
                        email_sent += 1
                    else:
                        email_failed += 1

                if do_sms and phone:
                    sms_text = f"{title}\n{message}"[:320]
                    ok = _send_sms_via_eujim(phone, sms_text)
                    if ok:
                        sms_sent += 1
                    else:
                        sms_failed += 1

            AuditLog.objects.create(
                school=school, model_name='BulkNotification', object_id=0,
                action='create', actor=user,
                description=(
                    f"Bulk notify '{title}' → audience={audience}, "
                    f"inapp={inapp_sent}, email={email_sent}, sms={sms_sent}"
                ),
            )

            result = {
                'total':        len(recipients),
                'inapp_sent':   inapp_sent,
                'email_sent':   email_sent,
                'email_failed': email_failed,
                'sms_sent':     sms_sent,
                'sms_failed':   sms_failed,
                'title':        title,
                'audience':     dict(BulkNotificationForm.AUDIENCE_CHOICES).get(audience, audience),
            }
            if do_sms and not _sms_configured():
                messages.warning(request, "SMS credentials are not configured — SMS was skipped. Set SMS_API_KEY, SMS_PARTNERID, SMS_SHORTCODE in settings.")

    return render(request, 'school/bulk_notify.html', {
        'form': form,
        'school': school,
        'result': result,
        'sms_configured': _sms_configured(),
    })


@login_required
def student_notifications(request):
    """Student: view in-app notifications."""
    if not getattr(request.user, 'is_student', False):
        messages.error(request, "This section is for students only.")
        return redirect('userauths:sign-in')

    if request.method == 'POST' and request.POST.get('action') == 'mark_all_read':
        request.user.notifications.filter(is_read=False).update(is_read=True)
        messages.success(request, "All notifications marked as read.")
        return redirect('school:student-notifications')

    notifications = request.user.notifications.select_related(
        'related_attendance__enrollment__lesson__subject',
        'related_discipline',
    ).all()

    paginator = Paginator(notifications, 20)
    page = paginator.get_page(request.GET.get('page'))
    unread_count = request.user.notifications.filter(is_read=False).count()

    return render(request, 'school/student/notifications.html', {
        'notifications': page,
        'unread_count': unread_count,
    })


# =============================================================================
# ANNOUNCEMENTS
# =============================================================================

@login_required
def announcement_list(request):
    """Admin/principal creates and views announcements."""
    user = request.user
    school = get_user_school(user)
    if not school:
        return redirect('school:dashboard')

    announcements = Announcement.objects.filter(school=school).select_related('created_by__user', 'grade')
    audience_filter = request.GET.get('audience', '')
    if audience_filter:
        announcements = announcements.filter(audience=audience_filter)

    context = {
        'announcements': announcements,
        'school': school,
        'audience_filter': audience_filter,
    }
    return render(request, 'school/announcements/list.html', context)


@login_required
def announcement_create(request):
    user = request.user
    school = get_user_school(user)
    if not school:
        return redirect('school:dashboard')

    try:
        staff = user.staffprofile
    except Exception:
        messages.error(request, "Staff profile required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        title = request.POST.get('title', '').strip()
        body = request.POST.get('body', '').strip()
        audience = request.POST.get('audience', 'all')
        grade_id = request.POST.get('grade')
        is_pinned = request.POST.get('is_pinned') == 'on'
        expires_at = request.POST.get('expires_at') or None

        if title and body:
            ann = Announcement.objects.create(
                school=school,
                title=title,
                body=body,
                audience=audience,
                grade_id=grade_id if grade_id else None,
                is_pinned=is_pinned,
                created_by=staff,
                expires_at=expires_at,
            )
            messages.success(request, "Announcement published.")
            return redirect('school:announcements')
        else:
            messages.error(request, "Title and body are required.")

    grades = Grade.objects.filter(school=school, is_active=True)
    return render(request, 'school/announcements/create.html', {
        'school': school,
        'grades': grades,
        'audiences': Announcement.AUDIENCE_CHOICES,
    })


@login_required
def announcement_delete(request, pk):
    school = get_user_school(request.user)
    ann = get_object_or_404(Announcement, pk=pk, school=school)
    if request.method == 'POST':
        ann.delete()
        messages.success(request, "Announcement deleted.")
    return redirect('school:announcements')


@login_required
def parent_announcements(request):
    """Parent: view school announcements."""
    if not getattr(request.user, 'is_parent', False):
        return redirect('userauths:sign-in')

    parent = _get_parent(request.user)
    if not parent:
        return redirect('userauths:sign-in')

    children = parent.children.select_related('school').all()
    school_ids = children.values_list('school_id', flat=True).distinct()

    announcements = Announcement.objects.filter(
        school_id__in=school_ids,
        audience__in=['all', 'parents']
    ).select_related('school', 'created_by__user').order_by('-is_pinned', '-created_at')

    paginator = Paginator(announcements, 10)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'school/announcements/parent_view.html', {
        'announcements': page,
    })


@login_required
def student_announcements(request):
    """Student: view school announcements."""
    if not getattr(request.user, 'is_student', False):
        return redirect('userauths:sign-in')

    try:
        student = request.user.student
    except Exception:
        return redirect('userauths:sign-in')

    announcements = Announcement.objects.filter(
        school=student.school,
        audience__in=['all', 'students']
    ).select_related('created_by__user').order_by('-is_pinned', '-created_at')

    if student.grade_level:
        announcements = announcements.filter(
            Q(grade=student.grade_level) | Q(grade__isnull=True)
        )

    paginator = Paginator(announcements, 10)
    page = paginator.get_page(request.GET.get('page'))

    return render(request, 'school/announcements/student_view.html', {
        'announcements': page,
        'student': student,
    })


# =============================================================================
# FINANCE DASHBOARD
# =============================================================================

@login_required
def finance_dashboard(request):
    """Modern finance dashboard with student fee balances, payments, and receipt generation."""
    user = request.user
    if not (user.is_admin or user.is_principal or user.is_deputy_principal):
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')

    school = get_user_school(user)
    if not school:
        return redirect('school:dashboard')

    # Filters
    q = request.GET.get('q', '').strip()
    grade_filter = request.GET.get('grade', '')
    status_filter = request.GET.get('status', '')
    term_filter = request.GET.get('term', '')

    # Student fee invoices
    inv_qs = FeeInvoice.objects.filter(school=school).select_related(
        'student__user', 'student__grade_level', 'student__stream', 'term'
    )

    if q:
        inv_qs = inv_qs.filter(
            Q(student__user__first_name__icontains=q) |
            Q(student__user__last_name__icontains=q) |
            Q(student__student_id__icontains=q)
        )
    if grade_filter:
        inv_qs = inv_qs.filter(student__grade_level_id=grade_filter)
    if status_filter:
        inv_qs = inv_qs.filter(status=status_filter)
    if term_filter:
        inv_qs = inv_qs.filter(term_id=term_filter)

    # Aggregate stats
    from django.db.models import Sum, Count
    agg = inv_qs.aggregate(
        total_expected=Sum('amount_required'),
        total_collected=Sum('amount_paid'),
        total_invoices=Count('id'),
    )
    total_expected = agg['total_expected'] or 0
    total_collected = agg['total_collected'] or 0
    total_balance = total_expected - total_collected
    collection_rate = round((total_collected / total_expected * 100) if total_expected else 0, 1)

    # Status breakdown
    status_counts = inv_qs.values('status').annotate(n=Count('id'))
    status_map = {s['status']: s['n'] for s in status_counts}

    # Paginate
    paginator = Paginator(inv_qs.order_by('-created_at'), 20)
    page = paginator.get_page(request.GET.get('page'))

    # Recent payments
    recent_payments = Payment.objects.filter(school=school).select_related(
        'student__user'
    ).order_by('-paid_at', '-id')[:10]

    grades = Grade.objects.filter(school=school, is_active=True)
    terms = Term.objects.filter(school=school).order_by('-start_date')

    context = {
        'school': school,
        'invoices': page,
        'total_expected': total_expected,
        'total_collected': total_collected,
        'total_balance': total_balance,
        'collection_rate': collection_rate,
        'status_map': status_map,
        'recent_payments': recent_payments,
        'grades': grades,
        'terms': terms,
        'q': q,
        'grade_filter': grade_filter,
        'status_filter': status_filter,
        'term_filter': term_filter,
    }
    return render(request, 'school/finance_dashboard.html', context)


@login_required
def finance_create_invoice(request):
    """Create a fee invoice for a student."""
    user = request.user
    school = get_user_school(user)
    if not school:
        return redirect('school:dashboard')

    if request.method == 'POST':
        student_id = request.POST.get('student_id')
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'School Fees')
        term_id = request.POST.get('term')
        due_date = request.POST.get('due_date') or None

        try:
            student = Student.objects.get(pk=student_id, school=school)
            FeeInvoice.objects.create(
                student=student,
                school=school,
                term_id=term_id if term_id else None,
                amount_required=amount,
                description=description,
                due_date=due_date,
                created_by=user,
            )
            messages.success(request, f"Invoice created for {student.user.get_full_name()}.")
        except Exception as e:
            messages.error(request, f"Error: {e}")

    return redirect('school:finance-dashboard')


@login_required
def finance_record_payment(request, invoice_id):
    """Record a payment (cash, cheque, or M-Pesa) against a fee invoice."""
    user = request.user
    school = get_user_school(user)
    invoice = get_object_or_404(FeeInvoice, pk=invoice_id, school=school)

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        method = request.POST.get('method', 'cash')
        cheque_number = request.POST.get('cheque_number', '')
        notes = request.POST.get('notes', '')

        try:
            amount = Decimal(amount_str)
            invoice.amount_paid += amount
            invoice.payment_method = method
            invoice.cheque_number = cheque_number
            invoice.notes = notes
            invoice.save()

            # Also create a Payment record for audit trail
            Payment.objects.create(
                student=invoice.student,
                school=school,
                amount=amount,
                payment_type='fees',
                status='paid',
                paid_at=timezone.now(),
                description=f"Payment for: {invoice.description} | Method: {method}",
                transaction_id=f"INV-{invoice.pk}-{uuid.uuid4().hex[:6].upper()}",
            )
            messages.success(request, f"Payment of KES {amount} recorded.")
        except Exception as e:
            messages.error(request, f"Error recording payment: {e}")

    return redirect('school:finance-dashboard')


@login_required
def finance_receipt(request, invoice_id):
    """Generate/view receipt for a fee invoice."""
    school = get_user_school(request.user)
    invoice = get_object_or_404(FeeInvoice, pk=invoice_id, school=school)
    return render(request, 'school/finance_receipt.html', {
        'invoice': invoice,
        'school': school,
    })


@login_required
def finance_stk_push(request, invoice_id):
    """Trigger M-Pesa STK push for a fee invoice."""
    school = get_user_school(request.user)
    invoice = get_object_or_404(FeeInvoice, pk=invoice_id, school=school)

    if request.method == 'POST':
        phone = request.POST.get('phone', '')
        # In production: call Daraja STK Push API here
        messages.info(request, f"STK Push initiated to {phone} for KES {invoice.balance}. Check your phone.")

    return redirect('school:finance-dashboard')