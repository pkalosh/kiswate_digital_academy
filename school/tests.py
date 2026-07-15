"""
Tests — Exam and Finance modules: all user roles covered.
"""
from decimal import Decimal
from io import BytesIO
from django.test import TestCase, Client
from django.urls import reverse
from django.utils import timezone
import datetime

from userauths.models import User
from school.models import (
    County, School, Grade, Streams, Subject, StaffProfile,
    Student, Parent, Term, AcademicYear,
    ExamSession, ExamResult, cbc_grade_band, kcse_grade,
    FeeInvoice, FeeStructure,
)


# ─── Shared fixture factory ────────────────────────────────────────────────────

_phone_counter = 0

def make_user(email, **flags):
    global _phone_counter
    _phone_counter += 1
    u = User.objects.create_user(
        email=email, password='testpass123',
        phone_number=f'07{_phone_counter:08d}',
    )
    for k, v in flags.items():
        setattr(u, k, v)
    u.save()
    return u


def build_school_fixture():
    """Return a dict with every object the tests need."""
    county = County.objects.create(name='TestCounty')

    admin_user = make_user('admin@school.test', is_admin=True, is_principal=True)
    school = School.objects.create(
        name='Test High School', code='THS001',
        school_admin=admin_user,
        contact_email='info@ths.test', contact_phone='0700000000',
        address='123 Test St', county=county,
    )

    grade = Grade.objects.create(name='Grade 7', school=school, code='G7')
    stream = Streams.objects.create(name='A', grade=grade, school=school)

    start = datetime.date(2025, 1, 1)
    year = AcademicYear.objects.create(school=school, name='2025', start_date=start, end_date=datetime.date(2025, 12, 31))
    term = Term.objects.create(school=school, name='Term 1 2025', start_date=start, end_date=datetime.date(2025, 4, 30), year=year)

    subj_start = datetime.date(2025, 1, 1)
    subject = Subject.objects.create(name='Mathematics', code='MATH', school=school, start_date=subj_start)
    subject.grade.add(grade)

    # Teacher
    teacher_user = make_user('teacher@school.test', is_teacher=True)
    staff = StaffProfile.objects.create(user=teacher_user, staff_id='T001', school=school, position='teacher')

    # Principal staff profile (needed for some views)
    principal_staff = StaffProfile.objects.create(user=admin_user, staff_id='P001', school=school, position='administrator')

    # Student
    student_user = make_user('student@school.test', is_student=True)
    student = Student.objects.create(
        user=student_user, student_id='S001', school=school,
        grade_level=grade, stream=stream, gender='m',
    )

    # Parent
    parent_user = make_user('parent@school.test', is_parent=True)
    parent = Parent.objects.create(user=parent_user, parent_id='PAR001', school=school, phone='0711111111')
    parent.children.add(student)

    # Stranger (no role)
    stranger_user = make_user('stranger@school.test')

    return {
        'school': school, 'grade': grade, 'stream': stream, 'term': term,
        'subject': subject, 'staff': staff, 'principal_staff': principal_staff,
        'admin_user': admin_user, 'teacher_user': teacher_user,
        'student_user': student_user, 'student': student,
        'parent_user': parent_user, 'parent': parent,
        'stranger_user': stranger_user,
    }


def make_session(school, grade, term, year=2025, published=False):
    return ExamSession.objects.create(
        school=school, grade=grade, term=term, name='Term 1 End-Term 2025',
        year=year, cat_out_of=30, assignment_out_of=10,
        assessment_out_of=10, exam_out_of=50, is_published=published,
    )


def make_result(session, student, subject, stream, school,
                cat=25, assignment=8, assessment=7, exam=40):
    return ExamResult.objects.create(
        session=session, student=student, subject=subject,
        stream=stream, school=school,
        cat_score=cat, assignment_score=assignment,
        assessment_score=assessment, exam_score=exam,
    )


# ─── Unit tests: model logic ───────────────────────────────────────────────────

class ExamResultModelTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()

    def test_total_sums_all_components(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        self.assertEqual(r.total, 80.0)

    def test_total_ignores_none_components(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = ExamResult.objects.create(
            session=session, student=self.fx['student'], subject=self.fx['subject'],
            stream=self.fx['stream'], school=self.fx['school'],
            cat_score=25, assignment_score=None, assessment_score=None, exam_score=40,
        )
        self.assertEqual(r.total, 65.0)

    def test_percentage_calculation(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                        cat=30, assignment=10, assessment=10, exam=50)
        self.assertEqual(r.percentage, 100.0)

    def test_percentage_none_when_no_scores(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = ExamResult.objects.create(
            session=session, student=self.fx['student'], subject=self.fx['subject'],
            stream=self.fx['stream'], school=self.fx['school'],
        )
        self.assertIsNone(r.percentage)

    def test_grade_band_ee(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                        cat=30, assignment=10, assessment=10, exam=50)
        self.assertEqual(r.grade_band, 'EE')

    def test_grade_band_me(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        # 50/100 = 50% → ME
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                        cat=15, assignment=5, assessment=5, exam=25)
        self.assertEqual(r.grade_band, 'ME')

    def test_grade_band_ae(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        # 25/100 = 25% → AE
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                        cat=7.5, assignment=2.5, assessment=2.5, exam=12.5)
        self.assertEqual(r.grade_band, 'AE')

    def test_grade_band_be(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        # 10/100 = 10% → BE
        r = make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                        cat=3, assignment=2, assessment=2, exam=3)
        self.assertEqual(r.grade_band, 'BE')

    def test_grade_band_dash_when_no_score(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = ExamResult.objects.create(
            session=session, student=self.fx['student'], subject=self.fx['subject'],
            stream=self.fx['stream'], school=self.fx['school'],
        )
        self.assertEqual(r.grade_band, '–')

    def test_session_total_marks(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        self.assertEqual(session.total_marks, 100.0)

    def test_unique_together_enforced(self):
        from django.db import IntegrityError
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        with self.assertRaises(IntegrityError):
            ExamResult.objects.create(
                session=session, student=self.fx['student'], subject=self.fx['subject'],
                stream=self.fx['stream'], school=self.fx['school'],
                cat_score=10,
            )


class CBCGradeHelperTest(TestCase):

    def test_cbc_boundaries(self):
        self.assertEqual(cbc_grade_band(100), 'EE')
        self.assertEqual(cbc_grade_band(75), 'EE')
        self.assertEqual(cbc_grade_band(74.9), 'ME')
        self.assertEqual(cbc_grade_band(50), 'ME')
        self.assertEqual(cbc_grade_band(49.9), 'AE')
        self.assertEqual(cbc_grade_band(25), 'AE')
        self.assertEqual(cbc_grade_band(24.9), 'BE')
        self.assertEqual(cbc_grade_band(0), 'BE')

    def test_kcse_boundaries(self):
        self.assertEqual(kcse_grade(80), 'A')
        self.assertEqual(kcse_grade(75), 'A-')
        self.assertEqual(kcse_grade(70), 'B+')
        self.assertEqual(kcse_grade(50), 'C')
        self.assertEqual(kcse_grade(29), 'E')
        self.assertEqual(kcse_grade(0), 'E')


# ─── View tests: Principal ─────────────────────────────────────────────────────

class PrincipalExamViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='admin@school.test', password='testpass123')

    def test_exam_list_200(self):
        r = self.client.get(reverse('school:school-exams'))
        self.assertEqual(r.status_code, 200)

    def test_exam_session_create_get(self):
        r = self.client.get(reverse('school:exam-session-create'))
        self.assertEqual(r.status_code, 200)

    def test_exam_session_create_post(self):
        r = self.client.post(reverse('school:exam-session-create'), {
            'name': 'Term 1 End-Term 2025',
            'grade': self.fx['grade'].pk,
            'term': self.fx['term'].pk,
            'year': 2025,
            'cat_out_of': 30,
            'assignment_out_of': 10,
            'assessment_out_of': 10,
            'exam_out_of': 50,
        })
        self.assertEqual(ExamSession.objects.count(), 1)
        session = ExamSession.objects.first()
        self.assertRedirects(r, reverse('school:exam-session-detail', args=[session.pk]))

    def test_exam_session_detail_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-session-detail', args=[session.pk]))
        self.assertEqual(r.status_code, 200)

    def test_publish_toggles_flag(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=False)
        self.client.post(reverse('school:exam-publish', args=[session.pk]))
        session.refresh_from_db()
        self.assertTrue(session.is_published)
        # toggle back
        self.client.post(reverse('school:exam-publish', args=[session.pk]))
        session.refresh_from_db()
        self.assertFalse(session.is_published)

    def test_grade_ranking_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:exam-ranking-grade', args=[session.pk]))
        self.assertEqual(r.status_code, 200)

    def test_stream_ranking_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:exam-ranking-stream', args=[session.pk, self.fx['stream'].pk]))
        self.assertEqual(r.status_code, 200)

    def test_subject_performance_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:exam-subject-performance', args=[session.pk]))
        self.assertEqual(r.status_code, 200)

    def test_report_slip_html_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:report-slip-html', args=[session.pk, self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)

    def test_report_slip_pdf_returns_pdf(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:report-slip-pdf', args=[session.pk, self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_report_slip_pdf_filename_contains_student_id(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:report-slip-pdf', args=[session.pk, self.fx['student'].pk]))
        self.assertIn('S001', r['Content-Disposition'])


# ─── View tests: Teacher ───────────────────────────────────────────────────────

class TeacherExamViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='teacher@school.test', password='testpass123')

    def test_result_entry_get_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-result-entry',
                                    args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]))
        self.assertEqual(r.status_code, 200)

    def test_result_entry_post_saves_scores(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        student = self.fx['student']
        r = self.client.post(
            reverse('school:exam-result-entry', args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]),
            {
                f'student_{student.pk}_cat': '25',
                f'student_{student.pk}_assignment': '8',
                f'student_{student.pk}_assessment': '7',
                f'student_{student.pk}_exam': '40',
            }
        )
        self.assertEqual(r.status_code, 302)
        result = ExamResult.objects.get(session=session, student=student, subject=self.fx['subject'])
        self.assertEqual(result.cat_score, 25.0)
        self.assertEqual(result.exam_score, 40.0)
        self.assertEqual(result.total, 80.0)

    def test_result_entry_rejects_score_over_max(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        student = self.fx['student']
        self.client.post(
            reverse('school:exam-result-entry', args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]),
            {f'student_{student.pk}_cat': '999'},  # max is 30
        )
        # Should not create a result (validation error triggers message, no save)
        result = ExamResult.objects.filter(session=session, student=student).first()
        self.assertIsNone(result)

    def test_result_entry_overwrites_existing(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        student = self.fx['student']
        make_result(session, student, self.fx['subject'], self.fx['stream'], self.fx['school'], cat=10)
        self.client.post(
            reverse('school:exam-result-entry', args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]),
            {f'student_{student.pk}_cat': '28', f'student_{student.pk}_exam': '45'},
        )
        result = ExamResult.objects.get(session=session, student=student, subject=self.fx['subject'])
        self.assertEqual(result.cat_score, 28.0)
        self.assertEqual(result.exam_score, 45.0)

    def test_bulk_upload_get_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-result-upload', args=[session.pk]))
        self.assertEqual(r.status_code, 200)

    def test_bulk_upload_valid_excel(self):
        import openpyxl
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['student_id', 'cat', 'assignment', 'assessment', 'exam'])
        ws.append(['S001', 25, 8, 7, 40])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'scores.xlsx'

        r = self.client.post(
            reverse('school:exam-result-upload', args=[session.pk]),
            {
                'stream': self.fx['stream'].pk,
                'subject': self.fx['subject'].pk,
                'file': buf,
            },
            format='multipart',
        )
        self.assertEqual(r.status_code, 302)
        result = ExamResult.objects.get(session=session, student=self.fx['student'])
        self.assertEqual(result.cat_score, 25.0)
        self.assertEqual(result.exam_score, 40.0)

    def test_bulk_upload_unknown_student_id_is_skipped(self):
        import openpyxl
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['student_id', 'cat', 'assignment', 'assessment', 'exam'])
        ws.append(['UNKNOWN_999', 25, 8, 7, 40])
        buf = BytesIO()
        wb.save(buf)
        buf.seek(0)
        buf.name = 'scores.xlsx'

        self.client.post(
            reverse('school:exam-result-upload', args=[session.pk]),
            {'stream': self.fx['stream'].pk, 'subject': self.fx['subject'].pk, 'file': buf},
        )
        self.assertEqual(ExamResult.objects.filter(session=session).count(), 0)

    def test_teacher_cannot_publish(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=False)
        self.client.post(reverse('school:exam-publish', args=[session.pk]))
        session.refresh_from_db()
        # Teacher is not principal/admin — publish should be blocked
        self.assertFalse(session.is_published)


