from django.core.management.base import BaseCommand
from core.models import ScheduleEntry

class Command(BaseCommand):

    help = "Delete schedule entries that have expired"

    def handle(self, *args, **kwargs):

        deleted_count = ScheduleEntry.objects.cleanup_past_entries()

        if deleted_count > 0:

            self.stdout.write(self.style.SUCCESS(f"Successfully deleted {deleted_count} past schedule entries"))

        else:

            self.stdout.write(self.style.SUCCESS("No past entries to delete"))
