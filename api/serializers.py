from rest_framework import serializers
from django.contrib.auth import get_user_model
from school.models import (
    School, Grade, Streams, Role, Subject, StaffProfile, Parent, Student,
    Enrollment, Term, TimeSlot, Timetable, Lesson, Attendance, DisciplineRecord,
    Assignment, Submission, Payment, SmartID, ScanLog, GradeAttendance, ContactMessage, Notification
)
from datetime import date
from django.utils import timezone
from datetime import timedelta
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

def get_user_school(user, role):
    if role == 'teacher':
        return getattr(user, 'staffprofile', None).school
    elif role == 'parent':
        return getattr(user, 'parent', None).school
    elif role == 'student':
        return getattr(user, 'student', None).school
    return None
# Status mapping for input (full name -> code)
STATUS_MAP = {
    'present': 'P',
    'excused tardy': 'ET',
    'unexcused tardy': 'UT',
    'excused absence': 'EA',
    'unexcused absence': 'UA',
    'inappropriate behavior': 'IB',
    'suspension': '18',
    'expulsion': '20'
}
INCIDENT_TYPE_CHOICES = [
    ('late', 'Late Arrival'),
    ('misconduct', 'Misconduct'),  # Covers IB
    ('absence', 'Unauthorized Absence'),  # Covers UA
    ('suspension', 'Suspension'),  # New: Aligns with '18'
    ('expulsion', 'Expulsion'),  # New: Aligns with '20'
    ('other', 'Other'),
]

SEVERITY_CHOICES = [
    ('minor', 'Minor'),
    ('major', 'Major'),
    ('critical', 'Critical'),
]
User = get_user_model()

def get_user_role(user):
    if hasattr(user, 'is_teacher') and user.is_teacher:
        return 'teacher'
    elif hasattr(user, 'is_parent') and user.is_parent:
        return 'parent'
    elif hasattr(user, 'is_student') and user.is_student:
        return 'student'
    elif hasattr(user, 'is_admin') and user.is_admin:
        return 'admin'
    elif hasattr(user, 'school_staff') and user.school_staff:
        return 'staff'
    return 'user'

def get_user_school(user, user_role=None):
    if user_role is None:
        user_role = get_user_role(user)
    if user_role == 'teacher':
        return getattr(user, 'staffprofile', None).school if hasattr(user, 'staffprofile') else None
    elif user_role == 'parent':
        return getattr(user, 'parent', None).school if hasattr(user, 'parent') else None
    elif user_role == 'student':
        return getattr(user, 'student', None).school if hasattr(user, 'student') else None
    elif user_role == 'admin':
        # Admins might have access to multiple schools; for simplicity, assume they have a school or return None
        return None  # Or implement multi-school logic if needed
    return None

# User Serializers (unchanged)
class ParentSerializer(serializers.ModelSerializer):
    # full_name = serializers.CharField()
    phone = serializers.CharField(source='user.phone_number', read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)


    class Meta:
        model = Parent
        fields = ['first_name', 'last_name', 'email', 'phone', 'address']

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}" if obj.user else None

    def get_email(self, obj):
        return obj.user.email  # Correct way to access email


class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    staff_details = serializers.SerializerMethodField()
    student_details = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'role', 'first_name', 'last_name',
            'is_active', 'is_verified', 'created_at',
            'staff_details', 'student_details'
        ]

    def get_role(self, obj):
        if obj.is_teacher:
            return 'teacher'
        elif obj.is_parent:
            return 'parent'
        elif obj.is_student:
            return 'student'
        elif obj.is_admin:
            return 'admin'
        elif obj.school_staff:
            return 'staff'
        return 'user'

    def get_staff_details(self, obj):
        if hasattr(obj, 'staffprofile') and obj.staffprofile:
            profile = obj.staffprofile
            return {
                'staff_id': profile.staff_id,
                'tsc_number': profile.tsc_number,
                'position': profile.position,
                'school': profile.school.name if profile.school else None,
                'roles': [role.name for role in profile.roles.all()]
            }
        return None

    def get_student_details(self, obj):
        if hasattr(obj, 'student') and obj.student:
            student = obj.student
            parents_data = ParentSerializer(student.parents.all(), many=True).data

            return {
                'student_id': student.student_id,
                'grade_level': student.grade_level.name if student.grade_level else None,
                'stream': student.stream.name if student.stream else None,
                'status': 'active',  # or compute from enrollment if needed
                'parents': parents_data
            }
        return None




