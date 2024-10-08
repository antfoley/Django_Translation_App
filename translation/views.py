import logging
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.contrib import messages
from .forms import FileUploadForm
from .models import File

logger = logging.getLogger(__name__)

def download_translated_file(document_id):
    document = get_object_or_404(File, id=document_id)
    if document.translated_file:
        response = HttpResponse(document.translatedFile, content_type='application/force-download')
        response['Content-Disposition'] = f'attachment; filename="{document.translatedFile.name}"'
        return response
    return Http404('No trnaslated document found')

def upload_file(request):
    form = FileUploadForm()
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_instance = form.save()
                return redirect('success', documentId=file_instance.id)
            except Exception as exc:
                messages.error(request, f'An error has occurred! Please try again later! \n {exc}')
    return render(request, 'upload.html', {'form': form})

def success(request, document_id):
    return render(request, 'success.html', {'documentId': document_id})
