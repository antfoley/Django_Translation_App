from django.shortcuts import get_object_or_404, render, redirect
from django.http import HttpResponse, Http404
from django.template import loader
from .models import File
from .forms import FileUploadForm  # Create this form in forms.py

# Create your views here.
def index(request):
    return HttpResponse('place holder for translation goes here')

def downloadTranslatedFile(request, documentId):
    document = get_object_or_404(File, id=documentId)
    if document.translatedFile:
        response = HttpResponse(document.translatedFile, content_type='application/force-download')
        response['Content-Disposition'] = f'attachment; filename="{document.translatedFile.name}"'
        return response
    else:
        return Http404('No trnaslated document found')
    
def upload_file(request):
    if request.method == 'POST':
        form = FileUploadForm(request.POST, request.FILES)
        if form.is_valid():
            file_instance = form.save()
            # Redirect to a success page or the same page to show the uploaded file
            return redirect('success', documentId=file_instance.id)  # Update with your success URL
    else:
        form = FileUploadForm()

    return render(request, 'upload.html', {'form': form})

def success(request, documentId):
    return render(request, 'success.html', {'documentId': documentId})