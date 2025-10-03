"""
Event Scheduling Optimizer using Google OR-Tools CP-SAT
Handles constraint-based scheduling for events, rooms, and time slots
"""

from ortools.sat.python import cp_model
import pandas as pd
from typing import List, Dict, Tuple, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScheduleOptimizer:
    """
    Constraint-based event scheduler using OR-Tools CP-SAT solver
    """
    
    def __init__(self):
        self.model = cp_model.CpModel()
        self.solver = cp_model.CpSolver()
        self.status = None
        self.solution = {}
        
        # Data containers
        self.sessions = []
        self.rooms = []
        self.time_slots = []
        self.constraints = {}
        
        # Decision variables
        self.assignment_vars = {}
        
    def load_data(self, sessions_df: pd.DataFrame, rooms_df: pd.DataFrame, 
                  slots_df: pd.DataFrame, constraints_df: Optional[pd.DataFrame] = None):
        """
        Load event data into the optimizer
        
        Args:
            sessions_df: DataFrame with columns [title, duration, speaker, track]
            rooms_df: DataFrame with columns [name, capacity]
            slots_df: DataFrame with columns [start_time, end_time, slot_id]
            constraints_df: Optional constraints DataFrame
        """
        self.sessions = sessions_df.to_dict('records')
        self.rooms = rooms_df.to_dict('records')
        self.time_slots = slots_df.to_dict('records')
        
        if constraints_df is not None:
            self.constraints = constraints_df.to_dict('records')
        
        logger.info(f"Loaded {len(self.sessions)} sessions, {len(self.rooms)} rooms, {len(self.time_slots)} slots")
    
    def create_decision_variables(self):
        """
        Create binary decision variables x[s,r,t] = 1 if session s is in room r at time t
        """
        self.assignment_vars = {}
        
        for s_idx, session in enumerate(self.sessions):
            for r_idx, room in enumerate(self.rooms):
                for t_idx, slot in enumerate(self.time_slots):
                    var_name = f"x_s{s_idx}_r{r_idx}_t{t_idx}"
                    self.assignment_vars[(s_idx, r_idx, t_idx)] = self.model.NewBoolVar(var_name)
        
        logger.info(f"Created {len(self.assignment_vars)} decision variables")
    
    def add_hard_constraints(self):
        """
        Add mandatory constraints that must be satisfied
        """
        # Constraint 1: Each session must be scheduled exactly once
        for s_idx in range(len(self.sessions)):
            assignment_sum = []
            for r_idx in range(len(self.rooms)):
                for t_idx in range(len(self.time_slots)):
                    assignment_sum.append(self.assignment_vars[(s_idx, r_idx, t_idx)])
            
            self.model.Add(sum(assignment_sum) == 1)
        
        # Constraint 2: No room double-booking (max one session per room per time slot)
        for r_idx in range(len(self.rooms)):
            for t_idx in range(len(self.time_slots)):
                room_time_assignments = []
                for s_idx in range(len(self.sessions)):
                    room_time_assignments.append(self.assignment_vars[(s_idx, r_idx, t_idx)])
                
                self.model.Add(sum(room_time_assignments) <= 1)
        
        # Constraint 3: Room capacity limits
        for s_idx, session in enumerate(self.sessions):
            for r_idx, room in enumerate(self.rooms):
                # If session has expected attendance, check against room capacity
                expected_attendance = session.get('expected_attendance', 0)
                if expected_attendance > 0 and expected_attendance > room['capacity']:
                    # This session cannot be assigned to this room
                    for t_idx in range(len(self.time_slots)):
                        self.model.Add(self.assignment_vars[(s_idx, r_idx, t_idx)] == 0)
        
        logger.info("Added hard constraints: unique assignment, no double-booking, capacity limits")
    
    def add_soft_constraints_as_objective(self):
        """
        Add soft preferences as weighted penalty terms in the objective function
        Fixed to avoid Boolean variable multiplication
        """
        penalty_terms = []
        
        # Soft constraint 1: Prefer earlier time slots for keynotes
        for s_idx, session in enumerate(self.sessions):
            if 'keynote' in session.get('title', '').lower():
                for r_idx in range(len(self.rooms)):
                    for t_idx in range(len(self.time_slots)):
                        # Higher time slot index = later in day = higher penalty
                        penalty_weight = t_idx * 10
                        penalty_terms.append(
                            penalty_weight * self.assignment_vars[(s_idx, r_idx, t_idx)]
                        )
        
        # Soft constraint 2: Penalize late sessions (prefer earlier slots)
        late_slot_penalty = 2
        for s_idx in range(len(self.sessions)):
            for r_idx in range(len(self.rooms)):
                for t_idx in range(len(self.time_slots)):
                    if t_idx >= len(self.time_slots) // 2:  # Second half of day
                        penalty_terms.append(
                            late_slot_penalty * self.assignment_vars[(s_idx, r_idx, t_idx)]
                        )
        
        # Soft constraint 3: Prefer larger rooms for sessions with higher attendance
        room_mismatch_penalty = 3
        for s_idx, session in enumerate(self.sessions):
            expected_attendance = session.get('expected_attendance', 50)
            for r_idx, room in enumerate(self.rooms):
                room_capacity = room['capacity']
                
                # Calculate mismatch penalty (prefer right-sized rooms)
                if room_capacity < expected_attendance:
                    continue  # Skip - this is handled by hard constraints
                
                # Small penalty for oversized rooms
                if room_capacity > expected_attendance * 2:
                    for t_idx in range(len(self.time_slots)):
                        penalty_terms.append(
                            room_mismatch_penalty * self.assignment_vars[(s_idx, r_idx, t_idx)]
                        )
        
        # Set objective to minimize penalties
        if penalty_terms:
            self.model.Minimize(sum(penalty_terms))
            logger.info(f"Added soft constraints as objective with {len(penalty_terms)} penalty terms")
        else:
            logger.info("No soft constraints added - using feasibility mode")
    
    def solve(self) -> bool:
        """
        Run the CP-SAT solver and return True if solution found
        """
        logger.info("Starting OR-Tools CP-SAT solver...")
        
        # Create variables and constraints
        self.create_decision_variables()
        self.add_hard_constraints()
        self.add_soft_constraints_as_objective()
        
        # Configure solver
        self.solver.parameters.max_time_in_seconds = 30.0  # 30 second timeout
        
        # Solve the model
        self.status = self.solver.Solve(self.model)
        
        if self.status == cp_model.OPTIMAL or self.status == cp_model.FEASIBLE:
            logger.info(f"Solution found! Status: {'OPTIMAL' if self.status == cp_model.OPTIMAL else 'FEASIBLE'}")
            self._extract_solution()
            return True
        else:
            logger.error(f"No solution found. Status: {self.solver.StatusName(self.status)}")
            return False
    
    def _extract_solution(self):
        """
        Extract the solution from the solver and organize it
        """
        self.solution = {
            'assignments': [],
            'room_utilization': {},
            'time_utilization': {},
            'conflicts': 0
        }
        
        # Extract assignments
        for s_idx, session in enumerate(self.sessions):
            for r_idx, room in enumerate(self.rooms):
                for t_idx, slot in enumerate(self.time_slots):
                    if self.solver.Value(self.assignment_vars[(s_idx, r_idx, t_idx)]) == 1:
                        assignment = {
                            'session_id': s_idx,
                            'session_title': session['title'],
                            'room_id': r_idx,
                            'room_name': room['name'],
                            'time_slot_id': t_idx,
                            'start_time': slot.get('start_time', f'Slot {t_idx}'),
                            'end_time': slot.get('end_time', f'Slot {t_idx} end'),
                            'speaker': session.get('speaker', 'TBD'),
                            'track': session.get('track', 'General'),
                            'duration': session.get('duration', 60),
                            'expected_attendance': session.get('expected_attendance', 0)
                        }
                        self.solution['assignments'].append(assignment)
        
        logger.info(f"Extracted {len(self.solution['assignments'])} assignments")
    
    def get_schedule_dataframe(self) -> pd.DataFrame:
        """
        Return the optimized schedule as a pandas DataFrame
        """
        if not self.solution or not self.solution['assignments']:
            return pd.DataFrame()
        
        return pd.DataFrame(self.solution['assignments'])
    
    def get_room_schedule_grid(self) -> pd.DataFrame:
        """
        Return a grid view of the schedule (rooms × time slots)
        """
        if not self.solution or not self.solution['assignments']:
            return pd.DataFrame()
        
        # Create the grid
        grid_data = {}
        
        # Get unique time slots and sort them
        time_slots = sorted(set(a['start_time'] for a in self.solution['assignments']))
        grid_data['Time'] = time_slots
        
        # Add room columns
        for room in self.rooms:
            room_schedule = [''] * len(time_slots)
            
            for assignment in self.solution['assignments']:
                if assignment['room_name'] == room['name']:
                    try:
                        time_idx = time_slots.index(assignment['start_time'])
                        room_schedule[time_idx] = assignment['session_title']
                    except ValueError:
                        continue
            
            grid_data[room['name']] = room_schedule
        
        return pd.DataFrame(grid_data)
    
    def get_optimization_stats(self) -> Dict:
        """
        Return statistics about the optimization results
        """
        if not self.solution:
            return {
                'total_sessions': len(self.sessions),
                'total_rooms': len(self.rooms), 
                'total_slots': len(self.time_slots),
                'assigned_sessions': 0,
                'solver_status': 'Not solved',
                'solve_time_seconds': 0,
                'conflicts': 0
            }
        
        stats = {
            'total_sessions': len(self.sessions),
            'total_rooms': len(self.rooms),
            'total_slots': len(self.time_slots),
            'assigned_sessions': len(self.solution['assignments']),
            'solver_status': self.solver.StatusName(self.status) if self.status else 'Not solved',
            'solve_time_seconds': self.solver.WallTime(),
            'conflicts': self.solution.get('conflicts', 0)
        }
        
        # Calculate room utilization
        room_usage = {}
        for assignment in self.solution['assignments']:
            room_name = assignment['room_name']
            room_usage[room_name] = room_usage.get(room_name, 0) + 1
        
        stats['room_utilization'] = room_usage
        stats['average_room_utilization'] = sum(room_usage.values()) / len(self.rooms) if self.rooms else 0
        
        return stats

