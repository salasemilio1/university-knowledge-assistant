"""
The purpose of this class is to classify queries and documents based on rules
and an LLM.
"""

class classify:

    # these lists will be used as a first pass to classify queries by matching 
    # query and document text against the contents of the list. the document or query will then be passed
    # into a LLM along with the lists for further matching that isn't feasible 
    # with rule-based matching (CS vs Computer Science, Bio vs Biology, Biolgy vs Biology)

    # all academic departments 
    academic_departments:list = [
        "Computer Science",
        ""
    ]

    # all university departments
    university_departments:list = [
        "Registrar",
        ""
    ]

    # all university departments
    university_departments:list = []

    # what the query or document refers to
    entity_type:list = [

        # academic structure
        "course",
        "program",
        "major",
        "minor",
        "degree",
        "academic_department",
        "research_lab",

        # people
        "professor",
        "faculty",
        "staff",
        "advisor",
        "student",

        # administrative units
        "university_department",
        "office",

        # academic resources
        "syllabus",
        "course_catalog",
        "academic_policy",
        "degree_requirement",

        # services
        "student_service",
        "career_service",
        "library_resource",
        "it_service",

        # logistics
        "event",
        "deadline",
        "registration_period",

        # locations
        "building",
        "room",
        "facility",

        # general information
        "faq",
        "announcement",
        "form",
        "webpage"
    ]


    # who the document or query is intended for
    audience:list = [

        "prospective_student",
        "undergraduate_student",
        "graduate_student",
        "faculty",
        "staff",
        "alumni",
        "general_public"

    ]

    # type of document (course catalog, etc.)
    document_type:list = [

    ]

    # intent of the query
    query_intent:list = [

        # information seeking
        "information_lookup",
        "definition",

        # navigation
        "navigation",
        "location_lookup",

        # people related
        "contact_lookup",

        # academic planning
        "requirement_lookup",
        "course_information",

        # procedural
        "procedure",
        "application_process",
        "registration_process",

        # time related
        "schedule_lookup",
        "deadline_lookup",

        # comparison
        "comparison",

        # resources
        "resource_access",

        # troubleshooting / help
        "support_request"

    ]

    # the time sensitivity of the query
    time_sensitivity:list = [
        "current",
        "historical"
    ]


    query_scope:list = [
        "specific",
        "broad",
        "multi-topic"
    ]

    @staticmethod
    def classify_query() -> dict:
        """
        Classifies a query.

        Returns:
            dict: Classified categories.
        """

        query_classification:dict = {

            "department": None,

        }

        return query_classification
    



    @staticmethod
    def classify_document() -> dict:
        """
        Classifies a document.

        Returns:
            dict: Classified categories.
        """
        document_classification:dict = {

            "department": None,

        }

        return document_classification
    