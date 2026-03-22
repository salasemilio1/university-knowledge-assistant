"""
The purpose of this class is to classify queries and documents based on rules
and an LLM.
"""

import re
from google import genai
import os

class Classify:


    # the model used to classify queries and documents
    # TODO set up environment variable locally and in gcp
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

    # these lists will be used as a first pass to classify queries by matching 
    # query and document text against the contents of the list. the document or query will then be passed
    # into a LLM along with the lists for further matching that isn't feasible 
    # with rule-based matching (CS vs Computer Science, Bio vs Biology, Biolgy vs Biology)

    #TODO fill in lists

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

        normalized_query = self.normalize_text(query)

        # add academic department to classification if it is present in query.
        for academic_department in self.academic_departments:
            if self.normalize_text(academic_department) in normalized_query:
                current_classification["academic_department"].append(academic_department)

        # add university department to classification if it is present in query.
        for university_department in self.university_departments:
            if self.normalize_text(university_department) in normalized_query:
                current_classification["university_department"].append(university_department)

        # add entity type to classification if it is present in query.
        for entity_type in self.entity_types:
            if self.normalize_text(entity_type) in normalized_query:
                current_classification["entity_type"].append(entity_type)

        # add audience to classification if it is present in query.
        for audience in self.audiences:
            if self.normalize_text(audience) in normalized_query:
                current_classification["audience"].append(audience)

        # add query intent to classification if it is present in query.
        for query_intent in self.query_intents:
            if self.normalize_text(query_intent) in normalized_query:
                current_classification["query_intent"].append(query_intent)

        # add time sensitivity to classification if it is present in query.
        for time_sensitivity in self.time_sensitivities:
            if self.normalize_text(time_sensitivity) in normalized_query:
                current_classification["time_sensitivity"].append(time_sensitivity)

        # add query scope to classification if it is present in query.
        for query_scope in self.query_scopes:
            if self.normalize_text(query_scope) in normalized_query:
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
    

    
    def classify_document_rule(self, document_text:str, document_metadata:dict, current_classification:dict) -> dict:
        """
        Classifies document by matching.

        Args:
            document_text(str): The text of the document to classify.
            document_metadata(dict): The metadata of the document to classify.
            current_classification(dict): The current document classification.

        Returns:
            dict: Classified document.
        """

        normalized_document_text = self.normalize_text(document_text)

        # add document type to classification if it is present in query.
        for document_type in self.document_types:
            if self.normalize_text(document_type) in normalized_document_text:
                current_classification["document_type"].append(document_type)

        # add academic department to classification if it is present in query.
        for academic_department in self.academic_departments:
            if self.normalize_text(academic_department) in normalized_document_text:
                current_classification["academic_department"].append(academic_department)

        # add university department to classification if it is present in query.
        for university_department in self.university_departments:
            if self.normalize_text(university_department) in normalized_document_text:
                current_classification["university_department"].append(university_department)

        # add entity type to classification if it is present in query.
        for entity_type in self.entity_types:
            if self.normalize_text(entity_type) in normalized_document_text:
                current_classification["entity_type"].append(entity_type)

        # add audience to classification if it is present in query.
        for audience in self.audiences:
            if self.normalize_text(audience) in normalized_document_text:
                current_classification["audience"].append(audience)

        # add time sensitivity to classification if it is present in query.
        for time_sensitivity in self.time_sensitivities:
            if self.normalize_text(time_sensitivity) in normalized_document_text:
                current_classification["time_sensitivity"].append(time_sensitivity)

        #TODO match metadata

        return current_classification
    
    def classify_document_LLM(self, document_text:str, document_metadata:dict, current_classification:dict) -> dict:
        """
        Classifies document by prompting LLM.

        Args:
            document_text(str): The text of the document to classify.
            document_metadata(dict): The metadata of the document to classify.
            current_classification(dict): The current document classification.

        Returns:
            dict: Classified document.
        """

        return {}
    

    def normalize_text(self, text:str) -> str:
        """
        Normalizes text for rule-based classification.

        Args:
            text(str): The text to normalize. Can be queries, classifications, or document text.

        Returns:
            dict: The normalized text.
        """

        text = text.lower()
        text = re.sub(r"[^a-z0-9\s]", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text
    

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
    

    def classify_document(self, document_text:str, document_metadata:dict) -> dict:
        """
        Classifies a document.

        Args:
            document_text(str): The text of the document to classify.
            document_metadata(dict): The metadata of the document to classify.

        Returns:
            dict: Classified categories.
        """
        document_classification:dict = {

            "document_type": [],
            "academic_department": [],
            "university_department": [],
            "entity_type": [],
            "audience": [],
            "time_sensitivity": []

        }

        # first pass with rule matching
        document_classification = self.classify_document_rule(document_text, document_metadata, document_classification)

        # second pass with LLM
        document_classification = self.classify_document_LLM(document_text, document_metadata, document_classification)

        return document_classification