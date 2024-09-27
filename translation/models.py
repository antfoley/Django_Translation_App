from django.conf import settings
from django.db import models
from django.core.files.base import ContentFile
import os
import re
import csv
import shutil 
import datetime
from google.cloud import translate_v2 as translate
import docx
from docx.oxml import parse_xml
from docx.oxml.ns import nsdecls
import pandas as pd
from io import BytesIO, TextIOWrapper
from lxml import etree as ET
import chardet
import openpyxl
from google.oauth2 import service_account

credentials = service_account.Credentials.from_service_account_file(
        settings.GOOGLE_CLOUD_CREDENTIALS_PATH)
    

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
    # credentials_path = r"C:\Users\AnthonyFoley\Project1_TranslationApp\translationApp\translation\booming-post-404017-49309d69296e.json"
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

    # Detect encoding
    encoding = detect_encoding(self.originalFile.path)

    now = datetime.datetime.now()
    formatted_dt = datetime.datetime.strftime(now, '%Y-%m-%dT%H:%M:%S')

    # Create the output file name and path
    output_file_name = f'translated_csv_file_{self.title}.csv'
    output_file_path = os.path.join('translated/', output_file_name)

    # Create a BytesIO buffer to hold CSV content
    output_file_content = BytesIO()
    
    # Create a TextIOWrapper around BytesIO to handle text data
    text_wrapper = TextIOWrapper(output_file_content, encoding='utf-8', newline='')

    # Use the text wrapper to write the CSV
    writer = csv.writer(text_wrapper)

    # Open the original CSV file for reading with the detected encoding
    with open(self.originalFile.path, "r", encoding=encoding) as input_file:
        reader_obj = csv.reader(input_file)

        # Iterate over each row in the CSV file using reader object 
        for row in reader_obj:
            # if len(row) < 2:
            #     #print(f"Skipping row: {row} (not enough columns)")
            #     continue  # Skip rows that don't have at least 2 columns
            english_text = row[1]
            translated_text = translate_string(target=self.desiredLang, text=english_text, sourceLang=self.originalLang)

            # Write translated text to the output row
            row[2] = translated_text

            # Write the row to the CSV
            writer.writerow(row)

    # Don't forget to flush the text wrapper to write any remaining data
    text_wrapper.flush()

    # Move to the start of the BytesIO buffer
    output_file_content.seek(0)

    # Get the content from the BytesIO buffer as bytes
    content = output_file_content.getvalue()

    # Save the translated CSV file
    self.translatedFile.save(output_file_name, ContentFile(content))

    # Close the TextIOWrapper (this will also close the BytesIO)
    text_wrapper.close()

def translateXlsx(self):
    # credentials_path = r"C:\Users\AnthonyFoley\Project1_TranslationApp\translationApp\translation\booming-post-404017-49309d69296e.json"
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path

    now = datetime.datetime.now()
    formatted_dt = datetime.datetime.strftime(now, '%Y-%m-%dT%H:%M:%S')

    # Load the XLSX file using openpyxl (pandas supports this, but this provides more control)
    workbook = openpyxl.load_workbook(self.originalFile.path)
    sheet = workbook.active  # You can specify sheet name if needed

    # Iterate through the rows in the worksheet and translate the second column
    for row in sheet.iter_rows(min_row=2, max_row=sheet.max_row, min_col=2, max_col=2):
        cell = row[0]  # Get the cell in the second column (index starts at 0)
        english_text = cell.value

        if english_text:
            # Translate the text
            translated_text = translate_string(target=self.desiredLang, text=english_text, sourceLang=self.originalLang)

            # Write the translated text in the third column
            sheet.cell(row=cell.row, column=3, value=translated_text)

    # Save the translated data back to a new XLSX file
    output_file_name = f'translated_xlsx_file_{self.title}.xlsx'
    #output_file_path = os.path.join('translated/', output_file_name)
    output = BytesIO()
    workbook.save(output)
    content = ContentFile(output.getvalue())
    self.translatedFile.save(output_file_name, content)

    #workbook.save(output_file_path)
    
    # Store the translated file path in the model field
    # with open(self.translatedFile.path, 'rb') as translated_file:
    #     self.translatedFile.save(output_file_name, ContentFile(translated_file.read()))


