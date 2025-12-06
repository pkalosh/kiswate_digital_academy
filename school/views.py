from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from userauths.models import User
from .models import Grade, School, Parent,StaffProfile,Student, ScanLog, SmartID,Scholarship
import logging
from django.http import JsonResponse
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe
from django.core.mail import send_mail
import random
import string
from datetime import timedelta, date
from .services.timetable_generator import generate_for_stream
from collections import defaultdict
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponseForbidden
from datetime import timedelta
import datetime
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
import csv
from io import StringIO
import logging
from decimal import Decimal
from datetime import timedelta
import uuid
from userauths.models import User
from .models import (
    Grade, School, Parent, StaffProfile, Student, Subject, Enrollment, Timetable, Lesson,
    Session, Attendance, DisciplineRecord, SummaryReport, Notification, SmartID, ScanLog,
    Payment, Assignment, Submission, Role, Invoice, SchoolSubscription, SubscriptionPlan,
    ContactMessage, MpesaStkPushRequestResponse, MpesaPayment,GradeAttendance, Streams,Term, TimeSlot
)
from .forms import (
    # Assuming forms exist or need to be created; placeholders for now
    GradeForm,ParentCreationForm, ParentUpdateForm,StaffCreationForm, StaffUpdateForm,
    StudentCreationForm, StudentUpdateForm,SmartIDForm,GenerateTimetableForm,
    SubjectForm, EnrollmentForm, TimetableForm, LessonForm, SessionForm,
    AttendanceForm, DisciplineRecordForm, NotificationForm, PaymentForm,
    AssignmentForm, SubmissionForm, RoleForm, InvoiceForm, SchoolSubscriptionForm,
    ContactMessageForm,ParentStudentCreationForm,TermForm,TimeSlotForm,AssignParentStudentForm
)
from kiswate_digital_app.forms import StreamForm


logger = logging.getLogger(__name__)
# Create your views here.
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@login_required
def dashboard(request):
    # Determine the school based on user's profile
    school = None
    try:
        # If user is school admin
        school = request.user.school_admin_profile
    except AttributeError:
        try:
            # If user is staff
            school = request.user.staffprofile.school
        except AttributeError as e:
            logger.warning(f"Permission denied for user {request.user.email}: {e}")
            messages.error(
                request, 
                f"You do not have permission to access this page. (User: {request.user.email})"
            )
            return redirect('userauths:sign-in')  # redirect to login or some "no access" page

    # Aggregate data
    total_teachers = StaffProfile.objects.filter(school=school, position='teacher').count()
    total_students = Student.objects.filter(school=school).count()
    total_parents = Parent.objects.filter(school=school).count()
    total_discipline_cases = DisciplineRecord.objects.filter(school=school).count()
    total_timetable_slots = Timetable.objects.filter(school=school).count()

    recent_discipline = DisciplineRecord.objects.filter(school=school).order_by('-date')[:5]

    timetables = Timetable.objects.filter(school=school).select_related('grade').order_by('-year', 'term')

    timetables_with_lessons = []
    for tt in timetables:
        lessons_qs = Lesson.objects.filter(timetable=tt)\
                                   .select_related('subject', 'teacher')\
                                   .order_by('time_slot','lesson_date')[:20]
        lessons_count = Lesson.objects.filter(timetable=tt).count()
        timetables_with_lessons.append({
            'timetable': tt,
            'lessons': lessons_qs,
            'lessons_count': lessons_count,
            'active': timezone.now().date() >= tt.start_date and timezone.now().date() <= tt.end_date,
        })

    context = {
        "total_teachers": total_teachers,
        "total_students": total_students,
        "school": school,
        "total_parents": total_parents,
        "total_discipline_cases": total_discipline_cases,
        "total_timetable_slots": total_timetable_slots,
        "recent_discipline": recent_discipline,
        "timetables_with_lessons": timetables_with_lessons,
    }

    return render(request, "school/dashboard.html", context)


@login_required
def time_slot_list(request):
    school_profile = getattr(request.user, 'school_admin_profile', None)
    if not school_profile:
        messages.error(request, "Access denied.")
        return redirect('school:dashboard')
    school = school_profile
    slots = TimeSlot.objects.filter(school=school)
    form = TimeSlotForm(school=school)  # Empty form for modal
    return render(request, "school/time_slots.html", {
        "slots": slots,
        "school": school,
        "form": form,  # Enables {{ form.field }} in template
    })

@login_required
def time_slot_create(request):
    try:
        school_profile = request.user.school_admin_profile
        school = school_profile  # Fix: Get actual School instance
    except ObjectDoesNotExist:
        messages.error(request, "You must have a school admin profile to create time slots.")
        return redirect("school:time-slot-list")  # Or dashboard

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
    try:
        school_profile = request.user.school_admin_profile
        user_school = school_profile  # For permission check
    except ObjectDoesNotExist:
        messages.error(request, "You must have a school admin profile to edit time slots.")
        return redirect("school:time-slot-list")

    # Optional role check
    # user_role = get_user_role(request.user)
    # if user_role not in ['admin']:
    #     messages.error(request, "Insufficient permissions.")
    #     return redirect("school:time-slot-list")

    slot = get_object_or_404(TimeSlot, pk=pk, school=user_school)
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
    slot = get_object_or_404(TimeSlot, pk=pk, school=request.user.school_admin_profile)
    if request.method == "POST":
        slot.delete()
        messages.success(request, "Time slot deleted successfully.")
        return redirect("school:time-slot-list")

    return render(request, "school/time_slots.html", {"slot": slot})



