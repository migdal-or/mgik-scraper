"""
Main module for MGIK news monitoring pipeline.
"""

from mgik_website_worker import load_decisions_from_web_to_database


def main():
    """
    Main execution function for MGIK news processing pipeline.

    Orchestrates data fetching (commented), file loading, and database persistence.
    Provides logging for debugging and monitoring pipeline execution.
    """
    load_decisions_from_web_to_database()
    # process_attachments()


if __name__ == "__main__":
    main()
