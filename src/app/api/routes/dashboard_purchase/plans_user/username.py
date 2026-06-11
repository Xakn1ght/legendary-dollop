"""Service-name helpers — thin wrappers over the shared flow service so the webapp
and the bot can never disagree on availability rules."""
from app.services.flows.purchase import generate_unique_service_name, is_service_name_taken

_generate_unique_username = generate_unique_service_name
_is_username_taken = is_service_name_taken
