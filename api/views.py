from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.decorators import api_view, permission_classes
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate, get_user_model
from django.db.models import Q
from rest_framework.parsers import JSONParser
from rest_framework.renderers import JSONRenderer
from django.db.models.functions import TruncHour
from django.db.models import Count
from datetime import date
from django.utils import timezone
from .serializers import (
    RegisterSerializer, LoginSerializer, TimeSlotSerializer,
    TeacherTimetableSerializer, StudentTimetableSerializer, AnnouncementSerializer,
    StudentStatsSerializer, ParentStatsSerializer, UserSerializer, AttendanceRecordSerializer, AttendanceModelSerializer,
    AttendanceCreateSerializer, AttendanceUpdateSerializer, DisciplineCreateSerializer, DisciplineUpdateSerializer,
    AssignmentCreateSerializer, AssignmentUpdateSerializer, DisciplineRecordSerializer, AssignmentSerializer, SampleDisciplineSerializer,
    TeacherStatsSerializer, ParentChildrenSerializer, TeacherLessonSerializer, StudentListSerializer,
    GradeAttendanceCreateSerializer, GradeAttendanceSerializer,
    # Extended serializers
    ProfileUpdateSerializer,
    SchoolSerializer, GradeSerializer, StreamSerializer, TermSerializer, SubjectListSerializer,
    StaffSerializer, StaffUpdateSerializer,
    StudentDetailSerializer, StudentUpdateSerializer, StudentStatusSerializer,
    ParentListSerializer, ParentUpdateSerializer,
    LessonSerializer, LessonCreateSerializer, LessonUpdateSerializer,
    SubmissionSerializer, SubmissionCreateSerializer, SubmissionGradeSerializer,
    ExamSessionSerializer, ExamSessionCreateSerializer,
    ExamResultSerializer, ExamResultCreateSerializer, ExamResultBulkSerializer,
    FeeInvoiceSerializer, FeeInvoiceCreateSerializer, FeePaymentSerializer,
    FeeStructureSerializer, FeeStructureCreateSerializer,
    ComplaintSerializer, ComplaintCreateSerializer, ComplaintResponseSerializer,
    SchoolAnnouncementSerializer, SchoolAnnouncementCreateSerializer,
    NotificationSendSerializer,
    AdminDashboardSerializer, TeacherDashboardSerializer, StudentDashboardSerializer, ParentDashboardSerializer,
)
from school.models import (
    StaffProfile, Student, Parent, SubjectEnrollment, TimeSlot, Lesson, School, Grade, Enrollment, Streams,
    Attendance, DisciplineRecord, Assignment, ContactMessage, Submission, Term, Subject, Notification,
    GradeAttendance, Announcement, FeeInvoice, FeeStructure, FeeType, ExamSession, ExamResult, Complaint,
    ClassTeacherAssignment, AcademicYear, Timetable,
)
from rest_framework.decorators import action
from django.db.models import Count, Case, When, IntegerField, Sum
from django.db.models import Avg, Q, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta
User = get_user_model()

ADMIN_ROLES = {'admin', 'principal', 'deputy'}
STAFF_ROLES = {'admin', 'principal', 'deputy', 'policy_maker', 'staff', 'teacher'}
ALL_ROLES = {'admin', 'principal', 'deputy', 'policy_maker', 'staff', 'teacher', 'parent', 'student'}


def get_user_role(user):
    # Admin roles take priority so a principal who is also a teacher
    # is correctly identified as principal, not teacher.
    if user.is_principal:
        return 'principal'
    elif user.is_deputy_principal:
        return 'deputy'
    elif user.is_policy_maker:
        return 'policy_maker'
    elif user.is_admin:
        return 'admin'
    elif user.is_teacher:
        return 'teacher'
    elif user.is_parent:
        return 'parent'
    elif user.is_student:
        return 'student'
    elif user.school_staff:
        return 'staff'
    return 'user'


def get_user_school(user, role=None):
    if role is None:
        role = get_user_role(user)
    if role in ('teacher', 'principal', 'deputy', 'policy_maker', 'staff'):
        sp = getattr(user, 'staffprofile', None)
        return sp.school if sp else None
    if role == 'admin':
        sp = getattr(user, 'staffprofile', None)
        if sp:
            return sp.school
        try:
            return user.school_admin_profile
        except Exception:
            return None
    if role == 'parent':
        p = getattr(user, 'parent', None)
        return p.school if p else None
    if role == 'student':
        s = getattr(user, 'student', None)
        return s.school if s else None
    return None

# Auth Views - Updated with AllowAny
@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    serializer = RegisterSerializer(data=request.data, context={'request': request})
    if serializer.is_valid():
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LoginSerializer(data=request.data)
    if serializer.is_valid():
        user = authenticate(
            request=request,
            email=serializer.validated_data['email'],
            password=serializer.validated_data['password']
        )
        if user:
            refresh = RefreshToken.for_user(user)
            return Response({
                'user': UserSerializer(user).data,
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }, status=status.HTTP_200_OK)
        return Response({'error': 'Invalid credentials'}, status=status.HTTP_401_UNAUTHORIZED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class LogoutView(APIView):
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get("refresh")
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
            return Response({'message': 'Logged out successfully'}, status=status.HTTP_205_RESET_CONTENT)
        except Exception as e:
            return Response({'error': 'Invalid or expired token'}, status=status.HTTP_400_BAD_REQUEST)

# Data Views
class StaticDataView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user = request.user
        role = get_user_role(user)
        school = None
        if role in ['teacher', 'parent', 'student']:
            if role == 'teacher':
                profile = getattr(user, 'staffprofile', None)
            elif role == 'parent':
                profile = getattr(user, 'parent', None)
            elif role == 'student':
                profile = getattr(user, 'student', None)
            if profile:
                school = profile.school
        
        time_slots = []
        if school:
            ts_objs = TimeSlot.objects.filter(school=school).order_by('start_time')
            time_slots = [f"{ts.start_time.strftime('%H-%M')}-{ts.end_time.strftime('%H-%M')}" for ts in ts_objs]
        else:
            time_slots = ['8-10', '10-12', '12-2', '2-4', '4-6']  # Default from sample
        
        data_dict = {
            'timeSlots': time_slots,
            'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        }
        serializer = TimeSlotSerializer(data=data_dict)
        serializer.is_valid()
        return Response(serializer.data)

class TeacherTimetableView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, teacher_id):
        teacher = get_object_or_404(StaffProfile, staff_id=teacher_id)
        user_role = get_user_role(request.user)
        if user_role != 'teacher' or request.user != teacher.user:
            # Allow admins or same school staff
            if user_role != 'admin' and (not hasattr(request.user, 'school') or request.user.school != teacher.school):
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        serializer = TeacherTimetableSerializer(teacher)
        return Response(serializer.data)


class TeacherLessonsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, teacher_id):
        teacher = get_object_or_404(StaffProfile, staff_id=teacher_id)

        user_role = get_user_role(request.user)
        # Authorization: Allow teacher themselves, admins, or same-school staff
        if user_role != 'teacher' or request.user != teacher.user:
            if user_role != 'admin' and (not hasattr(request.user, 'school') or request.user.school != teacher.school):
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Get active term
        active_term = Term.objects.filter(school=teacher.school, is_active=True).first()
        if not active_term:
            return Response([])

        # Fetch lessons
        lessons = Lesson.objects.filter(
            teacher=teacher,
            timetable__term=active_term,
            timetable__school=teacher.school
        ).select_related(
            'subject', 'time_slot', 'stream', 'stream__grade', 'timetable__term'
        ).order_by(
            'stream__grade__name',
            'day_of_week',
            'time_slot__start_time'
        )

        serializer = TeacherLessonSerializer(lessons, many=True)
        return Response(serializer.data)


