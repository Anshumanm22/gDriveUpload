import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
from datetime import datetime
import io

# Previous constants remain the same
FOLDER_ID = "1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-"
SHEET_ID = "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw"
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/spreadsheets']

# Initialize session state for form sections
if 'current_section' not in st.session_state:
    st.session_state.current_section = 1
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}

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
    

def read_school_data(sheets_service):
    """Read school and teacher mapping data."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range='Schools!A1:Z1000'  # Adjust range name as needed
        ).execute()
        
        values = result.get('values', [])
        if not values:
            st.warning("No school data found")
            return pd.DataFrame()
            
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception as e:
        st.error(f"Error reading school data: {str(e)}")
        return None

def render_basic_details_section():
    """Section 1: Basic Details"""
    st.subheader("Basic Details")
    
    col1, col2 = st.columns(2)
    with col1:
        pm_name = st.text_input("Program Manager Name")
        visit_date = st.date_input("Date of Visit", datetime.now())
    
    with col2:
        school_data = read_school_data(st.session_state.sheets_service)
        if school_data is not None:
            pm_schools = school_data[school_data['Program Manager'] == pm_name]['School Name'].unique()
            school = st.selectbox("Select School", options=pm_schools if len(pm_schools) > 0 else ['No schools found'])
    
    if st.button("Next →") and pm_name and school:
        st.session_state.form_data.update({
            'pm_name': pm_name,
            'visit_date': visit_date,
            'school': school
        })
        st.session_state.current_section = 2
        st.experimental_rerun()

def render_teacher_selection_section():
    """Section 2: Teacher Selection"""
    st.subheader("Teacher Selection")
    
    school_data = read_school_data(st.session_state.sheets_service)
    if school_data is not None:
        school_teachers = school_data[
            (school_data['School Name'] == st.session_state.form_data['school']) &
            (school_data['Program Manager'] == st.session_state.form_data['pm_name'])
        ]['Teacher Name'].unique()
        
        selected_teacher = st.selectbox("Select Teacher", options=school_teachers)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Back"):
                st.session_state.current_section = 1
                st.experimental_rerun()
        
        with col2:
            if st.button("Next →"):
                st.session_state.form_data['teacher'] = selected_teacher
                st.session_state.current_section = 3
                st.experimental_rerun()

def render_observation_section():
    """Section 3: Teacher and Student Actions"""
    st.subheader("Daily Observation")
    
    # Teacher actions
    st.write("##### Teacher Actions")
    teacher_actions = {
        'lesson_plan': st.radio("Has the teacher shared the lesson plan in advance?", ['Yes', 'No', 'Sometimes']),
        'movement': st.radio("Is the teacher moving around in the classroom?", ['Yes', 'No', 'Sometimes']),
        'activities': st.radio("Is the teacher using hands-on activities?", ['Yes', 'No', 'Sometimes']),
        'encouragement': st.radio("Is the teacher encouraging the child to answer?", ['Yes', 'No', 'Sometimes'])
    }
    
    # Student actions
    st.write("##### Student Actions")
    student_actions = {
        'questions': st.radio("Are children asking questions?", ['Yes', 'No', 'Sometimes']),
        'explanation': st.radio("Are children explaining their work?", ['Yes', 'No', 'Sometimes']),
        'involvement': st.radio("Are children involved in the activities?", ['Yes', 'No', 'Sometimes']),
        'peer_learning': st.radio("Are students helping each other to learn/do an activity?", ['Yes', 'No', 'Sometimes'])
    }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state.current_section = 2
            st.experimental_rerun()
    
    with col2:
        if st.button("Next →"):
            st.session_state.form_data.update({
                'teacher_actions': teacher_actions,
                'student_actions': student_actions
            })
            st.session_state.current_section = 4
            st.experimental_rerun()

def render_infrastructure_section():
    """Section 4: Infrastructure (Monthly)"""
    st.subheader("Infrastructure Assessment (Monthly)")
    
    subjects = ['Math', 'Science', 'English', 'Social Studies']
    infrastructure_data = {}
    
    for subject in subjects:
        st.write(f"##### {subject}")
        infrastructure_data[subject] = {
            'materials': st.radio(f"Are learning materials available for {subject}?", ['Yes', 'No', 'Partial']),
            'condition': st.radio(f"Condition of {subject} materials", ['Good', 'Fair', 'Poor']),
            'storage': st.radio(f"Proper storage for {subject} materials?", ['Yes', 'No'])
        }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state.current_section = 3
            st.experimental_rerun()
    
    with col2:
        if st.button("Next →"):
            st.session_state.form_data['infrastructure'] = infrastructure_data
            st.session_state.current_section = 5
            st.experimental_rerun()

def render_community_section():
    """Section 5: Community Engagement (Monthly)"""
    st.subheader("Community Engagement (Monthly)")
    
    community_data = {
        'parent_meetings': st.number_input("Number of parent meetings held this month", min_value=0),
        'attendance': st.slider("Average parent attendance percentage", 0, 100),
        'involvement': st.radio("Level of community involvement in school activities", 
                              ['High', 'Medium', 'Low']),
        'feedback': st.text_area("Community feedback and suggestions")
    }
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Back"):
            st.session_state.current_section = 4
            st.experimental_rerun()
    
    with col2:
        if st.button("Submit Form"):
            st.session_state.form_data['community'] = community_data
            submit_form_data()

def submit_form_data():
    """Submit the complete form data to Google Sheets"""
    try:
        # Flatten the form data into a row format
        flat_data = flatten_form_data(st.session_state.form_data)
        
        # Create DataFrame with single row
        df = pd.DataFrame([flat_data])
        
        # Write to sheet
        result = write_to_sheet(st.session_state.sheets_service, df)
        
        if result:
            st.success("Form submitted successfully!")
            # Reset form
            st.session_state.current_section = 1
            st.session_state.form_data = {}
            st.experimental_rerun()
    except Exception as e:
        st.error(f"Error submitting form: {str(e)}")

def flatten_form_data(form_data):
    """Convert nested form data into flat format for sheet submission"""
    flat_data = {
        'Program Manager': form_data['pm_name'],
        'Visit Date': form_data['visit_date'].strftime('%Y-%m-%d'),
        'School': form_data['school'],
        'Teacher': form_data['teacher']
    }
    
    # Add teacher actions
    for key, value in form_data['teacher_actions'].items():
        flat_data[f'Teacher_{key}'] = value
    
    # Add student actions
    for key, value in form_data['student_actions'].items():
        flat_data[f'Student_{key}'] = value
    
    # Add infrastructure data
    for subject, data in form_data['infrastructure'].items():
        for key, value in data.items():
            flat_data[f'Infrastructure_{subject}_{key}'] = value
    
    # Add community data
    for key, value in form_data['community'].items():
        flat_data[f'Community_{key}'] = value
    
    return flat_data

def render_form():
    """Render the appropriate form section"""
    if st.session_state.current_section == 1:
        render_basic_details_section()
    elif st.session_state.current_section == 2:
        render_teacher_selection_section()
    elif st.session_state.current_section == 3:
        render_observation_section()
    elif st.session_state.current_section == 4:
        render_infrastructure_section()
    elif st.session_state.current_section == 5:
        render_community_section()

def main():
    st.title("School Observation System")
    
    # Initialize Google services
    drive_service, sheets_service = get_google_services()
    
    if not drive_service or not sheets_service:
        st.error("Failed to initialize Google services")
        return
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Observation Form", "File Upload", "Data View"])
    
    with tab1:
        st.header("School Observation Form")
        # Form implementation here
    
    with tab2:
        st.header("File Upload")
        uploaded_files = st.file_uploader(
            "Choose files to upload",
            type=['png', 'jpg', 'jpeg', 'mp4', 'mov', 'avi', 'csv', 'xlsx'],
            accept_multiple_files=True
        )
        
        if uploaded_files:
            for file in uploaded_files:
                if st.button("Upload", key=f"upload_{file.name}"):
                    try:
                        file_id = upload_to_drive(
                            drive_service,
                            file.getvalue(),
                            file.name,
                            file.type
                        )
                        if file_id:
                            st.success(f"Successfully uploaded {file.name}")
                    except Exception as e:
                        st.error(f"Error uploading {file.name}: {str(e)}")
    
    with tab3:
        st.header("View Data")
        try:
            # Get available sheets
            sheet_names = get_sheet_names(sheets_service)
            
            if sheet_names:
                # Let user select a sheet
                selected_sheet = st.selectbox(
                    "Select sheet to view",
                    options=sheet_names
                )
                
                if st.button("View Data"):
                    # Read and display data
                    df = read_from_sheet(sheets_service, f"{selected_sheet}!A1:Z1000")
                    if df is not None:
                        st.dataframe(df)
        except Exception as e:
            st.error(f"Error accessing sheets: {str(e)}")

if __name__ == "__main__":
    main()
