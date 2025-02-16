import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import pandas as pd
from datetime import datetime
import io

# Set page config
st.set_page_config(page_title="Program Manager Visit Form", layout="wide")

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/drive.file',
          'https://www.googleapis.com/auth/spreadsheets']

# Initialize session state for form sections
if 'current_section' not in st.session_state:
    st.session_state.current_section = 1
if 'form_data' not in st.session_state:
    st.session_state.form_data = {}
if 'total_sections' not in st.session_state:
    st.session_state.total_sections = 5

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

def read_sheet_data(sheets_service, sheet_id):
    """Read data from the Google Sheet."""
    try:
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=sheet_id,
            range='A1:ZZ'
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
            
        df = pd.DataFrame(values[1:], columns=values[0])
        return df
    except Exception as e:
        st.error(f"Error reading sheet: {str(e)}")
        return None

def get_pm_schools(df, pm_name):
    """Get list of schools for a program manager."""
    if 'Your Name' in df.columns and 'School Name' in df.columns:
        schools = df[df['Your Name'] == pm_name]['School Name'].unique()
        return list(schools)
    return []

def get_teachers_for_school(df, school_name):
    """Get list of teachers for a school."""
    # Find all columns that contain "Select a teacher from"
    teacher_columns = [col for col in df.columns if 'Select a teacher from' in col]
    
    all_teachers = []
    for col in teacher_columns:
        if school_name in col:
            teachers = df[col].dropna().unique()
            all_teachers.extend(teachers)
    
    return list(set(all_teachers))

def render_section_1():
    """Basic Details Section"""
    st.subheader("Basic Details")
    
    # Get program managers from the sheet
    df = read_sheet_data(sheets_service, "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw")
    if df is not None:
        program_managers = df['Your Name'].unique()
        
        col1, col2 = st.columns(2)
        with col1:
            pm_name = st.selectbox("Program Manager", options=program_managers)
            visit_date = st.date_input("Date of Visit", value=datetime.now())
        
        with col2:
            if pm_name:
                schools = get_pm_schools(df, pm_name)
                school = st.selectbox("Select School", options=schools)
                visit_time = st.time_input("Time of Visit")
        
        if st.button("Next →"):
            st.session_state.form_data.update({
                'pm_name': pm_name,
                'school': school,
                'visit_date': visit_date,
                'visit_time': visit_time
            })
            st.session_state.current_section += 1
            st.experimental_rerun()

def render_section_2():
    """Teacher Selection Section"""
    st.subheader("Teacher Details")
    
    df = read_sheet_data(sheets_service, "1EthvhhCttQDabz1qJenLqHTDDJ1zFxK-rFZMQH9p4uw")
    if df is not None and 'school' in st.session_state.form_data:
        teachers = get_teachers_for_school(df, st.session_state.form_data['school'])
        
        selected_teacher = st.selectbox("Select Teacher", options=teachers)
        standard = st.text_input("Which standard are you observing?")
        num_students = st.number_input("Number of students", min_value=0)
        subjects = st.text_input("Subjects Taught")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("← Previous"):
                st.session_state.current_section -= 1
                st.experimental_rerun()
        
        with col2:
            if st.button("Next →"):
                st.session_state.form_data.update({
                    'teacher': selected_teacher,
                    'standard': standard,
                    'num_students': num_students,
                    'subjects': subjects
                })
                st.session_state.current_section += 1
                st.experimental_rerun()

def render_section_3():
    """Teacher and Student Actions Section"""
    st.subheader("Classroom Observation")
    
    # Teacher actions
    st.write("Teacher Actions")
    col1, col2 = st.columns(2)
    with col1:
        lesson_plan = st.radio("Has the teacher shared the lesson plan in advance?", 
                             ["Yes", "No", "Sometimes"])
        teacher_movement = st.radio("Is the teacher moving around in the classroom?", 
                                  ["Yes", "No", "Sometimes"])
        hands_on = st.radio("Is the teacher using hands-on activities?", 
                           ["Yes", "No", "Sometimes"])
        encouragement = st.radio("Is the teacher encouraging the child to answer?", 
                               ["Yes", "No", "Sometimes"])
    
    # Student actions
    st.write("Student Actions")
    with col2:
        questions = st.radio("Are children asking questions?", 
                           ["Yes", "No", "Sometimes"])
        explanations = st.radio("Are children explaining their work?", 
                              ["Yes", "No", "Sometimes"])
        involvement = st.radio("Are children involved in the activities?", 
                             ["Yes", "No", "Sometimes"])
        peer_help = st.radio("Are students helping each other to learn/do an activity?", 
                            ["Yes", "No", "Sometimes"])
    
    strengths = st.text_area("Strengths")
    growth_areas = st.text_area("Growth Areas")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.current_section -= 1
            st.experimental_rerun()
    
    with col2:
        if st.button("Next →"):
            st.session_state.form_data.update({
                'lesson_plan': lesson_plan,
                'teacher_movement': teacher_movement,
                'hands_on': hands_on,
                'encouragement': encouragement,
                'questions': questions,
                'explanations': explanations,
                'involvement': involvement,
                'peer_help': peer_help,
                'strengths': strengths,
                'growth_areas': growth_areas
            })
            st.session_state.current_section += 1
            st.experimental_rerun()

