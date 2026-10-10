from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import DrawingFile


@receiver(post_delete, sender=DrawingFile)
def delete_file_from_storage(sender, instance, **kwargs):
    """Deleting a database row does not remove the uploaded file, so do it here."""
    if instance.file:
        try:
            instance.file.delete(save=False)
        except OSError:
            pass
