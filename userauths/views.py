from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth import authenticate, login, logout,update_session_auth_hash
from django.contrib import messages
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from school.models import (
    Timetable,TeacherStreamAssignment,Streams, Term, Lesson, Session, Enrollment, Subject,
    StaffProfile, Student, Parent,Attendance,DisciplineRecord,TimeSlot,Assignment, Notification,ContactMessage,
    Payment, FeeInvoice, Announcement, Complaint
)
from django.utils import timezone
from collections import defaultdict
from userauths.models import User
from django.db.models import Sum
from userauths.models import OTP,User
from userauths.backends import EmailBackend
from school.views import send_email, _send_sms_via_eujim
from django.db.models import Q
import random
from django_ratelimit.decorators import ratelimit
from django.db.models import Count, Q, F, FloatField, ExpressionWrapper
from django.db.models import Count, Case, When, FloatField, F,BooleanField
from django.db.models.functions import Cast

import logging

logger = logging.getLogger(__name__)


def index(request):
    return render(request, "landing/index.html",{})

def about(request):
    return render(request, "landing/about.html",{})

def modules(request):
    return render(request, "landing/modules.html",{})

def how_it_works(request):
    return render(request, "landing/how_it_works.html",{})

def pricing(request):
    return render(request, "landing/pricing.html",{})

def faqs(request):
    return render(request, "landing/faqs.html",{})


def get_client_ip(request):

    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")

    if x_forwarded_for:
        ip = x_forwarded_for.split(",")[0]
    else:
        ip = request.META.get("REMOTE_ADDR")

    return ip


@ratelimit(key='ip', rate='5/h', block=True)
def demo(request):

    if request.method == "POST":

        ip = get_client_ip(request)

        first_name = request.POST.get("first_name")
        last_name = request.POST.get("last_name")
        email = request.POST.get("email_address")
        phone = request.POST.get("contact_phone")
        school_name = request.POST.get("school_name")

        school_category = request.POST.get("school_category")

        county = request.POST.get("county")
        sub_county = request.POST.get("sub_county")
        constituency = request.POST.get("constituency")
        ward = request.POST.get("ward")
        city = request.POST.get("city")
        address = request.POST.get("address")

        message = request.POST.get("message")

        # prevent duplicate leads within 24 hrs
        last_24hrs = timezone.now() - timedelta(hours=24)

        duplicate = ContactMessage.objects.filter(
            created_at__gte=last_24hrs
        ).filter(
            email_address=email
        ).exists()

        if duplicate:
            messages.warning(
                request,
                "A demo request with this email was already submitted within the last 24 hours. Our team will contact you shortly."
            )
            return redirect("userauths:demo")

        phone_exists = ContactMessage.objects.filter(
            created_at__gte=last_24hrs,
            contact_phone=phone
        ).exists()

        if phone_exists:
            messages.warning(
                request,
                "A demo request with this phone number already exists. Our team will contact you shortly."
            )
            return redirect("userauths:demo")

        school_exists = ContactMessage.objects.filter(
            created_at__gte=last_24hrs,
            school_name=school_name
        ).exists()

        if school_exists:
            messages.warning(
                request,
                "A demo request for this school was already submitted recently."
            )
            return redirect("userauths:demo")

        # save lead
        ContactMessage.objects.create(
            first_name=first_name,
            last_name=last_name,
            email_address=email,
            contact_phone=phone,
            school_name=school_name,
            school_category=school_category,
            county=county,
            sub_county=sub_county,
            constituency=constituency,
            ward=ward,
            city=city,
            address=address,
            message=message,
            ip_address=ip,
        )

        messages.success(
            request,
            "Your demo request has been submitted successfully. Our team will contact you shortly."
        )

        return redirect("userauths:demo")

    return render(request, "landing/demo.html")

# Integrated LoginView with Role-Based Redirects
from django.contrib.auth import authenticate, login
from django.contrib import messages
from django.shortcuts import redirect, render
# from django.contrib.auth.models import User


