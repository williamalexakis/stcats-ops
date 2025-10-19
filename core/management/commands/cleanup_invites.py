from django.core.management.base import BaseCommand
from core.models import InviteCode

class Command(BaseCommand):

    help = "Clean up expired and fully used invite codes"

    def handle(self, *args, **options):

        deleted_count = InviteCode.objects.cleanup_invalid()

        if deleted_count > 0:

            self.stdout.write(
                self.style.SUCCESS(f"Successfully deleted {deleted_count} invalid invite code(s)")
            )

        else:

            self.stdout.write(self.style.SUCCESS("No invalid invite codes to delete"))
