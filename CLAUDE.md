# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run development server
python manage.py runserver

# Apply migrations
python manage.py migrate

# Create new migrations after model changes
python manage.py makemigrations

# Create superuser
python manage.py createsuperuser

# Run management command to check lessons
python manage.py check_lessons

# Run ZKTeco biometric device sync (background process)
python zkteco_to_cloud.py

# Collect static files
python manage.py collectstatic

# Run tests
python manage.py test
python manage.py test school          # test single app
python manage.py test school.tests.SpecificTestCase  # single test
```

## Architecture Overview

**Multi-tenant school management SaaS** — each `School` is a tenant, and all core models carry a `school` FK to enforce data isolation. Authentication uses email (not username) via a custom `User` model in `userauths`.

### Django Apps

| App | Responsibility |
|-----|---------------|
| `userauths` | Custom `User` model (email-based login), `OTP`, custom `EmailBackend` |
| `school` | Core domain models: timetable, attendance, discipline, payments, smart ID, library, scholarships, subscriptions |
| `kiswate_digital_app` | Platform admin layer — school onboarding, subscription plans, `UserProfile`, virtual classes, assessments, notifications |
| `api` | DRF REST API with JWT auth — endpoints for mobile apps (teachers, students, parents) |

### URL Routing (`src/urls.py`)

- `/admin/` → Django admin (Jazzmin theme)
- `/` → `userauths.urls` (landing pages, auth: sign-in/sign-up/OTP)
- `/` → `school.urls` (school management views — timetable, attendance, staff, students, etc.)
- `/` → `kiswate_digital_app.urls` (Kiswate-admin views — school list, subscriptions)
- `/api/` → `api.urls` (DRF — JWT auth, timetables, attendance, stats)

### Authentication & Access Control

- Login is email-based; `userauths.backends.EmailBackend` is registered first.
- `User` has boolean role flags: `is_teacher`, `is_student`, `is_parent`, `is_principal`, `is_deputy_principal`, `is_policy_maker`, `is_kiswate_user`, `is_kiswate_admin`.
- Web views use `@login_required` + manual role checks on `request.user`.
- API uses `JWTAuthentication` (SimpleJWT); `ACCESS_TOKEN_LIFETIME = 60 min`, `REFRESH_TOKEN_LIFETIME = 7 days`.

### Core Domain Models (`school/models.py`)

The model hierarchy: `School → Grade → Streams → Lesson (via Timetable + TimeSlot) → Enrollment → Attendance`

Key relationships:
- `StaffProfile` — one-to-one with `User`; has `position` (teacher/HOD/admin etc.) and M2M `roles` for granular permissions.
- `Student` — one-to-one with `User`; linked to `Grade`, `Streams`, optional `Pathway`.
- `Parent` — one-to-one with `User`; M2M to `Student` via `parents`.
- `Timetable` — scoped to `(school, grade, stream, term, year)`.
- `Lesson` — one slot in a timetable: `(timetable, subject, day_of_week, time_slot, stream, lesson_date)`.
- `Attendance` — per `Enrollment` (student↔lesson link) with statuses: P, ET, UT, EA, UA, IB, 18 (Suspension), 20 (Expulsion).
- `SmartID` + `ScanLog` — biometric/QR card system; `zkteco_to_cloud.py` syncs ZKTeco fingerprint devices into `ScanLog` → `GradeAttendance`.

### Timetable Generation

`school/services/timetable_generator.py` — `generate_for_stream()` auto-assigns lessons respecting:
- Max 2 consecutive slots per subject
- Max 3 lessons/day per teacher
- Priority scheduling for Mathematics and English

### API App (`api/`)

DRF views for mobile clients. All endpoints require JWT auth. Key endpoints:
- `POST /api/auth/login/` — returns access + refresh tokens
- `GET /api/timetable/teacher/<staff_id>/` — teacher's weekly schedule
- `GET/POST /api/attendance/` — attendance records
- `GET /api/stats/teacher/` / `student/<id>/` / `parent/` — dashboard stats

### Settings Notes

- `TIME_ZONE = "Africa/Nairobi"` — all datetime logic is Kenya-local.
- `AUTH_USER_MODEL = 'userauths.User'`
- Database: SQLite in dev (`db.sqlite3`); `mysqlclient` is installed for production MySQL.
- SMS via EUJIM API — credentials in `SMS_API_KEY/SMS_PARTNERID/SMS_SHORTCODE` (currently disabled/empty).
- CORS configured for `localhost:3000` (React Native dev) — update `CORS_ALLOWED_ORIGINS` for production.

### Templates

Templates live in `templates/` with subdirectories: `landing/`, `school/`, `Dashboard/`, `dim/`. School views use `templates/school/base.html` as the base layout with Bootstrap 5 + crispy-forms. The admin uses `django-jazzmin`.

### Key Third-Party Libraries

- `reportlab` — PDF generation (certificates, reports)
- `openpyxl` / `pandas` — Excel bulk import/export for grades, users, subjects
- `pyzk` — ZKTeco biometric device communication
- `django-widget-tweaks` — template-level form field customization
- `crispy-forms` + `crispy-bootstrap5` — form rendering
