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

def get_google_services():
    # Previous implementation remains the same
    [... previous code ...]

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
    
    # Store services in session state
    st.session_state.drive_service = drive_service
    st.session_state.sheets_service = sheets_service
    
    # Create tabs
    tab1, tab2, tab3 = st.tabs(["Observation Form", "File Upload", "Data View"])
    
    with tab1:
        render_form()
    
    with tab2:
        # Previous file upload code
        [... previous upload code ...]
    
    with tab3:
        # Previous sheet view code
        [... previous sheet view code ...]

if __name__ == "__main__":
    main()
