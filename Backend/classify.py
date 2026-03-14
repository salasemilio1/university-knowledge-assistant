"""
The purpose of this class is to classify queries and documents based on rules
and an LLM.
"""

class Classify:

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

    # what the query or document refers to
    entity_types:list = [

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
    audiences:list = [

        "prospective_student",
        "undergraduate_student",
        "graduate_student",
        "faculty",
        "staff",
        "alumni",
        "general_public"

    ]

    # type of document (course catalog, etc.)
    document_types:list = [

    ]

    # intent of the query
    query_intents:list = [

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
    time_sensitivities:list = [
        "current",
        "historical"
    ]

    query_scopes:list = [
        "specific",
        "broad",
        "multi-topic"
    ]

    def __init__(self):
        """
        Class constructor. Does nothing except instantiate an object.
        """

        pass

    def classify_query_rule(self, query:str, current_classification:dict) -> dict:
        """
        Classifies query by matching.

        Args:
            query(str): The query to classify.
            current_classification(dict): The current query classification.

        Returns:
            dict: Classified query.
        """

        query_tokens = query.split()

        # add academic department to classification if it is present in query.
        for academic_department in self.academic_departments:
            if academic_department in query_tokens:
                current_classification["academic_department"].append(academic_department)

        # add university department to classification if it is present in query.
        for university_department in self.university_departments:
            if university_department in query_tokens:
                current_classification["university_department"].append(university_department)

        # add entity type to classification if it is present in query.
        for entity_type in self.entity_types:
            if entity_type in query_tokens:
                current_classification["entity_type"].append(entity_type)

        # add audience to classification if it is present in query.
        for audience in self.audiences:
            if audience in query_tokens:
                current_classification["audience"].append(audience)

        # add query intent to classification if it is present in query.
        for query_intent in self.query_intents:
            if query_intent in query_tokens:
                current_classification["query_intent"].append(query_intent)

        # add time sensitivity to classification if it is present in query.
        for time_sensitivity in self.time_sensitivities:
            if time_sensitivity in query_tokens:
                current_classification["time_sensitivity"].append(time_sensitivity)

        # add query scope to classification if it is present in query.
        for query_scope in self.query_scopes:
            if query_scope in query_tokens:
                current_classification["query_scope"].append(query_scope)

        return current_classification
    


    def classify_query_LLM(self, query:str, current_classification:dict) -> dict:
        """
        Classifies query by prompting LLM.

        Args:
            query(str): The query to classify.
            current_classification(dict): The current query classification.

        Returns:
            dict: Classified query.
        """

        return {}
    
    def classify_document_rule(self, document, current_classification:dict) -> dict:
        """
        Classifies query by matching.

        Args:
            document( ): The document to classify.
            current_classification(dict): The current document classification.

        Returns:
            dict: Classified query.
        """

        return {}
    
    def classify_document_LLM(self, document, current_classification:dict) -> dict:
        """
        Classifies query by prompting LLM.

        Args:
            document( ): The document to classify.
            current_classification(dict): The current document classification.

        Returns:
            dict: Classified query.
        """

        return {}



    def classify_query(self, query:str) -> dict:
        """
        Classifies a query.

        Args:
            query(str): The query.

        Returns:
            dict: Classified categories.
        """

        # classification is represented as a dictionary.
        # each classifying category value is a list due to potential for multiple values
        query_classification:dict = {

            "academic_department": [],
            "university_department": [],
            "entity_type": [],
            "audience": [],
            "query_intent": [],
            "time_sensitivity": [],
            "query_scope":[]

        }

        # first pass with rule matching
        query_classification = self.classify_query_rule(query, query_classification)

        # second pass with LLM
        query_classification = self.classify_query_LLM(query, query_classification)

        return query_classification
    

    def classify_document(self) -> dict:
        """
        Classifies a document.

        Returns:
            dict: Classified categories.
        """
        document_classification:dict = {
        }

        return document_classification