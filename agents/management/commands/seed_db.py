from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.core.files.base import ContentFile
from io import BytesIO
from PIL import Image, ImageDraw
from profiles.models import Plan
from agents.models import Listing, ListingImage
import random

User = get_user_model()

class Command(BaseCommand):
    help = "Seed database with plans, property listings, and listing images (without creating new users)."

    def generate_sample_image(self, title_text, color):
        img = Image.new('RGB', (800, 600), color=color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([20, 20, 780, 580], outline=(255, 255, 255), width=5)
        
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        return ContentFile(buffer.getvalue(), name=f"{title_text.lower().replace(' ', '_')}.jpg")

    def handle(self, *args, **kwargs):
        self.stdout.write(self.style.SUCCESS("Starting database seeding process..."))

        # 1. Seed Subscription Plans
        plans_data = [
            {
                "name": "Basic Free",
                "price": 0.00,
                "max_listings": 3,
                "max_boosted": 0,
                "max_featured": 0,
            },
            {
                "name": "Silver Agent",
                "price": 19.99,
                "max_listings": 10,
                "max_boosted": 2,
                "max_featured": 1,
            },
            {
                "name": "Gold Pro Agent",
                "price": 49.99,
                "max_listings": 30,
                "max_boosted": 8,
                "max_featured": 5,
            },
            {
                "name": "Platinum Agency",
                "price": 99.99,
                "max_listings": 100,
                "max_boosted": 25,
                "max_featured": 15,
            }
        ]

        created_plans = []
        for p_data in plans_data:
            plan, created = Plan.objects.get_or_create(
                name=p_data["name"],
                defaults=p_data
            )
            created_plans.append(plan)
            status_str = "Created" if created else "Exists"
            self.stdout.write(f"  Plan: {plan.name} (${plan.price}) - {status_str}")

        # 2. Get an existing Agent User (without creating new users)
        agent_user = User.objects.filter(role='agent').first()
        if not agent_user:
            # Fallback to any existing user and set role='agent' if necessary
            agent_user = User.objects.first()
            if agent_user:
                agent_user.role = 'agent'
                agent_user.save()
                self.stdout.write(self.style.WARNING(f"  Assigned role='agent' to existing user: {agent_user.email}"))
            else:
                self.stdout.write(self.style.WARNING("  No users exist in database yet. Plans seeded successfully. Create a user to attach listings."))
                return

        # Assign Gold Plan to Agent Profile
        if hasattr(agent_user, 'agent_profile'):
            agent_user.agent_profile.plan = created_plans[2]  # Gold Plan
            agent_user.agent_profile.rating = 4.9
            agent_user.agent_profile.agency_name = "Apex Realty International"
            agent_user.agent_profile.save()

        # 3. Seed Property Listings
        sample_properties = [
            {
                "title": "Luxury Lekki Waterfront Duplex",
                "category": "duplex",
                "price": 250000000.00,
                "address": "Admiralty Way, Lekki Phase 1, Lagos",
                "latitude": 6.428100,
                "longitude": 3.421900,
                "bedrooms": 5,
                "bathrooms": 6,
                "balconies": 3,
                "total_rooms": 12,
                "facilities": ["24/7 Security", "Swimming Pool", "Gym", "Smart Home", "4-Car Parking"],
                "is_published": True,
                "is_boosted": True,
                "is_featured": True,
                "color": (26, 82, 118)
            },
            {
                "title": "Bourdillon Executive Apartment",
                "category": "apartment",
                "price": 180000000.00,
                "address": "Bourdillon Road, Ikoyi, Lagos",
                "latitude": 6.454900,
                "longitude": 3.434200,
                "bedrooms": 3,
                "bathrooms": 3,
                "balconies": 2,
                "total_rooms": 7,
                "facilities": ["Elevator", "Concierge", "Swimming Pool", "Gym", "Power Backup"],
                "is_published": True,
                "is_boosted": False,
                "is_featured": True,
                "color": (40, 116, 166)
            },
            {
                "title": "Maitama Diplomatic Villa",
                "category": "villa",
                "price": 520000000.00,
                "address": "Transcorp Hilton Way, Maitama, Abuja",
                "latitude": 9.076500,
                "longitude": 7.398600,
                "bedrooms": 6,
                "bathrooms": 7,
                "balconies": 4,
                "total_rooms": 16,
                "facilities": ["Armed Security Guard", "Helipad Access", "Olympic Pool", "CCTV", "Garden"],
                "is_published": True,
                "is_boosted": True,
                "is_featured": True,
                "color": (20, 143, 119)
            },
            {
                "title": "Yaba Tech Hub Apartment",
                "category": "single_flat",
                "price": 35000000.00,
                "address": "Herbert Macaulay Way, Yaba, Lagos",
                "latitude": 6.524400,
                "longitude": 3.379200,
                "bedrooms": 2,
                "bathrooms": 2,
                "balconies": 1,
                "total_rooms": 4,
                "facilities": ["Fibre Optic Wifi", "24/7 Power", "Security", "Parking"],
                "is_published": True,
                "is_boosted": False,
                "is_featured": False,
                "color": (120, 40, 140)
            },
            {
                "title": "Ikeja GRA Family Bungalow",
                "category": "bungalow",
                "price": 120000000.00,
                "address": "Isaac John Street, Ikeja GRA, Lagos",
                "latitude": 6.588200,
                "longitude": 3.356500,
                "bedrooms": 4,
                "bathrooms": 5,
                "balconies": 1,
                "total_rooms": 9,
                "facilities": ["Solar Power System", "Spacious Compound", "Boys Quarters", "Security"],
                "is_published": True,
                "is_boosted": True,
                "is_featured": False,
                "color": (160, 64, 0)
            },
            {
                "title": "Asokoro Hilltop Retreat",
                "category": "villa",
                "price": 390000000.00,
                "address": "Yakubu Gowon Crescent, Asokoro, Abuja",
                "latitude": 9.043300,
                "longitude": 7.525800,
                "bedrooms": 5,
                "bathrooms": 5,
                "balconies": 3,
                "total_rooms": 11,
                "facilities": ["Infinity Pool", "Hilltop View", "Security Post", "Gym"],
                "is_published": True,
                "is_boosted": False,
                "is_featured": True,
                "color": (34, 153, 84)
            },
            {
                "title": "Eko Atlantic Beachfront Condo",
                "category": "condo",
                "price": 210000000.00,
                "address": "Ocean Front Avenue, Eko Atlantic, Lagos",
                "latitude": 6.417200,
                "longitude": 3.415800,
                "bedrooms": 2,
                "bathrooms": 2,
                "balconies": 2,
                "total_rooms": 5,
                "facilities": ["Private Beach Access", "Swimming Pool", "Spa", "Underground Parking"],
                "is_published": True,
                "is_boosted": True,
                "is_featured": False,
                "color": (41, 128, 185)
            },
            {
                "title": "Chevron Lekki Cozy Airbnb Flat",
                "category": "airbnb",
                "price": 45000000.00,
                "address": "Chevron Drive, Lekki, Lagos",
                "latitude": 6.438500,
                "longitude": 3.535000,
                "bedrooms": 1,
                "bathrooms": 1,
                "balconies": 1,
                "total_rooms": 3,
                "facilities": ["Fully Furnished", "Netflix & DStv", "Security", "Cleaning Service"],
                "is_published": True,
                "is_boosted": False,
                "is_featured": False,
                "color": (142, 68, 173)
            }
        ]

        self.stdout.write(self.style.SUCCESS(f"Seeding {len(sample_properties)} property listings..."))

        for prop in sample_properties:
            color = prop.pop("color")
            title = prop["title"]

            listing, created = Listing.objects.get_or_create(
                title=title,
                agent=agent_user,
                defaults=prop
            )
            
            status_str = "Created" if created else "Updated"
            self.stdout.write(f"  Property: '{listing.title}' ({listing.category}) - {status_str}")

            if created or not listing.images.exists():
                cover_file = self.generate_sample_image(f"{listing.title} Cover", color)
                ListingImage.objects.create(
                    listing=listing,
                    image=cover_file,
                    is_cover=True
                )

                gallery_file = self.generate_sample_image(f"{listing.title} Interior", (100, 100, 100))
                ListingImage.objects.create(
                    listing=listing,
                    image=gallery_file,
                    is_cover=False
                )

        # 4. Seed Moderation Reports
        from agents.models import Report
        if not Report.objects.exists():
            first_listing = Listing.objects.first()
            buyer_user = User.objects.filter(role='buyer').first() or agent_user
            
            sample_reports = [
                {
                    "report_type": "listing",
                    "reason": "Fake images",
                    "description": "The images posted do not match the real property location.",
                    "listing": first_listing,
                    "reporter": buyer_user,
                    "status": "pending"
                },
                {
                    "report_type": "user",
                    "reason": "Off-platform transaction request",
                    "description": "Agent requested cash payment outside the platform.",
                    "reported_user": agent_user,
                    "reporter": buyer_user,
                    "status": "pending"
                },
                {
                    "report_type": "auto_fraud",
                    "reason": "Duplicate image hash detected",
                    "description": "Automated fraud system detected duplicated listing photo across multiple accounts.",
                    "listing": first_listing,
                    "status": "pending"
                },
                {
                    "report_type": "listing",
                    "reason": "Misleading price",
                    "description": "Price stated is significantly lower than actual market value.",
                    "listing": first_listing,
                    "reporter": buyer_user,
                    "status": "resolved"
                }
            ]
            for rep_data in sample_reports:
                Report.objects.create(**rep_data)
            self.stdout.write(self.style.SUCCESS("  Seeded sample moderation reports."))

        # 5. Seed Featured Plans & Subscriptions
        from profiles.models import FeaturedPlan, AgentSubscription, ListingFeature
        from django.utils import timezone

        if not FeaturedPlan.objects.exists():
            FeaturedPlan.objects.create(
                name="7 day plan",
                duration_days=7,
                price=5000.00,
                features=["Homepage placement", "Search boost", "Featured badge"]
            )
            FeaturedPlan.objects.create(
                name="14 day plan",
                duration_days=14,
                price=8500.00,
                features=["Homepage hero slot", "Priority search rank", "Featured verified badge", "Email campaign inclusion"]
            )
            FeaturedPlan.objects.create(
                name="30 day plan",
                duration_days=30,
                price=15000.00,
                features=["All 14-day features", "Push notification slot", "Social media feature"]
            )
            self.stdout.write(self.style.SUCCESS("  Seeded sample Featured Plans."))

        if agent_user and not AgentSubscription.objects.exists():
            plan = created_plans[1] if len(created_plans) > 1 else created_plans[0]
            AgentSubscription.objects.create(
                agent=agent_user,
                plan=plan,
                amount=8500.00,
                next_renewal=timezone.now() + timezone.timedelta(days=30),
                status='active'
            )
            self.stdout.write(self.style.SUCCESS("  Seeded sample Agent Subscription."))

        first_listing = Listing.objects.first()
        if first_listing and not ListingFeature.objects.exists():
            fp = FeaturedPlan.objects.first()
            ListingFeature.objects.create(
                listing=first_listing,
                featured_plan=fp,
                amount=8500.00,
                date_due=timezone.now() + timezone.timedelta(days=14),
                status='active'
            )
            self.stdout.write(self.style.SUCCESS("  Seeded sample Listing Feature."))

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
