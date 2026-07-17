"""
API views for the DIL (Digital Interactive Learning) module and Tuition platform.
All models live in kiswate_digital_app. Authentication is JWT (same as school API).
Users access DIL via their UserProfile (role: student | teacher | school_admin | super_admin).
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
from django.utils import timezone

from kiswate_digital_app.models import (
    UserProfile, Subject as DILSubject, Program, Enrollment as DILEnrollment,
    VirtualClass, ClassAttendance, Lesson as DILLesson,
    Assignment as DILAssignment, AssignmentSubmission,
    Assessment, Question, Choice, StudentAssessmentAttempt, StudentAnswer,
    NotificationTemplate, NotificationLog, TuitionPayment,
)

from .dil_serializers import (
    DILSubjectSerializer,
    ProgramSerializer, ProgramCreateSerializer,
    DILEnrollmentSerializer,
    VirtualClassSerializer, VirtualClassCreateSerializer, ClassAttendanceSerializer,
    DILLessonSerializer, DILLessonCreateSerializer,
    DILAssignmentSerializer, DILAssignmentCreateSerializer,
    DILSubmissionSerializer, DILSubmissionCreateSerializer, DILSubmissionGradeSerializer,
    AssessmentSerializer, AssessmentCreateSerializer,
    QuestionSerializer, QuestionStudentSerializer, QuestionCreateSerializer,
    TakeAssessmentSerializer, AttemptResultSerializer,
    NotificationTemplateSerializer,
    TuitionPaymentSerializer, TuitionPaymentCreateSerializer,
)


# ── Role helpers ──────────────────────────────────────────────────────────────

def _get_profile(user):
    return getattr(user, 'profile', None)


def _require_profile(user, response_on_fail=None):
    profile = _get_profile(user)
    if not profile:
        return None, Response(
            {'error': 'No DIL profile. Register on the DIL platform first.'},
            status=status.HTTP_403_FORBIDDEN
        )
    return profile, None


TEACHER_ROLES = {'teacher', 'school_admin', 'super_admin'}
ADMIN_ROLES_DIL = {'school_admin', 'super_admin'}


def _is_teacher(profile):
    return profile and profile.role in TEACHER_ROLES


def _is_admin(profile):
    return profile and profile.role in ADMIN_ROLES_DIL


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT 3 — DIL Module
# ═══════════════════════════════════════════════════════════════════════════════

# ── DIL Subject Catalog ───────────────────────────────────────────────────────

class DILSubjectsView(APIView):
    """GET all DIL subjects (public catalog)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = DILSubject.objects.all().order_by('name')
        return Response(DILSubjectSerializer(qs, many=True).data)


# ── Programs ──────────────────────────────────────────────────────────────────