class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=['teacher', 'parent', 'student', 'admin', 'staff'])
    school_id = serializers.IntegerField(required=False)
    grade_id = serializers.IntegerField(required=False)
    stream_id = serializers.IntegerField(required=False)
    
    class Meta:
        model = User
        fields = ['email', 'password', 'role', 'first_name', 'last_name', 'phone_number', 'country', 'school_id', 'grade_id', 'stream_id']
    
    def create(self, validated_data):
        role = validated_data.pop('role')
        password = validated_data.pop('password')
        school_id = validated_data.pop('school_id', None)
        grade_id = validated_data.pop('grade_id', None)
        stream_id = validated_data.pop('stream_id', None)
        
        user = User(email=validated_data['email'], **validated_data)
        if role == 'teacher':
            user.is_teacher = True
        elif role == 'parent':
            user.is_parent = True
        elif role == 'student':
            user.is_student = True
        elif role == 'admin':
            user.is_admin = True
        elif role == 'staff':
            user.school_staff = True
        user.set_password(password)
        user.save(using=self.context['request']._db or None)
        
        if school_id:
            school = School.objects.get(id=school_id)
            if role == 'teacher':
                StaffProfile.objects.create(user=user, school=school, staff_id=f"staff_{user.id}")
            elif role == 'parent':
                Parent.objects.create(user=user, school=school, parent_id=f"parent_{user.id}", phone=validated_data['phone_number'])
            elif role == 'student':
                if not grade_id:
                    raise serializers.ValidationError("Grade ID required for student registration")
                grade = Grade.objects.get(id=grade_id)
                stream = Streams.objects.get(id=stream_id) if stream_id else None
                Student.objects.create(
                    user=user,
                    school=school,
                    student_id=f"student_{user.id}",
                    grade_level=grade,
                    stream=stream,
                    enrollment_date=timezone.now().date()
                )
        return user

class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField()

# Static Data Serializer
class TimeSlotSerializer(serializers.Serializer):
    timeSlots = serializers.ListField(child=serializers.CharField())
    days = serializers.ListField(child=serializers.CharField())

# Timetable Slot Serializer (helper for schedule)
class TimetableSlotSerializer(serializers.Serializer):
    timeSlot = serializers.CharField()
    subject = serializers.CharField()
    subjectCode = serializers.CharField()
    className = serializers.CharField()  # For teacher; stream name

# Teacher Timetable Serializer (custom for StaffProfile instance)
class TeacherTimetableSerializer(serializers.Serializer):
    teacherId = serializers.CharField(source='staff_id')  # FIXED: Use actual field
    teacherName = serializers.SerializerMethodField()
    schedule = serializers.SerializerMethodField()
    
    def get_teacherName(self, obj):
        # obj is StaffProfile
        return obj.user.get_full_name()
    
    def get_schedule(self, obj):
        # Query active lessons for this teacher
        active_term = Term.objects.filter(school=obj.school, is_active=True).first()
        if not active_term:
            return {}  # No active term
        
        lessons = Lesson.objects.filter(
            teacher=obj,
            timetable__term=active_term,
            timetable__school=obj.school
        ).select_related('subject', 'time_slot', 'stream', 'timetable__term').order_by('day_of_week', 'time_slot__start_time')
        
        schedule = {}
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day_map = {'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday', 'thursday': 'Thursday', 'friday': 'Friday'}
        for day_name in days:
            day_key = day_name.lower()
            day_lessons = lessons.filter(day_of_week=day_key)
            day_slots = []
            for lesson in day_lessons:
                time_str = f"{lesson.time_slot.start_time.strftime('%H-%M')}-{lesson.time_slot.end_time.strftime('%H-%M')}" if lesson.time_slot else ''
                slot_data = {
                    'timeSlot': time_str,
                    'subject': lesson.subject.name if lesson.subject else '',
                    'subjectCode': lesson.subject.code if lesson.subject else '',
                    'class': lesson.stream.name if lesson.stream else ''
                }
                day_slots.append(slot_data)
            
            # Fill empty slots from school time_slots
            school_time_slots = TimeSlot.objects.filter(school=obj.school).order_by('start_time')
            for ts in school_time_slots:
                time_str = f"{ts.start_time.strftime('%H-%M')}-{ts.end_time.strftime('%H-%M')}"
                if not any(slot['timeSlot'] == time_str for slot in day_slots):
                    day_slots.append({
                        'timeSlot': time_str,
                        'subject': '',
                        'subjectCode': '',
                        'class': ''
                    })
            schedule[day_name] = sorted(day_slots, key=lambda x: x['timeSlot'])
        return schedule


