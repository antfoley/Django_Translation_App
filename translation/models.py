import subprocess
from django.conf import settings
from django.db import models
from django.core.files.base import ContentFile
import os
import re
import csv
import shutil 
import datetime
import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
import pandas as pd
from io import BytesIO, TextIOWrapper
from lxml import etree as ET
import chardet
import openpyxl
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.shapes import MSO_SHAPE_TYPE
from pptx.dml.color import RGBColor
from google.cloud import translate
from google.cloud.translate_v3 import TranslationServiceClient
from google.oauth2 import service_account
import fitz

credentials = service_account.Credentials.from_service_account_file(settings.GOOGLE_CLOUD_CREDENTIALS_PATH)
translate_client = TranslationServiceClient(credentials=credentials)
parent = f"projects/{settings.GOOGLE_PROJECT_ID}/locations/global"

def detect_encoding(file_path):
    with open(file_path, 'rb') as file:
        detector = chardet.UniversalDetector()
        for line in file:
            detector.feed(line)
            if detector.done:
                break
        detector.close()
    return detector.result['encoding']

def translate_string(target, text, sourceLang):
    translate_client = translate.Client(credentials=credentials)

    result = translate_client.translate(text, source_language=sourceLang, target_language=target, format_='text')
    return str(result["translatedText"])

def translateCsv(self):
    encoding = detect_encoding(self.originalFile.path)

    output_file_name = f'translated_csv_file_{self.title}.csv'
    output_file_content = BytesIO()
    text_wrapper = TextIOWrapper(output_file_content, encoding='utf-8', newline='')
    writer = csv.writer(text_wrapper)

    original_texts = []
    rows = []

    # Read the original CSV file
    with open(self.originalFile.path, "r", encoding=encoding) as input_file:
        reader_obj = csv.reader(input_file)

        for row in reader_obj:
            english_text = row[1]  # Assuming text to translate is in column 2
            original_texts.append(english_text)
            rows.append(row)  # Save the row for later

    # Translate all the collected text at once
    response = translate_client.translate_text(
        parent=parent,
        contents=original_texts,
        mime_type="text/plain",
        source_language_code=self.originalLang,
        target_language_code=self.desiredLang
    )

    translated_texts = [translation.translated_text for translation in response.translations]

    # Write the translated texts back to the CSV
    for i, row in enumerate(rows):
        row[2] = translated_texts[i]  # Assuming column 3 holds the translated text
        writer.writerow(row)

    text_wrapper.flush()
    output_file_content.seek(0)
    self.translatedFile.save(output_file_name, ContentFile(output_file_content.getvalue()))
    text_wrapper.close()

def translateXlsx(self):
    output_file_name = f'translated_xlsx_file_{self.title}.xlsx'
    
    workbook = openpyxl.load_workbook(self.originalFile.path)
    sheet = workbook.active

    original_texts = []
    cell_mapping = []  # Track which cells the text comes from

    # Collect all the texts to translate from the second column (B)
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=2, max_col=2):
        cell = row[0]
        english_text = cell.value
        if english_text:
            original_texts.append(english_text)
            cell_mapping.append(cell)

    # Translate all the collected text at once
    response = translate_client.translate_text(
        parent=parent,
        contents=original_texts,
        mime_type="text/plain",
        source_language_code=self.originalLang,
        target_language_code=self.desiredLang
    )

    translated_texts = [translation.translated_text for translation in response.translations]

    # Write the translated texts back into the XLSX file (in column 3)
    for i, cell in enumerate(cell_mapping):
        sheet.cell(row=cell.row, column=3, value=translated_texts[i])

    # Save the translated file
    output = BytesIO()
    workbook.save(output)
    self.translatedFile.save(output_file_name, ContentFile(output.getvalue()))


def translatePo(self):
    output_file_name = f'translated_po_file_{self.title}.po'
    output_file = self.translatedFile

    shutil.copyfile(self.originalFile.path, output_file.path)

    original_texts = []
    msgid_mapping = []

    with open(self.originalFile.path, 'r', encoding='utf-8') as source_file, open(output_file.path, 'w+', encoding='utf-8-sig') as outfile:
        msgid_found = False
        text_to_translate = ""

        for line in source_file:
            if line.startswith("msgid"):
                msgid_found = True
                text_to_translate = line.strip("msgid ").strip("\"")

            if msgid_found and not line.startswith("msgstr"):
                text_to_translate += line.strip("\"")

            if line.startswith("msgstr"):
                original_texts.append(text_to_translate)
                msgid_mapping.append(line)
                msgid_found = False

        # Translate all text at once
        response = translate_client.translate_text(
            parent=parent,
            contents=original_texts,
            mime_type="text/plain",
            source_language_code=self.originalLang,
            target_language_code=self.desiredLang
        )

        translated_texts = [translation.translated_text for translation in response.translations]

        # Write back the translated text
        for i, line in enumerate(msgid_mapping):
            outfile.write(f'msgstr "{translated_texts[i]}"\n')

