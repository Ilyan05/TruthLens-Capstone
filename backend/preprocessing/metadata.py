import os
from datetime import datetime

def get_metadata(file_path):

    return {
        "filename": os.path.basename(file_path),
        "size_mb": round(
            os.path.getsize(file_path)/(1024*1024),
            2
        ),
        "processed_time": str(datetime.now())
    }