def get_user_redirect(user):

    if user.is_superuser or user.is_kiswate_user:
        return "kiswate_digital_app:kiswate_admin_dashboard"

    if user.is_policy_maker:
        return "school:policy-dashboard"

    if user.is_parent:
        return "userauths:parent-dashboard"

    if user.is_student:
        return "userauths:student-dashboard"

    if user.is_principal or user.is_deputy_principal or user.is_admin or user.school_staff:
        # First-login check: redirect principal/admin to subject selection if school has no subjects
        if user.is_admin or user.is_principal:
            school = getattr(user, 'school_admin_profile', None)
            if not school:
                try:
                    school = user.staffprofile.school
                except Exception:
                    school = None
            if school:
                from school.models import Subject as SchoolSubject
                if not SchoolSubject.objects.filter(school=school).exists():
                    return "school:subject-activate-catalog"
        return "school:dashboard"

    if user.is_teacher:
        return "userauths:teacher-dashboard"

    logger.warning(f"User {user.id} has no role assigned.")
    return "userauths:sign-in"


@ratelimit(key='ip', rate='10/m', block=True)
def LoginView(request):

    # If already logged in
    if request.user.is_authenticated:
        return redirect(get_user_redirect(request.user))

    if request.method == "POST":

        email = request.POST.get("email")
        password = request.POST.get("password")

        user = authenticate(request, email=email, password=password)

        if user is None:
            messages.warning(request, "Invalid email or password")
            return redirect("userauths:sign-in")

        login(request, user)

        messages.success(request, f"Welcome back, {user.get_full_name()}!")

        return redirect(get_user_redirect(user))

    return render(request, "landing/login.html")

# Updated Dashboard Views (Adjusted for User Model Booleans and Profile Access)
# Note: Assumes OneToOneFields (e.g., user.parent for is_parent=True users).
# For school attr, derive from profile (e.g., parent.school) since User lacks direct 'school'.

from collections import defaultdict

def generate_timetable_grid(student, timetable):
    """
    Returns a nested dict of lessons by weekday and time slot for the student's grade.
    Format: { 'monday': {1: [lesson1, lesson2], 2: [...] }, ... }
    """
    from collections import defaultdict

    grid = defaultdict(lambda: defaultdict(list))

    # Fix: use __in if streams is a RelatedManager
    student_streams = student.grade_level.streams.all()  # RelatedManager -> queryset

    lessons = Lesson.objects.filter(
        timetable=timetable,
        stream__in=student_streams
    ).select_related("subject", "teacher", "time_slot")

    for lesson in lessons:
        if lesson.day_of_week and lesson.time_slot:
            grid[lesson.day_of_week][lesson.time_slot.id].append(lesson)

    return grid

from django.utils.timezone import now
from datetime import timedelta
from django.db.models import Avg
from django.core.paginator import Paginator as _Paginator

@login_required
def parent_dashboard(request):
    parent = getattr(request.user, "parent", None)
    if not parent:
        messages.warning(request, "Parent profile not found. Please contact school admin.")
        return render(request, "school/parent/dashboard.html", {
            "child_data": [], "today": now().date(), "total_balance": 0,
            "unread_count": 0, "open_complaints": 0,
        })

    today = now().date()

    # All children linked to this parent via Student.parents M2M
    children = Student.objects.filter(parents=parent).select_related(
        'user', 'grade_level', 'stream', 'school'
    )

    unread_count = request.user.notifications.filter(is_read=False).count()
    open_complaints = Complaint.objects.filter(parent=parent, status='open').count()

    child_data = []
    total_balance = 0

    for student in children:
        school = student.school
        active_term = Term.objects.filter(school=school, is_active=True).first()

        # Attendance stats (all time for the school, not limited to active term)
        att_qs = Attendance.objects.filter(enrollment__student=student, enrollment__school=school)
        total_att = att_qs.count()
        present_att = att_qs.filter(status='P').count()
        att_rate = round((present_att / total_att * 100) if total_att else 0, 1)

        # Discipline
        discipline_count = DisciplineRecord.objects.filter(student=student, school=school).count()

        # Fee balance from FeeInvoice
        fee_invoices = FeeInvoice.objects.filter(student=student, school=school)
        student_balance = sum(inv.balance for inv in fee_invoices)
        total_balance += student_balance

        # Recent payments
        recent_payments = Payment.objects.filter(student=student, school=school).order_by('-paid_at', '-id')[:5]

        # Upcoming lessons
        upcoming_lessons = Lesson.objects.filter(
            l_enrollments__student=student,
            lesson_date__range=[today, today + timedelta(days=6)],
            is_canceled=False
        ).select_related("subject", "teacher__user", "time_slot").order_by(
            "lesson_date", "time_slot__start_time"
        )[:8]

        # Status
        if student.expelled:
            status_label = 'expelled'
            status_color = 'danger'
        elif student.suspended:
            status_label = 'suspended'
            status_color = 'warning'
        elif student_balance > 0:
            status_label = 'fee balance'
            status_color = 'warning'
        elif student.is_active:
            status_label = 'active'
            status_color = 'success'
        else:
            status_label = 'inactive'
            status_color = 'secondary'

        # Announcements for this school
        announcements = Announcement.objects.filter(
            school=school, audience__in=['all', 'parents']
        ).order_by('-is_pinned', '-created_at')[:3]

        child_data.append({
            "student": student,
            "school": school,
            "active_term": active_term,
            "total_att": total_att,
            "present_att": present_att,
            "att_rate": att_rate,
            "discipline_count": discipline_count,
            "fee_balance": student_balance,
            "recent_payments": recent_payments,
            "upcoming_lessons": upcoming_lessons,
            "status_label": status_label,
            "status_color": status_color,
            "announcements": announcements,
        })

    context = {
        "child_data": child_data,
        "today": today,
        "total_balance": total_balance,
        "unread_count": unread_count,
        "open_complaints": open_complaints,
        "parent": parent,
    }

    return render(request, "school/parent/dashboard.html", context)