def translateDocx(self, preserve_formatting=True):
    
    original_doc = docx.Document(self.originalFile.path)
    translated_doc = docx.Document()

    for paragraph in original_doc.paragraphs:
        translated_paragraph = translated_doc.add_paragraph()

        if not paragraph.text.strip():
            translated_paragraph.add_run("")
            continue

        for run in paragraph.runs:
            original_text = run.text
            response = translate_client.translate_text(
                parent=parent,
                contents=[original_text],
                mime_type="text/plain",  
                source_language_code=self.originalLang,
                target_language_code=self.desiredLang,
            )

            translated_text = response.translations[0].translated_text

            translated_run = translated_paragraph.add_run(translated_text)

            # Optionally preserve formatting
            if preserve_formatting:
                if run.bold:
                    translated_run.bold = True
                if run.italic:
                    translated_run.italic = True
                if run.underline:
                    translated_run.underline = True
                if run.font.size:
                    translated_run.font.size = run.font.size
                if run.font.name:
                    translated_run.font.name = run.font.name

    output = BytesIO()
    translated_doc.save(output)
    content = ContentFile(output.getvalue())

    translated_filename = f'translated_docx_file_{self.title}.docx'
    self.translatedFile.save(translated_filename, content)

def translateResx(self):
    output_file_name = f'translated_docx_file_{self.title}.docx'

    original_doc = docx.Document(self.originalFile.path)
    translated_doc = docx.Document()

    original_texts = []
    paragraph_mapping = []

    # Collect paragraphs for batch translation
    for paragraph in original_doc.paragraphs:
        if paragraph.text.strip():  # Ignore empty paragraphs
            original_texts.append(paragraph.text)
            paragraph_mapping.append(paragraph)

    # Translate all paragraphs at once
    response = translate_client.translate_text(
        parent=parent,
        contents=original_texts,
        mime_type="text/plain",
        source_language_code=self.originalLang,
        target_language_code=self.desiredLang
    )

    translated_texts = [translation.translated_text for translation in response.translations]

    # Write the translated text to the new document
    for i, paragraph in enumerate(paragraph_mapping):
        translated_paragraph = translated_doc.add_paragraph(translated_texts[i])
        # Optionally handle run formatting (bold, italic, etc.)

    # Save the translated document
    output = BytesIO()
    translated_doc.save(output)
    self.translatedFile.save(output_file_name, ContentFile(output.getvalue()))

def translateDoc(self):
    docx_path = self.originalFile.path.replace('.doc', '.docx')
    subprocess.run(['libreoffice', '--headless', '--convert-to', 'docx', self.originalFile.path, '--outdir', 'documents/'])
    
    # Once converted, translate as .docx
    self.originalFile.name = docx_path
    translateDocx(self)

def translatePpt(self, preserve_formatting=True):

    presentation = Presentation(self.originalFile.path)
    for slide in presentation.slides:
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue

            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    original_text = run.text
                    if original_text.strip():
                        # Google Cloud Translation v3 API request
                        response = translate_client.translate_text(
                            parent=parent,
                            contents=[original_text],
                            mime_type="text/plain",
                            source_language_code=self.originalLang,
                            target_language_code=self.desiredLang,
                        )
                        translated_text = response.translations[0].translated_text
                        run.text = translated_text

                        # Optionally preserve formatting
                        if preserve_formatting:
                            if run.font.bold:
                                run.font.bold = True
                            if run.font.italic:
                                run.font.italic = True
                            if run.font.underline:
                                run.font.underline = True
                            if run.font.size:
                                run.font.size = run.font.size
                            if run.font.name:
                                run.font.name = run.font.name

    output = BytesIO()
    presentation.save(output)
    content = ContentFile(output.getvalue())

    translated_filename = f'translated_ppt_file_{self.title}.pptx'
    self.translatedFile.save(translated_filename, content)

def translatePptx(self, preserve_formatting=True):
    # The function for `.pptx` is essentially the same as `.ppt` since python-pptx supports both
    translatePpt(self, preserve_formatting=preserve_formatting)


