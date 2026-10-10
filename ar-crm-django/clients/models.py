from django.db import models


class Client(models.Model):
    """A client of one architecture firm. Always belongs to exactly one firm."""

    SOURCE_CHOICES = [
        ("referral", "Referral"),
        ("website", "Website"),
        ("social", "Social media"),
        ("walk_in", "Walk-in"),
        ("other", "Other"),
    ]

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="clients")
    name = models.CharField(max_length=150)
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [models.Index(fields=["firm", "name"])]

    def __str__(self):
        return self.name
