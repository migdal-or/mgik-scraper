"""
Test script for process_attachments function
"""

import json
from mgik_website_worker import process_attachments

if __name__ == "__main__":
    # Call the function to test it
    print(json.dumps(process_attachments(), indent=2))
