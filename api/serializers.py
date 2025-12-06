from rest_framework import serializers
from django.contrib.auth import get_user_model
from school.models import (
    School, Grade, Streams, Role, Subject, StaffProfile, Parent, Student,
    Enrollment, Term, TimeSlot, Timetable, Lesson, Attendance, DisciplineRecord,
    Assignment, Submission, Payment, SmartID, ScanLog, GradeAttendance, ContactMessage
)
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

# User Serializers (unchanged)
class UserSerializer(serializers.ModelSerializer):
    role = serializers.SerializerMethodField()
    staff_details = serializers.SerializerMethodField()  # Combined staff profile fields

    class Meta:
        model = User
        fields = [
            'id', 'email', 'phone_number', 'role', 'first_name', 'last_name', 
            'is_active', 'is_verified', 'created_at', 'staff_details'
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
        else:
            return 'user'

    def get_staff_details(self, obj):
        """
        Returns dict with staff_id, tsc_number, position, school (name), roles (list of names)
        for staff/teachers; None otherwise.
        """
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
class AttendanceCreateSerializer(serializers.ModelSerializer):
    enrollment_id = serializers.IntegerField(write_only=True)  # Input enrollment ID
    status = AttendanceStatusField()  # FIXED: Use custom field for mapping
    
    class Meta:
        model = Attendance
        fields = ['enrollment_id', 'date', 'status', 'remarks']
    
    def create(self, validated_data):
        enrollment_id = validated_data.pop('enrollment_id')
        enrollment = Enrollment.objects.get(id=enrollment_id)
        # Ensure marked_by is current user if teacher
        request = self.context.get('request')
        if request and get_user_role(request.user) == 'teacher':
            validated_data['marked_by'] = request.user.staffprofile
        return Attendance.objects.create(enrollment=enrollment, **validated_data)

# For Update: Similar to create, but with PK
class AttendanceUpdateSerializer(AttendanceCreateSerializer):
    class Meta(AttendanceCreateSerializer.Meta):
        fields = ['date', 'status', 'remarks']  # No enrollment_id for update
# Discipline Serializer (derive studentName, className)
class DisciplineRecordSerializer(serializers.ModelSerializer):
    studentName = serializers.SerializerMethodField()
    className = serializers.SerializerMethodField()
    
    class Meta:
        model = DisciplineRecord
        fields = ['id', 'studentName', 'className', 'date', 'incident_type', 'description', 'severity', 'action_taken']
    
    def get_studentName(self, obj):
        return obj.student.user.get_full_name()
    
    def get_className(self, obj):
        return f"{obj.student.grade_level.name} {obj.student.stream.name}" if obj.student.stream else obj.student.grade_level.name
class DisciplineCreateSerializer(serializers.ModelSerializer):
    student_id = serializers.IntegerField(write_only=True)  # Input student ID
    teacher_id = serializers.IntegerField(write_only=True, required=False)  # Optional; auto-set if teacher
    severity = serializers.ChoiceField(choices=SEVERITY_CHOICES)  # Ensure choices imported
    incident_type = serializers.ChoiceField(choices=INCIDENT_TYPE_CHOICES)
    
    class Meta:
        model = DisciplineRecord
        fields = ['student_id', 'teacher_id', 'incident_type', 'description', 'date', 'severity', 'action_taken', 'reported_by']
    
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
        role = DisciplineCreateSerializer.get_user_role(user)
        if role == 'teacher':
            return getattr(user, 'staffprofile', None).school if hasattr(user, 'staffprofile') else None
        elif role == 'parent':
            return getattr(user, 'parent', None).school if hasattr(user, 'parent') else None
        elif role == 'student':
            return getattr(user, 'student', None).school if hasattr(user, 'student') else None
        return None
    
    def create(self, validated_data):
        student_id = validated_data.pop('student_id')
        teacher_id = validated_data.pop('teacher_id', None)
        student = Student.objects.get(id=student_id)
        request = self.context.get('request')
        school = self.get_user_school(request.user) if request else None
        
        if school and student.school != school:
            raise serializers.ValidationError("Student not in your school")
        
        # Auto-set teacher if current user is teacher
        if request and self.get_user_role(request.user) == 'teacher' and not teacher_id:
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
        return f"{obj.student.grade_level.name} {obj.student.stream.name}" if obj.student.stream else obj.student.grade_level.name

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
    id = serializers.UUIDField()  # No source needed
    title = serializers.SerializerMethodField()
    content = serializers.CharField(source='message')
    author = serializers.SerializerMethodField()
    date = serializers.DateTimeField(source='created_at')
    priority = serializers.SerializerMethodField()

    class Meta:
        model = ContactMessage
        fields = ['id', 'title', 'content', 'author', 'date', 'priority']

    def get_title(self, obj):
        # obj is now a ContactMessage instance
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message

    def get_author(self, obj):
        return obj.email_address  # Or f"{obj.first_name} {obj.last_name}"

    def get_priority(self, obj):
        return 'medium' if obj.is_read else 'high'
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