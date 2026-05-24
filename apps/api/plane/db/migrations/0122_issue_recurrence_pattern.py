from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0121_alter_estimate_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='issue',
            name='recurrence_pattern',
            field=models.JSONField(null=True, blank=True),
        ),
    ]
