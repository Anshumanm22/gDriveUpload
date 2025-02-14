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

def upload_to_drive(service, file_data, filename, mimetype):
    """Upload a file to Google Drive."""
    try:
        file_metadata = {'name': filename}
        media = MediaIoBaseUpload(
            io.BytesIO(file_data),
            mimetype=mimetype,
            resumable=True
        )
        
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
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

def read_from_sheet(sheets_service, spreadsheet_id, range_name='Sheet1!A1:Z1000'):
    """Read data from a Google Sheet."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
            
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception as e:
        st.error(f"Error reading from sheet: {str(e)}")
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
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi', 'csv', 'xlsx'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
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
                                file.type
                            )
                            if file_id:
                                st.success(f"Successfully uploaded {file.name}")
                                st.markdown(f"[View file](https://drive.google.com/file/d/{file_id}/view)")
    
    with tab2:
        st.header("Google Sheets Manager")
        
        sheet_action = st.radio(
            "Choose action:",
            ["Read sheet", "Update sheet"]
        )
        
        sheet_id = st.text_input("Enter Sheet ID (from sheet URL)")
        
        if sheet_id:
            if sheet_action == "Read sheet":
                if st.button("Read"):
                    with st.spinner("Reading data..."):
                        df = read_from_sheet(sheets_service, sheet_id)
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
    1. Make sure the Google Sheet is shared with the service account email
    2. Choose between File Upload or Sheets Manager
    3. For files: Select and upload files to Drive
    4. For sheets:
       - Read existing sheets using Sheet ID
       - Update existing sheets with new data
    
    The Sheet ID can be found in the sheet's URL:
    ```
    https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
    ```
    """)

if __name__ == "__main__":
    main()
