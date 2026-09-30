from django.db import migrations, models


def approve_existing(apps, schema_editor):
    # reviews written before approval existed were already public: keep them published
    apps.get_model("catalog", "Review").objects.update(status="approved")


class Migration(migrations.Migration):
    dependencies = [
        ("catalog", "0002_bundle_contactmessage_page_storesettings_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="review",
            name="status",
            field=models.CharField(
                choices=[("pending", "Waiting for approval"), ("approved", "Approved"), ("rejected", "Rejected")],
                db_index=True,
                default="pending",
                max_length=10,
            ),
        ),
        migrations.RunPython(approve_existing, migrations.RunPython.noop),
    ]
