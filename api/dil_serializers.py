"""
Serializers for the DIL (Digital Interactive Learning) module and Tuition platform.
All models live in kiswate_digital_app.
"""
from rest_framework import serializers
from kiswate_digital_app.models import (
    UserProfile, Subject as DILSubject, Program, Enrollment as DILEnrollment,
    VirtualClass, ClassAttendance, Lesson as DILLesson,
    Assignment as DILAssignment, AssignmentSubmission,
    Assessment, Question, Choice, StudentAssessmentAttempt, StudentAnswer,
    NotificationTemplate, NotificationLog, TuitionPayment,
)
from django.utils import timezone


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_profile(user):
    """Return the user's UserProfile or None."""
    return getattr(user, 'profile', None)


def require_profile(user):
    """Raise ValidationError if no UserProfile exists."""
    profile = get_profile(user)
    if not profile:
        raise serializers.ValidationError('No DIL profile found. Register on the DIL platform first.')
    return profile


# ── Subject Catalog ───────────────────────────────────────────────────────────

class DILSubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = DILSubject
        fields = ['id', 'name', 'code', 'description']


# ── Programs ──────────────────────────────────────────────────────────────────

class ProgramSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    enrolled_count = serializers.SerializerMethodField()

    class Meta:
        model = Program
        fields = ['id', 'name', 'subject', 'subject_name', 'teacher', 'teacher_name',
                  'description', 'is_active', 'is_tuition', 'price', 'level',
                  'category', 'enrolled_count', 'created_at']

    def get_teacher_name(self, obj):
        return obj.teacher.full_name if obj.teacher else None

    def get_enrolled_count(self, obj):
        return obj.enrollments.filter(is_active=True).count()


class ProgramCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ['name', 'subject', 'description', 'is_tuition', 'price', 'level', 'category']

    def create(self, validated_data):
        profile = self.context.get('profile')
        school = self.context.get('school')
        validated_data['teacher'] = profile
        validated_data['school'] = school
        return Program.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('teacher', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


# ── Enrollments ───────────────────────────────────────────────────────────────

class DILEnrollmentSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = DILEnrollment
        fields = ['id', 'student', 'student_name', 'program', 'program_name', 'enrolled_at', 'is_active']

    def get_student_name(self, obj):
        return obj.student.full_name


# ── Virtual Classes ───────────────────────────────────────────────────────────

class VirtualClassSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()
    is_upcoming = serializers.BooleanField(read_only=True)
    attendance_count = serializers.SerializerMethodField()

    class Meta:
        model = VirtualClass
        fields = ['id', 'program', 'program_name', 'title', 'description', 'teacher',
                  'teacher_name', 'platform', 'meeting_link', 'meeting_id', 'passcode',
                  'scheduled_at', 'duration_minutes', 'is_recurring', 'notes',
                  'recording_link', 'is_cancelled', 'is_upcoming', 'attendance_count', 'created_at']

    def get_teacher_name(self, obj):
        return obj.teacher.full_name if obj.teacher else None

    def get_attendance_count(self, obj):
        return obj.attendance_records.filter(is_present=True).count()


class VirtualClassCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = VirtualClass
        fields = ['program', 'title', 'description', 'platform', 'meeting_link',
                  'meeting_id', 'passcode', 'scheduled_at', 'duration_minutes',
                  'is_recurring', 'notes']

    def create(self, validated_data):
        profile = self.context['profile']
        validated_data['teacher'] = profile
        return VirtualClass.objects.create(**validated_data)


class ClassAttendanceSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = ClassAttendance
        fields = ['id', 'virtual_class', 'student', 'student_name', 'joined_at',
                  'marked_by_teacher', 'is_present', 'notes']

    def get_student_name(self, obj):
        return obj.student.full_name


# ── DIL Lessons ───────────────────────────────────────────────────────────────

class DILLessonSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = DILLesson
        fields = ['id', 'program', 'program_name', 'title', 'description', 'teacher',
                  'teacher_name', 'topic', 'notes_file', 'video_url', 'order',
                  'is_published', 'created_at']

    def get_teacher_name(self, obj):
        return obj.teacher.full_name if obj.teacher else None


class DILLessonCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DILLesson
        fields = ['program', 'title', 'description', 'topic', 'notes_file',
                  'video_url', 'order', 'is_published']

    def create(self, validated_data):
        profile = self.context['profile']
        validated_data['teacher'] = profile
        return DILLesson.objects.create(**validated_data)


# ── DIL Assignments ───────────────────────────────────────────────────────────

class DILAssignmentSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    submission_count = serializers.SerializerMethodField()
    my_submission = serializers.SerializerMethodField()

    class Meta:
        model = DILAssignment
        fields = ['id', 'program', 'program_name', 'lesson', 'title', 'instructions',
                  'attachment', 'due_date', 'total_marks', 'is_published',
                  'submission_count', 'my_submission', 'created_at']

    def get_submission_count(self, obj):
        return obj.submissions.count()

    def get_my_submission(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        profile = get_profile(request.user)
        if not profile or profile.role != 'student':
            return None
        sub = obj.submissions.filter(student=profile).first()
        if not sub:
            return None
        return {
            'id': sub.id,
            'submitted_at': sub.submitted_at,
            'marks_obtained': sub.marks_obtained,
            'feedback': sub.feedback,
        }


class DILAssignmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DILAssignment
        fields = ['program', 'lesson', 'title', 'instructions', 'attachment',
                  'due_date', 'total_marks', 'is_published']


class DILSubmissionSerializer(serializers.ModelSerializer):
    student_name = serializers.SerializerMethodField()
    assignment_title = serializers.CharField(source='assignment.title', read_only=True)

    class Meta:
        model = AssignmentSubmission
        fields = ['id', 'assignment', 'assignment_title', 'student', 'student_name',
                  'file', 'text_answer', 'submitted_at', 'marks_obtained',
                  'feedback', 'graded_at']

    def get_student_name(self, obj):
        return obj.student.full_name


class DILSubmissionCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentSubmission
        fields = ['assignment', 'file', 'text_answer']

    def validate_assignment(self, assignment):
        profile = self.context['profile']
        enrolled = DILEnrollment.objects.filter(
            student=profile, program=assignment.program, is_active=True
        ).exists()
        if not enrolled:
            raise serializers.ValidationError('Not enrolled in this program.')
        if AssignmentSubmission.objects.filter(assignment=assignment, student=profile).exists():
            raise serializers.ValidationError('Already submitted.')
        return assignment

    def create(self, validated_data):
        profile = self.context['profile']
        validated_data['student'] = profile
        return AssignmentSubmission.objects.create(**validated_data)


class DILSubmissionGradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssignmentSubmission
        fields = ['marks_obtained', 'feedback']

    def update(self, instance, validated_data):
        profile = self.context['profile']
        instance.marks_obtained = validated_data.get('marks_obtained', instance.marks_obtained)
        instance.feedback = validated_data.get('feedback', instance.feedback)
        instance.graded_at = timezone.now()
        instance.graded_by = profile
        instance.save()
        return instance


# ── Assessments ───────────────────────────────────────────────────────────────

class ChoiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Choice
        fields = ['id', 'text', 'is_correct']


class ChoiceStudentSerializer(serializers.ModelSerializer):
    """Hides is_correct from students."""
    class Meta:
        model = Choice
        fields = ['id', 'text']


class QuestionSerializer(serializers.ModelSerializer):
    choices = ChoiceSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'marks', 'order', 'explanation', 'choices']


class QuestionStudentSerializer(serializers.ModelSerializer):
    choices = ChoiceStudentSerializer(many=True, read_only=True)

    class Meta:
        model = Question
        fields = ['id', 'text', 'question_type', 'marks', 'order', 'choices']


class AssessmentSerializer(serializers.ModelSerializer):
    program_name = serializers.CharField(source='program.name', read_only=True)
    question_count = serializers.SerializerMethodField()
    my_attempt = serializers.SerializerMethodField()

    class Meta:
        model = Assessment
        fields = ['id', 'program', 'program_name', 'title', 'assessment_type',
                  'instructions', 'total_marks', 'pass_mark', 'duration_minutes',
                  'start_time', 'end_time', 'is_published', 'results_published',
                  'question_count', 'my_attempt', 'created_at']

    def get_question_count(self, obj):
        return obj.questions.count()

    def get_my_attempt(self, obj):
        request = self.context.get('request')
        if not request:
            return None
        profile = get_profile(request.user)
        if not profile or profile.role != 'student':
            return None
        attempt = obj.attempts.filter(student=profile).first()
        if not attempt:
            return None
        return {
            'id': attempt.id,
            'submitted_at': attempt.submitted_at,
            'score': attempt.score,
            'percentage': attempt.percentage,
            'passed': attempt.passed,
        }


class AssessmentCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Assessment
        fields = ['program', 'title', 'assessment_type', 'instructions', 'total_marks',
                  'pass_mark', 'duration_minutes', 'start_time', 'end_time', 'is_published']

    def create(self, validated_data):
        profile = self.context['profile']
        validated_data['created_by'] = profile
        return Assessment.objects.create(**validated_data)


class QuestionCreateSerializer(serializers.ModelSerializer):
    choices = serializers.ListField(
        child=serializers.DictField(), required=False, write_only=True
    )

    class Meta:
        model = Question
        fields = ['assessment', 'text', 'question_type', 'marks', 'order', 'explanation', 'choices']

    def create(self, validated_data):
        choices_data = validated_data.pop('choices', [])
        question = Question.objects.create(**validated_data)
        for c in choices_data:
            Choice.objects.create(
                question=question,
                text=c.get('text', ''),
                is_correct=c.get('is_correct', False)
            )
        return question


class StudentAnswerCreateSerializer(serializers.Serializer):
    question_id = serializers.IntegerField()
    choice_id = serializers.IntegerField(required=False, allow_null=True)
    text_answer = serializers.CharField(required=False, allow_blank=True, default='')


class TakeAssessmentSerializer(serializers.Serializer):
    answers = StudentAnswerCreateSerializer(many=True)


class AttemptResultSerializer(serializers.ModelSerializer):
    assessment_title = serializers.CharField(source='assessment.title', read_only=True)
    percentage = serializers.FloatField(read_only=True)
    passed = serializers.BooleanField(read_only=True)
    answers = serializers.SerializerMethodField()

    class Meta:
        model = StudentAssessmentAttempt
        fields = ['id', 'assessment', 'assessment_title', 'started_at', 'submitted_at',
                  'score', 'percentage', 'passed', 'is_graded', 'answers']

    def get_answers(self, obj):
        answers = obj.answers.select_related('question', 'selected_choice')
        return [
            {
                'question': a.question.text,
                'selected': a.selected_choice.text if a.selected_choice else a.text_answer,
                'correct': a.selected_choice.is_correct if a.selected_choice else None,
                'marks_awarded': a.marks_awarded,
            }
            for a in answers
        ]


# ── Notification Templates ─────────────────────────────────────────────────────

class NotificationTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = NotificationTemplate
        fields = ['id', 'name', 'notification_type', 'subject', 'body', 'is_active']


# ── Tuition Payments ──────────────────────────────────────────────────────────

class TuitionPaymentSerializer(serializers.ModelSerializer):
    enrollment_info = serializers.SerializerMethodField()

    class Meta:
        model = TuitionPayment
        fields = ['id', 'enrollment', 'enrollment_info', 'amount', 'payment_method',
                  'transaction_id', 'payer_phone', 'status', 'paid_at', 'notes', 'created_at']

    def get_enrollment_info(self, obj):
        return {
            'student': obj.enrollment.student.full_name,
            'program': obj.enrollment.program.name,
        }


class TuitionPaymentCreateSerializer(serializers.Serializer):
    program_id = serializers.IntegerField()
    payment_method = serializers.ChoiceField(choices=['mpesa', 'cash', 'bank', 'card', 'school'])
    payer_phone = serializers.CharField(required=False, allow_blank=True, default='')
    notes = serializers.CharField(required=False, allow_blank=True, default='')

    def create(self, validated_data):
        profile = self.context['profile']
        program = Program.objects.get(pk=validated_data['program_id'])
        enrollment, _ = DILEnrollment.objects.get_or_create(
            student=profile, program=program,
            defaults={'is_active': True}
        )
        payment, created = TuitionPayment.objects.get_or_create(
            enrollment=enrollment,
            defaults={
                'amount': program.price,
                'payment_method': validated_data['payment_method'],
                'payer_phone': validated_data.get('payer_phone', ''),
                'notes': validated_data.get('notes', ''),
                'status': 'pending',
            }
        )
        if not created:
            payment.payment_method = validated_data['payment_method']
            payment.payer_phone = validated_data.get('payer_phone', payment.payer_phone)
            payment.save()
        return payment
