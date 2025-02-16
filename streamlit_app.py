import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import io
from datetime import datetime

# Set page config
st.set_page_config(page_title="Google Drive & Sheets Manager", layout="wide")

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/spreadsheets']

# Hardcoded Google Sheet ID
SHEET_ID = "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw"

@st.cache_resource
def get_google_services():
    """Get Google Drive and Sheets services using service account."""
    try:
        # Debug: Check if secrets are loaded
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account not found in secrets")
            return None, None

        # Debug: Check service account structure
        required_fields = ["type", "project_id", "private_key", "client_email"]
        missing_fields = [field for field in required_fields if field not in st.secrets["gcp_service_account"]]
        if missing_fields:
            st.error(f"Missing required fields in service account: {missing_fields}")
            return None, None

        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES)

        drive_service = build('drive', 'v3', credentials=credentials)
        sheets_service = build('sheets', 'v4', credentials=credentials)
        return drive_service, sheets_service
    except Exception as e:
        st.error(f"Error setting up Google services: {str(e)}")
        return None, None

def check_folder_access(service, folder_id):
    """Check if the folder exists and is accessible."""
    try:
        st.info(f"Attempting to access folder with ID: {folder_id}")
        # Try to list files in the folder first
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)",
            spaces='drive'
        ).execute()
        # Even if list is empty, if we get here without error, we have access
        st.info(f"Successfully listed files in folder. Found {len(results.get('files', []))} files.")
        return True
    except Exception as list_error:
        st.warning(f"Error listing files in folder: {str(list_error)}")
        # If listing fails, try to get folder directly
        try:
            folder = service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType'
            ).execute()
            st.info(f"Found folder: {folder.get('name')} (Type: {folder.get('mimeType')})")
            return True
        except Exception as e:
            st.error(f"Error accessing folder: {str(e)}")
            if "404" in str(e):
                st.error("""Folder not found. Please check:
    1. The folder ID is correct (current ID: {folder_id})
    2. The folder is shared with the service account with at least 'Editor' access
    3. You're copying the ID from the URL after 'folders/' """)
            elif "403" in str(e):
                st.error("""Permission denied. Please verify:
    1. The service account email has been given access to this folder
    2. The sharing settings allow the service account to access the folder
    3. The service account has at least 'Editor' permissions""")
            return False

def upload_to_drive(service, file_data, filename, mimetype, folder_id):
    """Upload a file to a specific Google Drive folder."""
    try:
        # First check if we can access the folder
        if not check_folder_access(service, folder_id):
            st.error(f"Cannot access folder with ID: {folder_id}. Please make sure: \n" +
                     "1. The folder ID is correct\n" +
                     "2. The folder is shared with the service account email\n" +
                     "3. The service account has at least 'Editor' access to the folder")
            return None

        file_metadata = {
            'name': filename,
            'parents': [folder_id]
        }
        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=True
        )
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        return file.get('id')
    except Exception as e:
        st.error(f"Error uploading {filename}: {str(e)}")
        return None

def write_to_sheet(sheets_service, spreadsheet_id, data, range_name='Sheet1!A1'):
    """Write data to a Google Sheet."""
    try:
        values = data.values.tolist()
        headers = data.columns.tolist()
        values.insert(0, headers)
        body = {
            'values': values
        }
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        return result
    except Exception as e:
        st.error(f"Error writing to sheet: {str(e)}")
        return None

def get_sheet_names(sheets_service, spreadsheet_id):
    """Get all sheet names from the spreadsheet."""
    try:
        spreadsheet = sheets_service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        return [sheet['properties']['title'] for sheet in spreadsheet['sheets']]
    except Exception as e:
        st.error(f"Error getting sheet names: {str(e)}")
        return None

def read_from_sheet(sheets_service, spreadsheet_id, range_name=None):
    """Read data from a Google Sheet."""
    try:
        # First get available sheet names
        sheet_names = get_sheet_names(sheets_service, spreadsheet_id)
        if not sheet_names:
            st.error("Could not retrieve sheet names from the spreadsheet")
            return
