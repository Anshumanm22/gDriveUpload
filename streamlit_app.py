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

# Hardcoded Google Sheet ID
SHEET_ID = "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw"

@st.cache_resource
def get_google_services():
    """Get Google Drive and Sheets services using service account."""
    try:
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
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)",
            spaces='drive'
        ).execute()
        return True
    except Exception as e:
        try:
            folder = service.files().get(
                fileId=folder_id,
                fields='id, name, mimeType'
            ).execute()
            return True
        except Exception as e:
            st.error(f"Error accessing folder: {str(e)}")
            return False

def upload_to_drive(service, file_data, filename, mimetype, folder_id):
    """Upload a file to a specific Google Drive folder."""
    try:
        if not check_folder_access(service, folder_id):
            st.error(f"Cannot access folder with ID: {folder_id}.")
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
        if not values:
            st.warning("No data to write to sheet.")
            return None

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
        sheet_names = get_sheet_names(sheets_service, spreadsheet_id)
        if not sheet_names:
            st.error("Could not retrieve sheet names from the spreadsheet")
            return None

        if not range_name:
            range_name = f"{sheet_names[0]}!A1:Z1000"

        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_name
        ).execute()
        values = result.get('values', [])

        if not values:
            st.warning("No data found in the sheet")
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
        st.error("Failed to initialize Google services. Check service account.")
        return

    tab1, tab2 = st.tabs(["File Upload", "Data Entry"])

    with tab1:
        st.header("Upload Files to Drive")
        folder_id = st.text_input(
            "Enter Google Drive Folder ID",
            help="Folder ID from the URL."
        )

        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi', 'csv', 'xlsx'],
            accept_multiple_files=True
        )

        if uploaded_files and folder_id:
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
                                st.success(f"Uploaded {file.name}")
                                st.markdown(f"[View file](https://drive.google.com/file/d/{file_id}/view)")

    with tab2:
        st.header("Data Entry Form")

        # --- Load data from Google Sheets ---
        try:
            # Load Schools and Teachers data
            schools_df = read_from_sheet(sheets_service, SHEET_ID, "Schools")
            teachers_df = read_from_sheet(sheets_service, SHEET_ID, "Teachers")

            if schools_df is None or teachers_df is None:
                st.error("Could not load Schools or Teachers data.")
                return

            school_names = schools_df['School Name'].unique().tolist()
            program_managers = schools_df['Program Manager'].unique().tolist()


            # --- Form Section 1: School and Program Manager ---
            with st.form("school_pm_form"):
                st.subheader("School and Program Manager")
                selected_school = st.selectbox("Select School", school_names)
                # Find the Program Manager for the selected school (first match)
                # This assumes there's only one PM per school in the Schools sheet
                selected_pm = schools_df[schools_df['School Name'] == selected_school]['Program Manager'].iloc[0]
                st.write(f"Program Manager: {selected_pm}") # Display the PM - make read only to avoid error if not populated.

                submit_school_pm = st.form_submit_button("Select School and PM")


            # --- Form Section 2: Teacher Training Attendance ---
            if selected_school:
                with st.form("teacher_attendance_form"):
                    st.subheader("Teacher Training Attendance")

                    # Filter teachers based on the selected school
                    filtered_teachers = teachers_df[teachers_df['School Name'] == selected_school]['Teacher Name'].tolist()

                    if not filtered_teachers:
                        st.warning("No teachers found for the selected school.")
                    else:
                        teacher_attendance = {}
                        for teacher in filtered_teachers:
                            teacher_attendance[teacher] = st.checkbox(f"Attended: {teacher}")

                        submit_attendance = st.form_submit_button("Save Attendance")

                        if submit_attendance:
                            # Process and store attendance data
                            attendance_data = []
                            for
