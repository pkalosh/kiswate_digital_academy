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
from django.utils import timezone
from .serializers import (
    RegisterSerializer, LoginSerializer, TimeSlotSerializer,
    TeacherTimetableSerializer, StudentTimetableSerializer,AnnouncementSerializer,
    StudentStatsSerializer, ParentStatsSerializer, UserSerializer,AttendanceRecordSerializer, AttendanceModelSerializer,
    AttendanceCreateSerializer, AttendanceUpdateSerializer,DisciplineCreateSerializer,DisciplineUpdateSerializer,
    AssignmentCreateSerializer,AssignmentUpdateSerializer,DisciplineRecordSerializer,AssignmentSerializer,SampleDisciplineSerializer,
    TeacherStatsSerializer,ParentChildrenSerializer,TeacherLessonSerializer
)
from school.models import (
    StaffProfile, Student, Parent, TimeSlot, Lesson, School, Grade,Enrollment, Streams,Attendance, DisciplineRecord, Assignment, 
    ContactMessage,Submission,Term, Subject, Notification,GradeAttendance
)
from rest_framework.decorators import action
from django.db.models import Count, Case, When, IntegerField
from django.db.models import Count, Avg, Q, F, ExpressionWrapper, DecimalField
from django.utils import timezone
from datetime import timedelta
User = get_user_model()
def get_user_school(user, role):
    if role == 'teacher':
        return getattr(user, 'staffprofile', None).school
    elif role == 'parent':
        return getattr(user, 'parent', None).school
    elif role == 'student':
        return getattr(user, 'student', None).school
    return None