# Example usage and testing functions
def create_sample_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Create sample data for testing the optimizer
    """
    # Sample sessions
    sessions_data = {
        'title': [
            'Opening Keynote', 
            'AI Workshop', 
            'Panel Discussion',
            'Technical Deep Dive',
            'Networking Break',
            'Closing Remarks'
        ],
        'duration': [60, 90, 45, 75, 30, 30],
        'speaker': [
            'Dr. Smith', 
            'Prof. Johnson', 
            'Industry Panel',
            'Tech Lead',
            'Organizers',
            'Event Host'
        ],
        'track': ['General', 'Technical', 'Business', 'Technical', 'General', 'General'],
        'expected_attendance': [200, 50, 100, 30, 200, 150]
    }
    
    # Sample rooms
    rooms_data = {
        'name': ['Main Hall', 'Conference Room A', 'Workshop Space'],
        'capacity': [250, 100, 60]
    }
    
    # Sample time slots
    slots_data = {
        'start_time': ['09:00', '10:00', '11:00', '12:00', '14:00', '15:00'],
        'end_time': ['10:00', '11:00', '12:00', '13:00', '15:00', '16:00'],
        'slot_id': [0, 1, 2, 3, 4, 5]
    }
    
    return (
        pd.DataFrame(sessions_data),
        pd.DataFrame(rooms_data), 
        pd.DataFrame(slots_data)
    )

if __name__ == "__main__":
    # Test the optimizer with sample data
    print("🧠 Testing OR-Tools Event Scheduler...")
    
    sessions_df, rooms_df, slots_df = create_sample_data()
    
    optimizer = ScheduleOptimizer()
    optimizer.load_data(sessions_df, rooms_df, slots_df)
    
    success = optimizer.solve()
    
    if success:
        print("✅ Optimization successful!")
        schedule = optimizer.get_schedule_dataframe()
        print(schedule)
        
        print("\n📊 Room Schedule Grid:")
        grid = optimizer.get_room_schedule_grid()
        print(grid)
        
        print("\n📈 Optimization Stats:")
        stats = optimizer.get_optimization_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
    else:
        print("❌ Optimization failed!")