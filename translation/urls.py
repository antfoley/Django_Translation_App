from django.urls import path
from . import views

urlpatterns = [
    path('download/<int:documentId>/',
         views.download_translated_file,
         name='download_translated_file'),

    path('upload/',
         views.upload_file,
         name='upload_file'),

    path('success/<int:documentId>/',
         views.success,
         name='success'),
]
