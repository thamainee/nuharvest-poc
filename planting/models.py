from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


# ── Departments ───────────────────────────────────────────────────────────────
class Department(models.Model):
    name        = models.CharField(max_length=100, unique=True)
    code        = models.CharField(max_length=20,  unique=True)
    description = models.TextField(blank=True)
    colour      = models.CharField(max_length=7, default="#1B4332")
    is_active   = models.BooleanField(default=True)
    created_at  = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


# ── User Profile (extends Django User with role + department) ─────────────────
class UserProfile(models.Model):
    ROLES = [
        ("admin",   "Admin"),
        ("manager", "Manager"),
        ("viewer",  "Viewer"),
    ]
    user        = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    department  = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    role        = models.CharField(max_length=20, choices=ROLES, default="viewer")
    can_upload  = models.BooleanField(default=False)
    can_import  = models.BooleanField(default=False)
    can_view_all_departments = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.username} ({self.role})"

    def can_see_department(self, dept):
        if self.can_view_all_departments or self.role == "admin":
            return True
        return self.department == dept


# ── Fields master ─────────────────────────────────────────────────────────────
class PlantingField(models.Model):
    department  = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="fields")
    field_id    = models.CharField(max_length=20, unique=True)
    field_name  = models.CharField(max_length=100)
    block       = models.CharField(max_length=100)
    crop        = models.CharField(max_length=100)
    season      = models.CharField(max_length=50)
    is_active   = models.BooleanField(default=True)
    target_qty_per_week = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.field_name} – {self.crop}"


# ── Weekly planting records ───────────────────────────────────────────────────
class WeeklyPlanting(models.Model):
    department   = models.ForeignKey(Department, on_delete=models.CASCADE)
    field        = models.ForeignKey(PlantingField, on_delete=models.CASCADE, null=True, blank=True)
    week_number  = models.IntegerField()
    week_label   = models.CharField(max_length=20)
    season       = models.CharField(max_length=50)
    field_id_ref = models.CharField(max_length=20)
    field_name   = models.CharField(max_length=100)
    block        = models.CharField(max_length=100)
    crop         = models.CharField(max_length=100)
    planned_date = models.DateField(null=True, blank=True)
    actual_date  = models.DateField(null=True, blank=True)
    labor_cost   = models.FloatField(default=0)
    qty_planted  = models.IntegerField(default=0)
    target_qty   = models.IntegerField(default=0)
    notes        = models.TextField(blank=True, default="")
    imported_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("week_number", "season", "field_id_ref")]

    @property
    def cost_per_seedling(self):
        if self.qty_planted > 0:
            return round(self.labor_cost / self.qty_planted, 2)
        return 0

    @property
    def achievement_pct(self):
        if self.target_qty > 0:
            return round(self.qty_planted / self.target_qty * 100, 1)
        return 0

    @property
    def weeks_behind(self):
        if self.planned_date and self.actual_date:
            delta = (self.actual_date - self.planned_date).days
            return max(0, delta // 7)
        return 0

    @property
    def schedule_status(self):
        wb = self.weeks_behind
        if wb == 0: return "GREEN"
        if wb == 1: return "ORANGE"
        return "RED"

    @property
    def schedule_label(self):
        wb = self.weeks_behind
        if wb == 0: return "On Track"
        if wb == 1: return "1 Wk Behind"
        return f"{wb} Wks Behind"

    @property
    def cost_status(self):
        c = self.cost_per_seedling
        if c <= 2.50: return "GREEN"
        if c <= 3.50: return "ORANGE"
        return "RED"

    @property
    def qty_status(self):
        p = self.achievement_pct
        if p >= 95: return "GREEN"
        if p >= 80: return "ORANGE"
        return "RED"

    def __str__(self):
        return f"{self.week_label} – {self.field_name}"


# ── Notifications ─────────────────────────────────────────────────────────────
class Notification(models.Model):
    SEVERITY = [("info","Info"),("warning","Warning"),("critical","Critical")]
    department  = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True)
    title       = models.CharField(max_length=200)
    message     = models.TextField()
    severity    = models.CharField(max_length=20, choices=SEVERITY, default="info")
    field_name  = models.CharField(max_length=100, blank=True)
    kpi_name    = models.CharField(max_length=100, blank=True)
    kpi_value   = models.CharField(max_length=50,  blank=True)
    is_read     = models.BooleanField(default=False)
    created_at  = models.DateTimeField(auto_now_add=True)
    created_for = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.severity.upper()}] {self.title}"


# ── Upload Batch ──────────────────────────────────────────────────────────────
class UploadBatch(models.Model):
    STATUS = [("pending","Pending"),("validated","Validated"),("errors","Has Errors"),("imported","Imported")]
    department  = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    filename    = models.CharField(max_length=255)
    uploaded_at = models.DateTimeField(default=timezone.now)
    status      = models.CharField(max_length=20, choices=STATUS, default="pending")
    row_count   = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.filename} ({self.status})"


class ValidationError(models.Model):
    batch      = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="errors")
    row_number = models.IntegerField(null=True, blank=True)
    field_name = models.CharField(max_length=100, blank=True)
    error_type = models.CharField(max_length=100)
    message    = models.TextField()


class StagingRecord(models.Model):
    batch        = models.ForeignKey(UploadBatch, on_delete=models.CASCADE, related_name="rows")
    row_number   = models.IntegerField()
    week_number  = models.CharField(max_length=10,  blank=True, default="")
    week_label   = models.CharField(max_length=20,  blank=True, default="")
    season       = models.CharField(max_length=50,  blank=True, default="")
    field_id     = models.CharField(max_length=20,  blank=True, default="")
    field_name   = models.CharField(max_length=100, blank=True, default="")
    block        = models.CharField(max_length=100, blank=True, default="")
    crop         = models.CharField(max_length=100, blank=True, default="")
    planned_date = models.CharField(max_length=30,  blank=True, default="")
    actual_date  = models.CharField(max_length=30,  blank=True, default="")
    labor_cost   = models.CharField(max_length=30,  blank=True, default="")
    qty_planted  = models.CharField(max_length=30,  blank=True, default="")
    target_qty   = models.CharField(max_length=30,  blank=True, default="")
    notes        = models.TextField(blank=True, default="")
