from db import save_meet

def create_instant_meet(user_id, title="Instant Meeting"):
    link = "https://meet.google.com/" + title.lower().replace(" ","-")
    save_meet(user_id, title, link, None)
    return link

def schedule_meet(user_id, title, when_iso):
    link = "https://meet.google.com/" + title.lower().replace(" ","-")
    save_meet(user_id, title, link, when_iso)
    return link