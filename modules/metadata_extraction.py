import streamlit as st
import logging
import json
import requests
from typing import Dict, Any, List, Optional

# Corrected logging.basicConfig format string
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_extraction_functions() -> Dict[str, Any]:
    """
    Returns a dictionary of available metadata extraction functions.
    """
    from .metadata_confidence import enhance_confidence_with_template

    def extract_structured_metadata(
        client: Any, 
        file_id: str, 
        fields: Optional[List[Dict[str, Any]]] = None, 
        metadata_template: Optional[Dict[str, Any]] = None, 
        ai_model: str = 'azure__openai__gpt_4o_mini',
        document_text: str = ""  # Add document_text parameter
    ) -> Dict[str, Any]:
        """
        Extract structured metadata from a file using Box AI API with enhanced confidence scoring.
        
        Args:
            client: Box client
            file_id: ID of the file to process
            fields: List of field definitions
            metadata_template: Metadata template definition
            ai_model: AI model to use for extraction
            document_text: Optional document text for validation
            
        Returns:
            dict: Extracted metadata with enhanced confidence scoring
        """
        try:
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')

            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            
            # Enhanced system message with confidence instructions
            system_message = """You are an AI assistant specialized in extracting metadata from documents based on provided field definitions. 
            For each field, analyze the document content and extract the corresponding value. 
            
            CRITICALLY IMPORTANT: 
            1. For each field, respond with a JSON object containing:
               - "value": The extracted metadata value
               - "confidence": Your confidence level (High, Medium, or Low)
               - "reasoning": Brief explanation of your confidence assessment
            
            2. Confidence Guidelines:
               - High: Clear, unambiguous information in the document
               - Medium: Information is present but may need verification
               - Low: Information is inferred or uncertain
               
            3. If a field cannot be extracted, return null for the value with Low confidence.
            
            Example Response:
            {
              "invoice_number": {
                "value": "INV-12345",
                "confidence": "High",
                "reasoning": "Found in the top-right corner of the document"
              },
              "total_amount": {
                "value": 1250.99,
                "confidence": "Medium",
                "reasoning": "Matched pattern but needs verification"
              },
              "due_date": {
                "value": null,
                "confidence": "Low",
                "reasoning": "No clear due date found in document"
              }
            }"""
            
            ai_agent = {
                'type': 'ai_agent_extract_structured',
                'long_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': system_message
                },
                'basic_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': system_message
                }
            }
            
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/extract_structured'
            request_body: Dict[str, Any] = {
                'items': items, 
                'ai_agent': ai_agent
            }

            if metadata_template:
                request_body['metadata_template'] = metadata_template
            elif fields:
                api_fields = []
                for field in fields:
                    field_def = {
                        'key': field.get('key', ''),
                        'displayName': field.get('displayName', field.get('key', '')),
                        'type': field.get('type', 'string')
                    }
                    if 'description' in field:
                        field_def['description'] = field['description']
                    if 'options' in field:
                        field_def['options'] = field['options']
                    api_fields.append(field_def)
                request_body['fields'] = api_fields

            logger.info(f'Making Box AI API request to {api_url} with body: {json.dumps(request_body, indent=2)}')
            response = requests.post(api_url, headers=headers, json=request_body)

            if response.status_code != 200:
                logger.error(f'Box AI API error response: {response.status_code} - {response.reason}. Body: {response.text}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}', 'details': response.text}

            response_data = response.json()
            logger.info(f'Raw Box AI structured extraction response data: {json.dumps(response_data)}')

            # Process the response and enhance confidence using template if available
            processed_response = _process_ai_response(response_data)
            
            if metadata_template and isinstance(processed_response, dict):
                processed_response = enhance_confidence_with_template(
                    processed_response,
                    metadata_template,
                    document_text
                )
            
            return processed_response

        except Exception as e:
            logger.error(f'Error in extract_structured_metadata: {str(e)}', exc_info=True)
            return {'error': str(e)}

    def extract_freeform_metadata(
        client: Any, 
        file_id: str, 
        prompt: str, 
        ai_model: str = 'azure__openai__gpt_4o_mini',
        document_text: str = ""  # Add document_text parameter
    ) -> Dict[str, Any]:
        """
        Extract freeform metadata from a file using Box AI API with enhanced confidence scoring.
        
        Args:
            client: Box client
            file_id: ID of the file to process
            prompt: Prompt for the AI
            ai_model: AI model to use for extraction
            document_text: Optional document text for validation
            
        Returns:
            dict: Extracted metadata with enhanced confidence scoring
        """
        try:
            access_token = None
            if hasattr(client, '_oauth'):
                access_token = client._oauth.access_token
            elif hasattr(client, 'auth') and hasattr(client.auth, 'access_token'):
                access_token = client.auth.access_token
            if not access_token:
                raise ValueError('Could not retrieve access token from client')

            headers = {'Authorization': f'Bearer {access_token}', 'Content-Type': 'application/json'}
            
            # Enhanced system message for freeform extraction
            system_message = f"""You are an AI assistant that extracts information from documents based on the following instructions:
            
            {prompt}
            
            IMPORTANT INSTRUCTIONS:
            1. Respond with a JSON object where each key is a field name and each value is an object with:
               - "value": The extracted information
               - "confidence": Your confidence level (High, Medium, or Low)
               - "reasoning": Brief explanation of your confidence
            
            2. For each field, provide the most accurate value you can find, even if confidence is not high.
            
            3. If you're unsure about a field, set confidence to "Low" and explain why in the reasoning.
            
            Example Response:
            {{
              "field_name": {{
                "value": "example value",
                "confidence": "High",
                "reasoning": "Found in the document header"
              }}
            }}"""
            
            ai_agent = {
                'type': 'ai_agent_extract_structured',
                'long_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': system_message
                },
                'basic_text': {
                    'model': ai_model,
                    'mode': 'default',
                    'system_message': system_message
                }
            }
            
            items = [{'id': file_id, 'type': 'file'}]
            api_url = 'https://api.box.com/2.0/ai/extract_structured'
            request_body = {
                'items': items,
                'ai_agent': ai_agent
            }

            logger.info(f'Making Box AI API request to {api_url} with prompt: {prompt}')
            response = requests.post(api_url, headers=headers, json=request_body)

            if response.status_code != 200:
                logger.error(f'Box AI API error response: {response.status_code} - {response.reason}. Body: {response.text}')
                return {'error': f'Error in Box AI API call: {response.status_code} {response.reason}', 'details': response.text}

            response_data = response.json()
            logger.info(f'Raw Box AI freeform extraction response data: {json.dumps(response_data)}')

            # Process the response
            return _process_ai_response(response_data)
        except Exception as e:
            logger.error(f'Error in extract_freeform_metadata: {str(e)}', exc_info=True)
            return {'error': str(e)}

    def _process_ai_response(response_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process the AI response into a standardized format with confidence scores.
        
        Args:
            response_data: Raw response from the AI API
            
        Returns:
            dict: Processed response with standardized confidence format
        """
        processed_response = {}
        
        try:
            # Handle different response formats
            if 'answer' in response_data and isinstance(response_data['answer'], dict):
                answer_data = response_data['answer']
                
                # Handle the case where fields are in a 'fields' array
                if 'fields' in answer_data and isinstance(answer_data['fields'], list):
                    for field in answer_data['fields']:
                        if isinstance(field, dict) and 'key' in field:
                            processed_response[field['key']] = {
                                'value': field.get('value'),
                                'confidence': field.get('confidence', 'Medium'),
                                'reasoning': field.get('reasoning', 'No reasoning provided')
                            }
                # Handle the case where fields are direct keys in the answer
                else:
                    for key, value in answer_data.items():
                        if isinstance(value, dict) and 'value' in value:
                            processed_response[key] = {
                                'value': value.get('value'),
                                'confidence': value.get('confidence', 'Medium'),
                                'reasoning': value.get('reasoning', 'No reasoning provided')
                            }
                        else:
                            processed_response[key] = {
                                'value': value,
                                'confidence': 'Medium',
                                'reasoning': 'No confidence information provided'
                            }
            
            # If no valid data was processed, return the original response
            if not processed_response and isinstance(response_data, dict):
                return response_data
                
            return processed_response
            
        except Exception as e:
            logger.error(f'Error processing AI response: {str(e)}')
            return response_data if isinstance(response_data, dict) else {'error': 'Invalid response format'}

    return {
        'extract_structured_metadata': extract_structured_metadata,
        'extract_freeform_metadata': extract_freeform_metadata
    }

if __name__ == '__main__':
    class MockOAuth:
        def __init__(self, token):
            self.access_token = token

    class MockClient:
        def __init__(self, token):
            self._oauth = MockOAuth(token)

    # Simulate Streamlit session state for testing if st is available
    try:
        st.session_state.client = MockClient("test_access_token")
    except NameError: # st might not be defined if run directly as script without streamlit context
        pass 
        
    functions = get_extraction_functions()
    print(f"Available extraction functions: {list(functions.keys())}")

