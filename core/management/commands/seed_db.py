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
                "description": "Standard free plan for new real estate agents."
            },
            {
                "name": "Silver Agent",
                "price": 19.99,
                "max_listings": 10,
                "max_boosted": 2,
                "max_featured": 1,
                "description": "Popular plan for independent real estate agents."
            },
            {
                "name": "Gold Pro Agent",
                "price": 49.99,
                "max_listings": 30,
                "max_boosted": 8,
                "max_featured": 5,
                "description": "Pro plan for active agents and boutique firms."
            },
            {
                "name": "Platinum Agency",
                "price": 99.99,
                "max_listings": 100,
                "max_boosted": 25,
                "max_featured": 15,
                "description": "Unlimited plan for high-volume agencies."
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
                self.stdout.write(self.style.ERROR("  No users exist in the database! Please create at least one user first (e.g. via createsuperuser)."))
                return

        # Assign Silver Plan to Agent
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
                "description": "Exquisite 5 bedroom fully detached duplex with automated smart home systems, ocean view balcony, and private cinema.",
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
                "description": "High-rise luxury 3 bedroom apartment located in prestigious Ikoyi with panoramic Lagos lagoon skyline view.",
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
                "description": "Palatial 6 bedroom ambassadorial mansion in Maitama diplomatic zone featuring bulletproof doors and lush greenery.",
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
                "description": "Modern 2 bedroom flat designed for tech professionals and digital nomads close to Yaba tech ecosystem.",
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
                "description": "Charming standalone 4 bedroom bungalow set on a full plot of land in quiet residential Ikeja GRA.",
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
                "description": "Luxury hilltop sanctuary boasting panoramic views of Aso Rock and Abuja central business district.",
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
                "description": "Ultra-modern beachfront condo unit in West Africa's premier smart city development.",
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
                "description": "Turnkey short-let investment unit generating high monthly rental yield on Airbnb platform.",
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

            # Seed cover image & gallery image for listing
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

        self.stdout.write(self.style.SUCCESS("Database seeding completed successfully!"))