class TeacherLessonSerializer(serializers.Serializer):
    lessonId = serializers.IntegerField(source='id')
    subjectName = serializers.CharField(source='subject.name')
    subjectCode = serializers.CharField(source='subject.code')
    className = serializers.SerializerMethodField()
    dayOfWeek = serializers.CharField(source='day_of_week')
    startTime = serializers.SerializerMethodField()
    endTime = serializers.SerializerMethodField()
    timeSlot = serializers.SerializerMethodField()

    def get_className(self, obj):
        if obj.stream:
            grade = obj.stream.grade.name if obj.stream.grade else ''
            stream = obj.stream.name if obj.stream.name else ''
            return f"{grade} {stream}".strip()
        return ''

    def get_startTime(self, obj):
        return obj.time_slot.start_time.strftime('%H:%M') if obj.time_slot else ''

    def get_endTime(self, obj):
        return obj.time_slot.end_time.strftime('%H:%M') if obj.time_slot else ''

    def get_timeSlot(self, obj):
        start = self.get_startTime(obj)
        end = self.get_endTime(obj)
        return f"{start}-{end}" if start and end else ''
# Student Timetable Serializer (custom for Student instance)
class StudentTimetableSerializer(serializers.Serializer):
    studentId = serializers.CharField(source='student_id')  # FIXED: Use actual field
    studentName = serializers.SerializerMethodField()
    className = serializers.SerializerMethodField()  # Derive from grade_level + stream
    schedule = serializers.SerializerMethodField()
    
    def get_studentName(self, obj):
        # obj is Student
        return obj.user.get_full_name()
    
    def get_className(self, obj):
        if obj.stream:
            return f"{obj.grade_level.name} {obj.stream.name}"
        return obj.grade_level.name
    
    def get_schedule(self, obj):
        # Query lessons for student's stream
        if not obj.stream:
            return {}  # No stream assigned
        
        active_term = Term.objects.filter(school=obj.school, is_active=True).first()
        if not active_term:
            return {}
        
        lessons = Lesson.objects.filter(
            stream=obj.stream,
            timetable__term=active_term,
            timetable__school=obj.school
        ).select_related('subject', 'time_slot', 'timetable__term').order_by('day_of_week', 'time_slot__start_time')
        
        schedule = {}
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day_map = {'monday': 'Monday', 'tuesday': 'Tuesday', 'wednesday': 'Wednesday', 'thursday': 'Thursday', 'friday': 'Friday'}
        for day_name in days:
            day_key = day_name.lower()
            day_lessons = lessons.filter(day_of_week=day_key)
            day_slots = []
            for lesson in day_lessons:
                time_str = f"{lesson.time_slot.start_time.strftime('%H-%M')}-{lesson.time_slot.end_time.strftime('%H-%M')}" if lesson.time_slot else ''
                slot_data = {
                    'timeSlot': time_str,
                    'subject': lesson.subject.code if lesson.subject else '',  # As per sample
                    'subjectCode': lesson.subject.code if lesson.subject else '',
                    'subjectName': lesson.subject.name if lesson.subject else ''
                }
                day_slots.append(slot_data)
            
            # Fill empties
            school_time_slots = TimeSlot.objects.filter(school=obj.school).order_by('start_time')
            for ts in school_time_slots:
                time_str = f"{ts.start_time.strftime('%H-%M')}-{ts.end_time.strftime('%H-%M')}"
                if not any(slot['timeSlot'] == time_str for slot in day_slots):
                    day_slots.append({
                        'timeSlot': time_str,
                        'subject': '',
                        'subjectCode': '',
                        'subjectName': ''
                    })
            schedule[day_name] = sorted(day_slots, key=lambda x: x['timeSlot'])
        return schedule

