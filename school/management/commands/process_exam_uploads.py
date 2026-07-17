"""
process_exam_uploads — processes pending ExamUploadJob entries.

Reads each job's Excel/CSV file, inserts ExamResult rows, and tracks
progress (processed / saved / skipped) on the job record.

Expected Excel columns (case-insensitive):
    adm_no | student_id  — matched against Student.admission_number or student_id
    cat                  — CAT score
    assignment           — assignment score
    assessment           — assessment score
    exam                 — exam score

Run every minute via cron (jobs are usually few and fast):
    * * * * * /path/to/venv/bin/python manage.py process_exam_uploads >> /var/log/kiswate/exam_jobs.log 2>&1
"""
import os
from django.core.management.base import BaseCommand
from django.utils import timezone
from school.models import (
    ExamUploadJob, ExamResult, Student, StaffProfile,
)


def _col(df_columns, *candidates):
    """Return first column name that matches any candidate (case-insensitive)."""
    lower_map = {c.lower(): c for c in df_columns}
    for name in candidates:
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


class Command(BaseCommand):
    help = 'Process pending ExamUploadJob entries and insert ExamResult rows.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--limit', type=int, default=10,
            help='Max jobs to process per run (default 10).'
        )

    def handle(self, *args, **options):
        try:
            import openpyxl
            import pandas as pd
        except ImportError:
            self.stderr.write('openpyxl and pandas are required. Install them first.')
            return

        jobs = ExamUploadJob.objects.filter(
            status=ExamUploadJob.STATUS_PENDING
        ).order_by('created_at')[:options['limit']]

        if not jobs.exists():
            self.stdout.write('No pending exam upload jobs.')
            return

        for job in jobs:
            self._process_job(job, pd)

    def _process_job(self, job, pd):
        self.stdout.write(f'Processing job {job.id} (session: {job.session})')
        job.status = ExamUploadJob.STATUS_PROCESSING
        job.save(update_fields=['status'])

        try:
            if not os.path.exists(job.file_path):
                raise FileNotFoundError(f'File not found: {job.file_path}')

            ext = os.path.splitext(job.file_path)[1].lower()
            if ext in ('.xlsx', '.xls'):
                df = pd.read_excel(job.file_path, dtype=str)
            elif ext == '.csv':
                df = pd.read_csv(job.file_path, dtype=str)
            else:
                raise ValueError(f'Unsupported file type: {ext}')

            df.columns = [str(c).strip() for c in df.columns]
            job.total_rows = len(df)
            job.save(update_fields=['total_rows'])

            adm_col = _col(df.columns, 'adm_no', 'admission_number', 'student_id', 'admission')
            cat_col = _col(df.columns, 'cat', 'cat_score')
            ass_col = _col(df.columns, 'assignment', 'assignment_score')
            asmnt_col = _col(df.columns, 'assessment', 'assessment_score')
            exam_col = _col(df.columns, 'exam', 'exam_score')

            if not adm_col:
                raise ValueError(
                    'Missing student identifier column. '
                    'Expected one of: adm_no, student_id, admission_number'
                )

            # Build admission-number → Student lookup for this school
            students_by_adm = {
                s.admission_number: s
                for s in Student.objects.filter(
                    school=job.school, is_active=True
                ).only('id', 'admission_number', 'stream')
                if s.admission_number
            }
            students_by_sid = {
                s.student_id: s
                for s in Student.objects.filter(
                    school=job.school, is_active=True
                ).only('id', 'student_id', 'stream')
                if s.student_id
            }

            processed = saved = skipped = 0

            for _, row in df.iterrows():
                adm_val = str(row.get(adm_col, '')).strip()
                student = students_by_adm.get(adm_val) or students_by_sid.get(adm_val)
                processed += 1

                if not student:
                    skipped += 1
                    continue

                def _float(col):
                    if col and col in row:
                        v = str(row[col]).strip()
                        if v and v.lower() not in ('nan', 'none', ''):
                            try:
                                return float(v)
                            except ValueError:
                                pass
                    return None

                defaults = {
                    'cat_score':        _float(cat_col),
                    'assignment_score': _float(ass_col),
                    'assessment_score': _float(asmnt_col),
                    'exam_score':       _float(exam_col),
                    'school':           job.school,
                }
                if job.stream:
                    defaults['stream'] = job.stream

                _, created = ExamResult.objects.update_or_create(
                    session=job.session,
                    student=student,
                    subject=job.subject,
                    defaults=defaults,
                )
                if created:
                    saved += 1
                else:
                    saved += 1

            job.processed = processed
            job.saved = saved
            job.skipped = skipped
            job.status = ExamUploadJob.STATUS_DONE
            job.finished_at = timezone.now()
            job.save(update_fields=['processed', 'saved', 'skipped', 'status', 'finished_at'])
            self.stdout.write(
                self.style.SUCCESS(
                    f'  Job {job.id}: {processed} rows, {saved} saved, {skipped} skipped.'
                )
            )

        except Exception as exc:
            job.status = ExamUploadJob.STATUS_FAILED
            job.error = str(exc)
            job.finished_at = timezone.now()
            job.save(update_fields=['status', 'error', 'finished_at'])
            self.stderr.write(self.style.ERROR(f'  Job {job.id} FAILED: {exc}'))
