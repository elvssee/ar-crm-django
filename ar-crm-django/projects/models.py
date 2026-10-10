from django.core.validators import MinValueValidator
from django.db import models


class Project(models.Model):
    """A project for one client of one firm."""

    TYPE_CHOICES = [
        ("residential", "Residential"),
        ("commercial", "Commercial"),
        ("interior", "Interior"),
        ("other", "Other"),
    ]

    STAGE_ENQUIRY = "enquiry"
    STAGE_PROPOSAL = "proposal"
    STAGE_DESIGN = "design"
    STAGE_CONSTRUCTION = "construction"
    STAGE_COMPLETED = "completed"
    STAGE_CHOICES = [
        (STAGE_ENQUIRY, "Enquiry"),
        (STAGE_PROPOSAL, "Proposal sent"),
        (STAGE_DESIGN, "Design"),
        (STAGE_CONSTRUCTION, "Construction"),
        (STAGE_COMPLETED, "Completed"),
    ]

    firm = models.ForeignKey("accounts.Firm", on_delete=models.CASCADE, related_name="projects")
    # PROTECT: a client that still has projects cannot be deleted by accident.
    client = models.ForeignKey("clients.Client", on_delete=models.PROTECT, related_name="projects")
    title = models.CharField(max_length=150)
    project_type = models.CharField(max_length=20, choices=TYPE_CHOICES, default="residential")
    site_location = models.CharField(max_length=200, blank=True)
    area_sqft = models.PositiveIntegerField("area (sq ft)", null=True, blank=True)
    estimated_fee = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        validators=[MinValueValidator(0)],
    )
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default=STAGE_ENQUIRY)
    start_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["firm", "stage"])]

    def __str__(self):
        return self.title
