from django.db import models


class Guest(models.Model):
    class IdType(models.TextChoices):
        PASSPORT = "passport", "Passport"
        KEBELE = "kebele", "Kebele ID"
        FAYDA = "fayda", "Fayda (National ID)"
        DRIVING = "driving", "Driving licence"
        OTHER = "other", "Other"

    first_name = models.CharField(max_length=80)
    last_name = models.CharField(max_length=80, blank=True)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    nationality = models.CharField(max_length=60, blank=True, help_text="Country name or ISO code.")
    id_type = models.CharField(max_length=10, choices=IdType.choices, default=IdType.PASSPORT)
    id_number = models.CharField(max_length=40, blank=True)
    id_expiry = models.DateField(null=True, blank=True)
    visa_number = models.CharField(max_length=40, blank=True)
    visa_expiry = models.DateField(null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    address = models.CharField(max_length=255, blank=True)
    company = models.CharField(max_length=120, blank=True)
    company_tin = models.CharField("Company TIN", max_length=20, blank=True)
    vip = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [models.Index(fields=["phone"]), models.Index(fields=["id_number"])]

    @property
    def is_foreign(self):
        return bool(self.nationality) and self.nationality.strip().lower() not in ("et", "eth", "ethiopia", "ethiopian")

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __str__(self):
        return self.full_name
