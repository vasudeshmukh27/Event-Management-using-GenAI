"""
Calendar Export and Integration Module
Handles RFC 5545 .ics generation and Google Calendar API integration
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
import pandas as pd
from pathlib import Path
import io

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CalendarExporter:
    """
    Handle calendar export functionality including .ics generation and Google Calendar API
    """
    
    def __init__(self, use_google_api: bool = False):
        """
        Initialize calendar exporter
        
        Args:
            use_google_api: Whether to enable Google Calendar API integration
        """
        self.use_google_api = use_google_api
        self.service = None
        
        if use_google_api:
            self._setup_google_calendar()
    
    def _setup_google_calendar(self):
        """
        Setup Google Calendar API service
        Note: Requires OAuth credentials and authentication
        """
        try:
            from googleapiclient.discovery import build
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            
            logger.info("Setting up Google Calendar API...")
            # This would require proper OAuth setup in production
            # For now, we'll keep it as placeholder
            logger.info("Google Calendar API setup placeholder - implement OAuth flow")
            
        except Exception as e:
            logger.error(f"Failed to setup Google Calendar API: {e}")
            self.use_google_api = False
    
    def create_ics_content(self, schedule_df: pd.DataFrame, 
                          event_info: Dict,
                          timezone: str = "Asia/Kolkata") -> str:
        """
        Generate RFC 5545 compliant .ics file content
        
        Args:
            schedule_df: DataFrame with scheduled sessions
            event_info: Event metadata (name, description, etc.)
            timezone: Timezone for the events
            
        Returns:
            .ics file content as string
        """
        logger.info(f"Generating .ics content for {len(schedule_df)} events")
        
        # Start calendar
        ics_lines = [
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//EventGen AI//Event Management//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{event_info.get('name', 'Generated Event Schedule')}",
            f"X-WR-CALDESC:{event_info.get('description', 'AI-generated event schedule')}",
            f"X-WR-TIMEZONE:{timezone}"
        ]
        
        # Add timezone information
        ics_lines.extend([
            "BEGIN:VTIMEZONE",
            f"TZID:{timezone}",
            "BEGIN:STANDARD",
            "DTSTART:20240101T000000",
            "TZOFFSETFROM:+0530",
            "TZOFFSETTO:+0530",
            "TZNAME:IST",
            "END:STANDARD",
            "END:VTIMEZONE"
        ])
        
        # Process each scheduled session
        for _, session in schedule_df.iterrows():
            event_lines = self._create_vevent(session, event_info, timezone)
            ics_lines.extend(event_lines)
        
        # End calendar
        ics_lines.append("END:VCALENDAR")
        
        ics_content = "\\n".join(ics_lines)
        logger.info("✅ .ics content generated successfully")
        
        return ics_content
    
    def _create_vevent(self, session: pd.Series, event_info: Dict, timezone: str) -> List[str]:
        """
        Create VEVENT component for a single session
        
        Args:
            session: Session data from schedule DataFrame
            event_info: Event metadata
            timezone: Timezone string
            
        Returns:
            List of VEVENT lines
        """
        # Generate unique ID
        session_id = f"{session.get('session_id', 0)}"
        uid = f"session-{session_id}@eventgen.ai"
        
        # Parse time information
        start_time = self._parse_time(session.get('start_time', '09:00'))
        
        # Calculate end time (add duration or default 1 hour)
        duration_minutes = session.get('duration', 60)
        if isinstance(duration_minutes, str):
            try:
                duration_minutes = int(duration_minutes)
            except:
                duration_minutes = 60
        
        end_time = self._add_minutes_to_time(start_time, duration_minutes)
        
        # Format datetime for iCalendar (assuming today's date for demo)
        base_date = event_info.get('base_date', '20251015')  # YYYYMMDD format
        dtstart = f"{base_date}T{start_time.replace(':', '')}00"
        dtend = f"{base_date}T{end_time.replace(':', '')}00"
        
        # Create VEVENT
        vevent_lines = [
            "BEGIN:VEVENT",
            f"UID:{uid}",
            f"DTSTART;TZID={timezone}:{dtstart}",
            f"DTEND;TZID={timezone}:{dtend}",
            f"SUMMARY:{self._escape_ics_text(session.get('session_title', 'Session'))}",
            f"LOCATION:{self._escape_ics_text(session.get('room_name', 'TBD'))}",
            f"DESCRIPTION:{self._escape_ics_text(self._create_session_description(session))}",
            f"STATUS:CONFIRMED",
            f"TRANSP:OPAQUE",
            f"CATEGORIES:{session.get('track', 'General')}",
            f"CREATED:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
            f"LAST-MODIFIED:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}",
            "END:VEVENT"
        ]
        
        return vevent_lines
    
    def _parse_time(self, time_str: str) -> str:
        """
        Parse time string and ensure HH:MM format
        """
        try:
            if ':' in time_str:
                return time_str
            else:
                # Assume it's hour only
                return f"{time_str}:00"
        except:
            return "09:00"
    
    def _add_minutes_to_time(self, time_str: str, minutes: int) -> str:
        """
        Add minutes to time string
        """
        try:
            hour, minute = map(int, time_str.split(':'))
            total_minutes = hour * 60 + minute + minutes
            
            new_hour = (total_minutes // 60) % 24
            new_minute = total_minutes % 60
            
            return f"{new_hour:02d}:{new_minute:02d}"
        except:
            return "10:00"
    
    def _escape_ics_text(self, text: str) -> str:
        """
        Escape text for iCalendar format
        """
        if not isinstance(text, str):
            text = str(text)
        
        # Escape special characters according to RFC 5545
        text = text.replace('\\', '\\\\')
        text = text.replace(',', '\\,')
        text = text.replace(';', '\\;')
        text = text.replace('\\n', '\\n')
        
        return text
    
    def _create_session_description(self, session: pd.Series) -> str:
        """
        Create detailed description for session
        """
        description_parts = []
        
        if 'speaker' in session and session['speaker']:
            description_parts.append(f"Speaker: {session['speaker']}")
        
        if 'track' in session and session['track']:
            description_parts.append(f"Track: {session['track']}")
        
        if 'expected_attendance' in session and session['expected_attendance']:
            description_parts.append(f"Expected Attendance: {session['expected_attendance']}")
        
        return " | ".join(description_parts)
    
    def save_ics_file(self, ics_content: str, filename: str, output_dir: str = "calendars") -> str:
        """
        Save .ics content to file
        
        Args:
            ics_content: .ics file content
            filename: Output filename
            output_dir: Output directory
            
        Returns:
            Path to saved file
        """
        # Create output directory
        Path(output_dir).mkdir(exist_ok=True)
        
        # Ensure .ics extension
        if not filename.lower().endswith('.ics'):
            filename += '.ics'
        
        filepath = Path(output_dir) / filename
        
        # Write file
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(ics_content)
        
        logger.info(f"📅 .ics file saved to: {filepath}")
        return str(filepath)
    
    def create_personalized_ics(self, schedule_df: pd.DataFrame, 
                               event_info: Dict,
                               track_filter: Optional[List[str]] = None,
                               attendee_name: str = "Attendee") -> str:
        """
        Create personalized .ics file filtered by tracks or preferences
        
        Args:
            schedule_df: Full schedule DataFrame
            event_info: Event metadata
            track_filter: List of tracks to include (None for all)
            attendee_name: Name for personalized calendar
            
        Returns:
            Personalized .ics content
        """
        # Filter schedule if tracks specified
        if track_filter:
            filtered_df = schedule_df[schedule_df['track'].isin(track_filter)]
            logger.info(f"Filtered schedule to {len(filtered_df)} events for tracks: {track_filter}")
        else:
            filtered_df = schedule_df
        
        # Update event info for personalization
        personalized_info = event_info.copy()
        personalized_info['name'] = f"{event_info.get('name', 'Event')} - {attendee_name}'s Schedule"
        personalized_info['description'] = f"Personalized schedule for {attendee_name}"
        
        return self.create_ics_content(filtered_df, personalized_info)
    
    def get_ics_download_data(self, ics_content: str, filename: str) -> Tuple[str, str]:
        """
        Prepare .ics content for Streamlit download
        
        Args:
            ics_content: .ics file content
            filename: Desired filename
            
        Returns:
            Tuple of (content, filename)
        """
        if not filename.lower().endswith('.ics'):
            filename += '.ics'
        
        return ics_content, filename
    
    def validate_ics_content(self, ics_content: str) -> Dict[str, any]:
        """
        Validate .ics content for RFC 5545 compliance
        
        Args:
            ics_content: .ics content to validate
            
        Returns:
            Validation results dictionary
        """
        validation_results = {
            'is_valid': True,
            'errors': [],
            'warnings': [],
            'event_count': 0
        }
        
        lines = ics_content.split('\\n')
        
        # Check for required components
        has_vcalendar_begin = any(line.strip() == 'BEGIN:VCALENDAR' for line in lines)
        has_vcalendar_end = any(line.strip() == 'END:VCALENDAR' for line in lines)
        
        if not has_vcalendar_begin:
            validation_results['errors'].append("Missing BEGIN:VCALENDAR")
            validation_results['is_valid'] = False
        
        if not has_vcalendar_end:
            validation_results['errors'].append("Missing END:VCALENDAR")
            validation_results['is_valid'] = False
        
        # Count events
        event_count = sum(1 for line in lines if line.strip() == 'BEGIN:VEVENT')
        validation_results['event_count'] = event_count
        
        # Check for version
        has_version = any(line.strip().startswith('VERSION:') for line in lines)
        if not has_version:
            validation_results['warnings'].append("Missing VERSION property")
        
        logger.info(f"ICS validation: Valid={validation_results['is_valid']}, Events={event_count}")
        
        return validation_results
    
    def create_google_calendar_events(self, schedule_df: pd.DataFrame, 
                                    event_info: Dict,
                                    calendar_id: str = 'primary') -> List[str]:
        """
        Create events in Google Calendar (placeholder implementation)
        
        Args:
            schedule_df: Schedule DataFrame
            event_info: Event metadata
            calendar_id: Google Calendar ID
            
        Returns:
            List of created event IDs
        """
        if not self.use_google_api or not self.service:
            logger.warning("Google Calendar API not available")
            return []
        
        logger.info(f"Creating {len(schedule_df)} Google Calendar events")
        
        created_events = []
        
        # This is a placeholder - would implement actual Google Calendar API calls
        for _, session in schedule_df.iterrows():
            event_data = {
                'summary': session.get('session_title', 'Session'),
                'location': session.get('room_name', ''),
                'description': self._create_session_description(session),
                # Add proper datetime formatting for Google Calendar API
                'start': {'dateTime': '2025-10-15T09:00:00+05:30', 'timeZone': 'Asia/Kolkata'},
                'end': {'dateTime': '2025-10-15T10:00:00+05:30', 'timeZone': 'Asia/Kolkata'},
            }
            
            # Placeholder for API call
            # event = service.events().insert(calendarId=calendar_id, body=event_data).execute()
            # created_events.append(event['id'])
            
            logger.info(f"Would create event: {event_data['summary']}")
            created_events.append(f"placeholder-{session.get('session_id', 0)}")
        
        return created_events

# Example usage and testing functions
def create_sample_event_info() -> Dict:
    """Create sample event metadata"""
    return {
        'name': 'AI & Future Tech Conference 2025',
        'description': 'Leading conference on artificial intelligence and emerging technologies',
        'base_date': '20251015',  # October 15, 2025
        'organizer': 'Tech Events Inc',
        'location': 'Mumbai Convention Center'
    }

def test_calendar_export(schedule_df: pd.DataFrame):
    """Test calendar export functionality"""
    print("📅 Testing Calendar Export System...")
    
    # Initialize exporter
    exporter = CalendarExporter(use_google_api=False)
    
    # Create sample event info
    event_info = create_sample_event_info()
    
    # Generate .ics content
    ics_content = exporter.create_ics_content(schedule_df, event_info)
    
    # Validate content
    validation = exporter.validate_ics_content(ics_content)
    print(f"Validation: {validation}")
    
    # Save .ics file
    filepath = exporter.save_ics_file(ics_content, "test_schedule.ics")
    print(f"Saved to: {filepath}")
    
    # Test personalized calendar
    personalized_ics = exporter.create_personalized_ics(
        schedule_df, 
        event_info, 
        track_filter=['Technical', 'General'],
        attendee_name="John Doe"
    )
    
    personalized_path = exporter.save_ics_file(
        personalized_ics, 
        "personalized_schedule.ics"
    )
    print(f"Personalized calendar saved to: {personalized_path}")
    
    print("✅ Calendar export test completed!")

if __name__ == "__main__":
    # Create sample schedule for testing
    import pandas as pd
    from scheduler import create_sample_data
    
    sessions_df, rooms_df, slots_df = create_sample_data()
    
    # Create a simple schedule DataFrame for testing
    sample_schedule = pd.DataFrame({
        'session_id': [0, 1, 2],
        'session_title': ['Opening Keynote', 'AI Workshop', 'Panel Discussion'],
        'room_name': ['Main Hall', 'Conference Room A', 'Conference Room B'],
        'start_time': ['09:00', '10:00', '11:00'],
        'speaker': ['Dr. Smith', 'Prof. Johnson', 'Industry Panel'],
        'track': ['General', 'Technical', 'Business'],
        'duration': [60, 90, 45]
    })
    
    test_calendar_export(sample_schedule)