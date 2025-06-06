# Generated by Django 5.1.7 on 2025-03-27 05:05

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('neo', '0007_alter_room_admin'),
    ]

    operations = [
        migrations.AddField(
            model_name='room',
            name='is_expired',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='room',
            name='max_users',
            field=models.IntegerField(default=2),
        ),
    ]
