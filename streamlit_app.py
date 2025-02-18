import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime
from googleapiclient.http import MediaIoBaseUpload
import io

# Set page config
st.set_page_config(page_title="Program Manager Checklist", layout="wide")

# Hardcoded IDs
SHEET_ID = "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw"
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
]

def get_google_service():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account not found in secrets")
            return None
            
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        return build('sheets', 'v4', credentials=credentials)
    except Exception as e:
        st.error(f"Error setting up Google service: {str(e)}")
        return None

SCOPESdrive = [
    'https://www.googleapis.com/auth/drive.file'
]

#for google_drive_service
def get_google_drive_service():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account not found in secrets")
            return None
            
        # Updated scopes to include all necessary Drive permissions
        SCOPES = [
            'https://www.googleapis.com/auth/drive',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.metadata'
        ]
        
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        
        # Test the service by trying to get the root folder
        try:
            root_folder = drive_service.files().get(
                fileId='1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-',
                fields='id, name, mimeType',
                supportsAllDrives=True
            ).execute()
            st.success(f"Successfully connected to Drive and accessed root folder: {root_folder.get('name')}")
        except Exception as folder_error:
            st.error(f"Connected to Drive but couldn't access root folder: {str(folder_error)}")
        
        return drive_service
    except Exception as e:
        st.error(f"Error setting up Google Drive service: {str(e)}")
        return None

def test_upload_permissions(service, folder_id):
    """Test function to verify upload permissions"""
    try:
        # Create a small test file
        file_metadata = {
            'name': 'test.txt',
            'parents': [folder_id]
        }
        
        # Create a small text file in memory
        from io import BytesIO
        file_content = BytesIO(b'Test file content')
        
        media = MediaIoBaseUpload(
            file_content,
            mimetype='text/plain',
            resumable=True
        )
        
        # Try to upload
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id',
            supportsAllDrives=True
        ).execute()
        
        st.success(f"Successfully created test file with ID: {file.get('id')}")
        
        # Clean up by deleting the test file
        service.files().delete(fileId=file.get('id')).execute()
        st.info("Test file deleted successfully")
        
        return True
    except Exception as e:
        st.error(f"Error testing upload permissions: {str(e)}")
        return False
        
def read_from_sheet(service, range_name):
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=range_name
        ).execute()
        return pd.DataFrame(result.get('values', [])[1:], columns=result.get('values', [[]])[0])
    except Exception as e:
        st.error(f"Error reading from sheet: {str(e)}")
        return None

def check_folder_access(service, folder_id):
    """Debug function to check folder access and permissions"""
    try:
        # First try to get the folder metadata
        st.info(f"Checking folder metadata for ID: {folder_id}")
        folder = service.files().get(
            fileId=folder_id,
            fields='id, name, mimeType'
        ).execute()
        st.success(f"✓ Found folder: {folder.get('name')} (Type: {folder.get('mimeType')})")
        
        # Try to list files in the folder
        st.info("Checking ability to list files in folder...")
        results = service.files().list(
            q=f"'{folder_id}' in parents",
            fields="files(id, name)",
            spaces='drive',
            supportsAllDrives=True
        ).execute()
        st.success(f"✓ Successfully listed files. Found {len(results.get('files', []))} files.")
        
        return True
        
    except Exception as e:
        st.error(f"Error accessing folder: {str(e)}")
        if "404" in str(e):
            st.error(f"""Folder not found. Please verify:
            1. Folder ID is correct: {folder_id}
            2. No extra characters in the ID
            3. The ID is copied from the URL after 'folders/'""")
        elif "403" in str(e):
            st.error("""Permission denied. Please verify:
            1. Service account has been added to the folder
            2. Service account has at least 'Editor' access""")
        return False

