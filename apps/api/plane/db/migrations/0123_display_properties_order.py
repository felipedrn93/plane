import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("db", "0122_issue_recurrence_pattern"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name="projectuserproperty",
            name="display_properties_order",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="cycleuserproperties",
            name="display_properties_order",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="moduleuserproperties",
            name="display_properties_order",
            field=models.JSONField(default=list),
        ),
        migrations.AddField(
            model_name="workspaceuserproperties",
            name="display_properties_order",
            field=models.JSONField(default=list),
        ),
        migrations.CreateModel(
            name="IssueViewUserProperty",
            fields=[
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True, verbose_name="Created At"),
                ),
                (
                    "updated_at",
                    models.DateTimeField(
                        auto_now=True, verbose_name="Last Modified At"
                    ),
                ),
                (
                    "deleted_at",
                    models.DateTimeField(
                        blank=True, null=True, verbose_name="Deleted At"
                    ),
                ),
                (
                    "id",
                    models.UUIDField(
                        db_index=True,
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                        unique=True,
                    ),
                ),
                ("display_properties_order", models.JSONField(default=list)),
                (
                    "created_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_created_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Created By",
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="project_%(class)s",
                        to="db.project",
                    ),
                ),
                (
                    "updated_by",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="%(class)s_updated_by",
                        to=settings.AUTH_USER_MODEL,
                        verbose_name="Last Modified By",
                    ),
                ),
                (
                    "workspace",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="workspace_%(class)s",
                        to="db.workspace",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="view_user_properties",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "view",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="view_user_properties",
                        to="db.issueview",
                    ),
                ),
            ],
            options={
                "verbose_name": "Issue View User Property",
                "verbose_name_plural": "Issue View User Properties",
                "db_table": "issue_view_user_properties",
                "ordering": ("-created_at",),
                "unique_together": {("user", "view", "deleted_at")},
            },
        ),
        migrations.AddConstraint(
            model_name="issueviewuserproperty",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("user", "view"),
                name="view_user_property_unique_user_view_when_deleted_at_null",
            ),
        ),
    ]
