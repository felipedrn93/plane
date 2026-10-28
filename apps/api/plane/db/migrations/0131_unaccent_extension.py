from django.contrib.postgres.operations import UnaccentExtension
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('db', '0130_clientcompany_cnpj_optional'),
    ]

    operations = [UnaccentExtension()]