def get_user_role(user):
    if user.is_teacher:
        return 'teacher'
    elif user.is_parent:
        return 'parent'
    elif user.is_student:
        return 'student'
    elif user.is_admin:
        return 'admin'
    elif user.school_staff:
        return 'staff'
    return 'user'

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
        print(f"Fetching timetable for teacher ID: {teacher_id}")
        teacher = get_object_or_404(StaffProfile, staff_id=teacher_id)
        print(f"Found teacher: {teacher.user.get_full_name()}")
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
        print(f"Fetching lessons for teacher ID: {teacher_id}")
        teacher = get_object_or_404(StaffProfile, staff_id=teacher_id)
        print(f"Found teacher: {teacher.user.get_full_name()}")

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
            'subject', 'time_slot', 'stream', 'stream__grade_level', 'timetable__term'
        ).order_by(
            'stream__grade_level__name',
            'day_of_week',
            'time_slot__start_time'
        )

        serializer = TeacherLessonSerializer(lessons, many=True)
        return Response(serializer.data)

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
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        # Real query
        queryset = Attendance.objects.filter(  # Filter as in ViewSet
            enrollment__school=request.user.staffprofile.school  # Assume user has school via profile
        ).select_related('enrollment__student', 'marked_by')
        
        if not queryset.exists():
            # Fallback sample with string IDs
            sample_data = [  # Your full sample
                {
                    "id": "att_001",
                    "className": "Form 3A",
                    "studentName": "John Doe",
                    "date": "2024-01-15",
                    "present": 1,
                    "absent": 0,
                    "total": 1,
                    "status": "Present"
                },
                # ... all 5 from sample
            ]
            serializer = AttendanceRecordSerializer(data=sample_data, many=True)
            serializer.is_valid()
            return Response(serializer.data)
        
        # Real: Use model serializer
        serializer = AttendanceModelSerializer(queryset, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        # POST create
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions to mark attendance'}, status=status.HTTP_403_FORBIDDEN)
        
        serializer = AttendanceCreateSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            attendance = serializer.save()
            return Response(AttendanceModelSerializer(attendance).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class AttendanceDetailView(APIView):
    permission_classes = [IsAuthenticated]
    
    def put(self, request, pk):
        # Full update
        user_role = get_user_role(request.user)
        if user_role not in ['teacher', 'admin']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        attendance = get_object_or_404(Attendance, pk=pk)
        if attendance.enrollment.school != request.user.staffprofile.school:
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
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
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
            if discipline.student not in parent.children.all():
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
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)
        
        # Real query: Filter by school/subjects
        school = get_user_school(request.user, user_role)
        if not school:
            return Response({'error': 'No school access'}, status=status.HTTP_403_FORBIDDEN)
        
        queryset = Assignment.objects.filter(school=school).select_related('subject', 'school')
        
        if user_role == 'student':
            # Enrollments for student
            enrollments = Enrollment.objects.filter(student=request.user.student, status='active')
            subjects = [e.subject for e in enrollments]
            queryset = queryset.filter(subject__in=subjects)
        elif user_role == 'parent':
            parent = request.user.parent
            students = parent.children.all()
            enrollments = Enrollment.objects.filter(student__in=students, status='active')
            subjects = [e.subject for e in enrollments]
            queryset = queryset.filter(subject__in=subjects)
        elif user_role == 'teacher':
            staff = request.user.staffprofile
            subjects = staff.subjects.all()
            queryset = queryset.filter(subject__in=subjects)
        
        if not queryset.exists():
            # Fallback sample data - FIXED: Use data= and full sample
            sample_data = [
                {
                    "id": "assign_001",
                    "title": "Mathematics Problem Set 5",
                    "subject": "Mathematics",
                    "class": "Form 3A",
                    "dueDate": "2024-01-18",
                    "submissions": 12,
                    "totalStudents": 25,
                    "studentName": None,
                    "isSubmitted": None,
                    "file": {
                        "url": "https://example.com/files/math_problem_set_5.pdf",
                        "fileName": "math_problem_set_5.pdf",
                        "fileSize": 245678,
                        "fileType": "application/pdf"
                    }
                },
                {
                    "id": "assign_002",
                    "title": "English Essay: Climate Change",
                    "subject": "English",
                    "class": "Form 2B",
                    "dueDate": "2024-01-20",
                    "submissions": 8,
                    "totalStudents": 30,
                    "studentName": None,
                    "isSubmitted": None,
                    "file": {
                        "url": "https://example.com/files/english_essay_guidelines.docx",
                        "fileName": "english_essay_guidelines.docx",
                        "fileSize": 189234,
                        "fileType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                    }
                },
                {
                    "id": "assign_003",
                    "title": "Chemistry Lab Report",
                    "subject": "Chemistry",
                    "class": "Form 4A",
                    "dueDate": "2024-01-22",
                    "submissions": 15,
                    "totalStudents": 20,
                    "studentName": None,
                    "isSubmitted": None,
                    "file": {
                        "url": "https://example.com/files/chemistry_lab_template.pdf",
                        "fileName": "chemistry_lab_template.pdf",
                        "fileSize": 312456,
                        "fileType": "application/pdf"
                    }
                },
                {
                    "id": "assign_004",
                    "title": "History Research Paper",
                    "subject": "History",
                    "class": "Form 1C",
                    "dueDate": "2024-01-13",
                    "submissions": 18,
                    "totalStudents": 22,
                    "studentName": None,
                    "isSubmitted": None,
                    "file": {
                        "url": "https://example.com/files/history_research_requirements.pdf",
                        "fileName": "history_research_requirements.pdf",
                        "fileSize": 156789,
                        "fileType": "application/pdf"
                    }
                },
                {
                    "id": "assign_005",
                    "title": "Biology Field Study",
                    "subject": "Biology",
                    "class": "Form 3A",
                    "dueDate": "2024-01-25",
                    "submissions": 10,
                    "totalStudents": 25,
                    "studentName": "John Doe",
                    "isSubmitted": True,
                    "file": {
                        "url": "https://example.com/files/biology_field_study_instructions.pdf",
                        "fileName": "biology_field_study_instructions.pdf",
                        "fileSize": 278901,
                        "fileType": "application/pdf"
                    }
                },
                {
                    "id": "assign_006",
                    "title": "Geography Map Project",
                    "subject": "Geography",
                    "class": "Form 2B",
                    "dueDate": "2024-01-19",
                    "submissions": 5,
                    "totalStudents": 30,
                    "studentName": "Jane Smith",
                    "isSubmitted": False,
                    "file": {
                        "url": "https://example.com/files/geography_map_project.pdf",
                        "fileName": "geography_map_project.pdf",
                        "fileSize": 423567,
                        "fileType": "application/pdf"
                    }
                }
            ]
            serializer = AssignmentSerializer(data=sample_data, many=True)  # FIXED: data= implicit, but works
            serializer.is_valid()
            return Response(serializer.data)
        
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
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
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
        # Restrict to relevant roles that can receive/view announcements
        if user_role not in ['admin', 'teacher', 'parent', 'student']:
            return Response({'error': 'Insufficient permissions'}, status=status.HTTP_403_FORBIDDEN)

        # Fetch only notifications for the logged-in user, ordered by sent_at (recent first)
        # Limit to 10 recent for performance; adjust or add pagination as needed
        announcements = Notification.objects.filter(
            recipient=request.user,
            school=request.user.school  # Assuming User has school; adjust if via profile
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
        
        # 2. Assignments Stats (unchanged; filters via enrollments below)
        enrollments = Enrollment.objects.filter(
            student=student,
            status='active',
            subject__grade=student.grade_level  # FIXED: Only current grade's subjects
        )
        assignments = Assignment.objects.filter(
            subject__in=[e.subject for e in enrollments],
            due_date__gte=term_start
        )
        total_assignments = assignments.count()
        submissions = Submission.objects.filter(
            enrollment__student=student,
            enrollment__subject__grade=student.grade_level,  # FIXED: Current grade
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
        for enrollment in enrollments:  # Now filtered to current grade
            subject_subs = submissions.filter(enrollment__subject=enrollment.subject)
            avg_grade = subject_subs.aggregate(avg=Avg('score'))['avg'] or 0
            has_grades = subject_subs.filter(score__isnull=False).exists()
            grade_status = 'graded' if has_grades else 'pending'
            grade_letter = self._compute_grade_letter(avg_grade) if has_grades else 'Pending'
            teacher = enrollment.subject.teachers_subjects.first()
            subject_entry = {
                'subject': enrollment.subject.name,
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
        user_role = get_user_role(request.user)
        if user_role != 'parent':
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
        
        # Placeholder data for teacher stats (full sample)
        stats_data = {
            'teacherId': teacher.staff_id,
            'teacherName': teacher.user.get_full_name(),
            'classesTaught': [
                {
                    'className': 'Form 3A',
                    'subject': 'Mathematics',
                    'studentsCount': 25,
                    'averageAttendance': 92.5,
                    'averageAssignmentCompletion': 85.0
                },
                {
                    'className': 'Form 2B',
                    'subject': 'English',
                    'studentsCount': 30,
                    'averageAttendance': 90.0,
                    'averageAssignmentCompletion': 80.0
                }
            ]
        }
        
        serializer = TeacherStatsSerializer(data=stats_data)
        serializer.is_valid()
        return Response(serializer.data)


from django.db.models import Prefetch

class ParentChildrenView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_role = get_user_role(request.user)
        if user_role != 'parent':
            return Response({'error': 'Unauthorized'}, status=403)

        parent = get_object_or_404(Parent, user=request.user)

        children = parent.children.all().prefetch_related(
            Prefetch(
                'grade_attendance',   # <-- correct related name
                queryset=GradeAttendance.objects.select_related('grade'),
                to_attr='recent_grade_attendances'   # <-- what serializer expects
            ),
            Prefetch(
                'discipline_records',  # <-- correct related name
                queryset=DisciplineRecord.objects.all(),
                to_attr='recent_discipline_records'  # <-- expected by serializer
            ),
            Prefetch(
                'enrollments',       # <-- correct related name
                queryset=Enrollment.objects.select_related('subject', 'school', 'student'),
                to_attr='current_enrollments'  # <-- expected by serializer
            )
        )

        serializer = ParentChildrenSerializer(children, many=True)
        return Response(serializer.data)
