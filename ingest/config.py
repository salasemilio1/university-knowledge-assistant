"""
This file contains configuration for the ingest pipeline.
"""

# These are the document types that are supported by the ingest pipeline.
# We will first categorize the document type and then use the appropriate
# parsing method.

#TODO: Drill down on what document types we need to support
DOCUMENT_TYPES = {
    "course_catalog": {
        "boundary_pattern": r"\d{2}-\d{3}\s+[A-Z]",
        "id_pattern":       r"\d{2}-\d{3}",
        "entity_type":      "course",
        "needs_merge":      True,
    },
    "department_listing": {
        "boundary_pattern": r"Department of [A-Z]",
        "id_pattern":       r"...",
        "entity_type":      "department",
        "needs_merge":      False,
    },
    "standard": {
        "needs_merge":      False,
        "entity_type":      None,
    }
}