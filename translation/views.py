import logging
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import FileUploadForm

logger = logging.getLogger(__name__)

def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                file_instance = form.save()
                return redirect('success', documentId=file_instance.id)
            except Exception as e:
                messages.error(request, f'An Error has occured! Please try again later! \n {e}')
                render(request, 'upload.html', {'form': form})
    else:
        form = FileUploadForm()

    return render(request, 'upload.html', {'form': form})

def success(request, document_id):
    return render(request, 'success.html', {'documentId': document_id})
