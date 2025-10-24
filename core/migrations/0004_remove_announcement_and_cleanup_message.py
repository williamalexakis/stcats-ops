# Generated migration to clean up announcement system

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0003_message_announcement_title_message_is_announcement_and_more'),
    ]

    operations = [
        # Remove announcement_title field from message (not needed)
        migrations.RemoveField(
            model_name='message',
            name='announcement_title',
        ),
        # Rename pinned to is_pinned for consistency
        migrations.RenameField(
            model_name='message',
            old_name='pinned',
            new_name='is_pinned',
        ),
        # Delete the Announcement model entirely
        migrations.DeleteModel(
            name='Announcement',
        ),
    ]