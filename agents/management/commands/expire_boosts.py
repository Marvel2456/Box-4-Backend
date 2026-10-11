from django.core.management.base import BaseCommand
from agents.utils import expire_outdated_boosts


class Command(BaseCommand):
    help = "Check and expire active listing boosts that have passed their date_expires."

    def handle(self, *args, **options):
        count = expire_outdated_boosts()
        self.stdout.write(self.style.SUCCESS(f"Successfully processed boost expirations. Expired: {count}"))
