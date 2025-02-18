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
            
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPESdrive   
        )
        
        drive_service = build('drive', 'v3', credentials=credentials)
        
        return drive_service
    except Exception as e:
        st.error(f"Error setting up Google services: {str(e)}")
        return None
        
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
        
        final_thoughts = st.text_area("Final thoughts and observations")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_5"):
                st.session_state.step = 4
                st.rerun()
        with col2:
               # When submitting the form, include photo IDs in the data
            if st.button("Submit", key="submit"):
                # Prepare and submit data including photo IDs
                submission_data = {
                # ... existing data ...
                    'photo_ids': photo_ids if 'photo_ids' in locals() else []
                }
                # Prepare and submit data
                st.success("Form submitted successfully!")
                st.session_state.step = 1
                st.rerun()
 
        st.subheader("Photo Documentation")
        uploaded_photos = st.file_uploader(
            "Upload photos of infrastructure (optional)",
            type=['png', 'jpg', 'jpeg'],
            accept_multiple_files=True
        )
        
        if uploaded_photos:
            st.write("Selected photos:")
            photo_ids = []  # To store uploaded photo IDs
            
            for photo in uploaded_photos:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📷 {photo.name}")
                with col2:
                    if st.button("Upload", key=f"upload_{photo.name}"):
                        with st.spinner(f"Uploading {photo.name}..."):
                            # Use your configured folder ID
                            folder_id = "1qkrf5GEbhl0eRCtH9I2_zGsD8EbPXlH-"  # Replace with actual folder ID
                            photo_id = upload_to_drive(
                                drive_service,
                                photo.getvalue(),
                                photo.name,
                                photo.type,
                                folder_id
                            )
                            if photo_id:
                                photo_ids.append(photo_id)
                                st.success(f"Successfully uploaded {photo.name}")
                                st.markdown(f"[View photo](https://drive.google.com/file/d/{photo_id}/view)")

if __name__ == "__main__":
    main()
