
"""
Utility functions for exporting data to CSV format.
Used by recruiters to export application data.
"""

import csv
import io
from typing import List, Dict, Any
from datetime import datetime

def export_applications_to_csv(applications: List[Dict[str, Any]]) -> str:
    """
    Export applications data to CSV format.

    Args:
        applications: List of application dictionaries with candidate info

    Returns:
        CSV string ready to be downloaded
    """

    # Create in-memory string buffer
    output = io.StringIO()

    # Define CSV columns
    fieldnames = [
        'Application ID',
        'Candidate Name',
        'Candidate Email',
        'Job Title',
        'Status',
        'Applied Date',
        'Phone',
        'Skills',
        'Experience Years',
        'Location',
        'Resume ID'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # Write each application
    for app in applications:
        writer.writerow({
            'Application ID': app.get('application_id', ''),
            'Candidate Name': app.get('candidate_name', ''),
            'Candidate Email': app.get('candidate_email', ''),
            'Job Title': app.get('job_title', ''),
            'Status': app.get('status', ''),
            'Applied Date': app.get('applied_at', '').strftime('%Y-%m-%d %H:%M:%S') if isinstance(app.get('applied_at'), datetime) else '',
            'Phone': app.get('candidate_phone', ''),
            'Skills': ', '.join(app.get('candidate_skills', [])) if app.get('candidate_skills') else '',
            'Experience Years': app.get('candidate_experience', ''),
            'Location': app.get('candidate_location', ''),
            'Resume ID': app.get('resume_id', '')
        })

    # Get CSV string
    csv_string = output.getvalue()
    output.close()

    return csv_string


def export_jobs_to_csv(jobs: List[Dict[str, Any]]) -> str:
    """
    Export jobs data to CSV format.

    Args:
        jobs: List of job dictionaries

    Returns:
        CSV string ready to be downloaded
    """

    output = io.StringIO()

    fieldnames = [
        'Job ID',
        'Title',
        'Company',
        'Location',
        'Job Type',
        'Salary',
        'Skills Required',
        'Status',
        'Posted Date',
        'Application Count',
        'Deadline'
    ]

    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for job in jobs:
        writer.writerow({
            'Job ID': job.get('id', ''),
            'Title': job.get('title', ''),
            'Company': job.get('company', ''),
            'Location': job.get('location', ''),
            'Job Type': job.get('job_type', ''),
            'Salary': job.get('salary', ''),
            'Skills Required': ', '.join(job.get('skills', [])) if job.get('skills') else '',
            'Status': job.get('status', 'active'),
            'Posted Date': job.get('posted_date', '').strftime('%Y-%m-%d') if isinstance(job.get('posted_date'), datetime) else '',
            'Application Count': job.get('application_count', 0),
            'Deadline': job.get('application_deadline', '').strftime('%Y-%m-%d') if isinstance(job.get('application_deadline'), datetime) else ''
        })

    csv_string = output.getvalue()
    output.close()

    return csv_string


def export_analytics_to_csv(analytics_data: Dict[str, Any]) -> str:
    """
    Export job analytics to CSV format.

    Args:
        analytics_data: Dictionary containing analytics information

    Returns:
        CSV string ready to be downloaded
    """

    output = io.StringIO()

    fieldnames = ['Metric', 'Value']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    # Flatten analytics data
    writer.writerow({'Metric': 'Job Title', 'Value': analytics_data.get('job_title', '')})
    writer.writerow({'Metric': 'Total Applications', 'Value': analytics_data.get('total_applications', 0)})
    writer.writerow({'Metric': 'Pending Applications', 'Value': analytics_data.get('applications_by_status', {}).get('Pending', 0)})
    writer.writerow({'Metric': 'Shortlisted Applications', 'Value': analytics_data.get('applications_by_status', {}).get('Shortlisted', 0)})
    writer.writerow({'Metric': 'Rejected Applications', 'Value': analytics_data.get('applications_by_status', {}).get('Rejected', 0)})
    writer.writerow({'Metric': 'Selected Applications', 'Value': analytics_data.get('applications_by_status', {}).get('Selected', 0)})
    writer.writerow({'Metric': 'View Count', 'Value': analytics_data.get('view_count', 0)})
    writer.writerow({'Metric': 'Days Active', 'Value': analytics_data.get('days_active', 0)})
    writer.writerow({'Metric': 'Status', 'Value': analytics_data.get('status', '')})

    csv_string = output.getvalue()
    output.close()

    return csv_string


def create_csv_response_headers(filename: str) -> Dict[str, str]:
    """
    Create headers for CSV file download response.

    Args:
        filename: Name of the CSV file (without .csv extension)

    Returns:
        Dictionary of headers for FastAPI Response
    """

    return {
        "Content-Disposition": f"attachment; filename={filename}.csv",
        "Content-Type": "text/csv"
    }