from collections import defaultdict

from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from school.models import Lesson, TimeSlot, Enrollment, Session, Term
WEEKDAYS = [
    ("monday", "Monday"),
    ("tuesday", "Tuesday"),
    ("wednesday", "Wednesday"),
    ("thursday", "Thursday"),
    ("friday", "Friday"),
    ("saturday", "Saturday"),
    ("sunday", "Sunday"),
]



@login_required
def student_dashboard(request):
    user = request.user

    try:
        student = user.student
    except Student.DoesNotExist:
        logout(request)
        messages.error(request, "Student profile not found. Please contact your school administrator.")
        return redirect("userauths:sign-in")

    today = timezone.now().date()
    today_weekday = today.strftime("%A").lower()

    # ── ENROLLMENTS
    enrollments = (
        student.enrollments
        .filter(status="active")
        .select_related(
            "lesson__subject",
            "lesson__teacher__user",
            "lesson__time_slot",
            "lesson__stream"
        )
    )

    lesson_ids = enrollments.values_list("lesson_id", flat=True)

    # ── WEEK RANGE
    start_week = today - timedelta(days=today.weekday())
    end_week = start_week + timedelta(days=6)

    lessons_qs = (
        Lesson.objects
        .filter(
            id__in=lesson_ids,
            lesson_date__range=[start_week, end_week],
            timetable__school=student.school
        )
        .select_related(
            "subject",
            "teacher__user",
            "time_slot",
            "stream"
        )
        .order_by("day_of_week", "time_slot__start_time")
    )

    # ── TIME SLOTS
    time_slots = TimeSlot.objects.filter(school=student.school).order_by("start_time")
    for slot in time_slots:
        desc = (slot.description or "").lower()
        if "break" in desc:
            slot.slot_type = "break"
        elif "lunch" in desc:
            slot.slot_type = "lunch"
        elif "prep" in desc:
            slot.slot_type = "prep"
        else:
            slot.slot_type = "lesson"

    # ── TIMETABLE GRID
    timetable_grid = {key: {} for key, _ in WEEKDAYS}
    for lesson in lessons_qs:
        if not lesson.day_of_week or not lesson.time_slot:
            continue
        day = lesson.day_of_week.lower()
        timetable_grid[day].setdefault(lesson.time_slot.id, []).append(lesson)

    # ── ATTENDANCE HEATMAP
    attendance_records = (
        Attendance.objects
        .filter(
            enrollment__student=student,
            date__range=[start_week, end_week]
        )
        .values("date", "status")
    )
    attendance_map = {record["date"]: record["status"] for record in attendance_records}
    heatmap = []
    for i in range(7):
        date = start_week + timedelta(days=i)
        raw_status = attendance_map.get(date, "absent")
        status = str(raw_status).lower().strip() if raw_status else "absent"
        heatmap.append({
            "date": date,
            "status": status
        })

    # ── ASSIGNMENTS DUE
    student_subject_ids = (
        enrollments
        .values_list("lesson__subject_id", flat=True)
        .distinct()
    )
    assignments_due = (
        Assignment.objects
        .filter(
            subject_id__in=student_subject_ids,
            school=student.school,
            due_date__gte=today
        )
        .exclude(submissions__enrollment__student=student)
        .distinct()
        .count()
    )

    # ── STATS
    stats = [
        {
            "title": "This Week",
            "value": lessons_qs.count(),
            "icon": "bi-calendar-week",
            "color": "success",
            "url": ""
        },
        {
            "title": "Subjects",
            "value": enrollments.count(),
            "icon": "bi-book",
            "color": "primary",
            "url": ""
        },
        {
            "title": "Attendance",
            "value": f"{sum(1 for h in heatmap if h['status']=='present')}/{len(heatmap)}",
            "icon": "bi-bar-chart-line",
            "color": "info",
            "url": ""
        },
        {
            "title": "Assignments Due",
            "value": assignments_due,
            "icon": "bi-exclamation-circle",
            "color": "danger",
            "url": ""
        },
    ]

    # Fee balance
    from school.models import FeeInvoice
    fee_invoices = FeeInvoice.objects.filter(student=student, school=student.school)
    fee_balance = sum(inv.balance for inv in fee_invoices)

    # Complaints
    student_complaints = Complaint.objects.filter(student=student).order_by('-created_at')[:5]

    # Announcements — exclude expired/disabled ones
    from school.models import Announcement as AnnModel
    from django.db.models import Q
    announcements = AnnModel.objects.filter(
        school=student.school,
        audience__in=['all', 'students']
    ).filter(
        Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
    ).order_by('-is_pinned', '-created_at')[:3]

    context = {
        "student": student,
        "weekdays": WEEKDAYS,
        "time_slots": time_slots,
        "timetable_grid": timetable_grid,
        "stats": stats,
        "teachers": StaffProfile.objects.filter(position="teacher"),
        "subjects": Subject.objects.filter(id__in=lesson_ids),
        "heatmap": heatmap,
        "today_weekday": today_weekday,
        "grade": student.stream.grade if hasattr(student.stream, 'grade') else None,
        "fee_balance": fee_balance,
        "student_complaints": student_complaints,
        "announcements": announcements,
    }

    return render(request, "school/student/dashboard.html", context)

