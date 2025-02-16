import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd
from datetime import datetime

# Set page config
st.set_page_config(page_title="School Observation Form", layout="wide")

# Hardcoded IDs
SHEET_ID = "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw"

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def get_google_services():
    """Get Google Drive and Sheets services using service account."""
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("gcp_service_account not found in secrets")
            return None, None
            
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

def read_from_sheet(sheets_service, range_name):
    """Read data from the specified Google Sheet range."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
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

def write_to_sheet(sheets_service, data, range_name):
    """Write data to the specified Google Sheet."""
    try:
        values = data.values.tolist()
        headers = data.columns.tolist()
        values.insert(0, headers)
        
        body = {
            'values': values
        }
        
        result = sheets_service.spreadsheets().values().update(
            spreadsheetId=SHEET_ID,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        
        return result
    except Exception as e:
        st.error(f"Error writing to sheet: {str(e)}")
        return None

def create_observation_form():
    st.title("School Observation Form")
    
    # Initialize session state for multi-step form
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    # Get Google services
    drive_service, sheets_service = get_google_services()
    if not sheets_service:
        st.error("Failed to initialize Google services")
        return
    
    # Load data from different sheets
    schools_df = read_from_sheet(sheets_service, 'Schools!A:D')
    teachers_df = read_from_sheet(sheets_service, 'Teachers!A:D')
    
    if schools_df is None or teachers_df is None:
        return
    
    # Sidebar progress
    st.sidebar.markdown("### Form Progress")
    st.sidebar.progress(st.session_state.step / 5)
    
    # Section 1: Basic Details
    if st.session_state.step == 1:
        st.subheader("Basic Details")
        
        program_managers = schools_df['Program Manager'].unique()
        selected_pm = st.selectbox("Select Program Manager", program_managers)
        
        pm_schools = schools_df[
            schools_df['Program Manager'] == selected_pm
        ]['School Name'].unique()
        selected_school = st.selectbox("Select School", pm_schools)
        
        visit_date = st.date_input("Date of Visit")
        
        if st.button("Next"):
            st.session_state.step = 2
            st.session_state.selected_pm = selected_pm
            st.session_state.selected_school = selected_school
            st.session_state.visit_date = visit_date
            st.experimental_rerun()
    
    # Section 2: Teacher Selection
    elif st.session_state.step == 2:
        st.subheader("Teacher Details")
        
        school_teachers_df = teachers_df[
            teachers_df['School Name'] == st.session_state.selected_school
        ]
        
        col1, col2 = st.columns(2)
        with col1:
            if not school_teachers_df.empty:
                selected_teacher = st.selectbox(
                    "Select Teacher",
                    school_teachers_df['Teacher Name'].tolist()
                )
                if selected_teacher:
                    teacher_info = school_teachers_df[
                        school_teachers_df['Teacher Name'] == selected_teacher
                    ].iloc[0]
                    st.info(f"Training Status: {'Trained' if teacher_info['Is Trained'] else 'Not Trained'}")
        
        with col2:
            add_new_teacher = st.checkbox("Add New Teacher")
            if add_new_teacher:
                new_teacher_name = st.text_input("New Teacher Name")
                new_teacher_trained = st.checkbox("Teacher attended training")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous"):
                st.session_state.step = 1
                st.experimental_rerun()
        with col2:
            if st.button("Next"):
                st.session_state.step = 3
                st.experimental_rerun()
    
    # Section 3: Daily Visit Observations
    elif st.session_state.step == 3:
        st.subheader("Daily Visit Observations")
        
        st.markdown("#### Teacher Actions")
        teacher_actions = {
            'lesson_plan': st.checkbox("Has the teacher shared the lesson plan in advance?"),
            'moving_around': st.checkbox("Is the teacher moving around in the classroom?"),
            'hands_on': st.checkbox("Is the teacher using hands-on activities?"),
            'encouragement': st.checkbox("Is the teacher encouraging children to answer?")
        }
        
        st.markdown("#### Student Actions")
        student_actions = {
            'questions': st.checkbox("Are children asking questions?"),
            'explaining': st.checkbox("Are children explaining their work?"),
            'involvement': st.checkbox("Are children involved in the activities?"),
            'peer_help': st.checkbox("Are students helping each other to learn/do an activity?")
        }
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous"):
                st.session_state.step = 2
                st.experimental_rerun()
        with col2:
            if st.button("Next"):
                st.session_state.step = 4
                st.experimental_rerun()
    
    # Section 4: Infrastructure
    elif st.session_state.step == 4:
        st.subheader("Infrastructure Assessment (Monthly)")
        
        st.markdown("#### Classroom Environment")
        infrastructure = {}
        
        cols = st.columns(2)
        with cols[0]:
            infrastructure['classroom_condition'] = st.selectbox(
                "Classroom Condition",
                ["Good", "Needs Minor Repairs", "Needs Major Repairs"]
            )
            infrastructure['ventilation'] = st.selectbox(
                "Ventilation",
                ["Good", "Adequate", "Poor"]
            )
        
        with cols[1]:
            infrastructure['seating'] = st.selectbox(
                "Seating Arrangement",
                ["Individual Desks", "Shared Desks", "Floor Seating"]
            )
            infrastructure['blackboard'] = st.selectbox(
                "Blackboard Condition",
                ["Good", "Usable", "Needs Replacement"]
            )
        
        st.markdown("#### Teaching Resources")
        infrastructure['resources'] = st.multiselect(
            "Available Resources",
            ["Textbooks", "Teaching Aids", "Charts", "Sports Equipment", "Library Books"]
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous"):
                st.session_state.step = 3
                st.experimental_rerun()
        with col2:
            if st.button("Next"):
                st.session_state.step = 5
                st.experimental_rerun()
    
    # Section 5: Community
    elif st.session_state.step == 5:
        st.subheader("Community Engagement (Monthly)")
        
        community = {}
        
        st.markdown("#### Parent Engagement")
        community['parent_meetings'] = st.number_input(
            "Number of parent meetings held this month",
            min_value=0,
            max_value=31
        )
        
        community['parent_attendance'] = st.slider(
            "Average parent attendance percentage",
            0, 100, 50
        )
        
        st.markdown("#### Community Activities")
        community['activities'] = st.multiselect(
            "Community activities conducted this month",
            ["Parent-Teacher Meeting", "Community Event", "Educational Workshop", 
             "Cultural Program", "Sports Day", "Other"]
        )
        
        if community['activities'] and 'Other' in community['activities']:
            community['other_activity'] = st.text_input("Please specify other activity")
        
        st.markdown("#### Local Partnerships")
        community['partnerships'] = st.text_area(
            "Description of any local partnerships or initiatives"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous"):
                st.session_state.step = 4
                st.experimental_rerun()
        with col2:
            if st.button("Submit"):
                # Here you would add code to save all the collected data
                # to the Observations sheet
                st.success("Form submitted successfully!")
                st.session_state.step = 1
                st.experimental_rerun()

def main():
    create_observation_form()

if __name__ == "__main__":
    main()