class AttendanceStatusField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        from school.models import ATTENDANCE_STATUS_CHOICES  # Import choices
        super().__init__(choices=ATTENDANCE_STATUS_CHOICES, **kwargs)
    
    def to_internal_value(self, data):
        # Map full name to code if provided
        if data and data.lower() in STATUS_MAP:
            data = STATUS_MAP[data.lower()]
        return super().to_internal_value(data)
    
    def to_representation(self, value):
        # Return display name
        for choice_key, choice_value in self.choices:
            if choice_key == value:
                return choice_value
        return value

class AttendanceRecordSerializer(serializers.Serializer):  # For sample data fallback
    id = serializers.CharField()  # String for sample; int for real
    className = serializers.CharField()
    studentName = serializers.CharField(allow_null=True)
    date = serializers.DateField()
    present = serializers.IntegerField(required=False, default=0)  # For sample; aggregate in real
    absent = serializers.IntegerField(required=False, default=0)
    total = serializers.IntegerField(required=False, default=0)
    status = serializers.CharField(allow_null=True)

# For real model serialization (use in views for querysets)
class AttendanceModelSerializer(serializers.ModelSerializer):
    className = serializers.SerializerMethodField()
    studentName = serializers.SerializerMethodField()
    status_display = serializers.SerializerMethodField()  # Use display name
    
    class Meta:
        model = Attendance
        fields = ['id', 'className', 'studentName', 'date', 'status', 'status_display', 'remarks']
    
    def get_className(self, obj):
        return f"{obj.enrollment.student.grade_level.name} {obj.enrollment.student.stream.name}" if obj.enrollment.student.stream else obj.enrollment.student.grade_level.name
    
    def get_studentName(self, obj):
        return obj.enrollment.student.user.get_full_name()
    
    def get_status_display(self, obj):
        return obj.get_status_display()  # Full display name, e.g., 'Present'

# For POST: Input serializer with status mapping

class AttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()  # Student ID
    status = AttendanceStatusField()  # Present/absent/etc. from model choices
    remarks = serializers.CharField(max_length=255, required=False, default='')  # Optional remarks

class AttendanceCreateSerializer(serializers.ModelSerializer):
    lesson_id = serializers.IntegerField(write_only=True)  # Input lesson ID to determine subject/date
    attendances = serializers.ListField(
        child=AttendanceItemSerializer(),
        write_only=True
    )  # List of {student_id, status, remarks}

    class Meta:
        model = Attendance
        fields = ['lesson_id', 'attendances']  # No direct fields; bulk via attendances

    def create(self, validated_data):
        lesson_id = validated_data.pop('lesson_id')
        attendances_data = validated_data.pop('attendances')
        lesson = Lesson.objects.get(id=lesson_id)
        
        request = self.context.get('request')
        user_school = get_user_school(request.user) if request else None
        if user_school and lesson.subject.school != user_school:
            raise serializers.ValidationError("Lesson not in your school")
        
        # Auto-set marked_by if teacher
        marked_by = None
        if request and get_user_role(request.user) == 'teacher':
            marked_by = request.user.staffprofile
        
        created_attendances = []
        for item_data in attendances_data:
            student_id = item_data.pop('student_id')
            student = Student.objects.get(id=student_id)
            # Find enrollment for this student-subject
            enrollment = Enrollment.objects.get(
                student=student,
                subject=lesson.subject,
                school=lesson.subject.school  # Ensure school match
            )
            # Create attendance
            attendance = Attendance.objects.create(
                enrollment=enrollment,
                date=lesson.lesson_date,  # Use lesson date
                status=item_data['status'],
                remarks=item_data.get('remarks', ''),
                marked_by=marked_by
            )
            created_attendances.append(attendance)
        
        return created_attendances  # Return list for bulk response

# For Update: Similar to create, but with PK
class AttendanceUpdateSerializer(AttendanceCreateSerializer):
    class Meta(AttendanceCreateSerializer.Meta):
        fields = ['date', 'status', 'remarks']  # No enrollment_id for update

class StudentListSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    grade_level_name = serializers.CharField(source='grade_level.name', read_only=True)
    stream_name = serializers.CharField(source='stream.name', default='', allow_blank=True, read_only=True)

    class Meta:
        model = Student
        fields = ['id', 'full_name', 'grade_level_name', 'stream_name']

    def get_full_name(self, obj):
        return obj.user.get_full_name()

ATTENDANCE_STATUS_CHOICES = [
    ('P', 'Present'),
    ('A', 'Absent'),
    ('L', 'Late'),
    ('I', 'Illness'),
    ('O', 'Other'),
]

class GradeAttendanceItemSerializer(serializers.Serializer):
    student_id = serializers.IntegerField()  # Student ID
    status = serializers.ChoiceField(choices=ATTENDANCE_STATUS_CHOICES)  # Status from model choices

class GradeAttendanceCreateSerializer(serializers.Serializer):
    attendances = serializers.ListField(
        child=GradeAttendanceItemSerializer(),
        write_only=True
    )  # List of {student_id, status}

    def create(self, validated_data):
        attendances_data = validated_data.pop('attendances')
        stream = self.context['stream']
        created_attendances = []
        for item_data in attendances_data:
            student_id = item_data.pop('student_id')
            student = Student.objects.get(id=student_id)
            if student.stream != stream:
                raise serializers.ValidationError(f"Student {student_id} not in stream {stream.name}")
            # Create GradeAttendance (recorded_at auto_now_add=True)
            attendance = GradeAttendance.objects.create(
                student=student,
                stream=stream,
                status=item_data['status']
            )
            created_attendances.append(attendance)
        return created_attendances

class GradeAttendanceSerializer(serializers.ModelSerializer):
    studentName = serializers.SerializerMethodField()

    class Meta:
        model = GradeAttendance
        fields = ['id', 'studentName', 'status', 'recorded_at']

    def get_studentName(self, obj):
        return obj.student.user.get_full_name()

# Updated existing serializers (minor adjustments for consistency; add imports if needed)
class DisciplineCreateSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(write_only=True)  # Input student ID
    teacher_id = serializers.IntegerField(write_only=True, required=False)  # Optional; auto-set if teacher
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES)  # Ensure choices imported
    incident_type = serializers.ChoiceField(choices=INCIDENT_TYPE_CHOICES)

    class Meta:
        model = DisciplineRecord
        fields = ['student_id', 'teacher_id', 'incident_type', 'description', 'date', 'severity', 'action_taken', 'reported_by']

    def create(self, validated_data):
        student_id = validated_data.pop('student_id')
        teacher_id = validated_data.pop('teacher_id', None)
        student = Student.objects.get(id=student_id)
        request = self.context.get('request')
        school = get_user_school(request.user) if request else None
        if school and student.school != school:
            raise serializers.ValidationError("Student not in your school")
        # Auto-set teacher if current user is teacher
        if request and get_user_role(request.user) == 'teacher' and not teacher_id:
            validated_data['teacher'] = request.user.staffprofile
        if teacher_id:
            validated_data['teacher'] = StaffProfile.objects.get(id=teacher_id)
        # Auto-set reported_by to current user
        if request:
            validated_data['reported_by'] = request.user
        validated_data['school'] = school
        return DisciplineRecord.objects.create(student=student, **validated_data)

class DisciplineUpdateSerializer(DisciplineCreateSerializer):
    class Meta(DisciplineCreateSerializer.Meta):
        fields = ['incident_type', 'description', 'date', 'severity', 'action_taken', 'resolved']  # No student/teacher for update
        read_only_fields = ['student', 'teacher', 'reported_by', 'school']

class DisciplineRecordSerializer(serializers.ModelSerializer):
    studentName = serializers.SerializerMethodField()
    className = serializers.SerializerMethodField()

    class Meta:
        model = DisciplineRecord
        fields = ['id', 'studentName', 'className', 'date', 'incident_type', 'description', 'severity', 'action_taken']

    def get_studentName(self, obj):
        return obj.student.user.get_full_name()

    def get_className(self, obj):
        if hasattr(obj.student, 'stream') and obj.student.stream:
            return f"{obj.student.grade_level.name} {obj.student.stream.name}"
        return obj.student.grade_level.name