def term_list(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')
    terms = Term.objects.filter(school=school)
    form = TermForm()
    return render(request, "school/terms.html", {"school": school, "terms": terms, "form": form})


@login_required
def create_term(request):
    try:
        school = request.user.school_admin_profile
    
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')
    
    form = TermForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        term = form.save(commit=False)
        term.school = school
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


# @login_required
# def school_users(request):
#     school = None
#     try:
#         school = request.user.school_admin_profile
#     except AttributeError:
#         try:
#             school = request.user.staffprofile.school
#         except AttributeError as e:
#             logger.warning(f"Permission denied for user {request.user.email}: {e}")
#             messages.error(
#                 request,
#                 f"You do not have permission to access this page. (User: {request.user.email})"
#             )
#             return redirect('userauths:sign-in')

#     # Querysets
#     teachers = StaffProfile.objects.filter(school=school, position="teacher")
#     other_staff = StaffProfile.objects.filter(school=school).exclude(position="teacher")
#     students = Student.objects.filter(school=school)
#     parents = Parent.objects.filter(school=school)

#     # Forms
#     staff_form = StaffCreationForm(school=school)
#     student_form = StudentCreationForm(school=school)
#     parent_form = ParentCreationForm(school=school)
#     parent_student_form = ParentStudentCreationForm(school=school)

#     combined_parent_student_form = {
#         "parent_form": ParentCreationForm(school=school),
#         "student_form": StudentCreationForm(school=school)
#     }

#     if request.method == "POST":

#         # Create Staff
#         if "create_staff" in request.POST:
#             form = StaffCreationForm(request.POST, request.FILES, school=school)
#             if form.is_valid():
#                 staff, password = form.save()
#                 messages.success(request, f"Staff created. Password: {password}")
#                 return redirect("school:school-users")
#             staff_form = form  

#         # Create Student
#         if "create_student" in request.POST:
#             form = StudentCreationForm(request.POST, request.FILES, school=school)
#             if form.is_valid():
#                 student, password = form.save()
#                 messages.success(request, "Student created successfully.")
#                 return redirect("school:school-users")
#             student_form = form

#         # Create Parent
#         if "create_parent" in request.POST:
#             form = ParentCreationForm(request.POST, request.FILES, school=school)
#             if form.is_valid():
#                 parent, password = form.save()
#                 messages.success(request, "Parent created successfully.")
#                 return redirect("school:school-users")
#             parent_form = form

#         # Create Parent + Student
#         if "create_parent_student" in request.POST:
#             parent__student_form = ParentStudentCreationForm(request.POST, request.FILES, school=school)

#             if parent__student_form.is_valid():
#                 parent, _ = parent_form.save()
#                 student, _ = student_form.save()
#                 student.parents.add(parent)

#                 messages.success(request, "Parent + Student created successfully.")
#                 return redirect("school:school-users")

#             parent__student_form = parent__student_form

#         # Assign Student
#         if "assign_student" in request.POST:
#             parent = Parent.objects.get(id=request.POST.get("parent_id"), school=school)
#             student = Student.objects.get(id=request.POST.get("student_id"), school=school)
#             student.parents.add(parent)

#             messages.success(request, "Student assigned to parent.")
#             return redirect("school:school-users")

#     context = {
#         "teachers": teachers,
#         "other_staff": other_staff,
#         "students": students,
#         "parents": parents,

#         "staff_form": staff_form,
#         "student_form": student_form,
#         "parent_form": parent_form,

#         "combined_parent_student_form": combined_parent_student_form,
#         "parent_student_form": parent_student_form,

#         "assign_students": students,
#         "assign_parents": parents,
#     }

#     return render(request, "school/staff.html", context)


def paginate(request, queryset, per_page=10):
    """Helper for pagination (implement as needed)."""
    from django.core.paginator import Paginator
    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)