def translatePdf(self, preserve_formatting=True):
    pdf_document = fitz.open(self.originalFile.path)
    translated_pdf = fitz.open()  # Create a new blank PDF for translated content

    for page_num in range(len(pdf_document)):
        page = pdf_document.load_page(page_num)  # Load each page
        page_text = page.get_text("dict")  # Extract text with details

        translated_page = translated_pdf.new_page(width=page.rect.width, height=page.rect.height)

        # Loop through each block in the page (blocks contain paragraphs)
        for block in page_text["blocks"]:
            if "lines" not in block:
                continue  # Skip non-text blocks

            # Process each line in the block
            for line in block["lines"]:
                for span in line["spans"]:
                    original_text = span["text"]
                    if original_text.strip():
                        # Translate the text span
                        response = translate_client.translate_text(
                            parent=parent,
                            contents=[original_text],
                            mime_type="text/plain",
                            source_language_code=self.originalLang,
                            target_language_code=self.desiredLang,
                        )
                        translated_text = response.translations[0].translated_text

                        # Optionally preserve the formatting
                        if preserve_formatting:
                            # Get the original formatting details
                            font_size = span["size"]
                            font_name = span["font"]

                            # Try to preserve the font or fallback to a standard font
                            try:
                                translated_page.insert_text(
                                    fitz.Point(span["origin"][0], span["origin"][1]),
                                    translated_text,
                                    fontsize=font_size,
                                    fontname=font_name if fitz.Font(font_name) else "helv",  # Fallback to Helvetica
                                    fill=span["color"],
                                )
                            except:
                                # If font loading fails, use 'helv' by default
                                translated_page.insert_text(
                                    fitz.Point(span["origin"][0], span["origin"][1]),
                                    translated_text,
                                    fontsize=font_size,
                                    fontname="helv",  # Default to Helvetica if font is unavailable
                                    fill=span["color"],
                                )
                        else:
                            # Insert translated text without formatting
                            translated_page.insert_text(
                                fitz.Point(span["origin"][0], span["origin"][1]),
                                translated_text,
                                fontsize=12,
                                fontname="helv",  # Default to Helvetica
                            )


    # Save the translated PDF to BytesIO
    output = BytesIO()
    translated_pdf.save(output)
    content = ContentFile(output.getvalue())

    translated_filename = f'translated_pdf_file_{self.title}.pdf'
    self.translatedFile.save(translated_filename, content)

# Create your models here.
class File(models.Model):
    title = models.CharField(max_length=200)
    originalLang = models.CharField(default='en', max_length=2)
    desiredLang = models.CharField(max_length=2)
    originalFile = models.FileField(upload_to='documents/')
    translatedFile = models.FileField(upload_to='translated/', blank=True, null=True)
    #fileType = models.CharField(max_length=4, blank=True)
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.originalFile and not self.translatedFile:
            self.translate()

    def translate(self):
        # Read the contents of the original file
        #self.originalFile.open()
        #     content = self.originalFile.read().decode('utf-8')

        #     # Simulate translation (you would use an actual translation service here)
        #     translated_content = self.fake_translation(content)

        #     # Create the translated file
        #     translated_filename = slugify(self.originalFile.name) + "_translated.txt"
        #     translated_file = ContentFile(translated_content.encode('utf-8'))

        #     # Save the translated file to the translated_file field
        #     self.translatedFile.save(translated_filename, translated_file)

        # def fake_translation(self, content):
        #     # Placeholder for actual translation logic (API call, etc.)
        #     return content.replace('Hello', 'Hola')
        arr = self.originalFile.name.split('.')
        file_type = arr[-1].lower()
        #match file_type:
        if file_type == 'csv':
            self.translatedFile = f'translated_csv_file_{self.title}.csv'
            translateCsv(self)
        elif file_type == 'xlsx':
            self.translatedFile = f'translated_xlsx_file_{self.title}.xlsx'
            translateXlsx(self)
        elif file_type == 'po':
            self.translatedFile = f'translated_po_file_{self.title}.po'
            translatePo(self)
        elif file_type == 'docx':
            self.translatedFile = f'translated_docx_file_{self.title}.docx'
            translateDocx(self)
        elif file_type == 'doc':
            self.translatedFile = f'translated_doc_file_{self.title}.doc'
            translateDoc(self)
        elif file_type == 'resx':
            self.translatedFile = f'translated_resx_file_{self.title}.resx'
            translateResx(self)
        elif file_type == 'pptx':
            self.translatedFile = f'translated_pptx_file_{self.title}.pptx'
            translatePptx(self)
        elif file_type == 'ppt':
            self.translatedFile = f'translated_pptx_file_{self.title}.ppt'
            translatePptx(self) #lets hope they are the same :D
        elif file_type == 'pdf':
            self.translatedFile = f'translated_pdf_file_{self.title}.pdf'
            translatePdf(self)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        self.save(update_fields=['translatedFile'])


    