import requests
import hashlib
import time
import os
from django.conf import settings
import logging
import json

logger = logging.getLogger(__name__)

# List of potentially dangerous file extensions
BLOCKED_EXTENSIONS = {
    # Executable
    '.exe', '.bat', '.cmd', '.com', '.scr', '.ps1', '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf', '.wsh', '.msc',
    # Scripts
    '.hta', '.msi', '.msp', '.mst', '.pif', '.reg', '.dll', '.scf', '.lnk',
    # Other dangerous
    '.sys', '.cpl'  # Reduced list to only most dangerous types
}

def is_dangerous_file(filename):
    """Check if file extension is in blocked list"""
    ext = os.path.splitext(filename.lower())[1]
    return ext in BLOCKED_EXTENSIONS

def scan_file_metadefender(file_content, file_name):
    """
    Scan a file using MetaDefender Cloud API
    Returns: (is_safe: bool, threat_info: str)
    """
    try:
        # First check file extension
        if is_dangerous_file(file_name):
            return False, f"File type {os.path.splitext(file_name)[1]} is not allowed for security reasons"

        # Calculate file hash
        file_hash = hashlib.sha256(file_content).hexdigest()
        
        # MetaDefender Cloud API endpoint
        api_url = "https://api.metadefender.com/v4"
        headers = {
            "apikey": settings.METADEFENDER_API_KEY,
            "Content-Type": "application/octet-stream",
            "filename": file_name
        }

        # Upload file for scanning
        scan_response = requests.post(
            f"{api_url}/file",
            headers=headers,
            data=file_content
        )
        
        if scan_response.status_code != 200:
            logger.warning(f"Scan upload failed: {scan_response.text}")
            # Allow file if scan service is down
            return True, "File scan service unavailable, proceeding with caution"
        
        scan_result = scan_response.json()
        logger.debug(f"Scan upload response: {json.dumps(scan_result, indent=2)}")
        
        data_id = scan_result.get("data_id")
        if not data_id:
            # Allow file if we can't get scan ID
            return True, "File scan incomplete, proceeding with caution"

        # Wait for scan to complete (up to 10 seconds)
        max_retries = 5
        result = None
        
        for attempt in range(max_retries):
            logger.debug(f"Checking scan status (attempt {attempt + 1}/{max_retries})")
            result_response = requests.get(
                f"{api_url}/file/{data_id}",
                headers=headers
            )
            
            if result_response.status_code != 200:
                continue
                
            result = result_response.json()
            logger.debug(f"Scan status response: {json.dumps(result, indent=2)}")
            
            # Check if scan is complete
            if result.get("scan_results", {}).get("progress_percentage", 0) == 100:
                break
                
            time.sleep(2)  # Wait 2 seconds before checking again

        if not result:
            # Allow file if scan results unavailable
            return True, "File scan results unavailable, proceeding with caution"

        # Get scan details
        scan_results = result.get("scan_results", {})
        scan_details = scan_results.get("scan_details", {})
        
        logger.debug(f"Final scan results: {json.dumps(scan_results, indent=2)}")
        
        # Count actual threats found
        threats = []
        for engine, details in scan_details.items():
            threat_found = details.get("threat_found", "")
            scan_result_i = details.get("scan_result_i", 0)
            
            # Only count as threat if both threat_found exists and scan_result_i > 0
            if threat_found and scan_result_i > 0:
                threats.append(f"{engine}: {threat_found}")
        
        # If less than 2 engines detect a threat, consider it safe
        if len(threats) < 2:
            return True, "File appears safe"
        else:
            threat_info = "Multiple threats detected: " + "; ".join(threats[:2])
            return False, threat_info

    except Exception as e:
        logger.error(f"Scan error: {str(e)}")
        # Allow file if scan fails
        return True, "File scan failed, proceeding with caution"