@login_required
def school_users(request):
    """
    Unified view for managing school members (teachers, staff, students, parents).
    Handles listing with search/filter across tabs.
    Handles creation via POST from modals (separate forms for flexibility).
    """
    school = None
    try:
        # Fix: Get the actual School instance from admin profile
        school = request.user.school_admin_profile.school
    except AttributeError:
        try:
            school = request.user.staffprofile.school
        except AttributeError as e:
            logger.warning(f"Permission denied for user {request.user.email}: {e}")
            messages.error(
                request,
                f"You do not have permission to access this page. (User: {request.user.email})"
            )
            return redirect('userauths:sign-in')

    # Common search query
    query = request.GET.get('q', '')

    # Fetch teachers (StaffProfile with position='teacher')
    teachers = StaffProfile.objects.filter(school=school, position='teacher').select_related('user').order_by('-user__created_at')
    if query:
        teachers = teachers.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )
    teachers_page = paginate(request, teachers)

    # Fetch other staff
    other_staff = StaffProfile.objects.filter(school=school).exclude(position='teacher').select_related('user').order_by('-user__created_at')
    if query:
        other_staff = other_staff.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query)
        )
    staff_page = paginate(request, other_staff)

    # Fetch students
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
    students_page = paginate(request, students)

    # Fetch parents
    parents = Parent.objects.filter(school=school).select_related('user').order_by('-user__created_at')
    if query:
        parents = parents.filter(
            Q(user__first_name__icontains=query) |
            Q(user__last_name__icontains=query) |
            Q(parent_id__icontains=query) |
            Q(phone__icontains=query) |
            Q(user__email__icontains=query)
        )
    parents_page = paginate(request, parents)

    # Bound update forms for modals
    student_update_forms = {st.id: StudentUpdateForm(instance=st) for st in students}
    parent_update_forms = {p.id: ParentUpdateForm(instance=p) for p in parents}
    staff_update_forms = {s.id: StaffUpdateForm(instance=s) for s in list(other_staff) + list(teachers)}

    context = {
        'school': school,
        'query': query,
        'teachers': teachers,
        'teachers_page': teachers_page,
        'other_staff': other_staff,
        'staff_page': staff_page,
        'students': students,
        'students_page': students_page,
        'parents': parents,
        'parents_page': parents_page,
        # Forms - pass school for queryset filtering
        'student_update_forms': student_update_forms,
        'parent_update_forms': parent_update_forms,
        'staff_update_forms': staff_update_forms,
        'student_form': StudentCreationForm(school=school),
        'parent_form': ParentCreationForm(school=school),
        'parent_student_form': ParentStudentCreationForm(school=school),
        'assign_form': AssignParentStudentForm(school=school),
        'staff_form': StaffCreationForm(school=school),
    }

    # Handle POST for creations
    if request.method == 'POST':
        action = request.POST.get('action', '')

        if action == 'create_student':
            form = StudentCreationForm(request.POST, request.FILES, school=school)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Unpack tuple from form.save() (student, password)
                        student, password = form.save()
                        # Ensure school_id is set (form should already set via self.school)
                        if not student.school_id:
                            student.school_id = school.id
                            student.save(update_fields=['school_id'])
                        messages.success(
                            request,
                            f'Successfully created Student "{student.user.get_full_name()}" ({student.student_id}). '
                            f'Grade: {student.grade_level}. '
                            f'Temporary password: <strong>{password}</strong>. '
                            f'Email sent: {"Yes" if form.cleaned_data.get("send_email") else "No"}.'
                        )
                        # Map parents if selected
                        for parent in form.cleaned_data.get('parents', []):
                            student.parents.add(parent)
                        return redirect('school:school-users')
                except Exception as e:
                    messages.error(request, f"Failed to create Student: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors below.")
                context['student_form'] = form

        elif action == 'create_parent':
            form = ParentCreationForm(request.POST, request.FILES, school=school)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Unpack tuple
                        parent, password = form.save()
                        # Ensure school_id is set
                        if not parent.school_id:
                            parent.school_id = school.id
                            parent.save(update_fields=['school_id'])
                        messages.success(
                            request,
                            f'Successfully created Parent "{parent.user.get_full_name()}" ({parent.parent_id}). '
                            f'Temporary password: <strong>{password}</strong>. '
                            f'Email sent: {"Yes" if form.cleaned_data.get("send_email") else "No"}.'
                        )
                        return redirect('school:school-users')
                except Exception as e:
                    messages.error(request, f"Failed to create Parent: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors below.")
                context['parent_form'] = form

        elif action == 'create_parent_student':
            form = ParentStudentCreationForm(request.POST, request.FILES, school=school)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Unpack 4-tuple
                        parent, student, parent_password, student_password = form.save()
                        # Ensure school_id on both (form should set via self.school)
                        if not parent.school_id:
                            parent.school_id = school.id
                            parent.save(update_fields=['school_id'])
                        if not student.school_id:
                            student.school_id = school.id
                            student.save(update_fields=['school_id'])
                        # Link
                        student.parents.add(parent)
                        messages.success(
                            request,
                            f'Successfully created Parent "{parent.user.get_full_name()}" and Student "{student.user.get_full_name()}". '
                            f'They have been linked. Emails sent: {"Yes" if form.cleaned_data.get("send_email") else "No"}.'
                        )
                        return redirect('school:school-users')
                except Exception as e:
                    messages.error(request, f"Failed to create Parent and Student: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors below.")
                context['parent_student_form'] = form

        elif action == 'create_staff':
            form = StaffCreationForm(request.POST, request.FILES, school=school)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        # Unpack tuple
                        staff, password = form.save()
                        # Ensure school_id is set
                        if not staff.school_id:
                            staff.school_id = school.id
                            staff.save(update_fields=['school_id'])
                        messages.success(
                            request,
                            f'Successfully created Staff "{staff.user.get_full_name()}". '
                            f'Temporary password: <strong>{password}</strong>. '
                            f'Email sent: {"Yes" if form.cleaned_data.get("send_email") else "No"}.'
                        )
                        return redirect('school:school-users')
                except Exception as e:
                    messages.error(request, f"Failed to create Staff: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors below.")
                context['staff_form'] = form

        elif action == 'assign_parent_student':
            form = AssignParentStudentForm(request.POST, school=school)
            if form.is_valid():
                try:
                    with transaction.atomic():
                        parent = form.cleaned_data['parent']
                        student = form.cleaned_data['student']
                        student.parents.add(parent)
                        messages.success(request, f'Successfully assigned student "{student.user.get_full_name()}" to parent "{parent.user.get_full_name()}".')
                        return redirect('school:school-users')
                except Exception as e:
                    messages.error(request, f"Failed to assign: {str(e)}")
            else:
                messages.error(request, "Please correct the form errors below.")
                context['assign_form'] = form

    return render(request, 'school/staff.html', context)


@login_required
def update_student(request, pk):
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
            print(form.errors)
            messages.error(request, "Please correct the form errors below.")
    else:
        form = StudentUpdateForm(instance=student, school=school)
    context = {'form': form, 'student': student}
    return render(request, 'school/staff.html', context)

# Similar for Parent Update
@login_required
def update_parent(request, pk):
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
    context = {'form': form, 'parent': parent}
    return render(request, 'school/staff.html', context)

