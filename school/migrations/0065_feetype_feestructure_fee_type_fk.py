from django.db import migrations, models
import django.db.models.deletion


FEE_TYPE_DISPLAY = {
    'tuition': 'Tuition Fee',
    'development': 'Development Levy',
    'activity': 'Activity Fee',
    'boarding': 'Boarding Fee',
    'transport': 'Transport Fee',
    'uniform': 'Uniform Fee',
    'exam': 'Exam Fee',
    'other': 'Other',
}


def migrate_fee_types(apps, schema_editor):
    FeeStructure = apps.get_model('school', 'FeeStructure')
    FeeType = apps.get_model('school', 'FeeType')
    for fs in FeeStructure.objects.select_related('school').order_by('id'):
        old_slug = fs.fee_type_old or 'other'
        display_name = FEE_TYPE_DISPLAY.get(old_slug, old_slug.replace('_', ' ').title())
        ft, _ = FeeType.objects.get_or_create(school=fs.school, name=display_name)
        fs.fee_type_new = ft
        fs.save(update_fields=['fee_type_new'])


def reverse_fee_types(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('school', '0064_add_school_logo'),
    ]

    operations = [
        # 1. Create FeeType model
        migrations.CreateModel(
            name='FeeType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('school', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='fee_types', to='school.school')),
            ],
            options={
                'ordering': ['name'],
                'unique_together': {('school', 'name')},
            },
        ),

        # 2. Rename old fee_type CharField to fee_type_old
        migrations.RenameField(
            model_name='feestructure',
            old_name='fee_type',
            new_name='fee_type_old',
        ),

        # 3. Remove unique_together that references old char field
        migrations.AlterUniqueTogether(
            name='feestructure',
            unique_together=set(),
        ),

        # 4. Add new nullable FK field
        migrations.AddField(
            model_name='feestructure',
            name='fee_type_new',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='fee_structures',
                to='school.feetype',
            ),
        ),

        # 5. Data migration
        migrations.RunPython(migrate_fee_types, reverse_fee_types),

        # 6. Remove old char field
        migrations.RemoveField(
            model_name='feestructure',
            name='fee_type_old',
        ),

        # 7. Rename new FK to fee_type
        migrations.RenameField(
            model_name='feestructure',
            old_name='fee_type_new',
            new_name='fee_type',
        ),

        # 8. Restore unique_together using FK
        migrations.AlterUniqueTogether(
            name='feestructure',
            unique_together={('school', 'grade', 'stream', 'term', 'fee_type')},
        ),

        # 9. Update ordering
        migrations.AlterModelOptions(
            name='feestructure',
            options={'ordering': ['grade__name', 'fee_type__name']},
        ),
    ]
