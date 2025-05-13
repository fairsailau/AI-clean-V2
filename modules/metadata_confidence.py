"""
Module for enhancing metadata extraction confidence using validation rules and templates.
"""
from typing import Dict, Any, List, Optional, Tuple, Union
import re
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def validate_field_type(value: Any, field_type: str) -> Tuple[bool, str]:
    """
    Validate a field value against its expected type.
    
    Args:
        value: The value to validate
        field_type: The expected type (string, number, date, boolean, enum)
        
    Returns:
        Tuple of (is_valid, reason)
    """
    if value is None:
        return False, "Value is required"
        
    try:
        if field_type.lower() == 'string':
            if not isinstance(value, str):
                return False, f"Expected string, got {type(value).__name__}"
            return True, "Valid string"
            
        elif field_type.lower() == 'number':
            float(value)  # Try to convert to float
            return True, "Valid number"
            
        elif field_type.lower() == 'date':
            if isinstance(value, str):
                # Try common date formats
                date_formats = [
                    '%Y-%m-%d',  # 2023-01-01
                    '%m/%d/%Y',   # 01/01/2023
                    '%d/%m/%Y',   # 01/01/2023 (international)
                    '%Y-%m-%dT%H:%M:%S',  # ISO format
                    '%Y-%m-%d %H:%M:%S',   # with space instead of T
                ]
                
                for fmt in date_formats:
                    try:
                        datetime.strptime(value, fmt)
                        return True, f"Valid date (format: {fmt})"
                    except ValueError:
                        continue
                return False, "Date format not recognized"
            return False, f"Expected date string, got {type(value).__name__}"
            
        elif field_type.lower() == 'boolean':
            if isinstance(value, bool):
                return True, "Valid boolean"
            if isinstance(value, str) and value.lower() in ('true', 'false', 'yes', 'no', '1', '0'):
                return True, "Valid boolean string"
            return False, f"Expected boolean, got {type(value).__name__}"
            
        elif field_type.lower() == 'enum':
            # For enum, we need to know the allowed values
            # This will be handled in the template validation
            return True, "Enum type needs template validation"
            
        return False, f"Unknown field type: {field_type}"
        
    except (ValueError, TypeError) as e:
        return False, f"Validation failed: {str(e)}"

def validate_against_template(field_name: str, value: Any, template: Dict[str, Any]) -> Dict[str, Any]:
    """
    Validate a field value against its template definition.
    
    Args:
        field_name: Name of the field
        value: Field value to validate
        template: Template definition for the field
        
    Returns:
        Dict containing validation results and confidence score
    """
    result = {
        'is_valid': False,
        'confidence': 'Low',
        'reasoning': [],
        'suggested_correction': None
    }
    
    # Check if field exists in template
    if field_name not in template.get('fields', {}):
        result['reasoning'].append(f"Field '{field_name}' not found in template")
        return result
    
    field_def = template['fields'][field_name]
    field_type = field_def.get('type', 'string')
    
    # Check if field is required
    if field_def.get('required', False) and (value is None or value == ''):
        result['reasoning'].append("Required field is missing or empty")
        return result
    
    # Skip validation if value is empty and field is not required
    if value is None or value == '':
        result['is_valid'] = True
        result['confidence'] = 'High'
        result['reasoning'].append("Optional field is empty")
        return result
    
    # Validate field type
    is_valid, reason = validate_field_type(value, field_type)
    result['reasoning'].append(f"Type validation: {reason}")
    
    if not is_valid:
        result['confidence'] = 'Low'
        return result
    
    # Additional validations based on field type
    if field_type.lower() == 'enum':
        enum_values = field_def.get('options', [])
        if str(value) not in [str(v) for v in enum_values]:
            result['reasoning'].append(f"Value '{value}' not in allowed values: {', '.join(map(str, enum_values))}")
            result['suggested_correction'] = enum_values[0] if enum_values else None
            result['confidence'] = 'Low'
            return result
    
    elif field_type.lower() == 'number':
        num_value = float(value)
        if 'min' in field_def and num_value < field_def['min']:
            result['reasoning'].append(f"Value {num_value} is below minimum {field_def['min']}")
            result['suggested_correction'] = field_def['min']
            result['confidence'] = 'Low'
            return result
        if 'max' in field_def and num_value > field_def['max']:
            result['reasoning'].append(f"Value {num_value} is above maximum {field_def['max']}")
            result['suggested_correction'] = field_def['max']
            result['confidence'] = 'Low'
            return result
    
    elif field_type.lower() == 'string':
        str_value = str(value)
        if 'min_length' in field_def and len(str_value) < field_def['min_length']:
            result['reasoning'].append(f"String is too short (min {field_def['min_length']} characters)")
            result['confidence'] = 'Medium'
            return result
        if 'max_length' in field_def and len(str_value) > field_def['max_length']:
            result['reasoning'].append(f"String is too long (max {field_def['max_length']} characters)")
            result['confidence'] = 'Medium'
            return result
        if 'pattern' in field_def and not re.match(field_def['pattern'], str_value):
            result['reasoning'].append(f"String does not match expected pattern: {field_def['pattern']}")
            result['confidence'] = 'Medium'
            return result
    
    # If we get here, all validations passed
    result['is_valid'] = True
    result['confidence'] = 'High'
    return result

