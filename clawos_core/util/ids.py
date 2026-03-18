"""ID generators."""
import uuid

def task_id()    -> str: return f"task_{uuid.uuid4().hex[:8]}"
def session_id() -> str: return str(uuid.uuid4())
def entry_id()   -> str: return str(uuid.uuid4())[:8]
def req_id()     -> str: return str(uuid.uuid4())[:8]
