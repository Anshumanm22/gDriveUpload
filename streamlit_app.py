import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
import io

# Set page config
st.set_page_config(page_title="Google Drive & Sheets Manager", layout="wide")

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/spreadsheets']

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
            scopes=SCOPES
        )
        
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
            return None
            
        st.info(f"Available sheets: {', '.join(sheet_names)}")
        
        # If no range specified, use the first sheet
        if not range_name:
            range_name = f"{sheet_names[0]}!A1:Z1000"
            st.info(f"Using sheet: {sheet_names[0]}")
        
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            st.warning("No data found in the sheet")
            return pd.DataFrame()
            
        df = pd.DataFrame(values[1:], columns=values[0])
        st.success(f"Successfully read {len(df)} rows of data")
        return df
    except Exception as e:
        st.error(f"Error reading from sheet: {str(e)}")
        if "Unable to parse range" in str(e):
            st.error("Sheet name might be incorrect. Please check the available sheet names above.")
        return None

def main():
    st.title("📁 Google Drive & Sheets Manager")
    
    # Initialize services
    drive_service, sheets_service = get_google_services()
    
    if not drive_service or not sheets_service:
        st.error("Failed to initialize Google services. Please check your service account configuration.")
        return
        
    tab1, tab2 = st.tabs(["File Upload", "Sheets Manager"])
    
    with tab1:
        st.header("Upload Files to Drive")
        
        # Store folder ID in session state if not already there
        if 'folder_id' not in st.session_state:
            st.session_state.folder_id = ''
            
        # Add folder ID input at the top
        folder_id = st.text_input(
            "Enter Google Drive Folder ID",
            value=st.session_state.folder_id,
            help="This is the ID of the folder where files will be uploaded. " +
                 "You can find it in the folder's URL: " +
                 "https://drive.google.com/drive/folders/FOLDER_ID"
        )
        
        # Update session state and validate folder ID
        st.session_state.folder_id = folder_id
        
        if folder_id:
            with st.spinner("Testing folder access..."):
                if check_folder_access(drive_service, folder_id):  # Fixed: Changed test_folder_access to check_folder_access
                    st.success("✅ Folder access confirmed and tested")
                else:
                    st.error("❌ Cannot properly access this folder. Please check the error details above.")
                    st.info("Make sure the service account has full Editor access to this folder.")
        
        st.markdown("---")
        
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi', 'csv', 'xlsx'],
            accept_multiple_files=True
        )
        
        if uploaded_files and folder_id:
            st.write("Selected files:")
            for file in uploaded_files:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📎 {file.name}")
                with col2:
                    if st.button("Upload", key=f"upload_{file.name}"):
                        with st.spinner(f"Uploading {file.name}..."):
                            file_id = upload_to_drive(
                                drive_service,
                                file.getvalue(),
                                file.name,
                                file.type,
                                folder_id
                            )
                            if file_id:
                                st.success(f"Successfully uploaded {file.name}")
                                st.markdown(f"[View file](https://drive.google.com/file/d/{file_id}/view)")
        elif uploaded_files:
            st.warning("Please enter a folder ID before uploading files.")
    
    with tab2:
        st.header("Google Sheets Manager")
        
        sheet_action = st.radio(
            "Choose action:",
            ["Read sheet", "Update sheet"]
        )
        
        sheet_id = st.text_input("Enter Sheet ID (from sheet URL)")
        
        if sheet_id:
            if sheet_action == "Read sheet":
                # Get sheet names first
                sheet_names = get_sheet_names(sheets_service, sheet_id)
                if sheet_names:
                    selected_sheet = st.selectbox(
                        "Select sheet to read",
                        options=sheet_names
                    )
                    if st.button("Read"):
                        with st.spinner("Reading data..."):
                            range_name = f"{selected_sheet}!A1:Z1000"
                            df = read_from_sheet(sheets_service, sheet_id, range_name)
                            if df is not None:
                                st.dataframe(df)
            
            else:  # Update sheet
                uploaded_file = st.file_uploader(
                    "Upload new data (CSV/Excel)",
                    type=['csv', 'xlsx']
                )
                
                if uploaded_file and st.button("Update"):
                    with st.spinner("Updating sheet..."):
                        if uploaded_file.type == "text/csv":
                            df = pd.read_csv(uploaded_file)
                        else:
                            df = pd.read_excel(uploaded_file)
                            
                        result = write_to_sheet(
                            sheets_service,
                            sheet_id,
                            df
                        )
                        
                        if result:
                            st.success("Sheet updated successfully!")
    
    st.sidebar.markdown("""
    ### Instructions:
    1. For uploading files:
       - Get the folder ID from your Google Drive folder URL
       - Paste the folder ID in the input field
       - Select files to upload
       - Make sure the folder is shared with the service account email
       
    2. For Google Sheets:
       - Make sure the sheet is shared with the service account email
       - Get the Sheet ID from the sheet's URL
       - Choose to read or update the sheet
    
    To get Folder ID:
    ```
    https://drive.google.com/drive/folders/{FOLDER_ID}
    ```
    
    To get Sheet ID:
    ```
    https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
    ```
    """)

if __name__ == "__main__":
    main()
