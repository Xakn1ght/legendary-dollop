import re
from datetime import datetime
from typing import Any, List, Literal, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


def validate_request(schema_class: type[BaseModel], data: dict) -> tuple[BaseModel | None, dict | None]:
    """
    Validate request data against a Pydantic schema.
    
    Returns:
        tuple: (validated_model, None) on success, or (None, error_dict) on failure
    """
    try:
        validated = schema_class.model_validate(data)
        return validated, None
    except Exception as e:
        # Extract validation errors
        if hasattr(e, 'errors'):
            errors = []
            for err in e.errors():
                field = '.'.join(str(loc) for loc in err['loc']) if err['loc'] else 'root'
                errors.append({
                    'field': field,
                    'message': err['msg'],
                    'type': err['type']
                })
            return None, {
                'ok': False,
                'error': 'validation_error',
                'message': 'Invalid input data',
                'details': errors
            }
        return None, {
            'ok': False,
            'error': 'validation_error',
            'message': str(e)
        }


def create_validation_error_response(error_dict: dict, status: int = 400) -> dict:
    """
    Create a standardized validation error response.
    """
    return error_dict