def translatePo(self):
    now = datetime.datetime.now()
    formatted_dt = datetime.datetime.strftime(now, '%Y-%m-%dT%H:%M:%S')


    source_file = self.originalFile

    # source_filepath= "/home/surewash/Desktop/new_translations/"
    # output_file = "%s/edited_django_po_file-%s.po" % (source_filepath, formatted_dt)
    # print(output_file)
    output_file = self.translatedFile
    
    shutil.copyfile(source_file.path,output_file.path)

    # credentials_path = r"C:\Users\AnthonyFoley\Project1_TranslationApp\translationApp\translation\booming-post-404017-49309d69296e.json"
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path


    with open(source_file.path) as source_file, open(output_file.path, 'w+', encoding='utf-8-sig') as outfile:
    
        msgid_found = False

        # The 'readable' variable stores the source text
        # in a more readable form, removing 'newline' characters,
        # html tags and django variables(from both .py files and template files)
        cumulative_msg_str_readable = ""
        
        # The 'raw' variable stores the source text as-is
        cumulative_msg_str_raw = ""

        # Stores the 'file locations' comment lines from .po files
        file_locations = ""
        text_to_translate = ""
        for line_number, line_content in enumerate(source_file): 
            readable_content = line_content

            if line_content.startswith("msgid"):
                msgid_found = True
                readable_content = line_content.strip("msgid ")
                # print(readable_content)


            if not line_content.startswith("msgstr"):
                outfile.write(line_content)
               
    
            # When you hit this line it indicates that the source text 'msgid' string (which often spans multiple lines)
            # has completed, so we parse the text, write all to CSV, and reset the variables for the next msgid(string to be translated)
            if line_content.startswith("msgstr"):
                text_to_translate = cumulative_msg_str_readable 
                
                if line_content.startswith("msgstr \"\""):
                    translated_text = translate_string(target=self.desiredLang, text=text_to_translate, sourceLang=self.originalLang)
                    print(translated_text)
                    outfile.write("msgstr \"%s\"" % translated_text)
                    outfile.write("\n")
                else:
                    outfile.write(line_content)
                    outfile.write("\n")

                print("")
                msgid_found = False 
                cumulative_msg_str_readable = ""
                cumulative_msg_str_raw= ""
                file_locations = ""

    
            # If it's a comment that indicates which file the string is from,
            # add to the 'file_locations' variable
            if line_content.startswith("#:"):
                file_locations += line_content + ","
    
            # msgid's often span multiple lines, we want readable string version to not contain any newline characters
            if msgid_found:
                cumulative_msg_str_readable += readable_content.strip("\n").strip("\"")   
                cumulative_msg_str_raw += line_content

def translateDocx(self):
    # credentials_path = r"C:\Users\AnthonyFoley\Project1_TranslationApp\translationApp\translation\booming-post-404017-49309d69296e.json"
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path
    original_doc = docx.Document(self.originalFile.path)
    translated_doc = docx.Document()

    for paragraph in original_doc.paragraphs:
        # Create a new paragraph in the translated document
        translated_paragraph = translated_doc.add_paragraph()

        # numbering_format = None
        # if paragraph._element.xpath(".//w:numPr"):
        # numbering_format = get_numbering(paragraph)

        # Handle empty lines (paragraphs that are just whitespace)
        if not paragraph.text.strip():
            translated_paragraph.add_run("")
            continue  # Skip further processing for empty paragraphs

        for run in paragraph.runs:
            original_text = run.text
            translated_text = translate_string(target=self.desiredLang, text=original_text, sourceLang=self.originalLang)

            # Check for numbering or bullet points
            # numbering_format = get_numbering(paragraph)

            # Create a new run for the translated text
            translated_run = translated_paragraph.add_run(translated_text)

            # Preserve formatting (bold, italic, etc.)
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
        
        #if numbering_format:
           # translated_paragraph.insert(0, f'{numbering_format} ')  # Insert numbering at the beginning of the paragraph

    # Save the translated document to a BytesIO object
    output = BytesIO()
    translated_doc.save(output)
    content = ContentFile(output.getvalue())

    # Save the translated document
    translated_filename = f'translated_docx_file_{self.title}.docx'
    self.translatedFile.save(translated_filename, content)

def translateResx(self):
    # credentials_path = r"C:\Users\AnthonyFoley\Project1_TranslationApp\translationApp\translation\booming-post-404017-49309d69296e.json"
    # os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = credentials_path


    now = datetime.datetime.now()
    formatted_dt = datetime.datetime.strftime(now, '%Y-%m-%dT%H:%M:%S')


    source_file = self.originalFile
    # source_filepath= "/home/surewash/Desktop/translation/Resx"
    # output_file = "%s/frontend_text_for_translation-%s.xml" % (source_filepath, formatted_dt)
    # print(output_file)
    output_file = self.translatedFile
    shutil.copyfile(source_file.path,output_file.path)

    file_contents = open(output_file.path, 'rt').read()
    output = open(output_file.path, "wt")

    file_path = os.path.join(settings.MEDIA_ROOT, self.originalFile.name)
    #print(self.originalFile.name)
    doc = ET.parse(file_path.replace('\\','/'))
    # doc = ET.parse(self.originalFile)
    root = doc.getroot()
    data = root.xpath('data')
    english_keys = set()
    for elem in data:
        for val in elem:
            english_text = val.text
            if english_text:
                translated_text = translate_string(target=self.desiredLang, text=english_text, sourceLang=self.originalLang)
                val.text = translated_text
                print(translated_text)

    output_tree = ET.tostring(root, encoding='utf-8', pretty_print = True).decode('utf-8')
    output.write(output_tree)
    output.close()


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
        elif file_type == 'resx':
            self.translatedFile = f'translated_resx_file_{self.title}.resx'
            translateResx(self)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
        self.save(update_fields=['translatedFile'])


    