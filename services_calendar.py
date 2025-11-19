from db import save_event, save_schedule

def create_event(user_id, title, start_dt, end_dt, note=None):
    save_event(user_id, title, start_dt, end_dt, note)

def create_reminder(user_id, item, due_dt, note=None):
    save_schedule(user_id, item, due_dt, note)