def enhance_confidence_with_template(
    extracted_data: Dict[str, Any], 
    template: Dict[str, Any]
) -> Dict[str, Dict[str, Any]]:
    """
    Enhance confidence scores for extracted data using template validation.
    
    Args:
        extracted_data: Dictionary of extracted field values
        template: Template definition with validation rules
        
    Returns:
        Dictionary with enhanced confidence information for each field
    """
    enhanced_results = {}
    
    # Process each extracted field
    for field_name, value in extracted_data.items():
        if field_name.startswith('_'):  # Skip internal fields
            continue
            
        # Validate against template
        validation = validate_against_template(field_name, value, template)
        
        # Create enhanced result
        enhanced_results[field_name] = {
            'value': value,
            'confidence': validation['confidence'],
            'reasoning': validation['reasoning'],
            'is_valid': validation['is_valid']
        }
        
        # Add suggested correction if available
        if validation['suggested_correction'] is not None:
            enhanced_results[field_name]['suggested_correction'] = validation['suggested_correction']
    
    # Check for missing required fields
    if 'fields' in template:
        for field_name, field_def in template['fields'].items():
            if field_def.get('required', False) and field_name not in enhanced_results:
                enhanced_results[field_name] = {
                    'value': None,
                    'confidence': 'Low',
                    'reasoning': ["Required field is missing"],
                    'is_valid': False
                }
    
    return enhanced_results

def calculate_overall_confidence(enhanced_results: Dict[str, Dict[str, Any]]) -> str:
    """
    Calculate an overall confidence score based on individual field confidences.
    
    Args:
        enhanced_results: Dictionary of enhanced field results
        
    Returns:
        Overall confidence level ('High', 'Medium', or 'Low')
    """
    if not enhanced_results:
        return 'Low'
    
    # Count confidence levels
    confidence_counts = {'High': 0, 'Medium': 0, 'Low': 0}
    for field_data in enhanced_results.values():
        confidence = field_data.get('confidence', 'Low')
        if confidence in confidence_counts:
            confidence_counts[confidence] += 1
    
    # Determine overall confidence
    total_fields = len(enhanced_results)
    high_pct = confidence_counts['High'] / total_fields
    medium_pct = confidence_counts['Medium'] / total_fields
    
    if high_pct >= 0.7:  # At least 70% high confidence
        return 'High'
    elif (high_pct + medium_pct) >= 0.6:  # At least 60% high+medium confidence
        return 'Medium'
    else:
        return 'Low'

def format_confidence_results(
    enhanced_results: Dict[str, Dict[str, Any]],
    include_reasoning: bool = True
) -> Dict[str, Any]:
    """
    Format the enhanced results for display or storage.
    
    Args:
        enhanced_results: Dictionary of enhanced field results
        include_reasoning: Whether to include reasoning in the output
        
    Returns:
        Formatted results dictionary
    """
    formatted = {}
    
    for field_name, field_data in enhanced_results.items():
        # Always include the value
        formatted[field_name] = field_data['value']
        
        # Add confidence and reasoning with field name prefixes
        formatted[f"{field_name}_confidence"] = field_data['confidence']
        
        if include_reasoning and field_data.get('reasoning'):
            formatted[f"{field_name}_reasoning"] = " ".join(field_data['reasoning'])
    
    # Add overall confidence
    formatted['_overall_confidence'] = calculate_overall_confidence(enhanced_results)
    
    return formatted
