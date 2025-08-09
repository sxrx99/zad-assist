from django.core.management.base import BaseCommand
from zbot.models import Conversation
from django.db.models import Q


class Command(BaseCommand):
    help = 'Updates Conversation records with empty string type to "base"'

    def handle(self, *args, **options):
        updated_count = Conversation.objects.filter(Q(type="") | Q(type=None)).update(
            type="base"
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully updated {updated_count} Conversation records."
            )
        )