class SampleDisciplineSerializer(serializers.Serializer):
    id = serializers.CharField()
    studentName = serializers.CharField()
    className = serializers.CharField()
    date = serializers.DateField()
    incident_type = serializers.CharField(source='reason')  # Map if keys differ
    description = serializers.CharField(source='reason')  # Adjust mappings
    severity = serializers.CharField()
    action_taken = serializers.CharField(source='action')
# Assignment Serializer (basic; add submission count via method if needed)
# Assignment Serializer (basic; add submission count via method if needed)
class AssignmentFileSerializer(serializers.Serializer):
    url = serializers.SerializerMethodField()
    fileName = serializers.CharField(source='file_attachment.name')
    fileSize = serializers.SerializerMethodField()  # Compute if needed
    fileType = serializers.SerializerMethodField()
    
    def get_url(self, obj):
        return obj.file_attachment.url if obj.file_attachment else ''
    
    def get_fileSize(self, obj):
        if obj.file_attachment:
            return obj.file_attachment.size
        return 0
    
    def get_fileType(self, obj):
        if obj.file_attachment:
            return obj.file_attachment.content_type
        return ''

class AssignmentCreateSerializer(serializers.ModelSerializer):
    subject_id = serializers.IntegerField(write_only=True)  # Input subject ID
    dueDate = serializers.DateTimeField(write_only=True, source='due_date')  # Map to due_date
    
    class Meta:
        model = Assignment
        fields = ['subject_id', 'title', 'description', 'dueDate', 'assignment_type', 'max_score']
    
    @staticmethod
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
    
    @staticmethod
    def get_user_school(user):
        role = AssignmentCreateSerializer.get_user_role(user)
        if role == 'teacher':
            return getattr(user, 'staffprofile', None).school if hasattr(user, 'staffprofile') else None
        elif role == 'parent':
            return getattr(user, 'parent', None).school if hasattr(user, 'parent') else None
        elif role == 'student':
            return getattr(user, 'student', None).school if hasattr(user, 'student') else None
        return None
    
    def create(self, validated_data):
        subject_id = validated_data.pop('subject_id')
        subject = Subject.objects.get(id=subject_id)
        request = self.context.get('request')
        school = self.get_user_school(request.user) if request else None
        
        if school and subject.school != school:
            raise serializers.ValidationError("Subject not in your school")
        
        validated_data['subject'] = subject
        validated_data['school'] = school
        
        return Assignment.objects.create(**validated_data)

class AssignmentUpdateSerializer(AssignmentCreateSerializer):
    class Meta(AssignmentCreateSerializer.Meta):
        fields = ['title', 'description', 'due_date', 'assignment_type', 'max_score', 'file_attachment']  # Full update fields; due_date direct

class AssignmentSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField()  # FIXED: Assume auto PK int; change to UUIDField if model uses UUID
    subjectName = serializers.CharField(source='subject.name')
    subjectCode = serializers.CharField(source='subject.code')
    dueDate = serializers.DateTimeField(source='due_date')
    fileAttachment = AssignmentFileSerializer(source='*')  # FIXED: source='*' for self-reference, but works for file_attachment
    submissions = serializers.SerializerMethodField()  # FIXED: Added for sample
    totalStudents = serializers.SerializerMethodField()  # FIXED: Added
    className = serializers.SerializerMethodField()  # FIXED: Derive from subject.grade
    studentName = serializers.SerializerMethodField()  # FIXED: Context-based
    isSubmitted = serializers.SerializerMethodField()  # FIXED: Context-based
    
    class Meta:
        model = Assignment
        fields = ['id', 'subjectName', 'subjectCode', 'title', 'description', 'dueDate', 'assignment_type', 'max_score', 'submissions', 'totalStudents', 'className', 'studentName', 'isSubmitted', 'fileAttachment']
    
    def get_submissions(self, obj):
        return obj.submissions.count()
    
    def get_totalStudents(self, obj):
        return obj.subject.enrollments.filter(status='active').count()
    
    def get_className(self, obj):
        return obj.subject.grade.name
    
    def get_studentName(self, obj):
        # FIXED: For student view, use current user; else None
        request = self.context.get('request')
        if request and get_user_role(request.user) == 'student':
            return request.user.get_full_name()
        return None
    
    def get_isSubmitted(self, obj):
        # FIXED: Check if student has submission
        request = self.context.get('request')
        if request and get_user_role(request.user) == 'student':
            enrollment = Enrollment.objects.filter(student=request.user.student, subject=obj.subject, status='active').first()
            if enrollment:
                submission = Submission.objects.filter(enrollment=enrollment, assignment=obj).exists()
                return submission
        return None