class StudentsListView(APIView):
    """
    GET: List all students in the user's school (for admins/teachers)
    Includes enrolled subjects per student.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_role = get_user_role(request.user)

        if user_role not in STAFF_ROLES:
            return Response(
                {'error': 'Insufficient permissions'},
                status=status.HTTP_403_FORBIDDEN
            )

        school = get_user_school(request.user, user_role)

        if not school:
            return Response(
                {'error': 'No school access'},
                status=status.HTTP_403_FORBIDDEN
            )

        # 🔥 Optimized queryset
        queryset = Student.objects.filter(
            school=school,
            is_active=True
        ).select_related(
            'user',
            'grade_level',
            'stream'
        ).prefetch_related(
            Prefetch(
                'subject_enrollments',
                queryset=SubjectEnrollment.objects.filter(
                    is_active=True
                ).select_related('subject')
            )
        ).order_by(
            'user__last_name',
            'user__first_name'
        )

        serializer = StudentListSerializer(queryset, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

class StudentTimetableView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, student_id):
        student = get_object_or_404(Student, student_id=student_id)
        user_role = get_user_role(request.user)
        authorized = False
        if user_role == 'student' and request.user == student.user:
            authorized = True
        elif user_role == 'parent':
            parent = get_object_or_404(Parent, user=request.user)
            if student in parent.children.all():
                authorized = True
        elif user_role in ['admin', 'teacher']:
            # Check school match
            if hasattr(request.user, 'school') and request.user.school == student.school:
                authorized = True
        if not authorized:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        serializer = StudentTimetableSerializer(student)
        return Response(serializer.data)

# Placeholder Views for Missing Data (implement once models added)
class AttendanceRecordsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user_role = get_user_role(request.user)
        if user_role not in ALL_ROLES:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Real query
        school = get_user_school(request.user, user_role)
        if not school:
            return Response({'error': 'No school access'}, status=status.HTTP_403_FORBIDDEN)
        queryset = Attendance.objects.filter(
            enrollment__school=school
        ).select_related('enrollment__student', 'marked_by')
        
        serializer = AttendanceModelSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        """
        POST: Bulk create attendance for a lesson (teacher/admin only).
        """
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions to mark attendance'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AttendanceCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            attendances = serializer.save()  # List of created instances
            response_serializer = AttendanceModelSerializer(attendances, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request, pk):
        # Full update
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        attendance = get_object_or_404(Attendance, pk=pk)
        school = get_user_school(request.user, user_role)
        if attendance.enrollment.school != school:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AttendanceUpdateSerializer(attendance, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(AttendanceModelSerializer(attendance).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        # Partial update (same as put)
        return self.put(request, pk)
    
    def delete(self, request, pk):
        if get_user_role(request.user) != 'admin':
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        attendance = get_object_or_404(Attendance, pk=pk)
        attendance.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StreamAttendanceRecordsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        """
        GET: List attendance records for the stream (filtered by role/school).
        """
        user_role = get_user_role(request.user)
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        stream = get_object_or_404(Streams, pk=pk)
        school = get_user_school(request.user, user_role)
        if not school or stream.school != school:
            return Response({'error': 'No school access or unauthorized stream'}, status=status.HTTP_403_FORBIDDEN)
        
        # Base queryset
        queryset = GradeAttendance.objects.filter(stream=stream).select_related('student__user').order_by('-recorded_at')
        
        # Role-specific filtering
        if user_role == 'student':
            student_profile = getattr(request.user, 'student', None)
            if student_profile and student_profile.stream == stream:
                queryset = queryset.filter(student=student_profile)
            else:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'parent':
            parent_profile = getattr(request.user, 'parent', None)
            if parent_profile:
                queryset = queryset.filter(student__parents=parent_profile)
            else:
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        # For teacher/admin: all records in stream
        
        serializer = GradeAttendanceSerializer(queryset, many=True)
        return Response(serializer.data)  # Empty list [] if no records

    def post(self, request, pk):
        """
        POST: Bulk create attendance records for the stream (class teacher only, max 3 sessions/day).
        Expects: {
            "attendances": [
                {"student_id": <id>, "status": "P"},
                ...
            ]
        }
        Sessions limited to 3 per day (grouped by hour).
        """
        user_role = get_user_role(request.user)
        if user_role != 'teacher':
            return Response({'error': 'Only teachers can mark attendance'}, status=status.HTTP_403_FORBIDDEN)
        
        stream = get_object_or_404(Streams, pk=pk)
        school = get_user_school(request.user, user_role)
        if not school or stream.school != school:
            return Response({'error': 'No school access or unauthorized stream'}, status=status.HTTP_403_FORBIDDEN)
        
        # Check if class teacher (assuming position check; adjust if you have assigned_stream/grade field)
        teacher = request.user.staffprofile
        if not teacher:  # Adjust 'Class Teacher' to your POSITION_CHOICES value
            return Response({'error': 'Only class teachers can mark attendance for this stream'}, status=status.HTTP_403_FORBIDDEN)
        
        # Limit to max 3 sessions per day (grouped by hour via TruncHour)
        today = date.today()
        sessions_today = GradeAttendance.objects.filter(
            stream=stream,
            recorded_at__date=today
        ).annotate(hour=TruncHour('recorded_at')).values('hour').annotate(c=Count('id')).count()
        if sessions_today >= 3:
            return Response({'error': 'Maximum 3 attendance sessions allowed per day for this stream'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = GradeAttendanceCreateSerializer(data=request.data, context={'stream': stream})
        if serializer.is_valid():
            attendances = serializer.save()  # List of created instances
            response_serializer = GradeAttendanceSerializer(attendances, many=True)
            return Response(response_serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DisciplineRecordsView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [JSONParser]
    renderer_classes = [JSONRenderer]

    def get(self, request):
        """
        GET: List discipline records (filtered by role/school).
        Returns empty list if no records match filters.
        """
        user_role = get_user_role(request.user)
        if user_role not in ALL_ROLES:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Get school for filtering
        school = get_user_school(request.user, user_role)
        if not school:
            return Response({'error': 'No school access'}, status=status.HTTP_403_FORBIDDEN)

        # Real query: Filter by school/role
        queryset = DisciplineRecord.objects.filter(school=school).select_related('student__user', 'teacher', 'reported_by').prefetch_related('student__parents')
        if user_role == 'student':
            queryset = queryset.filter(student=request.user.student)
        elif user_role == 'parent':
            parent = request.user.parent
            queryset = queryset.filter(student__parents=parent)
        elif user_role == 'teacher':
            queryset = queryset.filter(teacher=request.user.staffprofile)

        # Always use ModelSerializer for real data (or empty)
        serializer = DisciplineRecordSerializer(queryset, many=True)
        return Response(serializer.data)  # Empty list [] if no records

    def post(self, request):
        """
        POST: Create a new discipline record (teacher/admin only).
        Expects: {"student": <id>, "incident_type": "...", "description": "...", "severity": "...", "action_taken": "..."}
        """
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions to report discipline'}, status=status.HTTP_403_FORBIDDEN)

        serializer = DisciplineCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            discipline = serializer.save()
            return Response(DisciplineRecordSerializer(discipline).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class DisciplineDetailView(APIView):  # For /discipline/<pk>/
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        user_role = get_user_role(request.user)
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        discipline = get_object_or_404(DisciplineRecord, pk=pk)
        school = get_user_school(request.user, user_role)
        if discipline.school != school:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        # Role-specific access
        if user_role == 'student' and discipline.student != request.user.student:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'parent':
            parent = request.user.parent
            if discipline.student not in parent.children.all():  # Assuming 'children' is a related_name for parents
                return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'teacher' and discipline.teacher != request.user.staffprofile:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DisciplineRecordSerializer(discipline)
        return Response(serializer.data)

    def put(self, request, pk):
        # Full update
        user_role = get_user_role(request.user)
        if user_role not in ['admin', 'teacher']:
            return Response({'error': 'Insufficient permissions to edit'}, status=status.HTTP_403_FORBIDDEN)
        discipline = get_object_or_404(DisciplineRecord, pk=pk)
        if discipline.school != get_user_school(request.user, user_role):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DisciplineUpdateSerializer(discipline, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(DisciplineRecordSerializer(discipline).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def patch(self, request, pk):
        # Partial update (same as put)
        return self.put(request, pk)

    def delete(self, request, pk):
        user_role = get_user_role(request.user)
        if user_role != 'admin':
            return Response({'error': 'Insufficient permissions to delete'}, status=status.HTTP_403_FORBIDDEN)
        discipline = get_object_or_404(DisciplineRecord, pk=pk)
        if discipline.school != get_user_school(request.user, user_role):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        discipline.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AssignmentsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        user_role = get_user_role(request.user)
        if user_role not in ALL_ROLES:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Real query: Filter by school/subjects
        school = get_user_school(request.user, user_role)
        if not school:
            return Response({'error': 'No school access'}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Assignment.objects.filter(school=school).select_related('subject', 'school')
        
        if user_role == 'student':
            from school.models import SubjectEnrollment
            subject_ids = SubjectEnrollment.objects.filter(
                student=request.user.student, is_active=True
            ).values_list('subject_id', flat=True)
            queryset = queryset.filter(subject_id__in=subject_ids)
        elif user_role == 'parent':
            from school.models import SubjectEnrollment
            students = request.user.parent.children.all()
            subject_ids = SubjectEnrollment.objects.filter(
                student__in=students, is_active=True
            ).values_list('subject_id', flat=True)
            queryset = queryset.filter(subject_id__in=subject_ids)
        elif user_role == 'teacher':
            staff = request.user.staffprofile
            subjects = staff.subjects.all()
            queryset = queryset.filter(subject__in=subjects)
        
        # Real data
        serializer = AssignmentSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)
    
    def post(self, request):
        # POST: Create assignment
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions to create assignment'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AssignmentCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            assignment = serializer.save()
            return Response(AssignmentSerializer(assignment, context={'request': request}).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AssignmentDetailView(APIView):  # For /assignments/<pk>/
    permission_classes = [IsAuthenticated]
    
    def get(self, request, pk):
        user_role = get_user_role(request.user)
        if user_role not in ALL_ROLES:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        assignment = get_object_or_404(Assignment, pk=pk)
        school = get_user_school(request.user, user_role)
        if assignment.school != school:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)

        # Role-specific: For student/parent, check enrollment
        if user_role == 'student':
            if not Enrollment.objects.filter(student=request.user.student, subject=assignment.subject, status='active').exists():
                return Response({'error': 'Not enrolled in this subject'}, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'parent':
            parent = request.user.parent
            if not Enrollment.objects.filter(student__parents=parent, subject=assignment.subject, status='active').exists():
                return Response({'error': 'No children enrolled in this subject'}, status=status.HTTP_403_FORBIDDEN)
        elif user_role == 'teacher':
            if assignment.subject not in request.user.staffprofile.subjects.all():
                return Response({'error': 'Not assigned to this subject'}, status=status.HTTP_403_FORBIDDEN)
        
        # For student-specific fields - FIXED: Pass submission to context
        context = {'request': request}
        if user_role == 'student':
            enrollment = Enrollment.objects.filter(student=request.user.student, subject=assignment.subject, status='active').first()
            if enrollment:
                submission = Submission.objects.filter(enrollment=enrollment, assignment=assignment).first()
                context['submission'] = submission
                context['enrollment'] = enrollment  # For isSubmitted check in serializer
        
        serializer = AssignmentSerializer(assignment, context=context)
        return Response(serializer.data)
    
    def put(self, request, pk):
        # Full update
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions to edit'}, status=status.HTTP_403_FORBIDDEN)
        
        assignment = get_object_or_404(Assignment, pk=pk)
        if assignment.school != get_user_school(request.user, user_role):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        if user_role == 'teacher' and assignment.subject not in request.user.staffprofile.subjects.all():
            return Response({'error': 'Not assigned to this subject'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AssignmentUpdateSerializer(assignment, data=request.data, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(AssignmentSerializer(assignment, context={'request': request}).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def patch(self, request, pk):
        # Partial update (same as put)
        return self.put(request, pk)
    
    def delete(self, request, pk):
        user_role = get_user_role(request.user)
        if user_role != 'admin':
            return Response({'error': 'Insufficient permissions to delete'}, status=status.HTTP_403_FORBIDDEN)
        
        assignment = get_object_or_404(Assignment, pk=pk)
        if assignment.school != get_user_school(request.user, user_role):
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        assignment.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class AnnouncementsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_role = get_user_role(request.user)
        if user_role not in ALL_ROLES:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Fetch only notifications for the logged-in user, ordered by sent_at (recent first)
        # Limit to 10 recent for performance; adjust or add pagination as needed
        announcements = Notification.objects.filter(
            recipient=request.user
        ).order_by('-sent_at')[:10]

        serializer = AnnouncementSerializer(announcements, many=True)
        return Response(serializer.data)
class StudentStatsView(APIView):
    permission_classes = [IsAuthenticated]
    
    def get(self, request, student_id):
        student = get_object_or_404(Student, student_id=student_id)
        user_role = get_user_role(request.user)
        authorized = False
        if user_role == 'student' and request.user == student.user:
            authorized = True
        elif user_role == 'parent':
            parent = get_object_or_404(Parent, user=request.user)
            if student in parent.children.all():
                authorized = True
        elif user_role in ['admin', 'teacher']:
            if hasattr(request.user, 'school') and request.user.school == student.school:
                authorized = True
        if not authorized:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        # Get current/active term for filtering
        current_term = Term.objects.filter(school=student.school, is_active=True).first()
        if not current_term:
            current_term = Term.objects.filter(school=student.school).order_by('-start_date').first()  # Latest term
        
        term_start = current_term.start_date if current_term else (timezone.now().date() - timedelta(days=90))  # Fallback 90 days
        term_end = current_term.end_date if current_term else timezone.now().date()
        
        # 1. Attendance Stats (unchanged)
        attendances = Attendance.objects.filter(
            enrollment__student=student,
            date__range=[term_start, term_end]
        )
        total_days = attendances.aggregate(total=Count('date'))['total'] or 0
        present_days = attendances.filter(status='P').count()
        absent_days = attendances.filter(status__in=['UA', 'EA']).count()
        attendance_rate = round((present_days / total_days * 100) if total_days > 0 else 0, 1)
        recent_absences = attendances.filter(status__in=['UA', 'EA'], date__gte=timezone.now().date() - timedelta(days=30)).count()
        last_absence = attendances.filter(status__in=['UA', 'EA']).order_by('-date').first()
        last_absence_date = last_absence.date.isoformat() if last_absence else None
        
        attendance_stats = {
            'totalDays': total_days,
            'presentDays': present_days,
            'absentDays': absent_days,
            'attendanceRate': attendance_rate,
            'recentAbsences': recent_absences,
            'lastAbsenceDate': last_absence_date
        }
        
        # 2. Assignments Stats
        from school.models import SubjectEnrollment
        subject_ids = SubjectEnrollment.objects.filter(
            student=student, is_active=True
        ).values_list('subject_id', flat=True)
        enrollments = Enrollment.objects.filter(
            student=student, status='active',
            lesson__subject_id__in=subject_ids
        ).select_related('lesson__subject')
        assignments = Assignment.objects.filter(
            subject_id__in=subject_ids,
            due_date__gte=term_start
        )
        total_assignments = assignments.count()
        submissions = Submission.objects.filter(
            enrollment__student=student,
            assignment__due_date__gte=term_start
        )
        completed = submissions.exclude(score__isnull=True).count()
        pending = submissions.filter(score__isnull=True).count()
        overdue = assignments.filter(
            due_date__lt=timezone.now(),
            submissions__isnull=True
        ).distinct().count()
        completion_rate = round((completed / total_assignments * 100) if total_assignments > 0 else 0, 1)
        average_score = submissions.aggregate(avg=Avg('score'))['avg'] or 0
        
        assignments_stats = {
            'total': total_assignments,
            'completed': completed,
            'pending': pending,
            'overdue': overdue,
            'completionRate': completion_rate,
            'averageScore': round(average_score, 1)
        }
        
        # 3. Discipline Stats (unchanged)
        disciplines = DisciplineRecord.objects.filter(
            student=student,
            date__range=[term_start, term_end]
        )
        total_records = disciplines.count()
        low_severity = disciplines.filter(severity='minor').count()
        medium_severity = disciplines.filter(severity='moderate').count()
        high_severity = disciplines.filter(severity='major').count()
        last_incident = disciplines.order_by('-date').first()
        last_incident_date = last_incident.date.isoformat() if last_incident else None
        
        discipline_stats = {
            'totalRecords': total_records,
            'lowSeverity': low_severity,
            'mediumSeverity': medium_severity,
            'highSeverity': high_severity,
            'lastIncidentDate': last_incident_date
        }
        
        # 4. Grades Stats - FIXED: Use only current grade enrollments
        subject_grades = []
        total_grades = 0
        num_graded_subjects = 0
        for enrollment in enrollments:
            subj = enrollment.lesson.subject if enrollment.lesson_id else None
            if not subj:
                continue
            subject_subs = submissions.filter(enrollment__lesson__subject=subj)
            avg_grade = subject_subs.aggregate(avg=Avg('score'))['avg'] or 0
            has_grades = subject_subs.filter(score__isnull=False).exists()
            grade_status = 'graded' if has_grades else 'pending'
            grade_letter = self._compute_grade_letter(avg_grade) if has_grades else 'Pending'
            teacher = subj.teachers_subjects.first()
            subject_entry = {
                'subject': subj.name,
                'grade': round(avg_grade, 1),
                'gradeLetter': grade_letter,
                'teacher': teacher.user.get_full_name() if teacher else 'TBD',
                'status': grade_status
            }
            subject_grades.append(subject_entry)
            if has_grades:
                total_grades += avg_grade
                num_graded_subjects += 1
        
        average = round(total_grades / num_graded_subjects if num_graded_subjects > 0 else 0, 1)
        gpa = round(average / 25, 1)  # Placeholder GPA
        
        grades_stats = {
            'average': average,
            'gpa': gpa,
            'subjects': subject_grades
        }
        
        # 5. Performance (unchanged; uses current stream/grade)
        stream_students = student.stream.student_stream.all() if student.stream else student.grade_level.students.all()
        rank_in_class = list(stream_students).index(student) + 1 if stream_students.exists() else 1
        total_in_class = stream_students.count()
        percentile = round((total_in_class - rank_in_class + 1) / total_in_class * 100) if total_in_class > 0 else 0
        trend = 'improving' if attendance_rate > 80 else 'needs improvement'
        
        performance_stats = {
            'trend': trend,
            'rankInClass': rank_in_class,
            'totalStudentsInClass': total_in_class,
            'percentile': percentile
        }
        
        # Compile stats_data
        stats_data = {
            'studentId': student.student_id,
            'studentName': student.user.get_full_name(),
            'className': f"{student.grade_level.name} {student.stream.name}" if student.stream else student.grade_level.name,
            'attendance': attendance_stats,
            'assignments': assignments_stats,
            'discipline': discipline_stats,
            'grades': grades_stats,
            'performance': performance_stats
        }
        
        serializer = StudentStatsSerializer(data=stats_data)
        if serializer.is_valid():
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def _compute_grade_letter(self, score):
        if score >= 90:
            return 'A'
        elif score >= 80:
            return 'B+'
        elif score >= 70:
            return 'B'
        elif score >= 60:
            return 'C'
        else:
            return 'F'

class ParentStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_parent:
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        parent = get_object_or_404(Parent, user=request.user)
        
        # Placeholder children data from sample (full)
        children_data = []
        for child in parent.children.all()[:2]:  # Limit to sample size
            child_stats_data = {
                'studentId': child.student_id,
                'studentName': child.user.get_full_name(),
                'className': f"{child.grade_level.name} {child.stream.name}" if child.stream else child.grade_level.name,
                'attendance': {
                    'totalDays': 90,
                    'presentDays': 85,
                    'absentDays': 5,
                    'attendanceRate': 94.4,
                    'recentAbsences': 2
                },
                'assignments': {
                    'total': 12,
                    'completed': 10,
                    'pending': 2,
                    'overdue': 0,
                    'completionRate': 83.3
                },
                'discipline': {
                    'totalRecords': 2,
                    'lowSeverity': 2,
                    'mediumSeverity': 0,
                    'highSeverity': 0
                },
                'grades': {
                    'average': 85.5,
                    'subjects': [
                        {
                            'subject': 'Mathematics',
                            'grade': 88,
                            'gradeLetter': 'A'
                        },
                        {
                            'subject': 'English',
                            'grade': 82,
                            'gradeLetter': 'B+'
                        },
                        {
                            'subject': 'Science',
                            'grade': 90,
                            'gradeLetter': 'A'
                        }
                    ]
                }
            }
            child_serializer = StudentStatsSerializer(data=child_stats_data)
            child_serializer.is_valid()
            children_data.append(child_serializer.data)
        
        data = {
            'parentId': parent.parent_id,
            'parentName': parent.user.get_full_name(),
            'children': children_data
        }
        serializer = ParentStatsSerializer(data=data)
        serializer.is_valid()
        return Response(serializer.data)


class TeacherStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_role = get_user_role(request.user)
        if user_role != 'teacher':
            return Response({'error': 'Unauthorized'}, status=status.HTTP_403_FORBIDDEN)
        
        teacher = get_object_or_404(StaffProfile, user=request.user)
        
        # Serialize the teacher instance directly (computes stats via methods)
        serializer = TeacherStatsSerializer(teacher)
        return Response(serializer.data)


from django.db.models import Prefetch

class ParentChildrenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_parent:
            return Response({'error': 'Unauthorized'}, status=403)

        parent = get_object_or_404(Parent, user=request.user)

        children = parent.children.all().prefetch_related(
            Prefetch(
                'grade_attendance',   # <-- correct related name
                queryset=GradeAttendance.objects.select_related('stream', 'student'),
                to_attr='recent_stream_attendances'   # <-- what serializer expects
            ),
            Prefetch(
                'discipline_records',  # <-- correct related name
                queryset=DisciplineRecord.objects.all(),
                to_attr='recent_discipline_records'  # <-- expected by serializer
            ),
            Prefetch(
                'enrollments',
                queryset=Enrollment.objects.select_related('lesson__subject', 'school', 'student'),
                to_attr='current_enrollments'
            )
        )

        serializer = ParentChildrenSerializer(children, many=True)
        return Response(serializer.data)


# ═══════════════════════════════════════════════════════════════════════════════
# EXTENDED API VIEWS — full role coverage
# ═══════════════════════════════════════════════════════════════════════════════

# ── Profile ──────────────────────────────────────────────────────────────────

class ProfileView(APIView):
    """GET/PATCH own profile for any authenticated user."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(request.user, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── School Info ───────────────────────────────────────────────────────────────