# Similar for Staff Update
@login_required
def update_staff(request, pk):
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
    context = {'form': form, 'staff': staff}
    return render(request, 'school/staff.html', context)

# Delete Views
@login_required
def delete_student(request, pk):
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
    school = getattr(request.user, 'school_admin_profile', None) or getattr(request.user, 'staffprofile', None).school
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
def generate_timetable_view(request):
    """
    Admin endpoint that processes GenerateTimetableForm and triggers generation.
    """
    if request.method == 'POST':
        form = GenerateTimetableForm(request.POST)
        if form.is_valid():
            scope = form.cleaned_data['scope']
            school = form.cleaned_data['school']
            grade = form.cleaned_data.get('grade')
            time_slot = form.cleaned_data.get('time_slot')
            stream = form.cleaned_data.get('stream')
            overwrite = form.cleaned_data.get('overwrite')

            # pick term: active term for that school
            term = Term.objects.filter(school=school, is_active=True).first()
            if not term:
                messages.error(request, "No active term defined for the selected school.")
                return redirect(request.META.get('HTTP_REFERER', '/'))

            created_total = 0
            errors = []
            if scope == 'school':
                streams_qs = Streams.objects.filter(grade__school=school)
                for st in streams_qs:
                    # create timetable if not exists
                    tt, created = Timetable.objects.get_or_create(
                        school=school, grade=st.grade, stream=st, term=term, year=term.start_date.year,
                        defaults={'start_date': term.start_date, 'end_date': term.end_date}
                    )
                    try:
                        created_lessons = generate_for_stream(tt, overwrite=overwrite)
                        created_total += len(created_lessons)
                    except Exception as e:
                        errors.append(str(e))
            elif scope == 'grade':
                if not grade:
                    messages.error(request, "Please select a grade.")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                streams_qs = Streams.objects.filter(grade=grade)
                for st in streams_qs:
                    tt, created = Timetable.objects.get_or_create(
                        school=school, grade=grade, stream=st, term=term, year=term.start_date.year,
                        defaults={'start_date': term.start_date, 'end_date': term.end_date}
                    )
                    try:
                        created_lessons = generate_for_stream(tt, overwrite=overwrite)
                        created_total += len(created_lessons)
                    except Exception as e:
                        errors.append(str(e))
            else:  # stream
                if not stream:
                    messages.error(request, "Please select a stream.")
                    return redirect(request.META.get('HTTP_REFERER', '/'))
                tt, created = Timetable.objects.get_or_create(
                    school=school, grade=stream.grade, stream=stream, term=term, year=term.start_date.year,
                    defaults={'start_date': term.start_date, 'end_date': term.end_date}
                )
                try:
                    created_lessons = generate_for_stream(tt, overwrite=overwrite)
                    created_total += len(created_lessons)
                except Exception as e:
                    errors.append(str(e))

            if created_total:
                messages.success(request, f"Timetable generated — {created_total} lessons created.")
            if errors:
                messages.warning(request, "Some errors: " + "; ".join(errors))
            return redirect(request.META.get('HTTP_REFERER', '/'))
    else:
        form = GenerateTimetableForm()

    return render(request, 'school/generate_timetable.html', {'form': form})


@login_required
def view_timetable_week(request):
    """
    Weekly timetable view: Admin, Teacher, Student, Parent
    Handles recurring lessons (day_of_week) and one-off lessons (lesson_date)
    """
    user = request.user
    school_id = user.school_admin_profile.id 

    # Focus date
    date_str = request.GET.get('date')
    try:
        focus_date = date.fromisoformat(date_str) if date_str else timezone.localdate()
    except ValueError:
        focus_date = timezone.localdate()

    # Week range: Monday → Friday
    monday = focus_date - timedelta(days=focus_date.weekday())
    week_days = [monday + timedelta(days=i) for i in range(5)]

    # Map Python weekday to Lesson.day_of_week
    WEEKDAY_MAP = {0:'monday',1:'tuesday',2:'wednesday',3:'thursday',4:'friday',5:'saturday',6:'sunday'}

    # Base lessons queryset
    lessons_qs = Lesson.objects.select_related('timetable','subject','teacher','stream','time_slot')
    if is_school_admin(user):
        if school_id:
            lessons_qs = lessons_qs.filter(timetable__school_id=school_id)
    elif hasattr(user,'staffprofile'):
        lessons_qs = lessons_qs.filter(teacher=user.staffprofile)
    elif hasattr(user,'student'):
        lessons_qs = lessons_qs.filter(stream=user.student.stream)
    elif hasattr(user,'parent'):
        child_stream_ids = user.parent.children.values_list('stream_id', flat=True)
        lessons_qs = lessons_qs.filter(stream_id__in=child_stream_ids)
    else:
        lessons_qs = lessons_qs.none()

    # Time slots for the school
    if school_id:
        school = get_object_or_404(School, id=school_id)
        print(f"school: {school.name}")
        time_slots = TimeSlot.objects.filter(school=school).order_by('start_time')

    else:
        time_slots = TimeSlot.objects.none()

    # Build table: {date: {slot: [lessons]}}
    table_data = {}
    for d in week_days:
        weekday_str = WEEKDAY_MAP[d.weekday()]
        table_data[d] = {}
        for slot in time_slots:
            # Include one-off lessons for this date
            lessons_on_date = lessons_qs.filter(time_slot=slot, lesson_date=d)
            print("lesson",lessons_on_date)
            # Include recurring lessons for this weekday
            lessons_recurring = lessons_qs.filter(time_slot=slot, day_of_week=weekday_str, lesson_date__isnull=True)
            table_data[d][slot] = lessons_on_date | lessons_recurring

    context = {
        'week_days': week_days,
        'time_slots': time_slots,
        'table_data': table_data,
        'focus_date': focus_date,
    }
    print(context)
    return render(request, 'school/timetable_week.html', context)


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
    week_days = [monday + timedelta(days=i) for i in range(5)]

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
    print("Accessing grades view as user:", request.user)  # Keep for console
    logger.info(f"Accessing grades view as user: {request.user.email} (ID: {request.user.id})")
    try:
        school = request.user.school_admin_profile
        logger.info(f"User's school: {school.name} (ID: {school.id})")
        print("User's school:", school.name)  # Keep for console
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    form = GradeForm(school=school)
    stream_form = StreamForm()

    # Fetch grades for the school, with search/filter
    query = request.GET.get('q', '')
    grades = Grade.objects.filter(school=school, is_active=True)
    streams = Streams.objects.filter(school=school, is_active=True)
    if query:
        grades = grades.filter(Q(name__icontains=query) | Q(code__icontains=query))

    context = {
        'grades': grades,
        'form': form,
        'stream_form': stream_form,
        'school': school,
        'streams': streams,
        'query': query,
    }
    return render(request, "school/grade.html", context)