from datetime import timedelta
import datetime

from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from datetime import timedelta
from school.models import Lesson, Session

@login_required
def teacher_dashboard(request):
    user = request.user

    # ----------------------------
    # Authorization
    # ----------------------------
    try:
        teacher_profile = user.staffprofile
    except StaffProfile.DoesNotExist:
        return render(request, 'school/teacher/not_authorized.html', status=403)

    if teacher_profile.position != 'teacher':
        return render(request, 'school/teacher/not_authorized.html', status=403)

    school = teacher_profile.school
    today = timezone.localdate()
    now_time = timezone.localtime().time()

    # ----------------------------
    # Week calculation
    # ----------------------------
    start_date_str = request.GET.get('start_date')
    nav = request.GET.get('nav')
    try:
        start_date = timezone.datetime.strptime(start_date_str, "%Y-%m-%d").date() if start_date_str else today
    except ValueError:
        start_date = today

    if nav == 'prev':
        start_date -= timedelta(days=7)
    elif nav == 'next':
        start_date += timedelta(days=7)

    week_start = start_date - timedelta(days=start_date.weekday())
    week_end = week_start + timedelta(days=6)
    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # ----------------------------
    # Lessons
    # ----------------------------
    assigned_lessons = Lesson.objects.filter(
        teacher=teacher_profile,
        lesson_date__range=(week_start, week_end),
        timetable__school=school
    ).select_related('timetable__grade', 'subject', 'time_slot', 'stream').order_by(
        'lesson_date', 'time_slot__start_time'
    )

    # ----------------------------
    # Time slots & timetable grid
    # ----------------------------
    time_slots = sorted({lesson.time_slot for lesson in assigned_lessons if lesson.time_slot}, key=lambda ts: ts.start_time)
    timetable_by_slot = {}
    for lesson in assigned_lessons:
        if not lesson.time_slot:
            continue
        timetable_by_slot.setdefault(lesson.time_slot, {}).setdefault(lesson.lesson_date, []).append(lesson)

    timetable_grid = []
    for slot in time_slots:
        row = {'slot': slot, 'lessons_by_day': []}
        for day in week_days:
            lessons = timetable_by_slot.get(slot, {}).get(day, [])
            for lesson in lessons:
                # mark LIVE NOW
                lesson.live_now = lesson.lesson_date == today and slot.start_time <= now_time <= slot.end_time
                # disable attendance button if not happening today
                lesson.can_mark_attendance = lesson.lesson_date == today and slot.start_time <= now_time <= slot.end_time
            row['lessons_by_day'].append({'day': day, 'lessons': lessons})
        timetable_grid.append(row)

    # ----------------------------
    # Dashboard stats
    # ----------------------------
    discipline_count = DisciplineRecord.objects.filter(
        teacher=teacher_profile,
        school=school,
        date__range=(week_start, week_end)
    ).count()

    assignment_count = Assignment.objects.filter(
        subject__in=teacher_profile.subjects.all(),
        school=school
    ).count()

    today_lessons_count = assigned_lessons.filter(lesson_date=today).count()
    week_lessons_count = assigned_lessons.count()

    stats = [
        {'title': "Today's Lessons", 'value': today_lessons_count, 'icon': 'fa-chalkboard-teacher', 'color': 'success'},
        {'title': "Week's Lessons", 'value': week_lessons_count, 'icon': 'fa-calendar-week', 'color': 'success'},
        {'title': "Discipline", 'value': discipline_count, 'icon': 'fa-gavel', 'color': 'success'},
        {'title': "Assignments", 'value': assignment_count, 'icon': 'fa-tasks', 'color': 'success'},
    ]

    # ----------------------------
    # Attendance analytics per class/stream
    # ----------------------------
    attendance_analytics = Enrollment.objects.filter(
        lesson__teacher=teacher_profile,
        school=school,
        status='active',
        lesson__lesson_date__range=(week_start, week_end)
    ).values(
        grade_name=F('lesson__timetable__grade__name'),
        stream_name=F('lesson__stream__name')
    ).annotate(
        total_students=Count('student', distinct=True),
        attended=Count(
            Case(
                When(attendances__status='P', then=1)
            )
        ),
    ).annotate(
        attendance_rate=Cast(F('attended') * 100.0 / F('total_students'), FloatField())
    )

    context = {
        'school': school,
        'today': today,
        'now_time': now_time,
        'week_days': week_days,
        'timetable_grid': timetable_grid,
        'time_slots': time_slots,
        'stats': stats,
        'start_date': week_start,
        'end_date': week_end,
        'attendance_analytics': attendance_analytics,
    }

    return render(request, 'school/teacher/dashboard.html', context)


