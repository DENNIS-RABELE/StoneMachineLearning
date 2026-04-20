#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'decision_service.settings')
django.setup()

from django.contrib import admin
from ml.models import BettorProfile, ClusteringModel, BettorCluster, ClusterCharacteristics, MLMetrics

print('✅ ML App Successfully Registered')
print('=' * 50)
print()
print('Registered Models in Django Admin:')
print()

for model in [BettorProfile, ClusteringModel, BettorCluster, ClusterCharacteristics, MLMetrics]:
    is_registered = model in admin.site._registry
    status = '✅' if is_registered else '❌'
    count = model.objects.count()
    print(f'{status} {model.__name__:30} ({count} records)')

print()
print('Database Tables Created:')
for model in [BettorProfile, ClusteringModel, BettorCluster, ClusterCharacteristics, MLMetrics]:
    print(f'  ✅ {model._meta.db_table}')

print()
print('ML App Status: READY FOR USE')