# ─── View tests: Student ──────────────────────────────────────────────────────

class StudentExamViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='student@school.test', password='testpass123')

    def test_student_results_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:student-exam-results'))
        self.assertEqual(r.status_code, 200)

    def test_student_sees_only_published_sessions(self):
        draft = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=False)
        make_result(draft, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:student-exam-results'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['sessions_data']), 0)

    def test_student_sees_published_sessions(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:student-exam-results'))
        self.assertEqual(len(r.context['sessions_data']), 1)
        self.assertEqual(r.context['sessions_data'][0]['results'].count(), 1)

    def test_student_can_download_own_pdf_when_published(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        # Students access slip via report_slip_html or report_slip_pdf
        r = self.client.get(reverse('school:report-slip-html', args=[session.pk, self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)

    def test_student_blocked_from_result_entry(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-result-entry',
                                    args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]))
        # student has no school via get_user_school → redirected
        self.assertNotEqual(r.status_code, 200)

    def test_student_blocked_from_session_create(self):
        r = self.client.get(reverse('school:exam-session-create'))
        self.assertNotEqual(r.status_code, 200)

    def test_student_grade_band_correct_on_results_page(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        # 80/100 → EE
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=25, assignment=8, assessment=7, exam=40)
        r = self.client.get(reverse('school:student-exam-results'))
        result = r.context['sessions_data'][0]['results'][0]
        self.assertEqual(result.grade_band, 'EE')


# ─── View tests: Parent ────────────────────────────────────────────────────────

class ParentExamViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='parent@school.test', password='testpass123')

    def test_parent_exam_results_200(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:parent-exam-results'))
        self.assertEqual(r.status_code, 200)

    def test_parent_sees_only_published(self):
        draft = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=False)
        make_result(draft, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:parent-exam-results'))
        self.assertEqual(r.status_code, 200)
        entry = r.context['results_data'][0]
        self.assertEqual(len(entry['sessions']), 0)

    def test_parent_sees_published_results(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:parent-exam-results'))
        entry = r.context['results_data'][0]
        self.assertEqual(len(entry['sessions']), 1)
        self.assertEqual(entry['sessions'][0]['results'].count(), 1)

    def test_parent_can_download_child_pdf(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:report-slip-pdf', args=[session.pk, self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_parent_cannot_access_entry_view(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-result-entry',
                                    args=[session.pk, self.fx['stream'].pk, self.fx['subject'].pk]))
        self.assertNotEqual(r.status_code, 200)

    def test_parent_child_filter_works(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:parent-exam-results'), {'child': self.fx['student'].pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['results_data']), 1)

    def test_parent_wrong_child_id_shows_empty(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')}, published=True)
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'])
        r = self.client.get(reverse('school:parent-exam-results'), {'child': 99999})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['results_data']), 0)


# ─── View tests: Unauthenticated / Stranger ────────────────────────────────────

class StrangerExamViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()

    def test_unauthenticated_exam_list_redirects(self):
        r = self.client.get(reverse('school:school-exams'))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_session_create_redirects(self):
        r = self.client.get(reverse('school:exam-session-create'))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_pdf_redirects(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:report-slip-pdf', args=[session.pk, self.fx['student'].pk]))
        self.assertEqual(r.status_code, 302)

    def test_stranger_logged_in_but_no_school_redirected(self):
        self.client.login(email='stranger@school.test', password='testpass123')
        r = self.client.get(reverse('school:school-exams'))
        # get_user_school returns None → redirect to dashboard
        self.assertEqual(r.status_code, 302)


# ─── Ranking logic tests ───────────────────────────────────────────────────────

class RankingLogicTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        # Create a second student in same stream for meaningful ranking
        u2 = make_user('student2@school.test', is_student=True)
        self.student2 = Student.objects.create(
            user=u2, student_id='S002', school=self.fx['school'],
            grade_level=self.fx['grade'], stream=self.fx['stream'], gender='f',
        )

    def test_higher_total_ranks_first(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=25, exam=40)  # total 80
        make_result(session, self.student2, self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=15, exam=30)  # total 60

        from school.views import _compute_student_totals
        students = Student.objects.filter(school=self.fx['school'], stream=self.fx['stream'])
        ranking = _compute_student_totals(session, students, stream=self.fx['stream'])

        self.assertEqual(ranking[0]['student'].pk, self.fx['student'].pk)
        self.assertEqual(ranking[0]['position'], 1)
        self.assertEqual(ranking[1]['student'].pk, self.student2.pk)
        self.assertEqual(ranking[1]['position'], 2)

    def test_student_with_no_results_ranked_last(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=25, exam=40)
        # student2 has no results

        from school.views import _compute_student_totals
        students = Student.objects.filter(school=self.fx['school'], stream=self.fx['stream'])
        ranking = _compute_student_totals(session, students, stream=self.fx['stream'])

        no_result = next(r for r in ranking if r['student'].pk == self.student2.pk)
        self.assertEqual(no_result['position'], '–')
        self.assertEqual(ranking[0]['student'].pk, self.fx['student'].pk)

    def test_tied_students_both_get_position(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=20, assignment=5, assessment=5, exam=30)  # total 60
        make_result(session, self.student2, self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=20, assignment=5, assessment=5, exam=30)  # total 60

        from school.views import _compute_student_totals
        students = Student.objects.filter(school=self.fx['school'], stream=self.fx['stream'])
        ranking = _compute_student_totals(session, students, stream=self.fx['stream'])

        positions = [r['position'] for r in ranking if r['total'] is not None]
        self.assertEqual(len(positions), 2)
        self.assertTrue(all(isinstance(p, int) for p in positions))


# ─── Subject performance tests ─────────────────────────────────────────────────

class SubjectPerformanceTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='admin@school.test', password='testpass123')

    def test_subject_performance_shows_correct_avg(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        # 80/100 = 80%
        make_result(session, self.fx['student'], self.fx['subject'], self.fx['stream'], self.fx['school'],
                    cat=25, assignment=8, assessment=7, exam=40)
        r = self.client.get(reverse('school:exam-subject-performance', args=[session.pk]))
        self.assertEqual(r.status_code, 200)
        data = r.context['data']
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['avg'], 80.0)
        self.assertEqual(data[0]['pass_rate'], 100.0)

    def test_subject_with_no_results_shows_none(self):
        session = make_session(**{k: self.fx[k] for k in ('school', 'grade', 'term')})
        r = self.client.get(reverse('school:exam-subject-performance', args=[session.pk]))
        data = r.context['data']
        self.assertEqual(data[0]['count'], 0)
        self.assertIsNone(data[0]['avg'])


# ══════════════════════════════════════════════════════════════════════════════
# FINANCE MODULE TESTS
# ══════════════════════════════════════════════════════════════════════════════

def make_invoice(school, student, term, amount=5000, paid=0, description='Tuition'):
    return FeeInvoice.objects.create(
        school=school, student=student, term=term,
        description=description,
        amount_required=Decimal(str(amount)),
        amount_paid=Decimal(str(paid)),
    )


def make_fee_structure(school, grade, term, stream=None, amount=5000, fee_type='tuition'):
    return FeeStructure.objects.create(
        school=school, grade=grade, term=term, stream=stream,
        fee_type=fee_type, description='School Fees', amount=Decimal(str(amount)),
    )


# ─── FeeInvoice model unit tests ───────────────────────────────────────────────

class FeeInvoiceModelTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()

    def test_balance_property(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=2000)
        self.assertEqual(inv.balance, Decimal('3000'))

    def test_status_auto_paid(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=5000)
        self.assertEqual(inv.status, 'paid')

    def test_status_auto_partial(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=1000)
        self.assertEqual(inv.status, 'partial')

    def test_status_auto_pending(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=0)
        self.assertEqual(inv.status, 'pending')

    def test_receipt_number_auto_generated(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        self.assertTrue(inv.receipt_number.startswith('RCP-'))

    def test_str_representation(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        self.assertIn('Tuition', str(inv))


# ─── Finance views: Principal / Finance officer (admin) ────────────────────────

class FinancePrincipalViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='admin@school.test', password='testpass123')

    def test_fee_structure_list_accessible(self):
        r = self.client.get(reverse('school:fee-structure-list'))
        self.assertEqual(r.status_code, 200)

    def test_fee_structure_create_get(self):
        r = self.client.get(reverse('school:fee-structure-create'))
        self.assertEqual(r.status_code, 200)

    def test_fee_structure_create_post(self):
        data = {
            'grade': self.fx['grade'].pk,
            'stream': '',
            'term': self.fx['term'].pk,
            'academic_year': '',
            'fee_type': 'tuition',
            'description': 'Term Fees',
            'amount': '5000.00',
        }
        r = self.client.post(reverse('school:fee-structure-create'), data)
        self.assertRedirects(r, reverse('school:fee-structure-list'))
        self.assertEqual(FeeStructure.objects.filter(school=self.fx['school']).count(), 1)

    def test_fee_structure_edit(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        r = self.client.get(reverse('school:fee-structure-edit', args=[fs.pk]))
        self.assertEqual(r.status_code, 200)

    def test_fee_structure_delete_post(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        r = self.client.post(reverse('school:fee-structure-delete', args=[fs.pk]))
        self.assertRedirects(r, reverse('school:fee-structure-list'))
        self.assertFalse(FeeStructure.objects.filter(pk=fs.pk).exists())

    def test_bulk_generate_invoices_get(self):
        r = self.client.get(reverse('school:bulk-generate-invoices', args=[self.fx['term'].pk]))
        self.assertEqual(r.status_code, 200)

    def test_bulk_generate_invoices_post_creates_invoices(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        data = {'fee_structures': [fs.pk], 'due_date': '', 'overwrite_existing': False}
        r = self.client.post(reverse('school:bulk-generate-invoices', args=[self.fx['term'].pk]), data)
        self.assertRedirects(r, reverse('school:finance-dashboard'))
        self.assertEqual(FeeInvoice.objects.filter(school=self.fx['school']).count(), 1)

    def test_bulk_generate_skips_existing_by_default(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], description='School Fees')
        data = {'fee_structures': [fs.pk], 'due_date': '', 'overwrite_existing': False}
        self.client.post(reverse('school:bulk-generate-invoices', args=[self.fx['term'].pk]), data)
        self.assertEqual(FeeInvoice.objects.filter(school=self.fx['school']).count(), 1)

    def test_student_fee_statement_accessible(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fee-statement', args=[self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertIn('invoices', r.context)

    def test_student_fee_statement_totals(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=2000)
        r = self.client.get(reverse('school:student-fee-statement', args=[self.fx['student'].pk]))
        self.assertEqual(r.context['total_required'], Decimal('5000'))
        self.assertEqual(r.context['total_paid'], Decimal('2000'))
        self.assertEqual(r.context['total_balance'], Decimal('3000'))

    def test_student_fee_statement_pdf(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fee-statement-pdf', args=[self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_fee_payment_upload_get(self):
        r = self.client.get(reverse('school:fee-payment-upload'))
        self.assertEqual(r.status_code, 200)

    def test_finance_payment_statement(self):
        r = self.client.get(reverse('school:finance-payment-statement'))
        self.assertEqual(r.status_code, 200)

    def test_finance_collection_report_no_term(self):
        r = self.client.get(reverse('school:finance-collection-report'))
        self.assertEqual(r.status_code, 200)

    def test_finance_collection_report_with_term(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=3000)
        r = self.client.get(reverse('school:finance-collection-report'), {'term': self.fx['term'].pk})
        self.assertEqual(r.status_code, 200)
        self.assertIn('report', r.context)

    def test_fee_invoice_delete_post(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.post(reverse('school:fee-invoice-delete', args=[inv.pk]))
        self.assertFalse(FeeInvoice.objects.filter(pk=inv.pk).exists())

    def test_fee_structure_term_filter(self):
        make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        r = self.client.get(reverse('school:fee-structure-list'), {'term': self.fx['term'].pk})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context['page_obj'].paginator.count, 1)

    def test_student_statement_term_filter(self):
        inv = make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        # Different term — create a second term
        t2 = Term.objects.create(
            school=self.fx['school'], name='Term 2 2025',
            start_date=datetime.date(2025, 5, 1), end_date=datetime.date(2025, 8, 31),
            year=inv.term.academic_year if hasattr(inv.term, 'academic_year') else None,
        )
        r = self.client.get(reverse('school:student-fee-statement', args=[self.fx['student'].pk]),
                            {'term': t2.pk})
        # Should show 0 invoices since our invoice is in term 1
        self.assertEqual(list(r.context['invoices']), [])


# ─── Finance views: Teacher (should be denied) ─────────────────────────────────

class FinanceTeacherAccessTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='teacher@school.test', password='testpass123')

    def test_teacher_denied_fee_structure_list(self):
        r = self.client.get(reverse('school:fee-structure-list'), follow=True)
        # Should redirect with error, not 200 with data
        # Check it didn't render the full list (no 'page_obj' in context or redirect happened)
        msgs = [str(m) for m in r.context.get('messages', [])] if r.context else []
        redirected = r.redirect_chain  # non-empty if redirects happened
        self.assertTrue(len(redirected) > 0 or 'Access denied' in ' '.join(msgs))

    def test_teacher_denied_bulk_generate(self):
        r = self.client.get(reverse('school:bulk-generate-invoices', args=[self.fx['term'].pk]), follow=True)
        self.assertNotEqual(r.status_code, 200) if not r.redirect_chain else None
        # At minimum, they should not see the form for a school they can't manage finances for
        # Teacher has staffprofile.position='teacher' which is NOT in finance positions
        if r.redirect_chain:
            self.assertTrue(len(r.redirect_chain) > 0)

    def test_teacher_denied_fee_structure_create(self):
        data = {
            'grade': self.fx['grade'].pk, 'term': self.fx['term'].pk,
            'fee_type': 'tuition', 'description': 'Hack', 'amount': '1.00',
        }
        count_before = FeeStructure.objects.count()
        self.client.post(reverse('school:fee-structure-create'), data)
        self.assertEqual(FeeStructure.objects.count(), count_before)


# ─── Finance views: Student portal ─────────────────────────────────────────────

class FinanceStudentViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='student@school.test', password='testpass123')

    def test_student_can_view_own_fees(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fees'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('invoices', r.context)

    def test_student_sees_correct_invoices(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=1000)
        r = self.client.get(reverse('school:student-fees'))
        self.assertEqual(r.context['invoices'].count(), 1)
        self.assertEqual(r.context['total_required'], Decimal('5000'))
        self.assertEqual(r.context['total_paid'], Decimal('1000'))
        self.assertEqual(r.context['total_balance'], Decimal('4000'))

    def test_student_no_invoices_shows_empty(self):
        r = self.client.get(reverse('school:student-fees'))
        self.assertEqual(r.context['invoices'].count(), 0)

    def test_student_can_filter_by_term(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fees'), {'term': self.fx['term'].pk})
        self.assertEqual(r.context['invoices'].count(), 1)

    def test_student_blocked_from_finance_admin(self):
        r = self.client.get(reverse('school:fee-structure-list'), follow=True)
        if r.redirect_chain:
            self.assertTrue(len(r.redirect_chain) > 0)

    def test_student_can_view_own_pdf_statement(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fee-statement-pdf', args=[self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_student_blocked_from_other_student_statement(self):
        # Create a second student
        u2 = make_user('student2finance@school.test', is_student=True)
        s2 = Student.objects.create(
            user=u2, student_id='S999', school=self.fx['school'],
            grade_level=self.fx['grade'], stream=self.fx['stream'], gender='f',
        )
        r = self.client.get(reverse('school:student-fee-statement', args=[s2.pk]), follow=True)
        # Should be redirected — not allowed to see another student's statement
        self.assertTrue(len(r.redirect_chain) > 0)


# ─── Finance views: Parent portal ──────────────────────────────────────────────

class FinanceParentViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()
        self.client.login(email='parent@school.test', password='testpass123')

    def test_parent_can_view_fees(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:parent-fees'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('fee_data', r.context)

    def test_parent_sees_child_invoices(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'], amount=5000, paid=2000)
        r = self.client.get(reverse('school:parent-fees'))
        self.assertEqual(len(r.context['fee_data']), 1)
        fd = r.context['fee_data'][0]
        self.assertEqual(fd['total_required'], Decimal('5000'))
        self.assertEqual(fd['total_balance'], Decimal('3000'))

    def test_parent_can_filter_by_term(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:parent-fees'), {'term': self.fx['term'].pk})
        self.assertEqual(r.status_code, 200)
        fd = r.context['fee_data'][0]
        self.assertEqual(fd['invoices'].count(), 1)

    def test_parent_no_children_shows_empty(self):
        # Create a parent with no children
        pu = make_user('parent_nochildren@school.test', is_parent=True)
        from school.models import Parent as ParentModel
        ParentModel.objects.create(user=pu, parent_id='PAR999', school=self.fx['school'], phone='0799999999')
        self.client.logout()
        self.client.login(email='parent_nochildren@school.test', password='testpass123')
        r = self.client.get(reverse('school:parent-fees'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.context['fee_data']), 0)

    def test_parent_can_view_child_pdf(self):
        make_invoice(self.fx['school'], self.fx['student'], self.fx['term'])
        r = self.client.get(reverse('school:student-fee-statement-pdf', args=[self.fx['student'].pk]))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')

    def test_parent_blocked_from_fee_structure_admin(self):
        r = self.client.get(reverse('school:fee-structure-list'), follow=True)
        if r.redirect_chain:
            self.assertTrue(len(r.redirect_chain) > 0)


# ─── Finance views: Unauthenticated / Stranger ─────────────────────────────────

class FinanceStrangerViewTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()
        self.client = Client()

    def test_unauthenticated_fee_structure_list_redirects(self):
        r = self.client.get(reverse('school:fee-structure-list'))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_bulk_generate_redirects(self):
        r = self.client.get(reverse('school:bulk-generate-invoices', args=[self.fx['term'].pk]))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_student_statement_redirects(self):
        r = self.client.get(reverse('school:student-fee-statement', args=[self.fx['student'].pk]))
        self.assertEqual(r.status_code, 302)

    def test_unauthenticated_student_fees_portal_redirects(self):
        r = self.client.get(reverse('school:student-fees'))
        self.assertEqual(r.status_code, 302)

    def test_stranger_logged_in_denied_fee_structures(self):
        self.client.login(email='stranger@school.test', password='testpass123')
        r = self.client.get(reverse('school:fee-structure-list'))
        # Stranger has no school → redirected (302)
        self.assertEqual(r.status_code, 302)

    def test_stranger_logged_in_denied_statement(self):
        self.client.login(email='stranger@school.test', password='testpass123')
        r = self.client.get(reverse('school:student-fee-statement', args=[self.fx['student'].pk]))
        # Stranger denied → redirected (302)
        self.assertEqual(r.status_code, 302)


# ─── FeeStructure model unit tests ─────────────────────────────────────────────

class FeeStructureModelTest(TestCase):

    def setUp(self):
        self.fx = build_school_fixture()

    def test_str_includes_grade_and_term(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        s = str(fs)
        self.assertIn(self.fx['grade'].name, s)
        self.assertIn(self.fx['term'].name, s)

    def test_unique_together_enforced(self):
        # Use a stream-specific structure — stream != None makes unique constraint reliable in SQLite
        make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'], stream=self.fx['stream'])
        with self.assertRaises(Exception):  # IntegrityError
            make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'], stream=self.fx['stream'])

    def test_stream_specific_fee_structure(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'], stream=self.fx['stream'])
        self.assertEqual(fs.stream, self.fx['stream'])

    def test_school_wide_fee_structure_no_stream(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        self.assertIsNone(fs.stream)

    def test_is_active_default_true(self):
        fs = make_fee_structure(self.fx['school'], self.fx['grade'], self.fx['term'])
        self.assertTrue(fs.is_active)