@login_required
def logoutView(request):
    logout(request)
    messages.success(request, "You have been logged out.")
    return redirect("userauths:sign-in")




@login_required
def change_passwordView(request):
    user = request.user

    # Pick base template and success redirect based on role
    if getattr(user, 'is_kiswate_admin', False) or getattr(user, 'is_kiswate_user', False):
        base_tpl = 'Dashboard/base.html'
        success_url = 'kiswate_digital_app:kiswate_admin_dashboard'
    elif getattr(user, 'is_principal', False) or getattr(user, 'is_deputy_principal', False) or getattr(user, 'is_admin', False):
        base_tpl = 'school/base.html'
        success_url = 'school:dashboard'
    elif getattr(user, 'is_teacher', False):
        base_tpl = 'school/teacher/base.html'
        success_url = 'userauths:teacher-dashboard'
    elif getattr(user, 'is_parent', False):
        base_tpl = 'school/parent/base.html'
        success_url = 'userauths:parent-dashboard'
    elif getattr(user, 'is_student', False):
        base_tpl = 'school/student/base.html'
        success_url = 'userauths:student-dashboard'
    else:
        base_tpl = 'school/base.html'
        success_url = 'userauths:sign-in'

    if request.method == 'POST':
        current  = request.POST.get('current_password', '')
        new_pw   = request.POST.get('new_password', '')
        confirm  = request.POST.get('confirm_password', '')

        if not user.check_password(current):
            messages.error(request, 'Current password is incorrect.')
        elif len(new_pw) < 8:
            messages.error(request, 'New password must be at least 8 characters.')
        elif new_pw != confirm:
            messages.error(request, 'New passwords do not match.')
        else:
            user.set_password(new_pw)
            user.save()
            update_session_auth_hash(request, user)
            messages.success(request, 'Password changed successfully.')
            return redirect(success_url)

    return render(request, 'users/change_password.html', {'base_template': base_tpl})



