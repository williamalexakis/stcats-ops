from django.db import migrations, models


def ensure_groups_present(apps, schema_editor):
    ScheduleEntry = apps.get_model("core", "ScheduleEntry")
    missing_group_count = ScheduleEntry.objects.filter(group__isnull=True).count()

    if missing_group_count > 0:
        raise RuntimeError(
            "Cannot enforce a non-null ClassGroup on ScheduleEntry because "
            f"{missing_group_count} existing entr{'y' if missing_group_count == 1 else 'ies'} "
            "do not have a group assigned. Please assign a group to each schedule entry "
            "before applying this migration."
        )


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_classgroup_scheduleentry_group"),
    ]

    operations = [
        migrations.RunPython(ensure_groups_present, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="scheduleentry",
            name="group",
            field=models.ForeignKey(
                on_delete=models.PROTECT,
                related_name="schedule_entries",
                to="core.classgroup",
            ),
        ),
    ]