@login_required
def smartid_list(request):

    school = getattr(request.user, "school_admin_profile", None)

    if not isinstance(school, School):
        logger.warning(f"Permission denied for user {request.user.email}")
        messages.error(request, "You do not have permission to access Smart IDs.")
        return redirect("school:dashboard")

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
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
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
    print((logs))
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
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
        return redirect('school:dashboard')

    if request.method != 'POST':
        return redirect('school:school-grades')

    form = GradeForm(request.POST, school=school)
    if form.is_valid():
        grade = form.save(commit=False)
        grade.school = school
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
def grade_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError as e:
        logger.warning(f"Permission denied for user {request.user.email}: {e}")
        messages.error(request, f"You do not have permission to access this page. (User: {request.user.email})")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        form = ParentCreationForm(request.POST, request.FILES, school=school)
        print(form.errors)
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:parent_list_create')

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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:parent_list_create')

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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
            print(form.errors)  # <-- DEBUG: see why it's invalid
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:staff_list_create')

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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:staff_list_create')

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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:student_list_create')

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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:student_list_create')

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
def school_finance(request):
    return render(request, "school/finance.html", {})

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
        print(school)
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
    try:
        school = request.user.school_admin_profile
        print(school)
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    subjects = Subject.objects.filter(school=school).select_related('grade')
    if query:
        subjects = subjects.filter(
            Q(name__icontains=query) | Q(code__icontains=query) | Q(teacher__user__first_name__icontains=query)
        )
    
    form = SubjectForm(school=school)
    context = {
        'subjects': subjects,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/subject.html', context)

@login_required
def subject_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-subjects')
    
    subject = get_object_or_404(Subject, pk=pk, school=school)
    if request.method == 'POST':
        subject.is_active = False  # Soft delete
        subject.save()
        messages.success(request, f'Subject "{subject.name}" deactivated.')
        return redirect('school:school-subjects')
    return redirect('school:school-subjects')

@login_required
def school_enrollment(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-enrollment')
    
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
    """
    List all timetables with search/filter by grade, term, year.
    Displays lessons/sessions under each timetable.
    """
    try:
        school = request.user.school_admin_profile  # Adjust based on your User extension
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    timetables = Timetable.objects.filter(school=school).select_related('grade').order_by('-year', 'term')
    if query:
        timetables = timetables.filter(
            Q(grade__name__icontains=query) | Q(term__icontains=query) | Q(year__icontains=query)
        )
    
    # Pagination
    paginator = Paginator(timetables, 10)
    page_number = request.GET.get('page')
    timetables_page = paginator.get_page(page_number)
    
    # For each timetable, fetch sample lessons (limit to avoid overload)
    timetables_with_lessons = []
    for tt in timetables_page:
        lessons_qs = Lesson.objects.filter(timetable=tt).select_related('subject', 'teacher').order_by('date', 'start_time')[:20]
        lessons_count = Lesson.objects.filter(timetable=tt).count()
        timetables_with_lessons.append({
            'timetable': tt,
            'lessons': lessons_qs,
            'lessons_count': lessons_count,
            'active': timezone.now().date() >= tt.start_date and timezone.now().date() <= tt.end_date,
        })

    
    form = TimetableForm(school=school)
    context = {
        'timetables': timetables_with_lessons,
        'form': form,
        'school': school,
        'query': query,
    }
    return render(request, 'school/timetable.html', context)

@login_required
def timetable_create(request):
    """
    Create a new timetable for a grade/term/year.
    Validates unique_together and date range.
    """
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
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
    lessons = Lesson.objects.filter(teacher=teacher).select_related('subject', 'timetable').order_by('lesson_date')
    
    query = request.GET.get('q', '')
    if query:
        lessons = lessons.filter(
            Q(subject__name__icontains=query) |
            Q(timetable__grade__name__icontains=query) |
            Q(stream=query)
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    timetable = get_object_or_404(Timetable, id=timetable_id, school=school)
    lessons = timetable.lessons.select_related('subject', 'teacher').order_by('date', 'start_time')
    
    query = request.GET.get('q', '')
    if query:
        lessons = lessons.filter(
            Q(subject__name__icontains=query) |
            Q(teacher__user__first_name__icontains=query) |
            Q(teacher__user__last_name__icontains=query) |
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
    return render(request, 'school/lessons.html', context)


@login_required
def lesson_create(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
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


@login_required
def lesson_edit(request, lesson_id):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    
    if request.method == 'POST':
        form = LessonForm(request.POST, instance=lesson, school=school)
        if form.is_valid():
            form.save()
            messages.success(request, f'Lesson for {lesson.subject} on {lesson.date} updated.')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:lesson-list', timetable_id=lesson.timetable.id)


@login_required
def lesson_delete(request, lesson_id):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-timetable')
    
    lesson = get_object_or_404(Lesson, id=lesson_id, timetable__school=school)
    timetable_id = lesson.timetable.id
    lesson.delete()
    messages.success(request, "Lesson deleted successfully.")
    return redirect('school:lesson-list', timetable_id=timetable_id)

@login_required
def school_virtual_classes(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    if request.method == 'POST':
        session.delete()
        messages.success(request, f"Session '{session.title}' deleted successfully.")
    return redirect('school:school-sessions')



def auto_mark_attendance_from_scan(student, grade, scan_log=None):
    """
    Auto-mark attendance using the given scan log.
    Only creates GradeAttendance if the scan came from a device ID starting with 'grade'.
    If scan_log is None, use the latest ScanLog for the student.
    """
    if not scan_log:
        scan_log = ScanLog.objects.filter(
            smart_id__profile=student.user,
            smart_id__school=grade.school
        ).order_by('-scanned_at').first()

    if not scan_log:
        print(f"⚠️ No scan found for {student.user.get_full_name()}")
        return

    # Only mark if device_id starts with 'grade'
    if scan_log.device_id.lower().startswith('grade'):
        GradeAttendance.objects.create(
            student=student,
            grade=grade,
            status='P',
            scan_log=scan_log
        )
        print(f"✅ Attendance saved for {student.user.get_full_name()} at {scan_log.scanned_at}")
    else:
        print(f"⚠️ Scan ignored (device_id: {scan_log.device_id}) for {student.user.get_full_name()}")



@login_required
def teacher_class_attendance_report(request, grade_id):
    school = request.user.staffprofile.school
    grade = get_object_or_404(Grade, id=grade_id, school=school)

    students = grade.students.all()
    attendance_summary = []

    # Handle POST save
    if request.method == 'POST':
        for student in students:
            status_key = f"status_{student.id}"
            status = request.POST.get(status_key)

            if status:
                # Update latest attendance OR create new if none exists
                latest = GradeAttendance.objects.filter(student=student, grade=grade).order_by('-recorded_at').first()
                if latest:
                    latest.status = status
                    latest.save()
                else:
                    GradeAttendance.objects.create(student=student, grade=grade, status=status)
        
        messages.success(request, "Attendance saved successfully!")
        return redirect(request.path)

    # GET → Show UI
    for student in students:

        # Auto-mark using ScanLog (creates new records for each scan)
        auto_mark_attendance_from_scan(student, grade)

        # Get latest attendance for display
        latest = GradeAttendance.objects.filter(student=student, grade=grade).order_by('-recorded_at').first()

        attendance_summary.append({
            'student': student,
            'existing': latest
        })

    paginator = Paginator(attendance_summary, 50)
    page = request.GET.get('page')
    attendance_summary = paginator.get_page(page)

    context = {
        'grade': grade,
        'attendance_summary': attendance_summary,
        'school': school,
    }
    return render(request, 'school/teacher/class_attendance_report.html', context)

@login_required
def school_attendance(request):
    # Ensure this is a school admin
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')

    # Base queryset
    attendances = Attendance.objects.filter(
        enrollment__school=school
    ).select_related(
        'enrollment__student__user',
        'enrollment__subject',
        'marked_by__user'
    )

    # ----------- FILTERS -----------
    date_filter = request.GET.get('date')
    subject_id = request.GET.get('subject')
    grade_id = request.GET.get('grade')
    stream_id = request.GET.get('stream')
    status_filter = request.GET.get('status')

    if date_filter:
        attendances = attendances.filter(date=date_filter)

    if subject_id:
        attendances = attendances.filter(enrollment__subject_id=subject_id)

    if grade_id:
        attendances = attendances.filter(enrollment__student__grade_id=grade_id)

    if stream_id:
        attendances = attendances.filter(enrollment__student__stream_id=stream_id)

    if status_filter:
        attendances = attendances.filter(status=status_filter)

    # ----------- AGGREGATIONS -----------

    # Individual status counts
    count_P = attendances.filter(status="P").count()
    count_ET = attendances.filter(status="ET").count()
    count_UT = attendances.filter(status="UT").count()
    count_EA = attendances.filter(status="EA").count()
    count_UA = attendances.filter(status="UA").count()
    count_IB = attendances.filter(status="IB").count()
    count_18 = attendances.filter(status="18").count()
    count_20 = attendances.filter(status="20").count()

    # ----------- Grade Stats -----------
    grade_attendance = (
        attendances.values(
            'enrollment__student__grade_level__name',
            'enrollment__student__stream__name'
        )
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status="P")),
            tardy=Count('id', filter=Q(status__in=["ET", "UT"])),
            absent=Count('id', filter=Q(status__in=["EA", "UA"])),
        )
        .order_by('enrollment__student__grade_level__name')
    )

    # ----------- Subject Stats -----------
    subject_attendance = (
        attendances.values('enrollment__subject__name')
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status="P")),
            absent=Count('id', filter=Q(status__in=["EA", "UA"])),
            behavior=Count('id', filter=Q(status="IB")),
        )
        .order_by('enrollment__subject__name')
    )

    # ----------- Student Stats -----------
    student_attendance = (
        attendances.values(
            'enrollment__student__user__first_name',
            'enrollment__student__user__last_name',
        )
        .annotate(
            total=Count('id'),
            present=Count('id', filter=Q(status="P")),
            tardy=Count('id', filter=Q(status__in=["ET", "UT"])),
            absent=Count('id', filter=Q(status__in=["EA", "UA"])),
        )
        .order_by('-total')
    )

    # ----------- Daily Trend for Charts -----------
    daily_data = (
        attendances.values('date')
        .annotate(count=Count('id'))
        .order_by('date')
    )

    # ----------- Pie Chart Data (status distribution) -----------
    status_pie = (
        attendances.values('status')
        .annotate(count=Count('id'))
        .order_by('status')
    )

    # ----------- Subject Bar Chart Data -----------
    subject_bar = (
        attendances.values('enrollment__subject__name')
        .annotate(present=Count('id', filter=Q(status="P")))
        .order_by('enrollment__subject__name')
    )

    # Pagination
    paginator = Paginator(attendances.order_by('-date', '-marked_at'), 50)
    page = request.GET.get('page')
    attendances_page = paginator.get_page(page)

    # Filter dropdowns
    subjects = Subject.objects.filter(school=school).order_by('name')
    grades = Grade.objects.filter(school=school).order_by('-id')
    streams = Streams.objects.filter(school=school).order_by('name')

    # Core context
    context = {
        'school': school,
        'attendances': attendances_page,
        'subjects': subjects,
        'grades': grades,
        'streams': streams,
        'total_attendance': attendances.count(),
    }

    # Add stats
    context.update({
        "stats": {
            "P": count_P,
            "ET": count_ET,
            "UT": count_UT,
            "EA": count_EA,
            "UA": count_UA,
            "IB": count_IB,
            "SUSP": count_18,
            "EXPEL": count_20,
        },
        "grade_stats": grade_attendance,
        "subject_stats": subject_attendance,
        "student_stats": student_attendance,
        "daily_trend": daily_data,
        "status_pie": status_pie,
        "subject_bar": subject_bar,
    })

    return render(request, 'school/attendance.html', context)




