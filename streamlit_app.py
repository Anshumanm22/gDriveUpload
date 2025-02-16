import streamlit as st
from google.oauth2 import service_account
from googleapiclient.discovery import build
import pandas as pd

# Set page config
st.set_page_config(page_title="School Observation Form", layout="wide")

# Define the scope
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

@st.cache_resource
def get_google_service():
    """Get Google Sheets service using service account."""
    try:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"],
            scopes=SCOPES
        )
        sheets_service = build('sheets', 'v4', credentials=credentials)
        return sheets_service
    except Exception as e:
        st.error(f"Error setting up Google service: {str(e)}")
        return None

def read_sheet_data(service, spreadsheet_id, range_name):
    """Read data from specified Google Sheet range."""
    try:
        result = service.spreadsheets().values().get(
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

def write_to_sheet(service, spreadsheet_id, range_name, values):
    """Write data to the specified Google Sheet range."""
    try:
        body = {
            'values': values
        }
        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_name,
            valueInputOption='RAW',
            body=body
        ).execute()
        return result
    except Exception as e:
        st.error(f"Error writing to sheet: {str(e)}")
        return None

def create_observation_form():
    # Initialize Google Sheets service
    sheets_service = get_google_service()
    if not sheets_service:
        st.error("Failed to initialize Google Sheets service")
        return

    # Initialize session state for multi-step form
    if 'step' not in st.session_state:
        st.session_state.step = 1

    # Load data from Google Sheets
    SPREADSHEET_ID = st.secrets["spreadsheet_id"]  # You'll need to add this to your secrets
    
    # Read data from different sheets
    schools_data = read_sheet_data(sheets_service, SPREADSHEET_ID, 'Schools!A:D')
    teachers_data = read_sheet_data(sheets_service, SPREADSHEET_ID, 'Teachers!A:D')
    
    if schools_data is None or teachers_data is None:
        st.error("Failed to load data from Google Sheets")
        return

    # Sidebar progress indicator
    st.sidebar.markdown("### Form Progress")
    st.sidebar.progress(st.session_state.step / 5)

    # Section 1: Basic Details
    if st.session_state.step == 1:
        st.subheader("Basic Details")
        
        # Get unique program managers
        program_managers = schools_data['Program Manager'].unique()
        selected_pm = st.selectbox("Select Program Manager", program_managers)
        
        # Filter schools for selected PM
        pm_schools = schools_data[
            schools_data['Program Manager'] == selected_pm
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
        
        # Get teachers for selected school
        school_teachers_df = teachers_data[
            teachers_data['School Name'] == st.session_state.selected_school
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

        nav_col1, nav_col2 = st.columns(2)
        with nav_col1:
            if st.button("Previous"):
                st.session_state.step = 1
                st.experimental_rerun()
        with nav_col2:
            if st.button("Next"):
                st.session_state.step = 3
                st.experimental_rerun()

    # Continue with sections 3-5 similar to previous implementation
    # but save data to Google Sheets instead of local storage

def main():
    st.title("School Observation Form")
    create_observation_form()

if __name__ == "__main__":
    main()