class AnnouncementSerializer(serializers.ModelSerializer):
    id = serializers.UUIDField()  # Assuming UUID primary key; adjust if it's IntegerField
    title = serializers.CharField()
    content = serializers.CharField(source='message')
    author = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='sent_at')
    priority = serializers.SerializerMethodField()
    isRead = serializers.BooleanField(source='is_read')

    class Meta:
        model = Notification
        fields = ['id', 'title', 'content', 'author', 'date', 'priority', 'isRead']

    def get_author(self, obj):
        # Since model lacks explicit author, derive from context (e.g., system or related record)
        # For simplicity, default to "School System"; customize based on related_attendance/discipline if needed
        if obj.related_attendance:
            return f"Attendance System ({obj.related_attendance.student.user.get_full_name()})"
        elif obj.related_discipline:
            return f"Discipline System ({obj.related_discipline.student.user.get_full_name()})"
        return "School Administration"

    def get_priority(self, obj):
        # High for unread, low for read
        return 'high' if not obj.is_read else 'low'
# Stats Serializers (unchanged; compute in views)
class SubjectGradeSerializer(serializers.Serializer):
    subject = serializers.CharField()
    grade = serializers.FloatField()
    gradeLetter = serializers.CharField()
    teacher = serializers.CharField(required=False)
    status = serializers.CharField(required=False)

# class AttendanceStatsSerializer(serializers.Serializer):
#     totalDays = serializers.IntegerField()
#     presentDays = serializers.IntegerField()
#     absentDays = serializers.IntegerField()
#     attendanceRate = serializers.FloatField()
#     recentAbsences = serializers.IntegerField()
#     lastAbsenceDate = serializers.CharField(required=False)

class AttendanceStatsSerializer(serializers.Serializer):
    totalDays = serializers.IntegerField()
    presentDays = serializers.IntegerField()
    absentDays = serializers.IntegerField()
    attendanceRate = serializers.FloatField()
    recentAbsences = serializers.IntegerField()
    lastAbsenceDate = serializers.CharField(allow_null=True, required=False)

class AssignmentsStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    pending = serializers.IntegerField()
    overdue = serializers.IntegerField()
    completionRate = serializers.FloatField()
    averageScore = serializers.FloatField(required=False)

# class DisciplineStatsSerializer(serializers.Serializer):
#     totalRecords = serializers.IntegerField()
#     lowSeverity = serializers.IntegerField()
#     mediumSeverity = serializers.IntegerField()
#     highSeverity = serializers.IntegerField()
#     lastIncidentDate = serializers.CharField(required=False)


class DisciplineStatsSerializer(serializers.Serializer):
    totalRecords = serializers.IntegerField()
    lowSeverity = serializers.IntegerField()
    mediumSeverity = serializers.IntegerField()
    highSeverity = serializers.IntegerField()
    lastIncidentDate = serializers.CharField(allow_null=True, required=False)
class GradesStatsSerializer(serializers.Serializer):
    average = serializers.FloatField()
    gpa = serializers.FloatField(required=False)
    subjects = SubjectGradeSerializer(many=True)

class PerformanceSerializer(serializers.Serializer):
    trend = serializers.CharField()
    rankInClass = serializers.IntegerField()
    totalStudentsInClass = serializers.IntegerField()
    percentile = serializers.IntegerField()

class StudentStatsSerializer(serializers.Serializer):
    studentId = serializers.CharField()
    studentName = serializers.CharField()
    className = serializers.CharField()
    attendance = AttendanceStatsSerializer()
    assignments = AssignmentsStatsSerializer()
    discipline = DisciplineStatsSerializer()
    grades = GradesStatsSerializer()
    performance = PerformanceSerializer()

class ParentStatsSerializer(serializers.Serializer):
    parentId = serializers.CharField(source='parent_id')
    parentName = serializers.SerializerMethodField()
    children = StudentStatsSerializer(many=True)
    
    def get_parentName(self, obj):
        return obj.user.get_full_name()
    
