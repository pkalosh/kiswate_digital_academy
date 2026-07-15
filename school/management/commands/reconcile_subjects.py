"""
Management command: reconcile_subjects

For each school Subject that has no catalog_ref:
  - If a SubjectCatalog entry exists with the same code or name (case-insensitive) → link it.
  - Otherwise → create a new SubjectCatalog entry from the subject's data and link it.

Safe to re-run (idempotent): already-linked subjects are skipped.

Usage:
  python manage.py reconcile_subjects
  python manage.py reconcile_subjects --school 5
  python manage.py reconcile_subjects --dry-run
"""

from django.core.management.base import BaseCommand
from django.db.models import Q
from school.models import Subject, SubjectCatalog, School


class Command(BaseCommand):
    help = "Seed SubjectCatalog from orphan school subjects and link catalog_ref."

    def add_arguments(self, parser):
        parser.add_argument('--school', type=int, help='Limit to a specific school ID')
        parser.add_argument('--dry-run', action='store_true', help='Show what would happen without making changes')

    def handle(self, *args, **options):
        school_id = options.get('school')
        dry_run = options['dry_run']

        qs = Subject.objects.filter(catalog_ref__isnull=True, is_active=True)
        if school_id:
            qs = qs.filter(school_id=school_id)

        total = qs.count()
        self.stdout.write(f"Orphan subjects to reconcile: {total}")
        if dry_run:
            self.stdout.write("(dry-run — no changes will be saved)")

        created = linked = 0
        for s in qs.select_related('school'):
            existing = SubjectCatalog.objects.filter(
                Q(code__iexact=s.code) | Q(name__iexact=s.name)
            ).first()

            if existing:
                action = f"LINK  {s.school.name} / {s.code!r:10} → catalog '{existing.name}'"
                if not dry_run:
                    s.catalog_ref = existing
                    s.save(update_fields=['catalog_ref'])
                linked += 1
            else:
                action = f"CREATE catalog entry for {s.code!r:10} '{s.name}'"
                if not dry_run:
                    cat = SubjectCatalog.objects.create(
                        name=s.name,
                        code=s.code.upper(),
                        curriculum='cbc',
                        is_core=True,
                        is_active=True,
                        sessions_per_week_default=s.sessions_per_week or 2,
                    )
                    s.catalog_ref = cat
                    s.save(update_fields=['catalog_ref'])
                created += 1

            self.stdout.write(f"  {action}")

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone: {created} catalog entries created, {linked} linked to existing entries."
            )
        )
