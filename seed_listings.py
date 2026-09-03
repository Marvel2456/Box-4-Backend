import os
import django
import random

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.contrib.auth import get_user_model
from agents.models import Category, Listing, ListingImage
from profiles.models import AgentProfile, Plan, AgentKYC

User = get_user_model()

def seed_data():
    print("🌱 Seeding database with realistic test listings & agents...")

    # 1. Seed Categories
    categories_list = [
        "House", "Apartment", "Villa", "Duplex", "Condo", 
        "Bungalow", "Land", "Airbnb", "Shop", "Plaza"
    ]
    created_cats = []
    for cat_name in categories_list:
        cat_obj, created = Category.objects.get_or_create(
            name=cat_name,
            defaults={"is_active": True}
        )
        created_cats.append(cat_obj)
    print(f"✅ Created/verified {len(created_cats)} categories.")

    # 2. Seed Unlimited Subscription Plan
    unlimited_plan, _ = Plan.objects.get_or_create(
        name="Unlimited Agent Plan",
        defaults={
            "price": 0.00,
            "max_listings": 0,
            "max_boosted": 10,
            "max_featured": 10
        }
    )
    print(f"✅ Created/verified subscription plan: '{unlimited_plan.name}'")

    # 3. Seed Top Agents
    agents_data = [
        {"email": "agent.marvelous@box4homes.com", "name": "Marvelous Egbuhuzor", "agency": "Marvelous Real Estate Ltd", "rating": 4.9, "phone": "+2348011112222"},
        {"email": "agent.funke@box4homes.com", "name": "Funke Akindele", "agency": "Eko Luxury Properties", "rating": 4.8, "phone": "+2348022223333"},
        {"email": "agent.chidi@box4homes.com", "name": "Chidi Okafor", "agency": "Victoria Island Realty", "rating": 4.7, "phone": "+2348033334444"},
        {"email": "agent.zainab@box4homes.com", "name": "Zainab Bello", "agency": "Abuja Prime Estates", "rating": 4.9, "phone": "+2348044445555"},
        {"email": "agent.tunde@box4homes.com", "name": "Tunde Bakare", "agency": "Haven Properties Direct", "rating": 4.6, "phone": "+2348055556666"},
        {"email": "agent.emeka@box4homes.com", "name": "Emeka Nnamdi", "agency": "Port Harcourt Waterfront Realty", "rating": 4.8, "phone": "+2348066667777"},
    ]

    agent_users = []
    for data in agents_data:
        user, created = User.objects.get_or_create(
            email=data["email"],
            defaults={
                "username": data["email"],
                "full_name": data["name"],
                "role": "agent",
                "is_email_verified": True
            }
        )
        if created:
            user.set_password("Password123!")
            user.save()

        profile, _ = AgentProfile.objects.get_or_create(user=user)
        profile.plan = unlimited_plan
        profile.agency_name = data["agency"]
        profile.rating = data["rating"]
        profile.phone_number = data["phone"]
        profile.bio = f"Experienced property specialist with {data['agency']}. Providing premium real estate solutions."
        profile.is_verified = True
        profile.save()

        kyc, _ = AgentKYC.objects.get_or_create(agent_profile=profile)
        kyc.status = 'verified'
        kyc.nin_number = "12345678901"
        kyc.nin_verified = True
        kyc.cac_number = f"RC{random.randint(100000, 999999)}"
        kyc.cac_verified = True
        kyc.save()

        agent_users.append(user)
    print(f"✅ Created/verified {len(agent_users)} top agent profiles.")

    # 4. Sample Property Photo Placeholders
    sample_photos = [
        "listings/house1.webp",
        "listings/house2.webp",
        "listings/house1_DgGxQkq.webp",
        "listings/house2_EOZG5uw.webp"
    ]

    # 5. Property Dataset
    properties_dataset = [
        # Lekki / VI / Ikoyi (Lagos Island)
        {
            "title": "Ultra-Modern 5 Bedroom Fully Detached Duplex with Swimming Pool",
            "category": "duplex",
            "price": 280000000.00,
            "address": "Chevron Alternative Route, Lekki Phase 1, Lagos, Nigeria",
            "latitude": 6.442100,
            "longitude": 3.518600,
            "bedrooms": 5,
            "bathrooms": 6,
            "balconies": 3,
            "total_rooms": 9,
            "facilities": ["Swimming Pool", "Gym", "24/7 Security", "CCTV Cameras", "Smart Home System"],
            "status": "active",
            "is_published": True,
            "is_featured": True,
            "is_boosted": True,
            "agent": agent_users[0]
        },
        {
            "title": "Luxury 3 Bedroom Waterfront Apartment",
            "category": "apartment",
            "price": 180000000.00,
            "address": "Banana Island, Ikoyi, Lagos, Nigeria",
            "latitude": 6.465400,
            "longitude": 3.460100,
            "bedrooms": 3,
            "bathrooms": 4,
            "balconies": 2,
            "total_rooms": 6,
            "facilities": ["Elevator", "Waterfront View", "Gym", "Concierge Service", "Standby Generator"],
            "status": "active",
            "is_published": True,
            "is_featured": True,
            "is_boosted": False,
            "agent": agent_users[1]
        },
        {
            "title": "Contemporary 4 Bedroom Terrace House in Secured Estate",
            "category": "house",
            "price": 120000000.00,
            "address": "Orchid Road, Lekki Phase 2, Lagos, Nigeria",
            "latitude": 6.431200,
            "longitude": 3.542100,
            "bedrooms": 4,
            "bathrooms": 4,
            "balconies": 2,
            "total_rooms": 7,
            "facilities": ["Clean Water", "Gated Security", "Children Playground"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": True,
            "agent": agent_users[2]
        },
        {
            "title": "Exclusive Executive Villa with Ocean View",
            "category": "villa",
            "price": 450000000.00,
            "address": "Victoria Island Extension, Lagos, Nigeria",
            "latitude": 6.428100,
            "longitude": 3.421900,
            "bedrooms": 6,
            "bathrooms": 7,
            "balconies": 4,
            "total_rooms": 11,
            "facilities": ["Infinity Pool", "Private Cinema", "Elevator", "Wine Cellar", "Helipad Access"],
            "status": "active",
            "is_published": True,
            "is_featured": True,
            "is_boosted": True,
            "agent": agent_users[0]
        },

        # Ikeja / Yaba / Maryland (Lagos Mainland)
        {
            "title": "Spacious 3 Bedroom Serviced Apartment",
            "category": "apartment",
            "price": 65000000.00,
            "address": "Allen Avenue, Ikeja, Lagos, Nigeria",
            "latitude": 6.598200,
            "longitude": 3.351200,
            "bedrooms": 3,
            "bathrooms": 3,
            "balconies": 1,
            "total_rooms": 5,
            "facilities": ["Solar Power", "Constant Water", "Paved Access Road"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": False,
            "agent": agent_users[4]
        },
        {
            "title": "Newly Built 2 Bedroom Shortlet Flat (Airbnb Ready)",
            "category": "airbnb",
            "price": 45000000.00,
            "address": "Yaba Tech Road, Yaba, Lagos, Nigeria",
            "latitude": 6.524400,
            "longitude": 3.379200,
            "bedrooms": 2,
            "bathrooms": 2,
            "balconies": 1,
            "total_rooms": 4,
            "facilities": ["High-Speed Wi-Fi", "Smart TV", "Fully Equipped Kitchen", "Keyless Entry"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": True,
            "agent": agent_users[1]
        },

        # Abuja Properties
        {
            "title": "Diplomatic Mansion in Prime Maitama District",
            "category": "villa",
            "price": 850000000.00,
            "address": "Gana Street, Maitama, Abuja, FCT, Nigeria",
            "latitude": 9.083300,
            "longitude": 7.498800,
            "bedrooms": 7,
            "bathrooms": 8,
            "balconies": 5,
            "total_rooms": 14,
            "facilities": ["Bulletproof Doors", "Underground Parking", "Olympic Pool", "Staff Quarters"],
            "status": "active",
            "is_published": True,
            "is_featured": True,
            "is_boosted": True,
            "agent": agent_users[3]
        },
        {
            "title": "Luxury 4 Bedroom Detached Bungalow with BQ",
            "category": "bungalow",
            "price": 140000000.00,
            "address": "Gwarinpa Estate, Abuja, FCT, Nigeria",
            "latitude": 9.112300,
            "longitude": 7.411200,
            "bedrooms": 4,
            "bathrooms": 5,
            "balconies": 2,
            "total_rooms": 7,
            "facilities": ["Green Garden", "Car Port for 4 Cars", "Borehole"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": False,
            "agent": agent_users[3]
        },

        # Port Harcourt Properties
        {
            "title": "Waterfront 4 Bedroom Executive Duplex",
            "category": "duplex",
            "price": 160000000.00,
            "address": "GRA Phase 2, Port Harcourt, Rivers State, Nigeria",
            "latitude": 4.815600,
            "longitude": 7.049800,
            "bedrooms": 4,
            "bathrooms": 5,
            "balconies": 2,
            "total_rooms": 7,
            "facilities": ["Perimeter Fencing", "Industrial Water Treatment", "Security Guard Post"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": True,
            "agent": agent_users[5]
        },
        {
            "title": "Commercial Office Space in Business District",
            "category": "shop",
            "price": 95000000.00,
            "address": "Trans Amadi Industrial Layout, Port Harcourt, Rivers State, Nigeria",
            "latitude": 4.801200,
            "longitude": 7.031200,
            "bedrooms": 0,
            "bathrooms": 2,
            "balconies": 1,
            "total_rooms": 4,
            "facilities": ["Ample Parking", "Elevator", "Fiber Optic Internet"],
            "status": "active",
            "is_published": True,
            "is_featured": False,
            "is_boosted": False,
            "agent": agent_users[5]
        }
    ]

    created_listings = []
    for prop in properties_dataset:
        listing, created = Listing.objects.get_or_create(
            title=prop["title"],
            defaults=prop
        )

        # Ensure cover photo exists
        if created or not listing.images.exists():
            chosen_img = random.choice(sample_photos)
            ListingImage.objects.create(
                listing=listing,
                image=chosen_img,
                is_cover=True
            )
        created_listings.append(listing)

    print(f"🎉 Successfully seeded {len(created_listings)} realistic listings across Lagos, Abuja, and Port Harcourt!")

if __name__ == "__main__":
    seed_data()