class SubjectSerializer(serializers.ModelSerializer):
    """
    Simple serializer for assigned subjects (name only).
    """
    class Meta:
        model = Subject
        fields = ['id', 'name']

class TeacherStatsSerializer(serializers.ModelSerializer):
    teacherName = serializers.SerializerMethodField()
    lessons = serializers.SerializerMethodField()  # Lessons today
    assignments = serializers.SerializerMethodField()  # Total assignments created
    discipline = serializers.SerializerMethodField()  # Discipline records captured so far
    announcements = serializers.SerializerMethodField()  # Total announcements posted
    staffId = serializers.CharField(source='staff_id')
    subjects = SubjectSerializer(many=True)  # List of assigned subjects (assuming M2M field 'subjects' on StaffProfile)

    class Meta:
        model = StaffProfile
        fields = [
            'staffId', 'teacherName', 'lessons', 'assignments', 
            'discipline', 'announcements', 'subjects'
        ]

    def get_teacherName(self, obj):
        return obj.user.get_full_name()

    def get_lessons(self, obj):
        today = date.today()
        return Lesson.objects.filter(teacher=obj, lesson_date=today).count()

    def get_assignments(self, obj):
        return Assignment.objects.filter(
            school=obj.school,
            subject__in=obj.subjects.all()
        ).count()

    def get_discipline(self, obj):
        return DisciplineRecord.objects.filter(teacher=obj).count()

    def get_announcements(self, obj):
        # Assuming Announcement has 'posted_by' as ForeignKey to StaffProfile or User; adjust as needed
        return Notification.objects.filter(recipient=obj.user).count()  # Or filter(posted_by=obj.user) if to User
class ParentChildrenSerializer(serializers.Serializer):
    childId = serializers.CharField(source='student_id')
    childName = serializers.SerializerMethodField()
    className = serializers.SerializerMethodField()
    classAttendanceStats = serializers.SerializerMethodField()
    lessonAttendanceStats = serializers.SerializerMethodField()
    disciplineStats = serializers.SerializerMethodField()

    def get_childName(self, obj):
        return obj.user.get_full_name()

    def get_className(self, obj):
        if obj.stream:
            return f"{obj.grade_level.name} {obj.stream.name}"
        return obj.grade_level.name

    def get_classAttendanceStats(self, obj):
        # Class attendance from GradeAttendance for current grade, last 30 days
        recent_date = timezone.now().date() - timedelta(days=30)
        attendances = obj.recent_stream_attendances  # Prefetched; filter in code if needed
        filtered_attendances = [a for a in attendances if a.recorded_at.date() >= recent_date and a.stream == obj.stream]
        
        total = len(filtered_attendances)
        present = len([a for a in filtered_attendances if a.status == 'P'])
        absent = total - present
        percentage = (present / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'present': present,
            'absent': absent,
            'percentage': round(percentage, 2)
        }

    def get_lessonAttendanceStats(self, obj):
        recent_date = timezone.now().date() - timedelta(days=30)

        # no grade_level on enrollment → just use all current enrollments
        enrollments = getattr(obj, 'current_enrollments', [])
        enrollment_ids = [e.id for e in enrollments]

        attendances = Attendance.objects.filter(
            enrollment__id__in=enrollment_ids,
            date__gte=recent_date
        )

        total = attendances.count()
        present = attendances.filter(status='present').count()
        absent = total - present
        percentage = (present / total * 100) if total > 0 else 0

        return {
            'total': total,
            'present': present,
            'absent': absent,
            'percentage': round(percentage, 2)
        }

    def get_disciplineStats(self, obj):
        # Discipline stats from DisciplineRecord, last 30 days
        recent_date = timezone.now().date() - timedelta(days=30)
        records = obj.recent_discipline_records  # Prefetched; filter in code
        filtered_records = [r for r in records if r.date >= recent_date]
        
        total = len(filtered_records)
        # Assuming SEVERITY_CHOICES has 'minor', 'major'; adjust as needed
        minor = len([r for r in filtered_records if r.severity == 'minor'])
        major = len([r for r in filtered_records if r.severity == 'major'])
        
        return {
            'total': total,
            'minor': minor,
            'major': major,
            'recent_incidents': total  # Or list summaries if needed
        }