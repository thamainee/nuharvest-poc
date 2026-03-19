"""
python manage.py setup_demo
Creates demo departments, users, and roles for the POC.
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from planting.models import Department, UserProfile


class Command(BaseCommand):
    help = 'Set up demo departments and users for the POC'

    def handle(self, *args, **kwargs):
        # ── Departments ───────────────────────────────────────────────────
        planting, _ = Department.objects.get_or_create(
            code="PLANT",
            defaults={"name": "Planting", "colour": "#1B4332",
                      "description": "Planting operations department"}
        )
        harvesting, _ = Department.objects.get_or_create(
            code="HARV",
            defaults={"name": "Harvesting", "colour": "#92400E",
                      "description": "Harvesting operations department"}
        )
        finance, _ = Department.objects.get_or_create(
            code="FIN",
            defaults={"name": "Finance", "colour": "#1E3A5F",
                      "description": "Finance department"}
        )
        self.stdout.write(self.style.SUCCESS("✅ Departments created: Planting, Harvesting, Finance"))

        # ── Users ─────────────────────────────────────────────────────────
        users_config = [
            {
                "username": "admin",
                "password": "admin123",
                "email": "admin@nuharvest.co.za",
                "first_name": "Admin",
                "last_name": "User",
                "is_staff": True,
                "department": None,
                "role": "admin",
                "can_upload": True,
                "can_import": True,
                "can_view_all": True,
            },
            {
                "username": "planting_mgr",
                "password": "pass123",
                "email": "planting.mgr@nuharvest.co.za",
                "first_name": "Planting",
                "last_name": "Manager",
                "is_staff": False,
                "department": planting,
                "role": "manager",
                "can_upload": True,
                "can_import": True,
                "can_view_all": False,
            },
            {
                "username": "viewer1",
                "password": "pass123",
                "email": "viewer1@nuharvest.co.za",
                "first_name": "Jane",
                "last_name": "Viewer",
                "is_staff": False,
                "department": planting,
                "role": "viewer",
                "can_upload": False,
                "can_import": False,
                "can_view_all": False,
            },
            {
                "username": "harv_mgr",
                "password": "pass123",
                "email": "harv.mgr@nuharvest.co.za",
                "first_name": "Harvesting",
                "last_name": "Manager",
                "is_staff": False,
                "department": harvesting,
                "role": "manager",
                "can_upload": True,
                "can_import": True,
                "can_view_all": False,
            },
        ]

        for cfg in users_config:
            user, created = User.objects.get_or_create(
                username=cfg["username"],
                defaults={
                    "email": cfg["email"],
                    "first_name": cfg["first_name"],
                    "last_name": cfg["last_name"],
                    "is_staff": cfg["is_staff"],
                }
            )
            if created:
                user.set_password(cfg["password"])
                user.save()

            UserProfile.objects.update_or_create(
                user=user,
                defaults={
                    "department": cfg["department"],
                    "role": cfg["role"],
                    "can_upload": cfg["can_upload"],
                    "can_import": cfg["can_import"],
                    "can_view_all_departments": cfg["can_view_all"],
                }
            )
            status = "created" if created else "updated"
            self.stdout.write(f"  {'✅' if created else '🔄'} {cfg['username']} ({cfg['role']}) — {status}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("🎉 Demo setup complete!"))
        self.stdout.write("")
        self.stdout.write("Login credentials:")
        self.stdout.write("  admin        / admin123   → Admin (sees all departments)")
        self.stdout.write("  planting_mgr / pass123    → Planting Manager (upload + import)")
        self.stdout.write("  viewer1      / pass123    → Planting Viewer (read only)")
        self.stdout.write("  harv_mgr     / pass123    → Harvesting Manager (different dept)")
        self.stdout.write("")
        self.stdout.write("Next: python manage.py runserver")