class SchoolInfoView(APIView):
    """GET school details for any member; PATCH for admin/principal."""
    permission_classes = [IsAuthenticated]

    def _school(self, user):
        return get_user_school(user)

    def get(self, request):
        school = self._school(request.user)
        if not school:
            return Response({'error': 'No school associated.'}, status=status.HTTP_404_NOT_FOUND)
        return Response(SchoolSerializer(school).data)

    def patch(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = self._school(request.user)
        if not school:
            return Response({'error': 'No school associated.'}, status=status.HTTP_404_NOT_FOUND)
        serializer = SchoolSerializer(school, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Grades ────────────────────────────────────────────────────────────────────

class GradesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        grades = Grade.objects.filter(school=school, is_active=True).order_by('name')
        return Response(GradeSerializer(grades, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = GradeSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GradeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_grade(self, pk, school):
        return get_object_or_404(Grade, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        grade = self._get_grade(pk, school)
        return Response(GradeSerializer(grade).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        grade = self._get_grade(pk, school)
        serializer = GradeSerializer(grade, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        grade = self._get_grade(pk, school)
        grade.is_active = False
        grade.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Streams ───────────────────────────────────────────────────────────────────

class StreamsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        grade_id = request.query_params.get('grade_id')
        qs = Streams.objects.filter(school=school, is_active=True)
        if grade_id:
            qs = qs.filter(grade_id=grade_id)
        qs = qs.select_related('grade').order_by('grade__name', 'name')
        return Response(StreamSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = StreamSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StreamDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_stream(self, pk, school):
        return get_object_or_404(Streams, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        stream = self._get_stream(pk, school)
        return Response(StreamSerializer(stream).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        stream = self._get_stream(pk, school)
        serializer = StreamSerializer(stream, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        stream = self._get_stream(pk, school)
        stream.is_active = False
        stream.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Terms ─────────────────────────────────────────────────────────────────────

class TermsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        terms = Term.objects.filter(school=school).order_by('-start_date')
        return Response(TermSerializer(terms, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = TermSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class TermDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_term(self, pk, school):
        return get_object_or_404(Term, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        return Response(TermSerializer(self._get_term(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        term = self._get_term(pk, school)
        serializer = TermSerializer(term, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get_term(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Subjects ──────────────────────────────────────────────────────────────────

class SubjectsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = Subject.objects.filter(school=school, is_active=True).prefetch_related('grade')
        grade_id = request.query_params.get('grade_id')
        if grade_id:
            qs = qs.filter(grade__id=grade_id)
        return Response(SubjectListSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = SubjectListSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubjectDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Subject, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        return Response(SubjectListSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        subject = self._get(pk, school)
        serializer = SubjectListSerializer(subject, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        subject = self._get(pk, school)
        subject.is_active = False
        subject.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Staff ─────────────────────────────────────────────────────────────────────

class StaffListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = StaffProfile.objects.filter(school=school).select_related('user').prefetch_related('subjects')
        position = request.query_params.get('position')
        if position:
            qs = qs.filter(position=position)
        return Response(StaffSerializer(qs, many=True).data)


class StaffDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(StaffProfile, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        return Response(StaffSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = self._get(pk, school)
        serializer = StaffUpdateSerializer(staff, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(StaffSerializer(staff).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = self._get(pk, school)
        staff.user.is_active = False
        staff.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Students (admin/principal manage) ────────────────────────────────────────

class StudentDetailManageView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Student, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES and not (role == 'student' and request.user.student.pk == pk):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        student = self._get(pk, school) if role != 'student' else get_object_or_404(Student, pk=pk)
        return Response(StudentDetailSerializer(student).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        student = self._get(pk, school)
        serializer = StudentUpdateSerializer(student, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(StudentDetailSerializer(student).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        student = self._get(pk, school)
        student.is_active = False
        student.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


class StudentStatusView(APIView):
    """POST: suspend / expel / reinstate a student (principal/admin only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        student = get_object_or_404(Student, pk=pk, school=school)
        serializer = StudentStatusSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        action_val = serializer.validated_data['action']
        if action_val == 'suspend':
            student.suspended = True
            student.expelled = False
        elif action_val == 'expel':
            student.expelled = True
            student.suspended = False
            student.is_active = False
        elif action_val == 'reinstate':
            student.suspended = False
            student.expelled = False
            student.is_active = True
        student.save()
        return Response(StudentDetailSerializer(student).data)


# ── Parents (admin manage) ────────────────────────────────────────────────────

class ParentsListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = Parent.objects.filter(school=school).select_related('user').prefetch_related('children')
        return Response(ParentListSerializer(qs, many=True).data)


class ParentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Parent, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES and not (role == 'parent' and request.user.parent.pk == pk):
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        parent = self._get(pk, school) if role != 'parent' else get_object_or_404(Parent, pk=pk)
        return Response(ParentListSerializer(parent).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        parent = self._get(pk, school)
        serializer = ParentUpdateSerializer(parent, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(ParentListSerializer(parent).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        parent = self._get(pk, school)
        parent.user.is_active = False
        parent.user.save()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Lessons (teacher/admin manage) ───────────────────────────────────────────

class LessonsManageView(APIView):
    """GET list of lessons; POST create a lesson (teacher/admin)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        active_term = Term.objects.filter(school=school, is_active=True).first()
        qs = Lesson.objects.filter(timetable__school=school)
        if active_term:
            qs = qs.filter(timetable__term=active_term)
        if role == 'teacher':
            qs = qs.filter(teacher=request.user.staffprofile)
        stream_id = request.query_params.get('stream_id')
        if stream_id:
            qs = qs.filter(stream_id=stream_id)
        qs = qs.select_related('subject', 'stream__grade', 'teacher__user', 'time_slot')
        return Response(LessonSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = LessonCreateSerializer(data=request.data)
        if serializer.is_valid():
            lesson = serializer.save()
            return Response(LessonSerializer(lesson).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LessonManageDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Lesson, pk=pk, timetable__school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        return Response(LessonSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        lesson = self._get(pk, school)
        if role == 'teacher' and lesson.teacher != request.user.staffprofile:
            return Response({'error': 'Not your lesson.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = LessonUpdateSerializer(lesson, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(LessonSerializer(lesson).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Submissions ───────────────────────────────────────────────────────────────

class SubmissionsView(APIView):
    """GET submissions (role-filtered); POST submit assignment (student)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = Submission.objects.filter(school=school).select_related(
            'enrollment__student__user', 'assignment__subject'
        )
        if role == 'student':
            qs = qs.filter(enrollment__student=request.user.student)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if parent:
                qs = qs.filter(enrollment__student__parents=parent)
        elif role == 'teacher':
            qs = qs.filter(assignment__subject__in=request.user.staffprofile.subjects.all())
        assignment_id = request.query_params.get('assignment_id')
        if assignment_id:
            qs = qs.filter(assignment_id=assignment_id)
        return Response(SubmissionSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role != 'student':
            return Response({'error': 'Only students can submit.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SubmissionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            submission = serializer.save()
            return Response(SubmissionSerializer(submission).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SubmissionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Submission, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        submission = self._get(pk, school)
        return Response(SubmissionSerializer(submission).data)

    def patch(self, request, pk):
        """Grade a submission (teacher/admin only)."""
        role = get_user_role(request.user)
        if role not in {'teacher'} | ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        submission = self._get(pk, school)
        serializer = SubmissionGradeSerializer(submission, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(SubmissionSerializer(submission).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Exams ─────────────────────────────────────────────────────────────────────

class ExamSessionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = ExamSession.objects.filter(school=school).select_related('grade', 'term')
        if role in ('student', 'parent'):
            qs = qs.filter(is_published=True)
        return Response(ExamSessionSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ExamSessionCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            session = serializer.save()
            return Response(ExamSessionSerializer(session).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ExamSessionDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(ExamSession, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        session = self._get(pk, school)
        return Response(ExamSessionSerializer(session).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        session = self._get(pk, school)
        serializer = ExamSessionCreateSerializer(session, data=request.data, partial=True,
                                                  context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(ExamSessionSerializer(session).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ExamPublishView(APIView):
    """POST: publish or unpublish exam results (admin/principal)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        session.is_published = not session.is_published
        session.save()
        return Response({'id': session.pk, 'is_published': session.is_published})


class ExamResultsView(APIView):
    """GET results for an exam session; POST/bulk-create results (admin/teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        if role in ('student', 'parent') and not session.is_published:
            return Response({'error': 'Results not yet published.'}, status=status.HTTP_403_FORBIDDEN)
        qs = ExamResult.objects.filter(session=session).select_related(
            'student__user', 'subject'
        )
        if role == 'student':
            qs = qs.filter(student=request.user.student)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if parent:
                qs = qs.filter(student__parents=parent)
        stream_id = request.query_params.get('stream_id')
        if stream_id:
            qs = qs.filter(stream_id=stream_id)
        subject_id = request.query_params.get('subject_id')
        if subject_id:
            qs = qs.filter(subject_id=subject_id)
        return Response(ExamResultSerializer(qs, many=True).data)

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in {'teacher'} | ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        results_data = request.data.get('results', [request.data])
        created = []
        errors = []
        for item in results_data:
            serializer = ExamResultCreateSerializer(
                data=item, context={'request': request, 'session': session}
            )
            if serializer.is_valid():
                created.append(serializer.save())
            else:
                errors.append(serializer.errors)
        if errors:
            return Response({'errors': errors, 'created': len(created)},
                            status=status.HTTP_207_MULTI_STATUS)
        return Response(ExamResultSerializer(created, many=True).data, status=status.HTTP_201_CREATED)


class MyExamResultsView(APIView):
    """GET own exam results (student) or children's results (parent)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if role == 'student':
            qs = ExamResult.objects.filter(
                student=request.user.student,
                session__is_published=True,
                school=school
            ).select_related('session__grade', 'subject')
            return Response(ExamResultSerializer(qs, many=True).data)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent:
                return Response({'error': 'No parent profile.'}, status=status.HTTP_403_FORBIDDEN)
            qs = ExamResult.objects.filter(
                student__parents=parent,
                session__is_published=True,
                school=school
            ).select_related('session__grade', 'subject', 'student__user')
            return Response(ExamResultSerializer(qs, many=True).data)
        return Response({'error': 'Only students or parents.'}, status=status.HTTP_403_FORBIDDEN)


# ── Finance ───────────────────────────────────────────────────────────────────

class FeeInvoicesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        qs = FeeInvoice.objects.filter(school=school).select_related('student__user', 'term')
        if role == 'student':
            qs = qs.filter(student=request.user.student)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if parent:
                qs = qs.filter(student__parents=parent)
        elif role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        status_filter = request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(FeeInvoiceSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = FeeInvoiceCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            invoice = serializer.save()
            return Response(FeeInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FeeInvoiceDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(FeeInvoice, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        invoice = self._get(pk, school)
        return Response(FeeInvoiceSerializer(invoice).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        invoice = self._get(pk, school)
        serializer = FeeInvoiceCreateSerializer(invoice, data=request.data, partial=True,
                                                 context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(FeeInvoiceSerializer(invoice).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class FeePaymentView(APIView):
    """POST: record a payment against an invoice (admin/finance only)."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)
        serializer = FeePaymentSerializer(data=request.data)
        if serializer.is_valid():
            amount = serializer.validated_data['amount']
            invoice.amount_paid += amount
            invoice.payment_method = serializer.validated_data['payment_method']
            if serializer.validated_data.get('notes'):
                invoice.notes = serializer.validated_data['notes']
            invoice.save()
            return Response(FeeInvoiceSerializer(invoice).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FeeStructuresView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        qs = FeeStructure.objects.filter(school=school, is_active=True).select_related(
            'grade', 'term', 'fee_type'
        )
        return Response(FeeStructureSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = FeeStructureCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            fs = serializer.save()
            return Response(FeeStructureSerializer(fs).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StudentFeesView(APIView):
    """GET fee statement for a student (self) or parent (for children)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if role == 'student':
            qs = FeeInvoice.objects.filter(student=request.user.student, school=school)
            return Response(FeeInvoiceSerializer(qs, many=True).data)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent:
                return Response({'error': 'No parent profile.'}, status=status.HTTP_403_FORBIDDEN)
            qs = FeeInvoice.objects.filter(student__parents=parent, school=school)
            return Response(FeeInvoiceSerializer(qs, many=True).data)
        return Response({'error': 'Only students or parents.'}, status=status.HTTP_403_FORBIDDEN)


# ── Complaints ────────────────────────────────────────────────────────────────

class ComplaintsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        status_filter = request.query_params.get('status')

        if role == 'student':
            try:
                qs = Complaint.objects.filter(student_complainant=request.user.student)
            except Exception:
                qs = Complaint.objects.none()
        elif role == 'teacher':
            try:
                qs = Complaint.objects.filter(teacher_complainant=request.user.staffprofile)
            except Exception:
                qs = Complaint.objects.none()
        elif request.user.is_parent:
            try:
                qs = Complaint.objects.filter(parent=request.user.parent)
            except Exception:
                qs = Complaint.objects.none()
        elif role in ADMIN_ROLES:
            if not school:
                return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
            qs = Complaint.objects.filter(school=school, target='school_admin').select_related(
                'parent__user', 'student__user', 'teacher_complainant__user', 'student_complainant__user'
            )
        else:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ComplaintSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        allowed = request.user.is_parent or role in ALL_ROLES
        if not allowed:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = ComplaintCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            complaint = serializer.save()
            return Response(ComplaintSerializer(complaint).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ComplaintDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Complaint, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        complaint = self._get(pk, school)
        if role == 'parent' and complaint.parent != request.user.parent:
            return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        return Response(ComplaintSerializer(complaint).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        complaint = self._get(pk, school)
        if role in ADMIN_ROLES:
            serializer = ComplaintResponseSerializer(
                complaint, data=request.data, partial=True, context={'request': request}
            )
        elif role == 'parent' and complaint.parent == request.user.parent:
            # Parent can only update description before response
            if complaint.status != 'open':
                return Response({'error': 'Cannot edit after complaint is in review.'},
                                status=status.HTTP_400_BAD_REQUEST)
            serializer = ComplaintCreateSerializer(complaint, data=request.data, partial=True,
                                                   context={'request': request})
        else:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        if serializer.is_valid():
            serializer.save()
            return Response(ComplaintSerializer(complaint).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── School Announcements ──────────────────────────────────────────────────────

class SchoolAnnouncementsView(APIView):
    """GET school announcements (all school members); POST create (admin/teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        from django.utils import timezone as tz
        qs = Announcement.objects.filter(school=school).select_related('grade', 'created_by__user')
        # Filter by audience
        audience_map = {
            'student': ['all', 'students'],
            'parent': ['all', 'parents'],
            'teacher': ['all', 'staff'],
            'admin': None, 'principal': None, 'deputy': None,
        }
        allowed = audience_map.get(role)
        if allowed is not None:
            qs = qs.filter(audience__in=allowed)
        # Exclude expired
        qs = qs.filter(Q(expires_at__isnull=True) | Q(expires_at__gte=tz.now()))
        return Response(SchoolAnnouncementSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Only staff can create announcements.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SchoolAnnouncementCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            ann = serializer.save()
            return Response(SchoolAnnouncementSerializer(ann).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class SchoolAnnouncementDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Announcement, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        return Response(SchoolAnnouncementSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        ann = self._get(pk, school)
        serializer = SchoolAnnouncementCreateSerializer(ann, data=request.data, partial=True,
                                                        context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(SchoolAnnouncementSerializer(ann).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Send Notification ─────────────────────────────────────────────────────────

class SendNotificationView(APIView):
    """POST: send targeted notifications (admin/principal/teacher)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = NotificationSendSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            created = serializer.save()
            return Response({'sent': len(created), 'message': 'Notifications sent.'},
                            status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Grade Promotion ───────────────────────────────────────────────────────────

class GradePromoteView(APIView):
    """POST: promote students from one grade to the next (principal/admin)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        from_grade_id = request.data.get('from_grade_id')
        to_grade_id = request.data.get('to_grade_id')
        to_stream_id = request.data.get('to_stream_id')
        student_ids = request.data.get('student_ids')  # optional; if absent, all in grade
        if not from_grade_id or not to_grade_id:
            return Response({'error': 'from_grade_id and to_grade_id are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        from_grade = get_object_or_404(Grade, pk=from_grade_id, school=school)
        to_grade = get_object_or_404(Grade, pk=to_grade_id, school=school)
        to_stream = get_object_or_404(Streams, pk=to_stream_id, school=school) if to_stream_id else None
        qs = Student.objects.filter(grade_level=from_grade, school=school, is_active=True)
        if student_ids:
            qs = qs.filter(pk__in=student_ids)
        promoted = qs.count()
        qs.update(grade_level=to_grade, stream=to_stream)
        return Response({'promoted': promoted, 'to_grade': to_grade.name})


# ── Class Teacher Assignment ──────────────────────────────────────────────────

class ClassTeacherAssignView(APIView):
    """POST: assign a class teacher to a stream (principal/admin)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        teacher_id = request.data.get('teacher_id')
        stream_id = request.data.get('stream_id')
        if not teacher_id or not stream_id:
            return Response({'error': 'teacher_id and stream_id are required.'},
                            status=status.HTTP_400_BAD_REQUEST)
        teacher = get_object_or_404(StaffProfile, pk=teacher_id, school=school)
        stream = get_object_or_404(Streams, pk=stream_id, school=school)
        assigner = getattr(request.user, 'staffprofile', None)
        assignment, created = ClassTeacherAssignment.objects.update_or_create(
            school=school, stream=stream,
            defaults={'teacher': teacher, 'assigned_by': assigner}
        )
        return Response({
            'teacher': teacher.user.get_full_name(),
            'stream': f"{stream.grade.name} {stream.name}",
            'created': created,
        })


# ── Dashboard ─────────────────────────────────────────────────────────────────

class DashboardView(APIView):
    """GET role-appropriate dashboard summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)

        if role in ADMIN_ROLES | {'policy_maker'}:
            return self._admin_dashboard(request.user, school)
        elif role == 'teacher':
            return self._teacher_dashboard(request.user, school)
        elif role == 'student':
            return self._student_dashboard(request.user, school)
        elif role == 'parent':
            return self._parent_dashboard(request.user, school)
        return Response({'error': 'No dashboard for this role.'}, status=status.HTTP_403_FORBIDDEN)

    def _admin_dashboard(self, user, school):
        from django.utils import timezone as tz
        active_term = Term.objects.filter(school=school, is_active=True).first()
        today = tz.now().date()
        total_present = GradeAttendance.objects.filter(
            student__school=school, recorded_at__date=today, status='P'
        ).count()
        total_students = Student.objects.filter(school=school, is_active=True).count()
        data = {
            'school_name': school.name,
            'total_students': total_students,
            'total_staff': StaffProfile.objects.filter(school=school).count(),
            'total_parents': Parent.objects.filter(school=school).count(),
            'active_term': active_term.name if active_term else None,
            'attendance_today': {
                'present': total_present,
                'total': total_students,
                'rate': round(total_present / total_students * 100, 1) if total_students else 0,
            },
            'pending_complaints': Complaint.objects.filter(school=school, status='open').count(),
            'recent_discipline': DisciplineRecord.objects.filter(school=school).count(),
            'unpaid_invoices': FeeInvoice.objects.filter(school=school, status='pending').count(),
        }
        return Response(AdminDashboardSerializer(data).data)

    def _teacher_dashboard(self, user, school):
        from django.utils import timezone as tz
        teacher = getattr(user, 'staffprofile', None)
        if not teacher:
            return Response({'error': 'No staff profile.'}, status=status.HTTP_403_FORBIDDEN)
        today = tz.now().date()
        data = {
            'teacher_name': user.get_full_name(),
            'lessons_today': Lesson.objects.filter(teacher=teacher, lesson_date=today).count(),
            'total_subjects': teacher.subjects.count(),
            'pending_assignments': Assignment.objects.filter(
                school=school, subject__in=teacher.subjects.all()
            ).count(),
            'recent_discipline': DisciplineRecord.objects.filter(teacher=teacher).count(),
        }
        return Response(TeacherDashboardSerializer(data).data)

    def _student_dashboard(self, user, school):
        student = getattr(user, 'student', None)
        if not student:
            return Response({'error': 'No student profile.'}, status=status.HTTP_403_FORBIDDEN)
        active_term = Term.objects.filter(school=school, is_active=True).first()
        total_att = Attendance.objects.filter(enrollment__student=student).count()
        present_att = Attendance.objects.filter(enrollment__student=student, status='P').count()
        rate = round(present_att / total_att * 100, 1) if total_att else 0
        pending_fee = FeeInvoice.objects.filter(student=student, status='pending').aggregate(
            total=Count('id'), amount=Sum('amount_required')
        ) if FeeInvoice else {'total': 0, 'amount': 0}
        pending_assignments = Assignment.objects.filter(
            school=school,
            subject__in=SubjectEnrollment.objects.filter(
                student=student, is_active=True
            ).values('subject'),
            due_date__gte=timezone.now(),
        ).count()
        data = {
            'student_name': user.get_full_name(),
            'class_name': (f"{student.grade_level.name} {student.stream.name}"
                           if student.stream else student.grade_level.name),
            'attendance_rate': rate,
            'pending_assignments': pending_assignments,
            'pending_fees': {
                'count': FeeInvoice.objects.filter(student=student, status__in=['pending', 'partial']).count(),
                'total_amount': float(FeeInvoice.objects.filter(
                    student=student, status__in=['pending', 'partial']
                ).aggregate(s=Sum('amount_required'))['s'] or 0),
            },
        }
        return Response(StudentDashboardSerializer(data).data)

    def _parent_dashboard(self, user, school):
        parent = getattr(user, 'parent', None)
        if not parent:
            return Response({'error': 'No parent profile.'}, status=status.HTTP_403_FORBIDDEN)
        data = {
            'parent_name': user.get_full_name(),
            'children_count': parent.children.count(),
            'unread_notifications': Notification.objects.filter(recipient=user, is_read=False).count(),
            'pending_complaints': Complaint.objects.filter(parent=parent, status='open').count(),
        }
        return Response(ParentDashboardSerializer(data).data)


# ── Policy Maker Dashboard ────────────────────────────────────────────────────

class PolicyDashboardView(APIView):
    """GET: high-level policy metrics (policy_maker/principal/admin)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES | {'policy_maker'}:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        active_term = Term.objects.filter(school=school, is_active=True).first()
        from django.db.models import Avg as _Avg
        data = {
            'school': SchoolSerializer(school).data,
            'active_term': TermSerializer(active_term).data if active_term else None,
            'enrollment': {
                'total_students': Student.objects.filter(school=school, is_active=True).count(),
                'total_staff': StaffProfile.objects.filter(school=school).count(),
            },
            'attendance_summary': {
                'last_7_days': GradeAttendance.objects.filter(
                    student__school=school,
                    recorded_at__gte=timezone.now() - timedelta(days=7)
                ).values('status').annotate(count=Count('id'))
            },
            'discipline_summary': {
                'total': DisciplineRecord.objects.filter(school=school).count(),
                'by_severity': list(
                    DisciplineRecord.objects.filter(school=school)
                    .values('severity').annotate(count=Count('id'))
                ),
            },
            'exam_summary': {
                'sessions': ExamSession.objects.filter(school=school).count(),
                'published': ExamSession.objects.filter(school=school, is_published=True).count(),
            },
            'finance_summary': {
                'total_invoiced': float(
                    FeeInvoice.objects.filter(school=school).aggregate(
                        s=Sum('amount_required')
                    )['s'] or 0
                ),
                'total_collected': float(
                    FeeInvoice.objects.filter(school=school).aggregate(
                        s=Sum('amount_paid')
                    )['s'] or 0
                ),
            },
        }
        return Response(data)


# ── Time Slots ────────────────────────────────────────────────────────────────

class TimeSlotsView(APIView):
    """GET all time slots; POST create (admin only)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)
        slots = TimeSlot.objects.filter(school=school).order_by('start_time')
        data = [
            {
                'id': ts.id,
                'description': ts.description,
                'start_time': ts.start_time.strftime('%H:%M'),
                'end_time': ts.end_time.strftime('%H:%M'),
            }
            for ts in slots
        ]
        return Response(data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = getattr(request.user, 'staffprofile', None)
        ts = TimeSlot.objects.create(
            school=school,
            start_time=request.data.get('start_time'),
            end_time=request.data.get('end_time'),
            description=request.data.get('description', ''),
            created_by=staff,
        )
        return Response({
            'id': ts.id, 'description': ts.description,
            'start_time': ts.start_time.strftime('%H:%M'),
            'end_time': ts.end_time.strftime('%H:%M'),
        }, status=status.HTTP_201_CREATED)


# ── Timetables ────────────────────────────────────────────────────────────────

class TimetablesView(APIView):
    """GET timetables; POST create timetable (admin/principal)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        qs = Timetable.objects.filter(school=school, is_active=True).select_related(
            'grade', 'stream', 'term'
        )
        data = [
            {
                'id': tt.id,
                'grade': tt.grade.name if tt.grade else None,
                'stream': tt.stream.name if tt.stream else None,
                'term': tt.term.name if tt.term else None,
                'year': tt.year,
                'start_date': tt.start_date,
                'end_date': tt.end_date,
                'is_active': tt.is_active,
            }
            for tt in qs
        ]
        return Response(data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        data = request.data
        tt = Timetable.objects.create(
            school=school,
            grade_id=data.get('grade_id'),
            stream_id=data.get('stream_id'),
            term_id=data.get('term_id'),
            year=data.get('year'),
            start_date=data.get('start_date'),
            end_date=data.get('end_date'),
        )
        return Response({'id': tt.id, 'grade': tt.grade.name if tt.grade else None}, status=status.HTTP_201_CREATED)


# ── Mark Notification Read ────────────────────────────────────────────────────

class MarkNotificationReadView(APIView):
    """PATCH: mark a notification as read."""
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        notification = get_object_or_404(Notification, pk=pk, recipient=request.user)
        notification.is_read = True
        notification.save()
        return Response({'id': pk, 'is_read': True})

    def post(self, request):
        """POST body: {"ids": [...]} — mark multiple as read."""
        ids = request.data.get('ids', [])
        Notification.objects.filter(recipient=request.user, pk__in=ids).update(is_read=True)
        return Response({'marked': len(ids)})


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT 1 — Core School Management Gaps
# ═══════════════════════════════════════════════════════════════════════════════

from .serializers import (
    CreateStudentSerializer, CreateStaffSerializer, CreateParentSerializer,
    PasswordResetSerializer, EnrollmentSerializer, EnrollmentCreateSerializer,
    FeeTypeSerializer, ClassTeacherAssignmentSerializer,
    ExamRankingEntrySerializer, FeeInvoiceReceiptSerializer,
)


# ── Student create (POST /api/students/) ──────────────────────────────────────

class StudentCreateView(APIView):
    """POST: admin creates a new student user + profile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = CreateStudentSerializer(data=request.data, context={'school': school, 'request': request})
        if serializer.is_valid():
            student = serializer.save()
            from .serializers import StudentDetailSerializer
            return Response(StudentDetailSerializer(student).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Staff create (POST /api/staff/) extended ──────────────────────────────────

class StaffCreateView(APIView):
    """POST: admin creates a new staff user + profile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = CreateStaffSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            staff = serializer.save()
            return Response(StaffSerializer(staff).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Parent create (POST /api/parents/) extended ───────────────────────────────

class ParentCreateView(APIView):
    """POST: admin creates a new parent user + profile."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = CreateParentSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            parent = serializer.save()
            return Response(ParentListSerializer(parent).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Password reset (POST /api/users/<pk>/reset-password/) ────────────────────

class UserPasswordResetView(APIView):
    """POST: admin resets any user's password."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        target_user = get_object_or_404(User, pk=pk)
        # Ensure target belongs to the same school
        target_school = get_user_school(target_user)
        if target_school != school:
            return Response({'error': 'User not in your school.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = PasswordResetSerializer(data=request.data)
        if serializer.is_valid():
            target_user.set_password(serializer.validated_data['new_password'])
            target_user.save()
            return Response({'message': 'Password reset successfully.'})
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ── Staff subjects (GET/POST /api/staff/<pk>/subjects/) ───────────────────────

class StaffSubjectsView(APIView):
    """GET subjects assigned to a teacher; POST assign a subject."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = get_object_or_404(StaffProfile, pk=pk, school=school)
        from .serializers import SubjectListSerializer
        return Response(SubjectListSerializer(staff.subjects.all(), many=True).data)

    def post(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = get_object_or_404(StaffProfile, pk=pk, school=school)
        subject_id = request.data.get('subject_id')
        if not subject_id:
            return Response({'error': 'subject_id required.'}, status=status.HTTP_400_BAD_REQUEST)
        subject = get_object_or_404(Subject, pk=subject_id, school=school)
        staff.subjects.add(subject)
        return Response({'message': f'{subject.name} assigned to {staff.user.get_full_name()}.'})


class StaffSubjectRemoveView(APIView):
    """DELETE: remove a subject from a teacher."""
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk, subject_pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        staff = get_object_or_404(StaffProfile, pk=pk, school=school)
        subject = get_object_or_404(Subject, pk=subject_pk, school=school)
        staff.subjects.remove(subject)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Parent-student link ───────────────────────────────────────────────────────

class ParentStudentLinkView(APIView):
    """POST: link an existing parent to an existing student."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        parent_id = request.data.get('parent_id')
        student_id = request.data.get('student_id')
        if not parent_id or not student_id:
            return Response({'error': 'parent_id and student_id are required.'}, status=status.HTTP_400_BAD_REQUEST)
        parent = get_object_or_404(Parent, pk=parent_id, school=school)
        student = get_object_or_404(Student, pk=student_id, school=school)
        student.parents.add(parent)
        return Response({
            'message': f'{parent.user.get_full_name()} linked to {student.user.get_full_name()}.',
            'parent_id': parent.pk,
            'student_id': student.pk,
        })

    def delete(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        parent_id = request.data.get('parent_id')
        student_id = request.data.get('student_id')
        parent = get_object_or_404(Parent, pk=parent_id, school=school)
        student = get_object_or_404(Student, pk=student_id, school=school)
        student.parents.remove(parent)
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Enrollments ───────────────────────────────────────────────────────────────

class EnrollmentsView(APIView):
    """GET/POST lesson enrollments (admin/teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        qs = Enrollment.objects.filter(school=school).select_related(
            'student__user', 'lesson__subject', 'lesson__stream'
        )
        lesson_id = request.query_params.get('lesson_id')
        if lesson_id:
            qs = qs.filter(lesson_id=lesson_id)
        student_id = request.query_params.get('student_id')
        if student_id:
            qs = qs.filter(student_id=student_id)
        return Response(EnrollmentSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = EnrollmentCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            enrollment = serializer.save()
            return Response(EnrollmentSerializer(enrollment).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class EnrollmentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Enrollment, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        return Response(EnrollmentSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        enrollment = self._get(pk, school)
        status_val = request.data.get('status')
        if status_val:
            enrollment.status = status_val
            enrollment.save()
        return Response(EnrollmentSerializer(enrollment).data)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Timetable detail (PATCH/DELETE) ──────────────────────────────────────────

class TimetableDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(Timetable, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        tt = self._get(pk, school)
        return Response({
            'id': tt.id, 'grade': tt.grade.name if tt.grade else None,
            'stream': tt.stream.name if tt.stream else None,
            'term': tt.term.name if tt.term else None,
            'year': tt.year, 'start_date': tt.start_date,
            'end_date': tt.end_date, 'is_active': tt.is_active,
        })

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        tt = self._get(pk, school)
        for field in ['grade_id', 'stream_id', 'term_id', 'year', 'start_date', 'end_date', 'is_active']:
            if field in request.data:
                setattr(tt, field, request.data[field])
        tt.save()
        return Response({
            'id': tt.id, 'grade': tt.grade.name if tt.grade else None,
            'is_active': tt.is_active,
        })

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Time slot detail (PATCH/DELETE) ──────────────────────────────────────────

class TimeSlotDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(TimeSlot, pk=pk, school=school)

    def get(self, request, pk):
        school = get_user_school(request.user)
        ts = self._get(pk, school)
        return Response({
            'id': ts.id, 'description': ts.description,
            'start_time': ts.start_time.strftime('%H:%M'),
            'end_time': ts.end_time.strftime('%H:%M'),
        })

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        ts = self._get(pk, school)
        if 'start_time' in request.data:
            ts.start_time = request.data['start_time']
        if 'end_time' in request.data:
            ts.end_time = request.data['end_time']
        if 'description' in request.data:
            ts.description = request.data['description']
        ts.save()
        return Response({
            'id': ts.id, 'description': ts.description,
            'start_time': ts.start_time.strftime('%H:%M'),
            'end_time': ts.end_time.strftime('%H:%M'),
        })

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Class Teacher Portal ──────────────────────────────────────────────────────

class ClassTeacherListView(APIView):
    """GET all class teacher assignments for the school (admin/principal)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        qs = ClassTeacherAssignment.objects.filter(school=school).select_related(
            'teacher__user', 'stream__grade'
        )
        return Response(ClassTeacherAssignmentSerializer(qs, many=True).data)


class ClassTeacherRosterView(APIView):
    """GET students in the class teacher's own assigned stream."""
    permission_classes = [IsAuthenticated]

    def _get_assignment(self, user, school):
        teacher = getattr(user, 'staffprofile', None)
        if not teacher:
            return None
        return ClassTeacherAssignment.objects.filter(school=school, teacher=teacher).first()

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)

        # Admin can pass stream_id; class teacher sees their own
        stream_id = request.query_params.get('stream_id')
        if role in ADMIN_ROLES and stream_id:
            stream = get_object_or_404(Streams, pk=stream_id, school=school)
        else:
            assignment = self._get_assignment(request.user, school)
            if not assignment:
                return Response({'error': 'No class teacher assignment found.'}, status=status.HTTP_404_NOT_FOUND)
            stream = assignment.stream

        students = Student.objects.filter(stream=stream, school=school, is_active=True).select_related('user')
        from .serializers import StudentDetailSerializer
        return Response({
            'stream': f"{stream.grade.name} {stream.name}",
            'total': students.count(),
            'students': StudentDetailSerializer(students, many=True).data,
        })


class ClassTeacherRollCallView(APIView):
    """POST: class teacher marks roll call (stream-level attendance)."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)

        stream_id = request.data.get('stream_id')
        if role in ADMIN_ROLES and stream_id:
            stream = get_object_or_404(Streams, pk=stream_id, school=school)
        else:
            teacher = getattr(request.user, 'staffprofile', None)
            assignment = ClassTeacherAssignment.objects.filter(school=school, teacher=teacher).first()
            if not assignment:
                return Response({'error': 'No class teacher assignment found.'}, status=status.HTTP_404_NOT_FOUND)
            stream = assignment.stream

        today = timezone.now().date()
        sessions_today = GradeAttendance.objects.filter(
            stream=stream, recorded_at__date=today
        ).annotate(hour=TruncHour('recorded_at')).values('hour').annotate(c=Count('id')).count()
        if sessions_today >= 3:
            return Response({'error': 'Maximum 3 sessions per day reached.'}, status=status.HTTP_400_BAD_REQUEST)

        attendances_data = request.data.get('attendances', [])
        created = []
        for item in attendances_data:
            student = get_object_or_404(Student, pk=item['student_id'], stream=stream, school=school)
            ga = GradeAttendance.objects.create(
                student=student, stream=stream, status=item.get('status', 'P')
            )
            created.append(ga)
        return Response({'created': len(created), 'stream': stream.name}, status=status.HTTP_201_CREATED)


class ClassTeacherAttendanceSummaryView(APIView):
    """GET attendance summary for a class teacher's stream."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)

        stream_id = request.query_params.get('stream_id')
        if role in ADMIN_ROLES and stream_id:
            stream = get_object_or_404(Streams, pk=stream_id, school=school)
        else:
            teacher = getattr(request.user, 'staffprofile', None)
            assignment = ClassTeacherAssignment.objects.filter(school=school, teacher=teacher).first()
            if not assignment:
                return Response({'error': 'No class teacher assignment.'}, status=status.HTTP_404_NOT_FOUND)
            stream = assignment.stream

        days = int(request.query_params.get('days', 30))
        since = timezone.now().date() - timedelta(days=days)
        qs = GradeAttendance.objects.filter(stream=stream, recorded_at__date__gte=since)

        total = qs.count()
        present = qs.filter(status='P').count()
        absent = total - present
        rate = round(present / total * 100, 1) if total else 0

        per_student = []
        students = Student.objects.filter(stream=stream, school=school, is_active=True).select_related('user')
        for s in students:
            s_qs = qs.filter(student=s)
            s_total = s_qs.count()
            s_present = s_qs.filter(status='P').count()
            per_student.append({
                'student_id': s.student_id,
                'name': s.user.get_full_name(),
                'present': s_present,
                'absent': s_total - s_present,
                'rate': round(s_present / s_total * 100, 1) if s_total else 0,
            })

        return Response({
            'stream': f"{stream.grade.name} {stream.name}",
            'period_days': days,
            'summary': {'total': total, 'present': present, 'absent': absent, 'rate': rate},
            'per_student': per_student,
        })


class ClassTeacherSubjectSummaryView(APIView):
    """GET assignment/submission performance summary per subject for a stream."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)

        stream_id = request.query_params.get('stream_id')
        if role in ADMIN_ROLES and stream_id:
            stream = get_object_or_404(Streams, pk=stream_id, school=school)
        else:
            teacher = getattr(request.user, 'staffprofile', None)
            assignment = ClassTeacherAssignment.objects.filter(school=school, teacher=teacher).first()
            if not assignment:
                return Response({'error': 'No class teacher assignment.'}, status=status.HTTP_404_NOT_FOUND)
            stream = assignment.stream

        subjects = Subject.objects.filter(school=school, grade=stream.grade, is_active=True)
        summary = []
        for subject in subjects:
            lessons = Lesson.objects.filter(stream=stream, subject=subject, timetable__school=school)
            assignments = Assignment.objects.filter(school=school, subject=subject)
            submissions = Submission.objects.filter(
                assignment__in=assignments,
                enrollment__student__stream=stream
            )
            avg_score = submissions.aggregate(avg=Avg('score'))['avg']
            summary.append({
                'subject_id': subject.id,
                'subject_name': subject.name,
                'total_lessons': lessons.count(),
                'total_assignments': assignments.count(),
                'total_submissions': submissions.count(),
                'average_score': round(avg_score, 1) if avg_score else None,
            })

        return Response({'stream': f"{stream.grade.name} {stream.name}", 'subjects': summary})


# ── Attendance Summary ────────────────────────────────────────────────────────

class AttendanceSummaryView(APIView):
    """GET attendance summary grouped by grade/stream/term (admin/teacher)."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)

        days = int(request.query_params.get('days', 30))
        since = timezone.now().date() - timedelta(days=days)

        streams = Streams.objects.filter(school=school, is_active=True).select_related('grade')
        summary = []
        for stream in streams:
            qs = GradeAttendance.objects.filter(stream=stream, recorded_at__date__gte=since)
            total = qs.count()
            present = qs.filter(status='P').count()
            summary.append({
                'stream_id': stream.id,
                'stream_name': f"{stream.grade.name} {stream.name}",
                'total_records': total,
                'present': present,
                'absent': total - present,
                'rate': round(present / total * 100, 1) if total else 0,
            })

        return Response({'period_days': days, 'streams': summary})


class TeacherAttendanceSummaryView(APIView):
    """GET teacher's own lesson attendance summary."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        teacher_id = request.query_params.get('teacher_id')
        school = get_user_school(request.user)

        if teacher_id and role in ADMIN_ROLES:
            teacher = get_object_or_404(StaffProfile, pk=teacher_id, school=school)
        else:
            teacher = getattr(request.user, 'staffprofile', None)
            if not teacher:
                return Response({'error': 'No staff profile.'}, status=status.HTTP_403_FORBIDDEN)

        active_term = Term.objects.filter(school=school, is_active=True).first()
        lessons = Lesson.objects.filter(teacher=teacher, timetable__school=school)
        if active_term:
            lessons = lessons.filter(timetable__term=active_term)

        lesson_summaries = []
        for lesson in lessons.select_related('subject', 'stream__grade'):
            total = Attendance.objects.filter(enrollment__lesson=lesson).count()
            present = Attendance.objects.filter(enrollment__lesson=lesson, status='P').count()
            lesson_summaries.append({
                'lesson_id': lesson.id,
                'subject': lesson.subject.name,
                'stream': f"{lesson.stream.grade.name} {lesson.stream.name}" if lesson.stream else '',
                'day': lesson.day_of_week,
                'date': lesson.lesson_date,
                'total_students': total,
                'present': present,
                'absent': total - present,
                'rate': round(present / total * 100, 1) if total else 0,
            })

        return Response({
            'teacher': teacher.user.get_full_name(),
            'active_term': active_term.name if active_term else None,
            'lessons': lesson_summaries,
        })


class SmartAttendanceView(APIView):
    """POST: mark attendance for a lesson via SmartID card scan."""
    permission_classes = [IsAuthenticated]

    def post(self, request, lesson_id):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        lesson = get_object_or_404(Lesson, pk=lesson_id, timetable__school=school)

        card_numbers = request.data.get('card_numbers', [])
        if not card_numbers:
            return Response({'error': 'card_numbers list is required.'}, status=status.HTTP_400_BAD_REQUEST)

        from school.models import SmartID
        marked_present = []
        not_found = []
        for card_num in card_numbers:
            smart_id = SmartID.objects.filter(card_number=card_num, school=school).first()
            if not smart_id or not smart_id.student:
                not_found.append(card_num)
                continue
            student = smart_id.student
            enrollment = Enrollment.objects.filter(student=student, lesson=lesson).first()
            if enrollment:
                teacher = getattr(request.user, 'staffprofile', None)
                Attendance.objects.update_or_create(
                    enrollment=enrollment,
                    date=lesson.lesson_date or timezone.now().date(),
                    defaults={'status': 'P', 'marked_by': teacher}
                )
                marked_present.append(student.user.get_full_name())

        return Response({
            'lesson_id': lesson_id,
            'marked_present': len(marked_present),
            'students': marked_present,
            'not_found_cards': not_found,
        })


# ═══════════════════════════════════════════════════════════════════════════════
# SPRINT 2 — Finance, Exams, Attendance Completeness
# ═══════════════════════════════════════════════════════════════════════════════

# ── Fee Type CRUD ─────────────────────────────────────────────────────────────

class FeeTypesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        qs = FeeType.objects.filter(school=school)
        return Response(FeeTypeSerializer(qs, many=True).data)

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        serializer = FeeTypeSerializer(data=request.data, context={'school': school})
        if serializer.is_valid():
            ft = serializer.save()
            return Response(FeeTypeSerializer(ft).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class FeeTypeDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(FeeType, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        return Response(FeeTypeSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        ft = self._get(pk, school)
        serializer = FeeTypeSerializer(ft, data=request.data, partial=True, context={'school': school})
        if serializer.is_valid():
            serializer.save()
            return Response(FeeTypeSerializer(ft).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Fee Structure detail (PATCH/DELETE) ──────────────────────────────────────

class FeeStructureDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(FeeStructure, pk=pk, school=school)

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        return Response(FeeStructureSerializer(self._get(pk, school)).data)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        fs = self._get(pk, school)
        serializer = FeeStructureCreateSerializer(fs, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            return Response(FeeStructureSerializer(fs).data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


# ── Fee Invoice bulk generate ─────────────────────────────────────────────────

class FeeInvoiceBulkGenerateView(APIView):
    """POST: generate invoices for all students in a term from fee structures."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        term_id = request.data.get('term_id')
        if not term_id:
            return Response({'error': 'term_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        term = get_object_or_404(Term, pk=term_id, school=school)

        structures = FeeStructure.objects.filter(school=school, term=term, is_active=True)
        if not structures.exists():
            return Response({'error': 'No active fee structures for this term.'}, status=status.HTTP_400_BAD_REQUEST)

        created_count = 0
        skipped_count = 0
        for structure in structures:
            students = Student.objects.filter(
                school=school, grade_level=structure.grade, is_active=True
            )
            if structure.stream:
                students = students.filter(stream=structure.stream)
            for student in students:
                _, created = FeeInvoice.objects.get_or_create(
                    school=school, student=student, term=term,
                    description=structure.description,
                    defaults={
                        'amount_required': structure.amount,
                        'created_by': request.user,
                    }
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        return Response({
            'term': term.name,
            'created': created_count,
            'skipped_existing': skipped_count,
        }, status=status.HTTP_201_CREATED)


# ── M-Pesa STK Push ──────────────────────────────────────────────────────────

class FeeSTKPushView(APIView):
    """POST: initiate M-Pesa STK push for a fee invoice."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)

        if role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent or invoice.student not in parent.children.all():
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        phone = request.data.get('phone', '')
        if not phone:
            return Response({'error': 'phone is required.'}, status=status.HTTP_400_BAD_REQUEST)

        # Initiate STK push (placeholder — integrate Daraja API in production)
        return Response({
            'message': f'STK Push initiated to {phone} for KES {float(invoice.balance)}.',
            'invoice_id': invoice.pk,
            'amount': float(invoice.balance),
            'phone': phone,
            'status': 'pending',
        })


# ── Fee Invoice receipt ───────────────────────────────────────────────────────

class FeeInvoiceReceiptView(APIView):
    """GET: receipt data for a paid invoice."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        invoice = get_object_or_404(FeeInvoice, pk=pk, school=school)

        if role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent or invoice.student not in parent.children.all():
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role == 'student':
            if not hasattr(request.user, 'student') or invoice.student != request.user.student:
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        return Response(FeeInvoiceReceiptSerializer(invoice).data)


# ── Fee Collection Report ─────────────────────────────────────────────────────

class FeeCollectionReportView(APIView):
    """GET aggregated fee collection report for admin/principal."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES | {'policy_maker'}:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        if not school:
            return Response({'error': 'No school.'}, status=status.HTTP_403_FORBIDDEN)

        term_id = request.query_params.get('term_id')
        qs = FeeInvoice.objects.filter(school=school)
        if term_id:
            qs = qs.filter(term_id=term_id)

        agg = qs.aggregate(
            total_invoiced=Sum('amount_required'),
            total_collected=Sum('amount_paid'),
        )
        total_invoiced = float(agg['total_invoiced'] or 0)
        total_collected = float(agg['total_collected'] or 0)
        balance = total_invoiced - total_collected
        collection_rate = round(total_collected / total_invoiced * 100, 1) if total_invoiced else 0

        by_status = list(qs.values('status').annotate(
            count=Count('id'), amount=Sum('amount_required')
        ))

        by_grade = []
        grades = Grade.objects.filter(school=school)
        for grade in grades:
            g_qs = qs.filter(student__grade_level=grade)
            g_agg = g_qs.aggregate(invoiced=Sum('amount_required'), collected=Sum('amount_paid'))
            by_grade.append({
                'grade': grade.name,
                'total_students': g_qs.values('student').distinct().count(),
                'total_invoiced': float(g_agg['invoiced'] or 0),
                'total_collected': float(g_agg['collected'] or 0),
            })

        return Response({
            'total_invoiced': total_invoiced,
            'total_collected': total_collected,
            'balance': balance,
            'collection_rate': collection_rate,
            'by_status': by_status,
            'by_grade': by_grade,
        })


# ── Student Fee Statement ─────────────────────────────────────────────────────

class StudentFeeStatementView(APIView):
    """GET full fee statement for a specific student (admin or parent)."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        student = get_object_or_404(Student, pk=pk, school=school)

        if role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent or student not in parent.children.all():
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role == 'student':
            if not hasattr(request.user, 'student') or request.user.student.pk != pk:
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)

        invoices = FeeInvoice.objects.filter(student=student, school=school).select_related('term').order_by('-created_at')
        agg = invoices.aggregate(total_invoiced=Sum('amount_required'), total_paid=Sum('amount_paid'))

        return Response({
            'student': {
                'id': student.pk,
                'name': student.user.get_full_name(),
                'grade': student.grade_level.name,
                'stream': student.stream.name if student.stream else None,
            },
            'summary': {
                'total_invoiced': float(agg['total_invoiced'] or 0),
                'total_paid': float(agg['total_paid'] or 0),
                'balance': float((agg['total_invoiced'] or 0) - (agg['total_paid'] or 0)),
            },
            'invoices': FeeInvoiceSerializer(invoices, many=True).data,
        })


# ── Exam Rankings ─────────────────────────────────────────────────────────────

def _compute_exam_ranking(session, students):
    """Return sorted list with position, totals, for students in session."""
    from school.models import ExamResult as ER
    rows = []
    for student in students:
        results = ER.objects.filter(session=session, student=student)
        total = sum(r.total for r in results if r.total is not None)
        pct = round(total / (session.total_marks * results.count()) * 100, 1) if results.count() and session.total_marks else None
        rows.append({
            'student': student,
            'total_score': round(total, 2) if results.count() else None,
            'percentage': pct,
        })
    rows.sort(key=lambda x: (x['total_score'] is None, -(x['total_score'] or 0)))
    ranked = []
    for i, row in enumerate(rows):
        ranked.append({
            'position': i + 1,
            'student_id': row['student'].student_id,
            'student_name': row['student'].user.get_full_name(),
            'stream_name': row['student'].stream.name if row['student'].stream else None,
            'total_score': row['total_score'],
            'percentage': row['percentage'],
            'grade_band': None,
        })
    return ranked


class ExamGradeRankingView(APIView):
    """GET grade-level ranking for an exam session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        if role in ('student', 'parent') and not session.is_published:
            return Response({'error': 'Results not published.'}, status=status.HTTP_403_FORBIDDEN)
        students = Student.objects.filter(
            school=school, grade_level=session.grade, is_active=True
        ).select_related('user', 'stream')
        ranking = _compute_exam_ranking(session, students)
        return Response({
            'session': session.name,
            'grade': session.grade.name,
            'total_students': len(ranking),
            'ranking': ranking,
        })


class ExamStreamRankingView(APIView):
    """GET stream-level ranking for an exam session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, stream_pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        stream = get_object_or_404(Streams, pk=stream_pk, school=school)
        if role in ('student', 'parent') and not session.is_published:
            return Response({'error': 'Results not published.'}, status=status.HTTP_403_FORBIDDEN)
        students = Student.objects.filter(
            school=school, stream=stream, is_active=True
        ).select_related('user', 'stream')
        ranking = _compute_exam_ranking(session, students)
        return Response({
            'session': session.name,
            'stream': f"{stream.grade.name} {stream.name}",
            'total_students': len(ranking),
            'ranking': ranking,
        })


class ExamSubjectPerformanceView(APIView):
    """GET subject-wise performance breakdown for an exam session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        role = get_user_role(request.user)
        if role not in STAFF_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)

        stream_id = request.query_params.get('stream_id')
        qs = ExamResult.objects.filter(session=session, school=school)
        if stream_id:
            qs = qs.filter(stream_id=stream_id)

        subjects = Subject.objects.filter(school=school, is_active=True)
        data = []
        for subject in subjects:
            s_qs = qs.filter(subject=subject)
            if not s_qs.exists():
                continue
            totals = [r.total for r in s_qs if r.total is not None]
            avg = round(sum(totals) / len(totals), 1) if totals else None
            data.append({
                'subject_id': subject.id,
                'subject_name': subject.name,
                'students_sat': s_qs.count(),
                'average_score': avg,
                'highest': round(max(totals), 1) if totals else None,
                'lowest': round(min(totals), 1) if totals else None,
            })

        return Response({'session': session.name, 'subjects': data})


class ExamResultSlipView(APIView):
    """GET individual student result slip for an exam session."""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk, student_pk):
        role = get_user_role(request.user)
        school = get_user_school(request.user)
        session = get_object_or_404(ExamSession, pk=pk, school=school)
        student = get_object_or_404(Student, pk=student_pk, school=school)

        if role == 'student':
            if not hasattr(request.user, 'student') or request.user.student.pk != student_pk:
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)
        elif role == 'parent':
            parent = getattr(request.user, 'parent', None)
            if not parent or student not in parent.children.all():
                return Response({'error': 'Unauthorized.'}, status=status.HTTP_403_FORBIDDEN)

        if role in ('student', 'parent') and not session.is_published:
            return Response({'error': 'Results not published.'}, status=status.HTTP_403_FORBIDDEN)

        results = ExamResult.objects.filter(
            session=session, student=student
        ).select_related('subject').order_by('subject__name')

        total_score = sum(r.total for r in results if r.total is not None)
        max_possible = session.total_marks * results.count() if session.total_marks and results.count() else None
        pct = round(total_score / max_possible * 100, 1) if max_possible else None

        return Response({
            'student': {
                'id': student.pk,
                'student_id': student.student_id,
                'name': student.user.get_full_name(),
                'grade': session.grade.name,
                'stream': student.stream.name if student.stream else None,
            },
            'session': {'id': session.pk, 'name': session.name, 'year': session.year},
            'results': ExamResultSerializer(results, many=True).data,
            'summary': {
                'total_score': round(total_score, 2),
                'max_possible': max_possible,
                'percentage': pct,
            },
        })


class ExamResultDetailView(APIView):
    """PATCH/DELETE a single exam result entry."""
    permission_classes = [IsAuthenticated]

    def _get(self, pk, school):
        return get_object_or_404(ExamResult, pk=pk, school=school)

    def patch(self, request, pk):
        role = get_user_role(request.user)
        if role not in {'teacher'} | ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        result = self._get(pk, school)
        for field in ['cat_score', 'assignment_score', 'assessment_score', 'exam_score']:
            if field in request.data:
                setattr(result, field, request.data[field])
        result.save()
        return Response(ExamResultSerializer(result).data)

    def delete(self, request, pk):
        role = get_user_role(request.user)
        if role not in ADMIN_ROLES:
            return Response({'error': 'Insufficient permissions.'}, status=status.HTTP_403_FORBIDDEN)
        school = get_user_school(request.user)
        self._get(pk, school).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
