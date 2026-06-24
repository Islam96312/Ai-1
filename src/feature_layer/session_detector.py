from datetime import datetime, time
import pandas as pd

class SessionDetector:
    """
    Identifies trading sessions based on UTC time.
    """
    SESSIONS = {
        "ASIAN": {"start": time(0, 0), "end": time(9, 0)},
        "LONDON": {"start": time(7, 0), "end": time(16, 0)},
        "NY": {"start": time(12, 0), "end": time(21, 0)},
    }

    @staticmethod
    def get_current_session(dt: datetime) -> str:
        """
        Returns the active session(s) for a given datetime.
        """
        current_time = dt.time()
        active_sessions = []
        
        for session, hours in SessionDetector.SESSIONS.items():
            if hours["start"] <= current_time <= hours["end"]:
                active_sessions.append(session)
        
        if not active_sessions:
            return "OFF_HOURS"
        if len(active_sessions) > 1:
            return "OVERLAP"
        return active_sessions[0]

    @staticmethod
    def add_session_features(df: pd.DataFrame) -> pd.DataFrame:
        """
        Adds session info to the dataframe.
        """
        df = df.copy()
        # Assuming 'open_time' is a datetime index or column
        if 'open_time' in df.columns:
            df['session'] = df['open_time'].apply(SessionDetector.get_current_session)
        elif isinstance(df.index, pd.DatetimeIndex):
            df['session'] = df.index.map(SessionDetector.get_current_session)
        
        return df