def render_section_4():
    """Infrastructure Section"""
    st.subheader("Infrastructure Assessment")
    
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    month = st.selectbox("Select Month", options=months)
    
    subjects = ["Agriculture", "Pottery", "Digital Literacy", "Health & Hygiene", "Music", "Mathematics"]
    subject = st.selectbox("Select Subject", options=subjects)
    
    st.write("Installation Status")
    status_options = ["Not Started (0%)", "In Progress (50%)", "Complete (100%)"]
    
    if subject == "Agriculture":
        col1, col2 = st.columns(2)
        with col1:
            compost = st.selectbox("Compost Pit", options=status_options)
            waste_bins = st.selectbox("Waste Bins", options=status_options)
        with col2:
            tools = st.selectbox("Khurpi/Other Tools", options=status_options)
            fertiliser = st.selectbox("Organic Fertiliser", options=status_options)
    
    elif subject == "Pottery":
        col1, col2 = st.columns(2)
        with col1:
            wheel = st.selectbox("Wheel Machine", options=status_options)
            tools = st.selectbox("Rolling Pins and Shaping Tools", options=status_options)
        with col2:
            clay = st.selectbox("Clay", options=status_options)
    
    maintenance = st.text_area("Maintenance and Action Required")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.current_section -= 1
            st.experimental_rerun()
    
    with col2:
        if st.button("Next →"):
            st.session_state.form_data.update({
                'infra_month': month,
                'subject': subject,
                'maintenance': maintenance
            })
            st.session_state.current_section += 1
            st.experimental_rerun()

def render_section_5():
    """Community Section"""
    st.subheader("Community Engagement")
    
    months = ["January", "February", "March", "April", "May", "June", 
              "July", "August", "September", "October", "November", "December"]
    month = st.selectbox("Select Month", options=months)
    
    col1, col2 = st.columns(2)
    with col1:
        awareness = st.radio("Are parents/community members aware of the program?",
                           ["Yes", "No", "Partial"])
        updates = st.radio("Are updates provided via PTMs, community meetings, or digital platforms?",
                          ["Yes", "No", "Partial"])
        engagement = st.radio("Are parents engaging with their children in program-related activities?",
                            ["Yes", "No", "Partial"])
    
    with col2:
        feedback = st.radio("Are feedback mechanisms in place (meetings, surveys)?",
                          ["Yes", "No", "Partial"])
        resources = st.radio("Are local resources (e.g., tools, expertise) utilised?",
                           ["Yes", "No", "Partial"])
        contributions = st.radio("Have parents contributed resources for projects?",
                               ["Yes", "No", "Partial"])
    
    if contributions == "Yes":
        resources_detail = st.text_area("What resources and name of parent")
    
    final_thoughts = st.text_area("Final thoughts and observations")
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Previous"):
            st.session_state.current_section -= 1
            st.experimental_rerun()
    
    with col2:
        if st.button("Submit"):
            st.session_state.form_data.update({
                'community_month': month,
                'awareness': awareness,
                'updates': updates,
                'engagement': engagement,
                'feedback': feedback,
                'resources': resources,
                'contributions': contributions,
                'final_thoughts': final_thoughts
            })
            # Here you would add code to submit the form data
            st.success("Form submitted successfully!")
            st.session_state.current_section = 1
            st.session_state.form_data = {}
            st.experimental_rerun()

def main():
    st.title("Program Manager Visit Form")
    
    # Initialize Google services
    drive_service, sheets_service = get_google_services()
    
    if not drive_service or not sheets_service:
        st.error("Failed to initialize Google services. Please check your service account configuration.")
        return
    
    # Progress bar
    progress = (st.session_state.current_section - 1) / st.session_state.total_sections
    st.progress(progress)
    
    # Render current section
    if st.session_state.current_section == 1:
        render_section_1()
    elif st.session_state.current_section == 2:
        render_section_2()
    elif st.session_state.current_section == 3:
        render_section_3()
    elif st.session_state.current_section == 4:
        render_section_4()
    elif st.session_state.current_section == 5:
        render_section_5()

if __name__ == "__main__":
    main()
