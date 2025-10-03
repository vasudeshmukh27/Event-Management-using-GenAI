import streamlit as st
import pandas as pd
from scheduler import ScheduleOptimizer
from calendar_export import CalendarExporter
from design import PosterGenerator
import os
import base64
from io import BytesIO

# Page configuration
st.set_page_config(
    page_title="EventGen AI - Smart Event Management",
    page_icon="🎪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Main title and description
st.title("🎪 EventGen AI - Smart Event Management")
st.markdown("**Intelligent scheduling • AI-powered posters • Seamless calendar integration**")

# Initialize session state
if 'schedule_data' not in st.session_state:
    st.session_state.schedule_data = None
if 'optimization_results' not in st.session_state:
    st.session_state.optimization_results = None
if 'generated_posters' not in st.session_state:
    st.session_state.generated_posters = []

# Initialize components
@st.cache_resource
def init_components():
    """Initialize AI components"""
    poster_gen = PosterGenerator(use_local_sdxl=False)  # Free version with placeholders
    calendar_exporter = CalendarExporter(use_google_api=False)  # Free .ics export
    return poster_gen, calendar_exporter

poster_generator, calendar_exporter = init_components()

# Sidebar for project info
with st.sidebar:
    
    
    st.header("💡 Quick Actions")
    if st.button("Load Sample Data"):
        st.session_state.sample_loaded = True
        st.success("Sample data loaded!")
    
    st.markdown("---")
    st.markdown("**Tech Stack:**")
    st.markdown("• OR-Tools CP-SAT ✅")
    st.markdown("• SDXL Posters ✅")
    st.markdown("• RFC 5545 .ics ✅")
    st.markdown("• Streamlit Cloud ✅")

# Create tabs for different functionalities
tab1, tab2, tab3, tab4 = st.tabs(["📊 Data Input", "🧠 Smart Scheduling", "🎨 Poster Generation", "📅 Calendar Export"])

# Tab 1: Data Input
with tab1:
    st.header("📊 Event Data Management")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Sessions Data")
        sessions_file = st.file_uploader("Choose sessions CSV file", type=['csv'], key="sessions")
        
        if sessions_file is not None:
            sessions_df = pd.read_csv(sessions_file)
            st.dataframe(sessions_df, height=200)
            st.session_state.sessions_df = sessions_df
        else:
            sample_sessions = {
                'title': ['Opening Keynote', 'AI Workshop', 'Panel Discussion'],
                'duration': [60, 90, 45],
                'speaker': ['Dr. Smith', 'Prof. Johnson', 'Industry Panel'],
                'track': ['General', 'Technical', 'Business'],
                'expected_attendance': [200, 50, 100]
            }
            st.markdown("**Expected format:**")
            st.dataframe(pd.DataFrame(sample_sessions), height=150)
    
    with col2:
        st.subheader("Rooms & Time Slots")
        
        rooms_file = st.file_uploader("Choose rooms CSV file", type=['csv'], key="rooms")
        if rooms_file is not None:
            rooms_df = pd.read_csv(rooms_file)
            st.dataframe(rooms_df, height=100)
            st.session_state.rooms_df = rooms_df
        else:
            sample_rooms = {
                'name': ['Hall A', 'Room B', 'Workshop C'],
                'capacity': [500, 100, 50]
            }
            st.markdown("**Expected format:**")
            st.dataframe(pd.DataFrame(sample_rooms), height=100)
        
        slots_file = st.file_uploader("Choose time slots CSV file", type=['csv'], key="slots")
        if slots_file is not None:
            slots_df = pd.read_csv(slots_file)
            st.dataframe(slots_df, height=100)
            st.session_state.slots_df = slots_df
    
    st.markdown("---")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("🎯 Create Sample Dataset", type="primary"):
            from scheduler import create_sample_data
            sessions_df, rooms_df, slots_df = create_sample_data()
            st.session_state.sessions_df = sessions_df
            st.session_state.rooms_df = rooms_df
            st.session_state.slots_df = slots_df
            st.success("Sample dataset created!")
            st.rerun()

# Tab 2: Smart Scheduling
with tab2:
    st.header("🧠 Constraint-Based Scheduling")
    
    if 'sessions_df' not in st.session_state:
        st.warning("⚠️ Please load data in the Data Input tab first")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Scheduling Parameters")
            
            st.markdown("**Hard Constraints:**")
            no_overlap = st.checkbox("No room double-booking", value=True, disabled=True)
            speaker_availability = st.checkbox("Respect speaker availability", value=True)
            capacity_limits = st.checkbox("Enforce room capacity limits", value=True)
            
            st.markdown("**Soft Preferences:**")
            track_grouping = st.slider("Track session grouping preference", 0, 10, 5)
            time_preference = st.slider("Preferred time slots weight", 0, 10, 3)
            
            if st.button("🚀 Run OR-Tools Optimizer", type="primary"):
                with st.spinner("Running CP-SAT solver..."):
                    optimizer = ScheduleOptimizer()
                    optimizer.load_data(
                        st.session_state.sessions_df,
                        st.session_state.rooms_df, 
                        st.session_state.slots_df
                    )
                    
                    success = optimizer.solve()
                    
                    if success:
                        st.session_state.optimization_results = optimizer
                        st.session_state.schedule_data = optimizer.get_schedule_dataframe()
                        st.success("✅ Schedule optimization completed!")
                        st.rerun()
                    else:
                        st.error("❌ Optimization failed - check constraints")
        
        with col2:
            st.subheader("Optimization Status")
            
            if st.session_state.optimization_results:
                stats = st.session_state.optimization_results.get_optimization_stats()
                st.success("✅ Solution Found")
                st.metric("Assigned Sessions", stats['assigned_sessions'])
                st.metric("Rooms Utilized", f"{len(stats['room_utilization'])}/{stats['total_rooms']}")
                st.metric("Solve Time", f"{stats['solve_time_seconds']:.2f}s")
            else:
                st.info("🔄 Ready to optimize")
        
        if st.session_state.optimization_results:
            st.markdown("---")
            st.subheader("📋 Generated Schedule")
            
            schedule_grid = st.session_state.optimization_results.get_room_schedule_grid()
            st.dataframe(schedule_grid, use_container_width=True)
            
            col1, col2 = st.columns(2)
            with col1:
                csv_data = schedule_grid.to_csv(index=False)
                st.download_button(
                    "📊 Download Schedule CSV",
                    csv_data,
                    "schedule.csv",
                    "text/csv"
                )

# Tab 3: Poster Generation
with tab3:
    st.header("🎨 AI-Powered Poster Generation")
    
    if st.session_state.optimization_results is None:
        st.info("💡 Generate a schedule first to create session-specific posters")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Design Configuration")
        
        poster_style = st.selectbox(
            "Poster Template",
            poster_generator.get_available_templates(),
            format_func=lambda x: x.replace('_', ' ').title()
        )
        
        # Event information
        st.markdown("**Event Information:**")
        event_title = st.text_input("Event Title", "AI & Future Tech Conference 2025")
        event_date = st.text_input("Event Date", "October 15-16, 2025")
        event_venue = st.text_input("Venue", "Mumbai Convention Center")
        event_details = st.text_area("Additional Details", "Join industry leaders in AI and emerging technologies")
        
        poster_type = st.radio("Generate", ["Main Event Poster", "Session Cards", "Both"])
        
        if st.button("🎨 Generate Posters", type="primary"):
            with st.spinner("Generating AI-powered designs..."):
                event_data = {
                    'title': event_title,
                    'date': event_date,
                    'venue': event_venue,
                    'details': event_details
                }
                
                generated_posters = []
                
                if poster_type in ["Main Event Poster", "Both"]:
                    main_poster = poster_generator.create_poster(event_data, poster_style)
                    generated_posters.append(("main_poster", main_poster))
                
                if poster_type in ["Session Cards", "Both"] and st.session_state.optimization_results:
                    session_cards = poster_generator.create_session_cards(
                        st.session_state.sessions_df, poster_style
                    )
                    for i, card in enumerate(session_cards):
                        generated_posters.append((f"session_card_{i}", card))
                
                st.session_state.generated_posters = generated_posters
                st.success(f"✅ Generated {len(generated_posters)} posters!")
                st.rerun()
    
    with col2:
        st.subheader("Generated Posters")
        
        if st.session_state.generated_posters:
            for name, poster in st.session_state.generated_posters:
                st.markdown(f"**{name.replace('_', ' ').title()}**")
                st.image(poster, use_column_width=True)
                
                # Download button
                img_buffer = BytesIO()
                poster.save(img_buffer, format='PNG')
                st.download_button(
                    f"📥 Download {name}",
                    img_buffer.getvalue(),
                    f"{name}.png",
                    "image/png"
                )
                st.markdown("---")
        else:
            st.info("Generated posters will appear here")

# Tab 4: Calendar Export
with tab4:
    st.header("📅 Calendar Integration & Export")
    
    if st.session_state.schedule_data is None:
        st.warning("⚠️ Please generate a schedule first")
    else:
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Export Configuration")
            
            # Event metadata for calendar
            cal_event_name = st.text_input("Calendar Name", "AI Tech Conference 2025")
            cal_description = st.text_area("Calendar Description", "AI and Future Technology Conference Schedule")
            base_date = st.date_input("Event Date", value=pd.to_datetime("2025-10-15"))
            
            export_type = st.radio(
                "Export Type",
                ["Complete Schedule", "Personalized by Track", "Custom Selection"]
            )
            
            if export_type == "Personalized by Track":
                available_tracks = st.session_state.schedule_data['track'].unique()
                selected_tracks = st.multiselect("Select Tracks", available_tracks)
            
            timezone = st.selectbox("Timezone", ["Asia/Kolkata", "UTC", "America/New_York", "Europe/London"])
            
            if st.button("📅 Generate .ics File", type="primary"):
                with st.spinner("Creating RFC 5545 calendar..."):
                    event_info = {
                        'name': cal_event_name,
                        'description': cal_description,
                        'base_date': base_date.strftime('%Y%m%d'),
                        'organizer': 'EventGen AI',
                        'location': 'Event Venue'
                    }
                    
                    # Filter data based on selection
                    if export_type == "Personalized by Track" and selected_tracks:
                        filtered_schedule = st.session_state.schedule_data[
                            st.session_state.schedule_data['track'].isin(selected_tracks)
                        ]
                    else:
                        filtered_schedule = st.session_state.schedule_data
                    
                    # Generate .ics content
                    ics_content = calendar_exporter.create_ics_content(
                        filtered_schedule, event_info, timezone
                    )
                    
                    st.session_state.ics_content = ics_content
                    st.session_state.ics_filename = f"{cal_event_name.replace(' ', '_')}.ics"
                    
                    # Validate
                    validation = calendar_exporter.validate_ics_content(ics_content)
                    if validation['is_valid']:
                        st.success(f"✅ Calendar created with {validation['event_count']} events")
                    else:
                        st.warning(f"⚠️ Validation warnings: {validation['warnings']}")
        
        with col2:
            st.subheader("Download & Preview")
            
            if 'ics_content' in st.session_state:
                st.metric("Events in Calendar", st.session_state.ics_content.count('BEGIN:VEVENT'))
                
                # Download button
                st.download_button(
                    "📥 Download .ics File",
                    st.session_state.ics_content,
                    st.session_state.ics_filename,
                    "text/calendar",
                    help="Import this file into Google Calendar, Apple Calendar, Outlook, or any RFC 5545 compatible calendar app"
                )
                
                # Preview
                with st.expander("📋 Preview .ics Content"):
                    st.code(st.session_state.ics_content[:1000] + "..." if len(st.session_state.ics_content) > 1000 else st.session_state.ics_content)
                
                st.markdown("**Compatible with:**")
                st.markdown("✅ Google Calendar")
                st.markdown("✅ Apple Calendar") 
                st.markdown("✅ Microsoft Outlook")
                st.markdown("✅ Mozilla Thunderbird")
                st.markdown("✅ Any RFC 5545 calendar app")
                
            else:
                st.info("Configure and generate calendar to see download options")