def generate_otp_code(length=6):
    import secrets
    return ''.join([str(secrets.randbelow(10)) for _ in range(length)])


def get_client_ip(request):
    """Get the client IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


def ForgotPasswordView(request):
    """
    Step 1: User enters email or phone to receive OTP
    """
    if request.method == "POST":
        identifier = request.POST.get("email")  # email or phone
        client_ip = get_client_ip(request)
        now = timezone.now()
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            user = User.objects.filter(
                Q(email__iexact=identifier) | Q(phone_number__iexact=identifier)
            ).first()

            if not user:
                messages.warning(request, "No user found with that email or phone number.")
                return redirect("userauths:forgot-password")

            # Count OTPs requested today by this user or IP
            otp_count = OTP.objects.filter(
                Q(user=user) | Q(user__isnull=True),  # optionally track by IP if needed
                created_at__gte=start_of_day,
                purpose="password_reset"
            ).count()

            if otp_count >= 3:
                messages.error(request, "You have reached the maximum of 3 OTP requests today. Try again tomorrow.")
                return redirect("userauths:forgot-password")

            # Generate OTP
            otp_code = generate_otp_code()
            expires_at = timezone.now() + timedelta(minutes=10)

            otp = OTP.objects.create(
                user=user,
                otp_code=otp_code,
                purpose="password_reset",
                expires_at=expires_at
            )

            # Send OTP via email or phone
            sent = False
            if user.email and '@' in identifier:
                subject = "Your Password Reset OTP"
                message = f"Your OTP code is {otp_code}. It will expire in 10 minutes."
                sent = send_email(user.email, subject, message)

            if not sent and user.phone_number:
                message = f"Your OTP code is {otp_code}. It will expire in 10 minutes."
                sent = _send_sms_via_eujim(user.phone_number, message)

            if sent:
                request.session['password_reset_user'] = user.id
                messages.success(request, "OTP sent successfully. Please check your email or SMS.")
                return redirect("userauths:verify-otp")
            else:
                messages.error(request, "Failed to send OTP. Please try again later.")
                return redirect("userauths:forgot-password")

        except Exception as e:
            messages.error(request, "An error occurred. Please try again.")
            return redirect("userauths:forgot-password")

    return render(request, "landing/forgot_password.html")


def VerifyOTPView(request):
    """
    Step 2: User enters OTP to verify and reset password
    """
    user_id = request.session.get("password_reset_user")
    if not user_id:
        messages.warning(request, "Session expired. Please try again.")
        return redirect("userauths:forgot-password")

    user = User.objects.filter(id=user_id).first()
    if not user:
        messages.warning(request, "User not found. Please try again.")
        return redirect("userauths:forgot-password")

    if request.method == "POST":
        otp_input = request.POST.get("otp")
        new_password = request.POST.get("password")
        confirm_password = request.POST.get("confirm_password")

        if new_password != confirm_password:
            messages.warning(request, "Passwords do not match.")
            return redirect("userauths:verify-otp")

        # Find the pending OTP for this user (ignore the code for now — check attempts first)
        otp = OTP.objects.filter(
            user=user,
            purpose="password_reset",
            is_used=False,
            expires_at__gt=timezone.now()
        ).order_by('-created_at').first()

        if not otp:
            messages.error(request, "Invalid or expired OTP. Please request a new one.")
            return redirect("userauths:forgot-password")

        # Brute-force guard: max 3 wrong attempts per OTP
        if otp.attempts >= 3:
            otp.is_used = True
            otp.save(update_fields=['is_used'])
            messages.error(request, "Too many wrong attempts. Please request a new OTP.")
            return redirect("userauths:forgot-password")

        if otp.otp_code != otp_input:
            otp.attempts += 1
            otp.save(update_fields=['attempts'])
            remaining = 3 - otp.attempts
            messages.error(request, f"Invalid OTP. {remaining} attempt(s) remaining.")
            return redirect("userauths:verify-otp")

        # Mark OTP as used
        otp.is_used = True
        otp.verified_at = timezone.now()
        otp.save(update_fields=['is_used', 'verified_at'])

        # Reset password
        user.set_password(new_password)
        user.save()

        # Clear session
        request.session.pop("password_reset_user", None)

        messages.success(request, "Password reset successful. Please login.")
        return redirect("userauths:sign-in")

    return render(request, "landing/verify_otp.html", {"user": user})