def create_folder_structure(service, school_name, visit_date):
    """Create folder structure with debug logging"""
    try:
        ROOT_FOLDER_ID = "1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-"
        
        # Check root folder access first
        st.subheader("Checking folder access...")
        if not check_folder_access(service, ROOT_FOLDER_ID):
            return None
            
        # If we get here, we have access. Continue with folder creation...
        st.info("Creating folder structure...")
        
        # Create school folder
        school_query = f"name='{school_name}' and mimeType='application/vnd.google-apps.folder' and '{ROOT_FOLDER_ID}' in parents"
        school_results = service.files().list(
            q=school_query,
            fields='files(id, name)',
            supportsAllDrives=True
        ).execute()
        
        if school_results.get('files'):
            school_folder_id = school_results['files'][0]['id']
            st.success(f"✓ Found existing school folder: {school_name}")
        else:
            school_folder = service.files().create(
                body={
                    'name': school_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [ROOT_FOLDER_ID]
                },
                fields='id',
                supportsAllDrives=True
            ).execute()
            school_folder_id = school_folder['id']
            st.success(f"✓ Created new school folder: {school_name}")
        
        # Create year folder
        year = visit_date.strftime("%Y")
        year_query = f"name='{year}' and mimeType='application/vnd.google-apps.folder' and '{school_folder_id}' in parents"
        year_results = service.files().list(
            q=year_query,
            fields='files(id, name)',
            supportsAllDrives=True
        ).execute()
        
        if year_results.get('files'):
            year_folder_id = year_results['files'][0]['id']
            st.success(f"✓ Found existing year folder: {year}")
        else:
            year_folder = service.files().create(
                body={
                    'name': year,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [school_folder_id]
                },
                fields='id',
                supportsAllDrives=True
            ).execute()
            year_folder_id = year_folder['id']
            st.success(f"✓ Created new year folder: {year}")
        
        # Create month folder
        month = visit_date.strftime("%B")
        month_query = f"name='{month}' and mimeType='application/vnd.google-apps.folder' and '{year_folder_id}' in parents"
        month_results = service.files().list(
            q=month_query,
            fields='files(id, name)',
            supportsAllDrives=True
        ).execute()
        
        if month_results.get('files'):
            month_folder_id = month_results['files'][0]['id']
            st.success(f"✓ Found existing month folder: {month}")
        else:
            month_folder = service.files().create(
                body={
                    'name': month,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [year_folder_id]
                },
                fields='id',
                supportsAllDrives=True
            ).execute()
            month_folder_id = month_folder['id']
            st.success(f"✓ Created new month folder: {month}")
        
        # Create visit date folder
        visit_folder_name = visit_date.strftime("%Y-%m-%d")
        visit_query = f"name='{visit_folder_name}' and mimeType='application/vnd.google-apps.folder' and '{month_folder_id}' in parents"
        visit_results = service.files().list(
            q=visit_query,
            fields='files(id, name)',
            supportsAllDrives=True
        ).execute()
        
        if visit_results.get('files'):
            visit_folder_id = visit_results['files'][0]['id']
            st.success(f"✓ Found existing visit folder: {visit_folder_name}")
        else:
            visit_folder = service.files().create(
                body={
                    'name': visit_folder_name,
                    'mimeType': 'application/vnd.google-apps.folder',
                    'parents': [month_folder_id]
                },
                fields='id',
                supportsAllDrives=True
            ).execute()
            visit_folder_id = visit_folder['id']
            st.success(f"✓ Created new visit folder: {visit_folder_name}")
        
        return visit_folder_id
            
    except Exception as e:
        st.error(f"Error in folder structure creation: {str(e)}")
        return None

def setup_folder_structure(service, school_name, visit_date):
    """Create folder structure: Root -> School -> Year -> Month -> Visit Date"""
    try:
        # Root folder ID (replace with your actual root folder ID)
        ROOT_FOLDER_ID = "1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-"
        
        # Create/get school folder
        school_folder_id = create_or_get_folder(service, school_name, ROOT_FOLDER_ID)
        if not school_folder_id:
            return None
            
        # Create/get year folder
        year = visit_date.strftime("%Y")
        year_folder_id = create_or_get_folder(service, year, school_folder_id)
        if not year_folder_id:
            return None
            
        # Create/get month folder
        month = visit_date.strftime("%B")  # Full month name
        month_folder_id = create_or_get_folder(service, month, year_folder_id)
        if not month_folder_id:
            return None
            
        # Create/get visit date folder
        visit_folder_name = visit_date.strftime("%Y-%m-%d")
        visit_folder_id = create_or_get_folder(service, visit_folder_name, month_folder_id)
        
        return visit_folder_id
        
    except Exception as e:
        st.error(f"Error setting up folder structure: {str(e)}")
        return None


def upload_to_drive(service, file_data, filename, mimetype, folder_id):
    try:
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

