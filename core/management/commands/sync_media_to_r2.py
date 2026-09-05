import os
import mimetypes
from django.core.management.base import BaseCommand
from django.conf import settings
from django.core.files.storage import default_storage
from agents.models import ListingImage
from profiles.models import AgentProfile, BuyerProfile


class Command(BaseCommand):
    help = "Syncs all local media files (e.g. listings, profiles, avatars) to Cloudflare R2 bucket."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("🔍 Starting Media Sync to Cloudflare R2..."))

        use_r2 = getattr(settings, 'USE_R2', False)
        if not use_r2:
            self.stdout.write(
                self.style.WARNING("⚠️ USE_R2 is currently set to False in environment. Set USE_R2=True to upload to Cloudflare R2.")
            )

        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            self.stdout.write(self.style.ERROR(f"❌ Media root does not exist: {media_root}"))
            return

        synced_count = 0
        skipped_count = 0
        error_count = 0

        # 1. Walk through all files under MEDIA_ROOT
        for root, _, files in os.walk(media_root):
            for file in files:
                if file.startswith('.'):
                    continue

                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, media_root).replace('\\', '/')

                try:
                    # Check if file exists on storage
                    if default_storage.exists(rel_path):
                        self.stdout.write(f"  ⏭️  Already exists on storage: {rel_path}")
                        skipped_count += 1
                        continue

                    # Read and upload file to default_storage (R2)
                    content_type, _ = mimetypes.guess_type(abs_path)
                    if not content_type:
                        content_type = 'image/webp' if rel_path.lower().endswith('.webp') else 'application/octet-stream'

                    with open(abs_path, 'rb') as f:
                        content = f.read()
                        from django.core.files.base import ContentFile
                        default_storage.save(rel_path, ContentFile(content))

                    self.stdout.write(self.style.SUCCESS(f"  ✅ Uploaded to R2: {rel_path}"))
                    synced_count += 1

                except Exception as e:
                    self.stdout.write(self.style.ERROR(f"  ❌ Error uploading {rel_path}: {e}"))
                    error_count += 1

        self.stdout.write(self.style.SUCCESS(
            f"\n🎉 Sync completed! Uploaded: {synced_count}, Skipped (Already on R2): {skipped_count}, Errors: {error_count}"
        ))
