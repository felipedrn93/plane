# FORK: fork interno usado somente em portugues.
#
# Muda o default de Profile.language de "en" para "pt-BR" e converte os perfis
# ja existentes. Sem a conversao de dados, quem ja tinha conta continuaria com
# "en" gravado — e o profile store do front sobrescreve o localStorage no login,
# entao esses usuarios seguiriam vendo o sistema em ingles.
#
# Reversivel: o backward apenas restaura o default do upstream. Nao tenta
# adivinhar qual era o idioma de cada usuario antes da conversao (essa
# informacao se perde), o que e aceitavel porque este fork so oferece pt-BR.

from django.db import migrations, models


def set_existing_profiles_to_pt_br(apps, schema_editor):
    Profile = apps.get_model("db", "Profile")
    Profile.objects.exclude(language="pt-BR").update(language="pt-BR")


def noop_reverse(apps, schema_editor):
    # Ver docstring do modulo: os idiomas anteriores nao sao recuperaveis.
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("db", "0125_alter_fileasset_comment"),
    ]

    operations = [
        migrations.AlterField(
            model_name="profile",
            name="language",
            field=models.CharField(default="pt-BR", max_length=255),
        ),
        migrations.RunPython(set_existing_profiles_to_pt_br, noop_reverse),
    ]