def main():
    st.title("Program Manager Checklist")
    
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    service = get_google_service()
    if not service:
        return
    
    drive_service = get_google_drive_service()
    if not service:
        return
    
    schools_df = read_from_sheet(service, 'Schools!A:D')
    if schools_df is None:
        return
    
    st.sidebar.progress(st.session_state.step / 5)
    st.sidebar.markdown(f"Step {st.session_state.step} of 5")
    
    # Basic Information
    if st.session_state.step == 1:
        st.header("Basic Information")
        
        col1, col2 = st.columns(2)
        with col1:
            # Get unique program managers
            program_managers = sorted(schools_df['Program Manager'].unique())
            selected_pm = st.selectbox("Program Manager", options=program_managers)
            
            # Filter schools based on selected program manager
            pm_schools = sorted(schools_df[schools_df['Program Manager'] == selected_pm]['School Name'].unique())
            selected_school = st.selectbox("School Name", options=pm_schools)
            
            date = st.date_input("Date of Visit")
        
        with col2:
            time = st.time_input("Time of visit")
            standard = st.selectbox("Which standard are you observing?", 
                                  options=["1", "2", "3", "4", "5"])
            num_students = st.number_input("Number of students", min_value=0)
            subjects = st.multiselect("Subjects Taught", 
                                    ["English", "Math", "Science", "Hindi", "Music", "Agriculture"])
        
        if st.button("Next", key="next_1"):
            if selected_pm and selected_school and date and time and standard and subjects:
                st.session_state.update({
                    'program_manager': selected_pm,
                    'school': selected_school,
                    'date': date,
                    'time': time,
                    'standard': standard,
                    'num_students': num_students,
                    'subjects': subjects
                })
                st.session_state.step = 2
                st.rerun()
            else:
                st.warning("Please fill all required fields")
    
    # Lesson Planning and Teaching
    elif st.session_state.step == 2:
        st.header("Lesson Planning and Teaching")
        
        st.subheader("Lesson Planning")
        lesson_plan = {}
        lesson_plan['shared_advance'] = st.radio(
            "Has the teacher shared the lesson plan in advance?",
            ["Yes", "No", "Sometimes"]
        )
        lesson_plan['clear_objectives'] = st.radio(
            "Does the lesson plan include clear learning objectives?",
            ["Yes", "No", "Partially"]
        )
        lesson_plan['aligned_activities'] = st.radio(
            "Are the activities aligned with the learning objectives?",
            ["Yes", "No", "Partially"]
        )
        
        st.subheader("Teaching Methodology")
        teaching = {}
        teaching['clear_instructions'] = st.radio(
            "Are instructions clear and easy to follow?",
            ["Yes", "No", "Sometimes"]
        )
        teaching['engaging_tone'] = st.radio(
            "Is the teacher's energy level and tone engaging?",
            ["Yes", "No", "Sometimes"]
        )
        teaching['classroom_movement'] = st.radio(
            "Is the teacher moving around in the classroom?",
            ["Yes", "No", "Sometimes"]
        )
        teaching['hands_on'] = st.radio(
            "Is the teacher using hands-on activities?",
            ["Yes", "No", "Sometimes"]
        )
        teaching['outdoor_spaces'] = st.radio(
            "Is the teacher using outdoor spaces to teach?",
            ["Yes", "No", "Sometimes"]
        )
        teaching['real_life_examples'] = st.radio(
            "Is this teacher able to use real-life examples to integrate core-academics with skill subjects?",
            ["Yes", "No", "Sometimes"]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_2"):
                st.session_state.step = 1
                st.rerun()
        with col2:
            if st.button("Next", key="next_2"):
                st.session_state.update({
                    'lesson_plan': lesson_plan,
                    'teaching': teaching
                })
                st.session_state.step = 3
                st.rerun()
    
    # Student Engagement
    elif st.session_state.step == 3:
        st.header("Student Engagement")
        
        student_engagement = {}
        student_engagement['asking_questions'] = st.radio(
            "Are children asking questions?",
            ["Yes", "No", "Sometimes"]
        )
        student_engagement['explaining_work'] = st.radio(
            "Are children explaining their work?",
            ["Yes", "No", "Sometimes"]
        )
        student_engagement['activity_involvement'] = st.radio(
            "Are children involved in the activities?",
            ["Yes", "No", "Sometimes"]
        )
        student_engagement['peer_help'] = st.radio(
            "Are students helping each other to learn/do an activity?",
            ["Yes", "No", "Sometimes"]
        )
        
        st.subheader("Observations")
        strengths = st.text_area("Strengths")
        growth_areas = st.text_area("Growth Areas")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_3"):
                st.session_state.step = 2
                st.rerun()
        with col2:
            if st.button("Next", key="next_3"):
                st.session_state.update({
                    'student_engagement': student_engagement,
                    'strengths': strengths,
                    'growth_areas': growth_areas
                })
                st.session_state.step = 4
                st.rerun()
    
    # Community Engagement
    elif st.session_state.step == 4:
        st.header("Community Engagement")
        
        month = st.selectbox("Select Month [CPM]", 
                           ["January", "February", "March", "April", "May", "June",
                            "July", "August", "September", "October", "November", "December"])
        
        community = {}
        community['program_awareness'] = st.radio(
            "Are parents/community members aware of the program?",
            ["Yes", "No", "Partially"]
        )
        community['updates_provided'] = st.radio(
            "Are updates provided via PTMs, community meetings, or digital platforms?",
            ["Yes", "No", "Sometimes"]
        )
        community['parent_engagement'] = st.radio(
            "Are parents engaging with their children in program-related activities?",
            ["Yes", "No", "Sometimes"]
        )
        community['feedback_mechanism'] = st.radio(
            "Are feedback mechanisms in place (meetings, surveys)?",
            ["Yes", "No", "In Progress"]
        )
        community['local_resources'] = st.radio(
            "Are local resources (e.g., tools, expertise) utilised?",
            ["Yes", "No", "Sometimes"]
        )
        
        parent_contribution = st.radio(
            "Have parents contributed resources for projects?",
            ["Yes", "No"]
        )
        
        if parent_contribution == "Yes":
            resource_details = st.text_area("What resource and name of parent")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_4"):
                st.session_state.step = 3
                st.rerun()
        with col2:
            if st.button("Next", key="next_4"):
                data = {
                    'month': month,
                    'community': community,
                    'parent_contribution': parent_contribution
                }
                if parent_contribution == "Yes":
                    data['resource_details'] = resource_details
                st.session_state.update(data)
                st.session_state.step = 5
                st.rerun()
    
    # Infrastructure Assessment
    elif st.session_state.step == 5:
        st.header("Infrastructure Assessment")
        
        subject = st.selectbox("Select Subject", 
                             ["Agriculture", "Pottery", "Computer", "Health & Hygiene", 
                              "Music", "Textile"])
        
        if subject == "Agriculture":
            st.subheader("Agriculture Infrastructure")
            ag_status = {
                'compost_pit': st.selectbox("Compost Pit [Installation Status]", 
                                          ["Installed", "Not Installed", "In Progress"]),
                'waste_bins': st.selectbox("Waste Bins [Installation Status]",
                                         ["Installed", "Not Installed", "In Progress"]),
                'tools': st.selectbox("Khurpi/Other Tools [Installation Status]",
                                    ["Installed", "Not Installed", "In Progress"]),
                'fertiliser': st.selectbox("Organic Fertiliser [Installation Status]",
                                         ["Available", "Not Available", "Needed"])
            }
            
            maintenance = {}
            for item in ['Compost Pit', 'Waste Bins', 'Khurpi/Other Tools', 'Organic Fertiliser']:
                needs_maintenance = st.checkbox(f"Maintenance Required for {item}")
                if needs_maintenance:
                    maintenance[item] = st.text_input(f"Specify maintenance needed for {item}")
        
        # Similar sections for other subjects...
        
        # In the main function, where you handle photo uploads:
        st.subheader("Photo Documentation")
        uploaded_photos = st.file_uploader(
        "Upload photos of infrastructure (optional)",
        type=['png', 'jpg', 'jpeg'],
        accept_multiple_files=True,
        key="infra_photos"
    )
    
        photo_ids = []
        # In your main function where you handle uploads:
if uploaded_photos:
    drive_service = get_google_drive_service()
    if drive_service:
        # Test upload permissions first
        if test_upload_permissions(drive_service, "1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-"):
            st.success("Upload permissions verified successfully")
            
            # Get the target folder for this visit
            target_folder_id = create_folder_structure(
                drive_service,
                st.session_state.school,
                st.session_state.date
            )
            
            if target_folder_id:
                st.write("Selected photos:")
                for photo in uploaded_photos:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📷 {photo.name}")
                    with col2:
                        if st.button("Upload", key=f"upload_{photo.name}"):
                            with st.spinner(f"Uploading {photo.name}..."):
                                timestamp = datetime.now().strftime("%H%M%S")
                                new_filename = f"{timestamp}_{photo.name}"
                                
                                photo_id = upload_to_drive(
                                    drive_service,
                                    photo.getvalue(),
                                    new_filename,
                                    photo.type,
                                    target_folder_id
                                )
                                if photo_id:
                                    st.success(f"Successfully uploaded {photo.name}")
                                    st.markdown(f"[View photo](https://drive.google.com/file/d/{photo_id}/view)")
            else:
                st.error("Could not create folder structure for photos")
        else:
            st.error("Failed to verify upload permissions")
    else:
        st.error("Could not initialize Google Drive service")
                
        final_thoughts = st.text_area("Final thoughts and observations")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_5"):
                st.session_state.step = 4
                st.rerun()
        with col2:
            if st.button("Submit", key="submit"):
                submission_data = {
                    'subject': subject,
                    'ag_status': ag_status if subject == "Agriculture" else None,
                    'maintenance': maintenance if subject == "Agriculture" else None,
                    'final_thoughts': final_thoughts,
                    'photo_ids': photo_ids  # Now photo_ids is always defined
                }
                # Add code here to save submission_data to your Google Sheet
                st.success("Form submitted successfully!")
                st.session_state.step = 1
                st.rerun()

if __name__ == "__main__":
    main()
