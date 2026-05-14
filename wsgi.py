import os
import sys


project_root_candidates = [
    os.path.expanduser("~/lms"),
    os.path.expanduser("~/Programming/lms"),
]

project_dir = next((path for path in project_root_candidates if os.path.isdir(path)), os.path.dirname(os.path.abspath(__file__)))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)


from app import create_app


application = create_app("production")