class DILProgramsView(APIView):
    """
    GET: list programs (teacher sees own; student sees enrolled + open tuition).
    POST: teacher/admin creates a program.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err

        qs = Program.objects.filter(is_active=True)
        if profile.role == 'student':
            enrolled_ids = DILEnrollment.objects.filter(
                student=profile, is_active=True
            ).values_list('program_id', flat=True)
            qs = qs.filter(id__in=enrolled_ids)
        elif profile.role == 'teacher':
            qs = qs.filter(teacher=profile)
        # admin/super_admin see all

        program_type = request.query_params.get('type')  # 'tuition' | 'school'
        if program_type == 'tuition':
            qs = qs.filter(is_tuition=True)
        elif program_type == 'school':
            qs = qs.filter(is_tuition=False)

        return Response(ProgramSerializer(qs, many=True).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Only teachers/admins can create programs.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = ProgramCreateSerializer(
            data=request.data,
            context={'profile': profile, 'school': getattr(profile, 'school', None)}
        )
        if serializer.is_valid():
            program = serializer.save()
            return Response(ProgramSerializer(program).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILProgramDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, profile):
        if _is_teacher(profile):
            return get_object_or_404(Program, pk=pk)
        return get_object_or_404(Program, pk=pk, is_active=True)

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        program = self._get(pk, profile)
        return Response(ProgramSerializer(program).data)

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        program = get_object_or_404(Program, pk=pk, teacher=profile)
        serializer = ProgramCreateSerializer(program, data=request.data, partial=True,
                                             context={'profile': profile})
        if serializer.is_valid():
            serializer.save()
            return Response(ProgramSerializer(program).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_admin(profile):
            return Response({'error': 'Only admins can delete programs.'}, status=status.HTTP_403_FORBIDDEN)
        program = get_object_or_404(Program, pk=pk)
        program.is_active = False
        program.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Enrollment into programs ──────────────────────────────────────────────────

class DILEnrollView(APIView):
    """POST: student self-enroll or admin enroll a student into a program."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err

        program_id = request.data.get('program_id')
        student_id = request.data.get('student_id')  # admin only

        program = get_object_or_404(Program, pk=program_id, is_active=True)

        if _is_admin(profile) and student_id:
            student = get_object_or_404(UserProfile, pk=student_id, role='student')
        elif profile.role == 'student':
            student = profile
        else:
            return Response({'error': 'Specify student_id or enroll as student.'}, status=status.HTTP_400_BAD_REQUEST)

        enrollment, created = DILEnrollment.objects.get_or_create(
            student=student, program=program,
            defaults={'is_active': True}
        )
        if not created and not enrollment.is_active:
            enrollment.is_active = True
            enrollment.save()
        return Response(DILEnrollmentSerializer(enrollment).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)

    def delete(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        program_id = request.data.get('program_id')
        enrollment = get_object_or_404(DILEnrollment, student=profile, program_id=program_id)
        enrollment.is_active = False
        enrollment.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Virtual Classes ───────────────────────────────────────────────────────────

class DILClassesView(APIView):
    """GET classes for current user; POST create class (teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err

        program_id = request.query_params.get('program_id')
        qs = VirtualClass.objects.select_related('program', 'teacher')

        if profile.role == 'student':
            enrolled_ids = DILEnrollment.objects.filter(
                student=profile, is_active=True
            ).values_list('program_id', flat=True)
            qs = qs.filter(program_id__in=enrolled_ids, is_cancelled=False)
        elif profile.role == 'teacher':
            qs = qs.filter(teacher=profile)
        # admin sees all

        if program_id:
            qs = qs.filter(program_id=program_id)
        return Response(VirtualClassSerializer(qs, many=True).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Only teachers can create classes.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = VirtualClassCreateSerializer(data=request.data, context={'profile': profile})
        if serializer.is_valid():
            vc = serializer.save()
            return Response(VirtualClassSerializer(vc).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILClassDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk):
        return get_object_or_404(VirtualClass, pk=pk)

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        return Response(VirtualClassSerializer(self._get(pk)).data)

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk, teacher=profile)
        serializer = VirtualClassCreateSerializer(vc, data=request.data, partial=True, context={'profile': profile})
        if serializer.is_valid():
            serializer.save()
            return Response(VirtualClassSerializer(vc).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk, teacher=profile)
        vc.is_cancelled = True
        vc.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DILClassJoinView(APIView):
    """POST: student joins a class (records attendance)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if profile.role != 'student':
            return Response({'error': 'Only students can join classes.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk, is_cancelled=False)
        # Verify enrolled
        enrolled = DILEnrollment.objects.filter(
            student=profile, program=vc.program, is_active=True
        ).exists()
        if not enrolled:
            return Response({'error': 'Not enrolled in this program.'}, status=status.HTTP_403_FORBIDDEN)
        attendance, created = ClassAttendance.objects.get_or_create(
            virtual_class=vc, student=profile,
            defaults={'is_present': True, 'joined_at': timezone.now()}
        )
        return Response(ClassAttendanceSerializer(attendance).data,
                        status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)


class DILClassAttendanceView(APIView):
    """GET attendance list; POST manual mark (teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk)
        qs = ClassAttendance.objects.filter(virtual_class=vc).select_related('student')
        return Response(ClassAttendanceSerializer(qs, many=True).data)

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk)
        student_id = request.data.get('student_id')
        is_present = request.data.get('is_present', True)
        student = get_object_or_404(UserProfile, pk=student_id, role='student')
        attendance, _ = ClassAttendance.objects.update_or_create(
            virtual_class=vc, student=student,
            defaults={'is_present': is_present, 'marked_by_teacher': True,
                      'notes': request.data.get('notes', '')}
        )
        return Response(ClassAttendanceSerializer(attendance).data)


class DILClassRecordingView(APIView):
    """POST: teacher uploads recording link for a class."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk, teacher=profile)
        recording_link = request.data.get('recording_link', '')
        if not recording_link:
            return Response({'error': 'recording_link is required.'}, status=status.HTTP_400_BAD_REQUEST)
        vc.recording_link = recording_link
        vc.save()
        return Response({'id': vc.pk, 'recording_link': vc.recording_link})


class DILClassReminderView(APIView):
    """POST: send reminder notifications for a class (teacher)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        vc = get_object_or_404(VirtualClass, pk=pk, teacher=profile)
        # Get enrolled students
        enrolled = DILEnrollment.objects.filter(
            program=vc.program, is_active=True
        ).select_related('student')
        message = (
            request.data.get('message') or
            f"Reminder: {vc.title} is scheduled for {vc.scheduled_at.strftime('%d %b %Y %H:%M')}. "
            f"Join at: {vc.meeting_link}"
        )
        created = 0
        for enrollment in enrolled:
            NotificationLog.objects.create(
                recipient=enrollment.student,
                notification_type='sms',
                message=message,
                status='pending',
                related_class=vc,
            )
            created += 1
        return Response({'sent': created, 'class': vc.title})


# ── DIL Lessons ───────────────────────────────────────────────────────────────

class DILLessonsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        program_id = request.query_params.get('program_id')
        qs = DILLesson.objects.select_related('program', 'teacher')

        if profile.role == 'student':
            enrolled_ids = DILEnrollment.objects.filter(
                student=profile, is_active=True
            ).values_list('program_id', flat=True)
            qs = qs.filter(program_id__in=enrolled_ids, is_published=True)
        elif profile.role == 'teacher':
            qs = qs.filter(teacher=profile)

        if program_id:
            qs = qs.filter(program_id=program_id)
        return Response(DILLessonSerializer(qs, many=True).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DILLessonCreateSerializer(data=request.data, context={'profile': profile})
        if serializer.is_valid():
            lesson = serializer.save()
            return Response(DILLessonSerializer(lesson).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILLessonDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        lesson = get_object_or_404(DILLesson, pk=pk)
        if profile.role == 'student' and not lesson.is_published:
            return Response({'error': 'Lesson not published.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(DILLessonSerializer(lesson).data)

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        lesson = get_object_or_404(DILLesson, pk=pk, teacher=profile)
        serializer = DILLessonCreateSerializer(lesson, data=request.data, partial=True, context={'profile': profile})
        if serializer.is_valid():
            serializer.save()
            return Response(DILLessonSerializer(lesson).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        lesson = get_object_or_404(DILLesson, pk=pk, teacher=profile)
        lesson.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── DIL Assignments ───────────────────────────────────────────────────────────

class DILAssignmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        program_id = request.query_params.get('program_id')
        qs = DILAssignment.objects.select_related('program')

        if profile.role == 'student':
            enrolled_ids = DILEnrollment.objects.filter(
                student=profile, is_active=True
            ).values_list('program_id', flat=True)
            qs = qs.filter(program_id__in=enrolled_ids, is_published=True)
        elif profile.role == 'teacher':
            qs = qs.filter(program__teacher=profile)

        if program_id:
            qs = qs.filter(program_id=program_id)
        return Response(DILAssignmentSerializer(qs, many=True, context={'request': request}).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DILAssignmentCreateSerializer(data=request.data)
        if serializer.is_valid():
            assignment = serializer.save()
            return Response(DILAssignmentSerializer(assignment, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILAssignmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        assignment = get_object_or_404(DILAssignment, pk=pk)
        return Response(DILAssignmentSerializer(assignment, context={'request': request}).data)

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assignment = get_object_or_404(DILAssignment, pk=pk, program__teacher=profile)
        serializer = DILAssignmentCreateSerializer(assignment, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(DILAssignmentSerializer(assignment, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assignment = get_object_or_404(DILAssignment, pk=pk, program__teacher=profile)
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DILAssignmentSubmitView(APIView):
    """POST: student submits a DIL assignment."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if profile.role != 'student':
            return Response({'error': 'Only students can submit assignments.'}, status=status.HTTP_403_FORBIDDEN)
        assignment = get_object_or_404(DILAssignment, pk=pk, is_published=True)
        serializer = DILSubmissionCreateSerializer(
            data={**request.data, 'assignment': assignment.pk},
            context={'profile': profile}
        )
        if serializer.is_valid():
            submission = serializer.save()
            return Response(DILSubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILSubmissionsView(APIView):
    """GET submissions (teacher sees all for their assignments; student sees own)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        assignment_id = request.query_params.get('assignment_id')
        qs = AssignmentSubmission.objects.select_related('assignment', 'student')
        if profile.role == 'student':
            qs = qs.filter(student=profile)
        elif profile.role == 'teacher':
            qs = qs.filter(assignment__program__teacher=profile)
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)
        return Response(DILSubmissionSerializer(qs, many=True).data)


class DILSubmissionGradeView(APIView):
    """PATCH: teacher grades a submission."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Only teachers can grade submissions.'}, status=status.HTTP_403_FORBIDDEN)
        submission = get_object_or_404(AssignmentSubmission, pk=pk)
        serializer = DILSubmissionGradeSerializer(submission, data=request.data, partial=True,
                                                   context={'profile': profile})
        if serializer.is_valid():
            serializer.save()
            return Response(DILSubmissionSerializer(submission).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Assessments ───────────────────────────────────────────────────────────────

class DILAssessmentsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        program_id = request.query_params.get('program_id')
        qs = Assessment.objects.select_related('program')

        if profile.role == 'student':
            enrolled_ids = DILEnrollment.objects.filter(
                student=profile, is_active=True
            ).values_list('program_id', flat=True)
            qs = qs.filter(program_id__in=enrolled_ids, is_published=True)
        elif profile.role == 'teacher':
            qs = qs.filter(program__teacher=profile)

        if program_id:
            qs = qs.filter(program_id=program_id)
        return Response(AssessmentSerializer(qs, many=True, context={'request': request}).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = AssessmentCreateSerializer(data=request.data, context={'profile': profile})
        if serializer.is_valid():
            assessment = serializer.save()
            return Response(AssessmentSerializer(assessment, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILAssessmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        assessment = get_object_or_404(Assessment, pk=pk)
        return Response(AssessmentSerializer(assessment, context={'request': request}).data)

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assessment = get_object_or_404(Assessment, pk=pk, created_by=profile)
        serializer = AssessmentCreateSerializer(assessment, data=request.data, partial=True, context={'profile': profile})
        if serializer.is_valid():
            serializer.save()
            return Response(AssessmentSerializer(assessment, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assessment = get_object_or_404(Assessment, pk=pk, created_by=profile)
        assessment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DILAssessmentQuestionsView(APIView):
    """GET questions; POST add question (teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        assessment = get_object_or_404(Assessment, pk=pk)
        qs = assessment.questions.prefetch_related('choices').order_by('order')
        if profile.role == 'student':
            return Response(QuestionStudentSerializer(qs, many=True).data)
        return Response(QuestionSerializer(qs, many=True).data)

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assessment = get_object_or_404(Assessment, pk=pk)
        data = {**request.data, 'assessment': assessment.pk}
        serializer = QuestionCreateSerializer(data=data)
        if serializer.is_valid():
            question = serializer.save()
            return Response(QuestionSerializer(question).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DILQuestionDetailView(APIView):
    """PATCH/DELETE a question (teacher)."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        question = get_object_or_404(Question, pk=pk)
        for attr in ['text', 'question_type', 'marks', 'order', 'explanation']:
            if attr in request.data:
                setattr(question, attr, request.data[attr])
        question.save()
        # Update choices if provided
        choices_data = request.data.get('choices')
        if choices_data is not None:
            question.choices.all().delete()
            for c in choices_data:
                Choice.objects.create(
                    question=question, text=c.get('text', ''),
                    is_correct=c.get('is_correct', False)
                )
        return Response(QuestionSerializer(question).data)

    def delete(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        question = get_object_or_404(Question, pk=pk)
        question.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DILTakeAssessmentView(APIView):
    """POST: student takes (submits answers for) an assessment."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if profile.role != 'student':
            return Response({'error': 'Only students can take assessments.'}, status=status.HTTP_403_FORBIDDEN)
        assessment = get_object_or_404(Assessment, pk=pk, is_published=True)

        if StudentAssessmentAttempt.objects.filter(assessment=assessment, student=profile).exists():
            return Response({'error': 'Already attempted.'}, status=status.HTTP_400_BAD_REQUEST)

        serializer = TakeAssessmentSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        attempt = StudentAssessmentAttempt.objects.create(
            assessment=assessment, student=profile, submitted_at=timezone.now()
        )

        total_score = 0.0
        auto_gradable = True
        for answer_data in serializer.validated_data['answers']:
            question = get_object_or_404(Question, pk=answer_data['question_id'], assessment=assessment)
            choice = None
            marks_awarded = None
            if answer_data.get('choice_id'):
                choice = Choice.objects.filter(pk=answer_data['choice_id'], question=question).first()
                if question.question_type in ('mcq', 'true_false') and choice:
                    marks_awarded = question.marks if choice.is_correct else 0
                    total_score += marks_awarded
            else:
                auto_gradable = False  # essay/short_answer needs manual grading
            StudentAnswer.objects.create(
                attempt=attempt,
                question=question,
                selected_choice=choice,
                text_answer=answer_data.get('text_answer', ''),
                marks_awarded=marks_awarded,
            )

        if auto_gradable:
            attempt.score = total_score
            attempt.is_graded = True
            attempt.auto_graded = True
        attempt.save()

        return Response(AttemptResultSerializer(attempt).data, status=status.HTTP_201_CREATED)


class DILAttemptResultView(APIView):
    """GET: view assessment attempt result."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        attempt = get_object_or_404(StudentAssessmentAttempt, pk=pk)
        if profile.role == 'student' and attempt.student != profile:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        if profile.role == 'student' and not attempt.assessment.results_published:
            return Response({'error': 'Results not yet published.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(AttemptResultSerializer(attempt).data)


class DILPublishResultsView(APIView):
    """POST: teacher publishes assessment results."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        assessment = get_object_or_404(Assessment, pk=pk, created_by=profile)
        assessment.results_published = not assessment.results_published
        assessment.save()
        return Response({'id': assessment.pk, 'results_published': assessment.results_published})


# ── Notification Templates ────────────────────────────────────────────────────

class DILNotificationTemplatesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_admin(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        qs = NotificationTemplate.objects.filter(is_active=True)
        return Response(NotificationTemplateSerializer(qs, many=True).data)

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_admin(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = NotificationTemplateSerializer(data=request.data)
        if serializer.is_valid():
            template = serializer.save()
            return Response(NotificationTemplateSerializer(template).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk=None):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_admin(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        template = get_object_or_404(NotificationTemplate, pk=pk)
        serializer = NotificationTemplateSerializer(template, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(NotificationTemplateSerializer(template).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT 4 — Tuition Platform
# ═══════════════════════════════════════════════════════════════════════════════

class TuitionProgramsView(APIView):
    """GET: browse all active tuition programs (public — any authenticated user)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Program.objects.filter(is_tuition=True, is_active=True).select_related('subject', 'teacher')
        subject = request.query_params.get('subject')
        level = request.query_params.get('level')
        category = request.query_params.get('category')
        if subject:
            qs = qs.filter(subject__name__icontains=subject)
        if level:
            qs = qs.filter(level=level)
        if category:
            qs = qs.filter(category=category)
        return Response(ProgramSerializer(qs, many=True).data)


class TuitionEnrollView(APIView):
    """POST: student or parent enrolls into a tuition program and creates payment record."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err

        serializer = TuitionPaymentCreateSerializer(data=request.data, context={'profile': profile})
        if serializer.is_valid():
            payment = serializer.save()
            return Response(TuitionPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TuitionPaymentSTKPushView(APIView):
    """POST: initiate M-Pesa STK push for a tuition payment."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        profile, err = _require_profile(request.user)
        if err:
            return err
        payment = get_object_or_404(TuitionPayment, pk=pk, enrollment__student=profile)
        phone = request.data.get('phone') or payment.payer_phone
        if not phone:
            return Response({'error': 'phone is required.'}, status=status.HTTP_400_BAD_REQUEST)
        # Placeholder — integrate Daraja API in production
        return Response({
            'message': f'STK Push initiated to {phone} for KES {float(payment.amount)}.',
            'payment_id': payment.pk,
            'amount': float(payment.amount),
            'phone': phone,
            'status': 'pending',
        })


class TuitionTeacherDashboardView(APIView):
    """GET: DIL teacher portal dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if not _is_teacher(profile):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        programs = Program.objects.filter(teacher=profile, is_active=True)
        total_enrolled = DILEnrollment.objects.filter(
            program__in=programs, is_active=True
        ).count()
        upcoming_classes = VirtualClass.objects.filter(
            teacher=profile, scheduled_at__gte=timezone.now(), is_cancelled=False
        ).count()
        pending_grading = AssignmentSubmission.objects.filter(
            assignment__program__in=programs, marks_obtained__isnull=True
        ).count()
        pending_assessments = StudentAssessmentAttempt.objects.filter(
            assessment__program__in=programs, is_graded=False
        ).count()

        return Response({
            'teacher': profile.full_name,
            'total_programs': programs.count(),
            'total_enrolled_students': total_enrolled,
            'upcoming_classes': upcoming_classes,
            'pending_grading': pending_grading,
            'pending_assessment_grading': pending_assessments,
            'programs': ProgramSerializer(programs, many=True).data,
        })


class TuitionStudentDashboardView(APIView):
    """GET: DIL student portal dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err
        if profile.role != 'student':
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        enrollments = DILEnrollment.objects.filter(student=profile, is_active=True).select_related('program')
        program_ids = enrollments.values_list('program_id', flat=True)

        upcoming_classes = VirtualClass.objects.filter(
            program_id__in=program_ids, scheduled_at__gte=timezone.now(), is_cancelled=False
        ).count()
        pending_assignments = DILAssignment.objects.filter(
            program_id__in=program_ids, is_published=True,
            due_date__gte=timezone.now()
        ).exclude(submissions__student=profile).count()
        pending_assessments = Assessment.objects.filter(
            program_id__in=program_ids, is_published=True
        ).exclude(attempts__student=profile).count()

        payments = TuitionPayment.objects.filter(enrollment__student=profile)
        unpaid = payments.filter(status='pending').count()

        return Response({
            'student': profile.full_name,
            'enrolled_programs': enrollments.count(),
            'upcoming_classes': upcoming_classes,
            'pending_assignments': pending_assignments,
            'pending_assessments': pending_assessments,
            'unpaid_fees': unpaid,
            'programs': [
                {
                    'id': e.program.id,
                    'name': e.program.name,
                    'subject': e.program.subject.name,
                    'payment_status': getattr(
                        TuitionPayment.objects.filter(enrollment=e).first(), 'status', 'none'
                    ),
                }
                for e in enrollments
            ],
        })


class TuitionParentView(APIView):
    """GET: parent/guardian view of their children's tuition progress."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        profile, err = _require_profile(request.user)
        if err:
            return err

        # Guardian is not a UserProfile role — parents can be any role here
        # Get guardians linked to this user
        from kiswate_digital_app.models import Guardian
        guardians = Guardian.objects.filter(
            student__user=request.user
        ).select_related('student')

        if not guardians.exists():
            # Try to find by profile if user has a student profile linked as child
            return Response({'error': 'No children found in the DIL platform.'}, status=status.HTTP_404_NOT_FOUND)

        children_data = []
        for guardian in guardians:
            child_profile = guardian.student
            enrollments = DILEnrollment.objects.filter(
                student=child_profile, is_active=True
            ).select_related('program')
            submissions = AssignmentSubmission.objects.filter(student=child_profile)
            attempts = StudentAssessmentAttempt.objects.filter(student=child_profile, is_graded=True)

            avg_score = None
            if attempts.exists():
                scores = [a.score for a in attempts if a.score is not None]
                avg_score = round(sum(scores) / len(scores), 1) if scores else None

            children_data.append({
                'child_name': child_profile.full_name,
                'relationship': guardian.relationship,
                'enrolled_programs': enrollments.count(),
                'assignments_submitted': submissions.count(),
                'assessments_taken': attempts.count(),
                'average_assessment_score': avg_score,
                'programs': [
                    {
                        'id': e.program.id,
                        'name': e.program.name,
                        'payment_status': getattr(
                            TuitionPayment.objects.filter(enrollment=e).first(), 'status', 'none'
                        ),
                    }
                    for e in enrollments
                ],
            })

        return Response({'children': children_data})