@login_required
def attendance_mark(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user.staffprofile)
    if request.method == 'POST':
        # Bulk mark or individual; assume formset or bulk logic
        enrollments = Enrollment.objects.filter(subject=lesson.subject, status='active')
        for enrollment in enrollments:
            status = request.POST.get(f'status_{enrollment.id}', 'P')
            Attendance.objects.update_or_create(
                enrollment=enrollment,
                lesson=lesson,
                defaults={'status': status, 'marked_by': request.user.staffprofile}
            )
        messages.success(request, f'Attendance marked for {lesson.subject} on {lesson.date}.')
        return redirect('school:school-attendance')
    return redirect('school:school-attendance')

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
    return redirect('school:school-attendance')

@login_required
def attendance_delete(request, attendance_id):
    attendance = get_object_or_404(Attendance, id=attendance_id, lesson__teacher=request.user.staffprofile)
    if request.method == 'POST':
        attendance.delete()
        messages.success(request, f'Attendance for {attendance.enrollment.student} deleted successfully.')
    return redirect('school:school-attendance')
# Summary view
@login_required
def attendance_summary(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    attendances = Attendance.objects.filter(lesson__teacher=request.user.staffprofile).select_related('enrollment__student', 'lesson')
    
    paginator = Paginator(attendances, 50)
    page = request.GET.get('page')
    attendances_page = paginator.get_page(page)
    
    context = {
        'attendances': attendances_page,
        'school': school,
    }
    return render(request, 'school/teacher/attendance.html', context)

from django.db import IntegrityError
@login_required
def teacher_attendance_mark(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id, teacher=request.user.staffprofile)
    
    # Filter by subject, stream, and active (prevents over-marking wrong students)
    students = Enrollment.objects.filter(
        subject=lesson.subject,
        status='active'
    ).select_related('student__user')  # Optimize for template
    
    if not students.exists():
        messages.warning(request, f'No active students found for {lesson.subject} in {lesson.stream}.')
        return redirect('school:teacher-attendance-mark', lesson_id=lesson.id)  # Or to list view
    
    # Pre-load existing attendance for status pre-filling (filter by lesson/date)
    attendance_qs = Attendance.objects.filter(
        enrollment__in=students,
        # If lesson FK: lesson=lesson
        # Else: date=lesson.lesson_date  # Fallback for date-based
    )
    attendance_dict = {att.enrollment.id: att for att in attendance_qs}
    
    if request.method == 'POST':
        updated_count = 0
        for enrollment in students:
            status = request.POST.get(f'status_{enrollment.id}', 'P')
            if status not in ['P', 'A', 'L']:  # Basic validation; expand to choices
                status = 'P'  # Fallback
            
            try:
                # If Attendance has lesson FK (recommended):
                Attendance.objects.update_or_create(
                    enrollment=enrollment,
                    defaults={
                        'status': status,
                        'marked_by': request.user.staffprofile,
                        'date': lesson.lesson_date,  # Fixes the NULL error
                    }
                )
                # Else (date-based uniqueness, no lesson FK):
                # Attendance.objects.update_or_create(
                #     enrollment=enrollment,
                #     date=lesson.lesson_date,
                #     defaults={'status': status, 'marked_by': request.user.staffprofile}
                # )
                updated_count += 1
            except IntegrityError:
                # Rare: If still fails (e.g., other constraints), log and skip
                messages.error(request, f'Error marking {enrollment.student.user.get_full_name}.')
                continue
        
        messages.success(request, f'Attendance marked for {updated_count} students on {lesson.lesson_date}.')
        return redirect('school:teacher-attendance-mark', lesson_id=lesson.id)  # Reloads form with updates
    
    context = {
        'school': request.user.staffprofile.school,
        'lesson': lesson,
        'students': students,
        'attendance_dict': attendance_dict,
    }
    return render(request, 'school/teacher/attendance_mark.html', context)

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
        school = request.user.staffprofile.school
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('userauths:teacher-dashboard')
    
    period_start = request.GET.get('start')
    period_end = request.GET.get('end')
    if not period_start or not period_end:
        period_start = timezone.now().date().replace(day=1)
        period_end = timezone.now().date()
    
    lessons = Lesson.objects.filter(lesson_date__range=[period_start, period_end], teacher=request.user.staffprofile)
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
            messages.success(request, f'Discipline record for {record.student} created.')
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    query = request.GET.get('q', '')
    records = DisciplineRecord.objects.filter(school=school).select_related('student', 'teacher')
    if query:
        records = records.filter(
            Q(student__user__first_name__icontains=query) | Q(description__icontains=query)
        )
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
    if request.method == 'POST':
        form = DisciplineRecordForm(request.POST, school=school)
        if form.is_valid():
            record = form.save(commit=False)
            record.school = school
            record.teacher = request.user.staffprofile
            record.reported_by = request.user
            record.save()
            
            # Trigger notification to first parent (User instance)
            parent_user = record.student.parents.first().user if record.student.parents.exists() else None
            if parent_user:
                Notification.objects.create(
                    recipient=parent_user,
                    title="Discipline Incident Logged",
                    message=f"An incident of {record.incident_type} has been recorded.",
                    related_discipline=record,
                    school=school
                )

            messages.success(request, f'Discipline record for {record.student} created.')
            return redirect('school:school-discipline')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{form.fields[field].label}: {error}")
    return redirect('school:school-discipline')

# Similar edit/delete, with validation for severity/frequency...

@login_required
def discipline_edit(request, pk):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-discipline')
    
    record = get_object_or_404(DisciplineRecord, id=pk, school=school)
    if request.method == 'POST':
        record.delete()
        messages.success(request, f'Discipline record for {record.student} deleted.')
    return redirect('school:school-discipline')


@login_required
def school_notifications(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    notifications = Notification.objects.filter(school=school).order_by('-sent_at')
    # Mark as read for current user if applicable
    if request.user.is_authenticated:
        notifications.filter(recipient=request.user, is_read=False).update(is_read=True)
    
    form = NotificationForm(school=school)
    context = {
        'notifications': notifications,
        'form': form,
        'school': school,
    }
    return render(request, 'school/notification.html', context)

@login_required
def notification_send(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:school-notifications')
    
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    
    query = request.GET.get('q', '')
    submissions = Submission.objects.filter(school=school).select_related('enrollment__student', 'assignment')
    if query:
        submissions = submissions.filter(Q(enrollment__student__user__first_name__icontains=query))
    
    context = {
        'submissions': submissions,
        'school': school,
        'query': query,
    }
    return render(request, 'school/submission.html', context)

# Grade submission (update score/feedback)
@login_required
def submission_grade(request, pk):
    submission = get_object_or_404(Submission, pk=pk)
    if request.method == 'POST':
        submission.score = request.POST.get('score')
        submission.feedback = request.POST.get('feedback')
        submission.save()
        messages.success(request, 'Submission graded successfully.')
        return redirect('school:school-students-submissions')
    return redirect('school:school-students-submissions')


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
def school_fees(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Events could be a new model or use existing (e.g., Sessions)
    # Placeholder: List sessions as events
    events = Session.objects.filter(school=school)
    context = {'events': events, 'school': school}
    return render(request, 'school/event.html', context)

# ------------------------------- SETTINGS & PERMISSIONS -------------------------------
@login_required
def school_settings(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
        return redirect('school:dashboard')
    
    # Log actions via middleware or signals; placeholder query
    logs = []  # From audit log model if added
    context = {'logs': logs, 'school': school}
    return render(request, 'school/permissions.html', context)  # Assume template

@login_required
def contact_messages(request):
    try:
        school = request.user.school_admin_profile
    except AttributeError:
        messages.error(request, "Access denied: Admin privileges required.")
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
    grade = get_object_or_404(Grade, id=grade_id)
    streams = grade.streams.all().values("id", "name")

    return JsonResponse(list(streams), safe=False)

@login_required
def create_stream(request, grade_id):
    grade = get_object_or_404(Grade, id=grade_id)

    if request.method == "POST":
        form = StreamForm(request.POST)
        if form.is_valid():
            stream = form.save(commit=False)
            stream.grade = grade
            stream.school = grade.school
            stream.save()
            messages.success(request, "Stream added successfully.")
        else:
            messages.error(request, "Failed to create stream. Check form inputs.")

    return redirect("school:school-grades")

@login_required
def delete_stream(request, stream_id):
    stream = get_object_or_404(Streams, id=stream_id)
    stream.delete()
    messages.success(request, "Stream deleted successfully.")
    return redirect("school:school-grades")


@login_required
def create_parent_student(request):
    # Ensure user is a school admin
    school = getattr(request.user, 'school_admin_profile', None)
    if not school:
        messages.error(request, "You do not have permission to add members.")
        return redirect('school:dashboard')

    if request.method == "POST":
        form = ParentStudentCreationForm(request.POST, request.FILES, school=school)
        print(form)
        print(form.errors)
        print(request.POST)
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

                # Redirect to the members listing page
                return redirect('school:members-list')

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
