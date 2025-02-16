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
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def get_google_service():
    """Get Google Sheets service using service account."""
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

def read_from_sheet(service, range_name):
    """Read data from the specified Google Sheet range."""
    try:
        result = service.spreadsheets().values().get(
            spreadsheetId=SHEET_ID,
            range=range_name
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return pd.DataFrame()
        
        return pd.DataFrame(values[1:], columns=values[0])
    except Exception as e:
        st.error(f"Error reading from sheet: {str(e)}")
        return None

def main():
    st.title("School Observation Form")
    
    # Initialize step in session state
    if 'step' not in st.session_state:
        st.session_state.step = 1
    
    # Get sheets service
    service = get_google_service()
    if not service:
        return
    
    # Read base data
    try:
        schools_df = read_from_sheet(service, 'Schools!A:D')
        if schools_df is None or schools_df.empty:
            st.error("Unable to load schools data")
            return
            
        teachers_df = read_from_sheet(service, 'Teachers!A:D')
        if teachers_df is None:
            st.error("Unable to load teachers data")
            return
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        return
    
    # Progress indicator
    st.sidebar.progress(st.session_state.step / 5)
    st.sidebar.markdown(f"Step {st.session_state.step} of 5")
    
    # Basic Details
    if st.session_state.step == 1:
        st.header("Basic Details")
        
        col1, col2 = st.columns(2)
        with col1:
            pm = st.selectbox(
                "Program Manager",
                options=sorted(schools_df['Program Manager'].unique().tolist())
            )
            
            if pm:
                schools = schools_df[schools_df['Program Manager'] == pm]['School Name'].unique()
                school = st.selectbox("School", options=sorted(schools))
        
        with col2:
            date = st.date_input("Visit Date")
        
        if st.button("Next", key="next_1"):
            if pm and school and date:
                st.session_state.pm = pm
                st.session_state.school = school
                st.session_state.date = date
                st.session_state.step = 2
                st.rerun()
            else:
                st.warning("Please fill all fields")
    
    # Teacher Selection
    elif st.session_state.step == 2:
        st.header("Teacher Selection")
        
        school_teachers = teachers_df[
            teachers_df['School Name'] == st.session_state.school
        ]
        
        teacher = st.selectbox(
            "Select Teacher",
            options=[""] + sorted(school_teachers['Teacher Name'].tolist())
        )
        
        if teacher:
            teacher_data = school_teachers[
                school_teachers['Teacher Name'] == teacher
            ].iloc[0]
            st.info(f"Training Status: {'Trained' if teacher_data['Is Trained'] else 'Not Trained'}")
        
        add_teacher = st.checkbox("Add New Teacher")
        if add_teacher:
            new_name = st.text_input("Teacher Name")
            is_trained = st.checkbox("Has completed training")
            
            if st.button("Add Teacher"):
                # Add logic to save new teacher
                pass
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_2"):
                st.session_state.step = 1
                st.rerun()
                
        with col2:
            if st.button("Next", key="next_2"):
                if teacher or (add_teacher and new_name):
                    st.session_state.teacher = teacher if teacher else new_name
                    st.session_state.step = 3
                    st.rerun()
                else:
                    st.warning("Please select or add a teacher")
    
    # Daily Observations
    elif st.session_state.step == 3:
        st.header("Daily Observations")
        
        st.subheader("Teacher Actions")
        teacher_actions = {}
        teacher_actions['lesson_plan'] = st.checkbox("Lesson plan shared in advance")
        teacher_actions['movement'] = st.checkbox("Moving around classroom")
        teacher_actions['activities'] = st.checkbox("Using hands-on activities")
        teacher_actions['engagement'] = st.checkbox("Encouraging student participation")
        
        st.subheader("Student Actions")
        student_actions = {}
        student_actions['questions'] = st.checkbox("Students asking questions")
        student_actions['explanations'] = st.checkbox("Students explaining work")
        student_actions['participation'] = st.checkbox("Active participation in activities")
        student_actions['peer_learning'] = st.checkbox("Peer learning observed")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_3"):
                st.session_state.step = 2
                st.rerun()
        with col2:
            if st.button("Next", key="next_3"):
                st.session_state.teacher_actions = teacher_actions
                st.session_state.student_actions = student_actions
                st.session_state.step = 4
                st.rerun()
    
    # Infrastructure
    elif st.session_state.step == 4:
        st.header("Infrastructure (Monthly)")
        
        col1, col2 = st.columns(2)
        with col1:
            condition = st.selectbox(
                "Classroom Condition",
                ["Good", "Needs Minor Repairs", "Needs Major Repairs"]
            )
            
            resources = st.multiselect(
                "Available Resources",
                ["Textbooks", "Charts", "Teaching Aids", "Sports Equipment"]
            )
        
        with col2:
            seating = st.selectbox(
                "Seating Arrangement",
                ["Individual Desks", "Shared Desks", "Floor Seating"]
            )
            
            facilities = st.multiselect(
                "Facilities",
                ["Drinking Water", "Clean Toilets", "Playground", "Library"]
            )
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_4"):
                st.session_state.step = 3
                st.rerun()
        with col2:
            if st.button("Next", key="next_4"):
                st.session_state.infrastructure = {
                    'condition': condition,
                    'seating': seating,
                    'resources': resources,
                    'facilities': facilities
                }
                st.session_state.step = 5
                st.rerun()
    
    # Community
    elif st.session_state.step == 5:
        st.header("Community Engagement (Monthly)")
        
        meetings = st.number_input("Parent meetings this month", 0, 31)
        attendance = st.slider("Average attendance (%)", 0, 100)
        
        activities = st.multiselect(
            "Activities conducted",
            ["PTA Meeting", "Cultural Event", "Sports Day", "Other"]
        )
        
        if "Other" in activities:
            other = st.text_input("Specify other activities")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Previous", key="prev_5"):
                st.session_state.step = 4
                st.rerun()
        with col2:
            if st.button("Submit", key="submit"):
                try:
                    # Prepare data for submission
                    data = {
                        'Date': st.session_state.date,
                        'Program Manager': st.session_state.pm,
                        'School': st.session_state.school,
                        'Teacher': st.session_state.teacher,
                        # Add other fields
                    }
                    
                    # Submit to sheet
                    st.success("Form submitted successfully!")
                    st.session_state.step = 1
                    st.rerun()
                except Exception as e:
                    st.error(f"Error submitting form: {str(e)}")

if __name__ == "__main__":
    main()
