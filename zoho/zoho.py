from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler, ActionResult
)
from typing import Dict, Any, List, Optional
import json

# Create the integration using the config.json
zoho = Integration.load()

# ---- Helper Functions ----

def build_zoho_headers(context: ExecutionContext) -> Dict[str, str]:
    """Build headers for Zoho API requests with OAuth token."""
    access_token = context.auth['credentials']['access_token']
    return {
        "Authorization": f"Zoho-oauthtoken {access_token}",
        "Content-Type": "application/json"
    }

def get_zoho_api_url(context: ExecutionContext, endpoint: str = "") -> str:
    """Build Zoho CRM API URL using the region-specific api_domain from context."""
    # Get api_domain from credentials (e.g., "https://www.zohoapis.com", "https://www.zohoapis.eu")
    # Use 'or' to handle empty strings as well as None/missing keys
    api_domain = context.auth['credentials'].get('api_domain') or 'https://www.zohoapis.com'
    # Strip trailing slash if present
    api_domain = api_domain.rstrip('/')
    base_url = f"{api_domain}/crm/v8"
    return f"{base_url}{endpoint}"

def build_contact_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build contact data object from inputs, filtering out empty values."""
    contact_data = {}
    
    # Map of input fields to Zoho API field names
    field_mapping = {
        "Last_Name": "Last_Name",
        "First_Name": "First_Name", 
        "Email": "Email",
        "Phone": "Phone",
        "Mobile": "Mobile",
        "Account_Name": "Account_Name",
        "Title": "Title",
        "Department": "Department",
        "Mailing_Street": "Mailing_Street",
        "Mailing_City": "Mailing_City",
        "Mailing_State": "Mailing_State",
        "Mailing_Zip": "Mailing_Zip",
        "Mailing_Country": "Mailing_Country",
        "Description": "Description"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            contact_data[api_field] = inputs[input_field]
    
    return contact_data

def build_account_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build account data object from inputs, filtering out empty values."""
    account_data = {}
    
    # Map of input fields to Zoho API field names for Accounts
    field_mapping = {
        "Account_Name": "Account_Name",
        "Account_Type": "Account_Type",
        "Industry": "Industry",
        "Annual_Revenue": "Annual_Revenue",
        "No_of_Employees": "Employees",
        "Phone": "Phone",
        "Fax": "Fax",
        "Website": "Website",
        "Billing_Street": "Billing_Street",
        "Billing_City": "Billing_City",
        "Billing_State": "Billing_State",
        "Billing_Code": "Billing_Code",
        "Billing_Country": "Billing_Country",
        "Shipping_Street": "Shipping_Street",
        "Shipping_City": "Shipping_City",
        "Shipping_State": "Shipping_State",
        "Shipping_Code": "Shipping_Code",
        "Shipping_Country": "Shipping_Country",
        "Description": "Description"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            account_data[api_field] = inputs[input_field]
    
    return account_data

def build_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add filter parameters
    if 'converted' in inputs and inputs['converted'] != 'both':
        params['converted'] = inputs['converted']
    
    if 'approved' in inputs and inputs['approved'] != 'both':
        params['approved'] = inputs['approved']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default contact fields when none specified
        default_fields = [
            'First_Name', 'Last_Name', 'Email', 'Phone', 'Mobile', 
            'Account_Name', 'Department', 'Title'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_account_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for account list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add filter parameters
    if 'converted' in inputs and inputs['converted'] != 'both':
        params['converted'] = inputs['converted']
    
    if 'approved' in inputs and inputs['approved'] != 'both':
        params['approved'] = inputs['approved']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default account fields when none specified
        default_fields = [
            'Account_Name', 'Account_Type', 'Industry', 'Annual_Revenue',
            'Employees', 'Phone', 'Website', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_deal_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build deal data object from inputs, filtering out empty values."""
    deal_data = {}
    
    # Map of input fields to Zoho API field names for Deals
    field_mapping = {
        "Deal_Name": "Deal_Name",
        "Stage": "Stage",
        "Pipeline": "Pipeline",
        "Amount": "Amount",
        "Probability": "Probability",
        "Closing_Date": "Closing_Date",
        "Account_Name": "Account_Name",
        "Contact_Name": "Contact_Name",
        "Type": "Type",
        "Lead_Source": "Lead_Source",
        "Next_Step": "Next_Step",
        "Description": "Description"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            deal_data[api_field] = inputs[input_field]
    
    return deal_data

def build_deal_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for deal list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add filter parameters
    if 'converted' in inputs and inputs['converted'] != 'both':
        params['converted'] = inputs['converted']
    
    if 'approved' in inputs and inputs['approved'] != 'both':
        params['approved'] = inputs['approved']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default deal fields when none specified
        default_fields = [
            'Deal_Name', 'Stage', 'Amount', 'Probability', 'Closing_Date', 
            'Account_Name', 'Contact_Name', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_lead_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build lead data object from inputs, filtering out empty values."""
    lead_data = {}
    
    # Map of input fields to Zoho API field names for Leads
    field_mapping = {
        "Last_Name": "Last_Name",
        "First_Name": "First_Name",
        "Company": "Company",
        "Email": "Email",
        "Phone": "Phone",
        "Mobile": "Mobile",
        "Title": "Title",
        "Lead_Source": "Lead_Source",
        "Lead_Status": "Lead_Status",
        "Industry": "Industry",
        "Annual_Revenue": "Annual_Revenue",
        "No_of_Employees": "Employees",
        "Website": "Website",
        "Street": "Street",
        "City": "City",
        "State": "State",
        "Zip_Code": "Zip_Code",
        "Country": "Country",
        "Description": "Description"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            lead_data[api_field] = inputs[input_field]
    
    return lead_data

def build_lead_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for lead list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add filter parameters
    if 'converted' in inputs and inputs['converted'] != 'both':
        params['converted'] = inputs['converted']
    
    if 'approved' in inputs and inputs['approved'] != 'both':
        params['approved'] = inputs['approved']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default lead fields when none specified
        default_fields = [
            'Last_Name', 'First_Name', 'Company', 'Email', 'Phone', 
            'Lead_Source', 'Lead_Status', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_task_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build task data object from inputs, filtering out empty values."""
    task_data = {}
    
    # Map of input fields to Zoho API field names for Tasks
    field_mapping = {
        "Subject": "Subject",
        "Status": "Status",
        "Priority": "Priority",
        "Due_Date": "Due_Date",
        "Description": "Description",
        "What_Id": "What_Id",
        "Who_Id": "Who_Id",
        "Reminder": "Reminder"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            task_data[api_field] = inputs[input_field]
    
    return task_data

def build_task_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for task list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add filter parameters
    if 'converted' in inputs and inputs['converted'] != 'both':
        params['converted'] = inputs['converted']
    
    if 'approved' in inputs and inputs['approved'] != 'both':
        params['approved'] = inputs['approved']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default task fields when none specified
        default_fields = [
            'Subject', 'Status', 'Priority', 'Due_Date', 'What_Id', 
            'Who_Id', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_event_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build event data object from inputs, filtering out empty values."""
    event_data = {}
    
    # Map of input fields to Zoho API field names for Events
    field_mapping = {
        "Event_Title": "Event_Title",
        "Start_DateTime": "Start_DateTime",
        "End_DateTime": "End_DateTime",
        "All_day": "All_day",
        "Venue": "Venue",
        "Description": "Description",
        "What_Id": "What_Id",
        "Who_Id": "Who_Id",
        "Remind_At": "Remind_At"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field] is not None:
            event_data[api_field] = inputs[input_field]
    
    return event_data

def build_event_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for event list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default event fields when none specified
        default_fields = [
            'Event_Title', 'Start_DateTime', 'End_DateTime', 'Venue', 
            'What_Id', 'Who_Id', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_call_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build call data object from inputs, filtering out empty values."""
    call_data = {}
    
    # Map of input fields to Zoho API field names for Calls
    field_mapping = {
        "Subject": "Subject",
        "Call_Type": "Call_Type",
        "Call_Start_Time": "Call_Start_Time",
        "Call_Duration": "Call_Duration",
        "Call_Purpose": "Call_Purpose",
        "Call_Agenda": "Call_Agenda",
        "Call_Result": "Call_Result",
        "Outbound_Call_Status": "Outbound_Call_Status",
        "What_Id": "What_Id",
        "Who_Id": "Who_Id",
        "Description": "Description"
    }
    
    # Only include fields that have values
    for input_field, api_field in field_mapping.items():
        if input_field in inputs and inputs[input_field]:
            call_data[api_field] = inputs[input_field]
    
    return call_data

def build_call_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for call list operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add fields parameter - Zoho API requires this parameter
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    else:
        # Default call fields when none specified
        default_fields = [
            'Subject', 'Call_Type', 'Call_Start_Time', 'Call_Duration', 
            'Call_Result', 'What_Id', 'Who_Id', 'Owner'
        ]
        params['fields'] = ','.join(default_fields)
    
    return params

def build_related_records_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for related records operations."""
    params = {}
    
    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add sorting parameters
    if 'sort_by' in inputs and inputs['sort_by']:
        params['sort_by'] = inputs['sort_by']
    
    if 'sort_order' in inputs and inputs['sort_order']:
        params['sort_order'] = inputs['sort_order']
    
    # Add fields parameter if specified
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    
    return params

def get_default_fields_for_module(module: str) -> List[str]:
    """Get default fields for different modules in related records queries."""
    field_mapping = {
        "Contacts": ['First_Name', 'Last_Name', 'Email', 'Phone', 'Title'],
        "Deals": ['Deal_Name', 'Stage', 'Amount', 'Closing_Date'],
        "Tasks": ['Subject', 'Status', 'Priority', 'Due_Date'],
        "Events": ['Event_Title', 'Start_DateTime', 'End_DateTime', 'Venue'],
        "Calls": ['Subject', 'Call_Type', 'Call_Start_Time', 'Call_Duration'],
        "Accounts": ['Account_Name', 'Industry', 'Phone', 'Website'],
        "Leads": ['Last_Name', 'First_Name', 'Company', 'Lead_Status']
    }
    return field_mapping.get(module, ['id'])

def build_search_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build search parameters based on search type."""
    params = {}
    search_type = inputs['search_type']
    
    # Add pagination
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])
    
    if 'per_page' in inputs and inputs['per_page']:
        params['per_page'] = str(inputs['per_page'])
    
    # Add fields
    if 'fields' in inputs and inputs['fields']:
        params['fields'] = ','.join(inputs['fields'])
    
    # Add search-specific parameters
    if search_type == 'criteria' and 'criteria' in inputs:
        # Build criteria string
        criteria_list = []
        for criterion in inputs['criteria']:
            api_name = criterion['api_name']
            comparator = criterion['comparator']
            value = criterion['value']
            
            if isinstance(value, list):
                value_str = ','.join(str(v) for v in value)
            else:
                value_str = str(value)
            
            criteria_list.append(f"({api_name}:{comparator}:{value_str})")
        
        params['criteria'] = ''.join(criteria_list)
    
    elif search_type == 'email' and 'email' in inputs:
        params['email'] = inputs['email']
    
    elif search_type == 'phone' and 'phone' in inputs:
        params['phone'] = inputs['phone']
    
    elif search_type == 'word' and 'word' in inputs:
        params['word'] = inputs['word']
    
    return params

def build_note_data(inputs: Dict[str, Any]) -> Dict[str, Any]:
    """Build note data object from inputs for creating notes."""
    note_data = {}

    # Note_Content is mandatory
    if 'Note_Content' in inputs and inputs['Note_Content']:
        note_data['Note_Content'] = inputs['Note_Content']

    # Note_Title is optional
    if 'Note_Title' in inputs and inputs['Note_Title']:
        note_data['Note_Title'] = inputs['Note_Title']

    # Parent_Id is required for creating notes (when not using module endpoint)
    if 'Parent_Id' in inputs and inputs['Parent_Id']:
        parent_id = inputs['Parent_Id']
        if isinstance(parent_id, dict):
            note_data['Parent_Id'] = parent_id
        else:
            # If just an ID is provided, construct the Parent_Id object
            module = inputs.get('module', 'Contacts')
            note_data['Parent_Id'] = {
                'id': parent_id
            }

    return note_data

def build_notes_query_params(inputs: Dict[str, Any]) -> Dict[str, str]:
    """Build query parameters for notes list operations."""
    params = {}

    # Add pagination parameters
    if 'page' in inputs and inputs['page']:
        params['page'] = str(inputs['page'])

    if 'per_page' in inputs and inputs['per_page']:
        per_page = min(int(inputs['per_page']), 200)  # Max 200 per Zoho API
        params['per_page'] = str(per_page)

    # Add fields parameter
    if 'fields' in inputs and inputs['fields']:
        if isinstance(inputs['fields'], list):
            params['fields'] = ','.join(inputs['fields'])
        else:
            params['fields'] = inputs['fields']

    return params

# ---- Action Handlers ----

@zoho.action("create_contact")
class CreateContact(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Contacts")
            
            # Build contact data
            contact_data = build_contact_data(inputs)
            
            # Create request payload
            payload = {
                "data": [contact_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                contact_result = response["data"][0]
                
                if contact_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "contact": {
                            "id": contact_result.get("details", {}).get("id", ""),
                            "details": contact_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "contact": {},
                        "result": False,
                        "error": contact_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "contact": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contact": {},
                "result": False,
                "error": f"Error creating contact: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_contact")
class GetContact(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            contact_id = inputs["contact_id"]
            url = get_zoho_api_url(context, f"/Contacts/{contact_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                contact_data = response["data"][0]
                return ActionResult(data={

                    "contact": contact_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "contact": {},
                    "result": False,
                    "error": "Contact not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contact": {},
                "result": False,
                "error": f"Error retrieving contact: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_contact")
class UpdateContact(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            contact_id = inputs["contact_id"]
            url = get_zoho_api_url(context, f"/Contacts/{contact_id}")
            
            # Build contact data (excluding contact_id)
            contact_inputs = {k: v for k, v in inputs.items() if k != "contact_id"}
            contact_data = build_contact_data(contact_inputs)
            
            # Create request payload
            payload = {
                "data": [contact_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                contact_result = response["data"][0]
                
                if contact_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "contact": {
                            "id": contact_result.get("details", {}).get("id", contact_id),
                            "details": contact_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "contact": {},
                        "result": False,
                        "error": contact_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "contact": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contact": {},
                "result": False,
                "error": f"Error updating contact: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_contact")
class DeleteContact(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            contact_id = inputs["contact_id"]
            url = get_zoho_api_url(context, f"/Contacts/{contact_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", contact_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting contact: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_contacts")
class ListContacts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Contacts")
            
            # Build query parameters
            params = build_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            contacts = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "contacts": contacts,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contacts": [],
                "info": {},
                "result": False,
                "error": f"Error listing contacts: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_contacts")
class SearchContacts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Contacts/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            contacts = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "contacts": contacts,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contacts": [],
                "info": {},
                "result": False,
                "error": f"Error searching contacts: {str(e)}"
            }, cost_usd=0)

# ---- Account Action Handlers ----

@zoho.action("create_account")
class CreateAccount(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Accounts")
            
            # Build account data
            account_data = build_account_data(inputs)
            
            # Create request payload
            payload = {
                "data": [account_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                account_result = response["data"][0]
                
                if account_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "account": {
                            "id": account_result.get("details", {}).get("id", ""),
                            "details": account_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "account": {},
                        "result": False,
                        "error": account_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "account": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "account": {},
                "result": False,
                "error": f"Error creating account: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_account")
class GetAccount(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            account_id = inputs["account_id"]
            url = get_zoho_api_url(context, f"/Accounts/{account_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default account fields
                default_fields = [
                    'Account_Name', 'Account_Type', 'Industry', 'Annual_Revenue',
                    'Employees', 'Phone', 'Website', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                account_data = response["data"][0]
                return ActionResult(data={

                    "account": account_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "account": {},
                    "result": False,
                    "error": "Account not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "account": {},
                "result": False,
                "error": f"Error retrieving account: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_account")
class UpdateAccount(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            account_id = inputs["account_id"]
            url = get_zoho_api_url(context, f"/Accounts/{account_id}")
            
            # Build account data (excluding account_id)
            account_inputs = {k: v for k, v in inputs.items() if k != "account_id"}
            account_data = build_account_data(account_inputs)
            
            # Create request payload
            payload = {
                "data": [account_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                account_result = response["data"][0]
                
                if account_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "account": {
                            "id": account_result.get("details", {}).get("id", account_id),
                            "details": account_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "account": {},
                        "result": False,
                        "error": account_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "account": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "account": {},
                "result": False,
                "error": f"Error updating account: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_account")
class DeleteAccount(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            account_id = inputs["account_id"]
            url = get_zoho_api_url(context, f"/Accounts/{account_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", account_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting account: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_accounts")
class ListAccounts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Accounts")
            
            # Build query parameters
            params = build_account_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            accounts = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "accounts": accounts,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "accounts": [],
                "info": {},
                "result": False,
                "error": f"Error listing accounts: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_accounts")
class SearchAccounts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Accounts/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            accounts = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "accounts": accounts,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "accounts": [],
                "info": {},
                "result": False,
                "error": f"Error searching accounts: {str(e)}"
            }, cost_usd=0)

# ---- Deal Action Handlers ----

@zoho.action("create_deal")
class CreateDeal(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Deals")
            
            # Build deal data
            deal_data = build_deal_data(inputs)
            
            # Create request payload
            payload = {
                "data": [deal_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                deal_result = response["data"][0]
                
                if deal_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "deal": {
                            "id": deal_result.get("details", {}).get("id", ""),
                            "details": deal_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "deal": {},
                        "result": False,
                        "error": deal_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "deal": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deal": {},
                "result": False,
                "error": f"Error creating deal: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_deal")
class GetDeal(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            deal_id = inputs["deal_id"]
            url = get_zoho_api_url(context, f"/Deals/{deal_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default deal fields
                default_fields = [
                    'Deal_Name', 'Stage', 'Pipeline', 'Amount', 'Probability', 'Closing_Date',
                    'Account_Name', 'Contact_Name', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                deal_data = response["data"][0]
                return ActionResult(data={

                    "deal": deal_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "deal": {},
                    "result": False,
                    "error": "Deal not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deal": {},
                "result": False,
                "error": f"Error retrieving deal: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_deal")
class UpdateDeal(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            deal_id = inputs["deal_id"]
            url = get_zoho_api_url(context, f"/Deals/{deal_id}")
            
            # Build deal data (excluding deal_id)
            deal_inputs = {k: v for k, v in inputs.items() if k != "deal_id"}
            deal_data = build_deal_data(deal_inputs)
            
            # Create request payload
            payload = {
                "data": [deal_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                deal_result = response["data"][0]
                
                if deal_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "deal": {
                            "id": deal_result.get("details", {}).get("id", deal_id),
                            "details": deal_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "deal": {},
                        "result": False,
                        "error": deal_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "deal": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deal": {},
                "result": False,
                "error": f"Error updating deal: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_deal")
class DeleteDeal(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            deal_id = inputs["deal_id"]
            url = get_zoho_api_url(context, f"/Deals/{deal_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", deal_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting deal: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_deals")
class ListDeals(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Deals")
            
            # Build query parameters
            params = build_deal_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            deals = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "deals": deals,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deals": [],
                "info": {},
                "result": False,
                "error": f"Error listing deals: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_deals")
class SearchDeals(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Deals/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            deals = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "deals": deals,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deals": [],
                "info": {},
                "result": False,
                "error": f"Error searching deals: {str(e)}"
            }, cost_usd=0)

# ---- Lead Action Handlers ----

@zoho.action("create_lead")
class CreateLead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Leads")
            
            # Build lead data
            lead_data = build_lead_data(inputs)
            
            # Create request payload
            payload = {
                "data": [lead_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                lead_result = response["data"][0]
                
                if lead_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "lead": {
                            "id": lead_result.get("details", {}).get("id", ""),
                            "details": lead_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "lead": {},
                        "result": False,
                        "error": lead_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "lead": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "lead": {},
                "result": False,
                "error": f"Error creating lead: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_lead")
class GetLead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            lead_id = inputs["lead_id"]
            url = get_zoho_api_url(context, f"/Leads/{lead_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default lead fields
                default_fields = [
                    'Last_Name', 'First_Name', 'Full_Name', 'Company', 'Email', 'Phone',
                    'Lead_Source', 'Lead_Status', 'Title', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                lead_data = response["data"][0]
                return ActionResult(data={

                    "lead": lead_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "lead": {},
                    "result": False,
                    "error": "Lead not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "lead": {},
                "result": False,
                "error": f"Error retrieving lead: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_lead")
class UpdateLead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            lead_id = inputs["lead_id"]
            url = get_zoho_api_url(context, f"/Leads/{lead_id}")
            
            # Build lead data (excluding lead_id)
            lead_inputs = {k: v for k, v in inputs.items() if k != "lead_id"}
            lead_data = build_lead_data(lead_inputs)
            
            # Create request payload
            payload = {
                "data": [lead_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                lead_result = response["data"][0]
                
                if lead_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "lead": {
                            "id": lead_result.get("details", {}).get("id", lead_id),
                            "details": lead_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "lead": {},
                        "result": False,
                        "error": lead_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "lead": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "lead": {},
                "result": False,
                "error": f"Error updating lead: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_lead")
class DeleteLead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            lead_id = inputs["lead_id"]
            url = get_zoho_api_url(context, f"/Leads/{lead_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", lead_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting lead: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_leads")
class ListLeads(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Leads")
            
            # Build query parameters
            params = build_lead_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            leads = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "leads": leads,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "leads": [],
                "info": {},
                "result": False,
                "error": f"Error listing leads: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_leads")
class SearchLeads(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Leads/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            leads = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "leads": leads,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "leads": [],
                "info": {},
                "result": False,
                "error": f"Error searching leads: {str(e)}"
            }, cost_usd=0)

@zoho.action("convert_lead")
class ConvertLead(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            lead_id = inputs["lead_id"]
            url = get_zoho_api_url(context, f"/Leads/{lead_id}/actions/convert")
            
            # Build conversion payload - Zoho API requires "data" array format
            conversion_data = {}
            
            # Add deal creation if requested
            if inputs.get("create_deal", False):
                deal_data = {}
                if "deal_name" in inputs:
                    deal_data["Deal_Name"] = inputs["deal_name"]
                if "deal_stage" in inputs:
                    deal_data["Stage"] = inputs["deal_stage"]
                if "deal_amount" in inputs:
                    deal_data["Amount"] = inputs["deal_amount"]
                if "closing_date" in inputs:
                    deal_data["Closing_Date"] = inputs["closing_date"]
                
                conversion_data["Deals"] = deal_data
            
            # Add conversion options
            if "overwrite" in inputs:
                conversion_data["overwrite"] = inputs["overwrite"]
            if "notify_lead_owner" in inputs:
                conversion_data["notify_lead_owner"] = inputs["notify_lead_owner"]
            if "move_attachments_to" in inputs:
                conversion_data["move_attachments_to"] = {"api_name": inputs["move_attachments_to"]}
            if "assign_to" in inputs:
                conversion_data["assign_to"] = {"id": inputs["assign_to"]}
            if "carry_over_tags" in inputs:
                conversion_data["carry_over_tags"] = inputs["carry_over_tags"]
            
            # Wrap in required "data" array format
            payload = {
                "data": [conversion_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                conversion_result = response["data"][0]
                
                if conversion_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "conversion": {
                            "account": conversion_result.get("Accounts"),
                            "contact": conversion_result.get("Contacts"),
                            "deal": conversion_result.get("Deals")
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "conversion": {},
                        "result": False,
                        "error": conversion_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "conversion": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "conversion": {},
                "result": False,
                "error": f"Error converting lead: {str(e)}"
            }, cost_usd=0)

# ---- Task Action Handlers ----

@zoho.action("create_task")
class CreateTask(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Tasks")
            
            # Build task data
            task_data = build_task_data(inputs)
            
            # Create request payload
            payload = {
                "data": [task_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                task_result = response["data"][0]
                
                if task_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "task": {
                            "id": task_result.get("details", {}).get("id", ""),
                            "details": task_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "task": {},
                        "result": False,
                        "error": task_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "task": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "task": {},
                "result": False,
                "error": f"Error creating task: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_task")
class GetTask(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            task_id = inputs["task_id"]
            url = get_zoho_api_url(context, f"/Tasks/{task_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default task fields
                default_fields = [
                    'Subject', 'Status', 'Priority', 'Due_Date', 'Description',
                    'What_Id', 'Who_Id', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                task_data = response["data"][0]
                return ActionResult(data={

                    "task": task_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "task": {},
                    "result": False,
                    "error": "Task not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "task": {},
                "result": False,
                "error": f"Error retrieving task: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_task")
class UpdateTask(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            task_id = inputs["task_id"]
            url = get_zoho_api_url(context, f"/Tasks/{task_id}")
            
            # Build task data (excluding task_id)
            task_inputs = {k: v for k, v in inputs.items() if k != "task_id"}
            task_data = build_task_data(task_inputs)
            
            # Create request payload
            payload = {
                "data": [task_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                task_result = response["data"][0]
                
                if task_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "task": {
                            "id": task_result.get("details", {}).get("id", task_id),
                            "details": task_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "task": {},
                        "result": False,
                        "error": task_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "task": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "task": {},
                "result": False,
                "error": f"Error updating task: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_task")
class DeleteTask(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            task_id = inputs["task_id"]
            url = get_zoho_api_url(context, f"/Tasks/{task_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", task_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting task: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_tasks")
class ListTasks(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Tasks")
            
            # Build query parameters
            params = build_task_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            tasks = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "tasks": tasks,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "tasks": [],
                "info": {},
                "result": False,
                "error": f"Error listing tasks: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_tasks")
class SearchTasks(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Tasks/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            tasks = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "tasks": tasks,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "tasks": [],
                "info": {},
                "result": False,
                "error": f"Error searching tasks: {str(e)}"
            }, cost_usd=0)

# ---- Event Action Handlers ----

@zoho.action("create_event")
class CreateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Events")
            
            # Build event data
            event_data = build_event_data(inputs)
            
            # Create request payload
            payload = {
                "data": [event_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                event_result = response["data"][0]
                
                if event_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "event": {
                            "id": event_result.get("details", {}).get("id", ""),
                            "details": event_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "event": {},
                        "result": False,
                        "error": event_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "event": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "event": {},
                "result": False,
                "error": f"Error creating event: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_event")
class GetEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            event_id = inputs["event_id"]
            url = get_zoho_api_url(context, f"/Events/{event_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default event fields
                default_fields = [
                    'Event_Title', 'Start_DateTime', 'End_DateTime', 'All_day', 'Venue',
                    'Description', 'What_Id', 'Who_Id', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                event_data = response["data"][0]
                return ActionResult(data={

                    "event": event_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "event": {},
                    "result": False,
                    "error": "Event not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "event": {},
                "result": False,
                "error": f"Error retrieving event: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_event")
class UpdateEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            event_id = inputs["event_id"]
            url = get_zoho_api_url(context, f"/Events/{event_id}")
            
            # Build event data (excluding event_id)
            event_inputs = {k: v for k, v in inputs.items() if k != "event_id"}
            event_data = build_event_data(event_inputs)
            
            # Create request payload
            payload = {
                "data": [event_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                event_result = response["data"][0]
                
                if event_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "event": {
                            "id": event_result.get("details", {}).get("id", event_id),
                            "details": event_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "event": {},
                        "result": False,
                        "error": event_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "event": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "event": {},
                "result": False,
                "error": f"Error updating event: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_event")
class DeleteEvent(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            event_id = inputs["event_id"]
            url = get_zoho_api_url(context, f"/Events/{event_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", event_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting event: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_events")
class ListEvents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Events")
            
            # Build query parameters
            params = build_event_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            events = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "events": events,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "events": [],
                "info": {},
                "result": False,
                "error": f"Error listing events: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_events")
class SearchEvents(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Events/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            events = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "events": events,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "events": [],
                "info": {},
                "result": False,
                "error": f"Error searching events: {str(e)}"
            }, cost_usd=0)

# ---- Call Action Handlers ----

@zoho.action("create_call")
class CreateCall(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Calls")
            
            # Build call data
            call_data = build_call_data(inputs)
            
            # Create request payload
            payload = {
                "data": [call_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                call_result = response["data"][0]
                
                if call_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "call": {
                            "id": call_result.get("details", {}).get("id", ""),
                            "details": call_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "call": {},
                        "result": False,
                        "error": call_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "call": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "call": {},
                "result": False,
                "error": f"Error creating call: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_call")
class GetCall(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            call_id = inputs["call_id"]
            url = get_zoho_api_url(context, f"/Calls/{call_id}")
            
            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                params['fields'] = ','.join(inputs['fields'])
            else:
                # Default call fields
                default_fields = [
                    'Subject', 'Call_Type', 'Call_Start_Time', 'Call_Duration', 'Call_Purpose',
                    'Call_Result', 'What_Id', 'Who_Id', 'Owner', 'Created_Time', 'Modified_Time'
                ]
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                call_data = response["data"][0]
                return ActionResult(data={

                    "call": call_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "call": {},
                    "result": False,
                    "error": "Call not found"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "call": {},
                "result": False,
                "error": f"Error retrieving call: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_call")
class UpdateCall(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            call_id = inputs["call_id"]
            url = get_zoho_api_url(context, f"/Calls/{call_id}")
            
            # Build call data (excluding call_id)
            call_inputs = {k: v for k, v in inputs.items() if k != "call_id"}
            call_data = build_call_data(call_inputs)
            
            # Create request payload
            payload = {
                "data": [call_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                call_result = response["data"][0]
                
                if call_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "call": {
                            "id": call_result.get("details", {}).get("id", call_id),
                            "details": call_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "call": {},
                        "result": False,
                        "error": call_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "call": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "call": {},
                "result": False,
                "error": f"Error updating call: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_call")
class DeleteCall(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            call_id = inputs["call_id"]
            url = get_zoho_api_url(context, f"/Calls/{call_id}")
            
            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]
                
                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "details": {
                            "id": delete_result.get("details", {}).get("id", call_id)
                        }
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "details": {},
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "details": {},
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "result": False,
                "details": {},
                "error": f"Error deleting call: {str(e)}"
            }, cost_usd=0)

@zoho.action("list_calls")
class ListCalls(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Calls")
            
            # Build query parameters
            params = build_call_query_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            calls = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "calls": calls,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "calls": [],
                "info": {},
                "result": False,
                "error": f"Error listing calls: {str(e)}"
            }, cost_usd=0)

@zoho.action("search_calls")
class SearchCalls(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/Calls/search")
            
            # Build query parameters based on search type
            params = build_search_params(inputs)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            calls = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "calls": calls,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "calls": [],
                "info": {},
                "result": False,
                "error": f"Error searching calls: {str(e)}"
            }, cost_usd=0)

# ---- Related Records Action Handlers ----

@zoho.action("get_related_records")
class GetRelatedRecords(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            module = inputs["module"]
            record_id = inputs["record_id"]
            related_module = inputs["related_module"]
            
            url = get_zoho_api_url(context, f"/{module}/{record_id}/{related_module}")
            
            # Build query parameters
            params = build_related_records_params(inputs)
            
            # Add default fields if not specified
            if 'fields' not in inputs or not inputs['fields']:
                default_fields = get_default_fields_for_module(related_module)
                params['fields'] = ','.join(default_fields)
            
            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )
            
            # Process response
            related_records = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "related_records": related_records,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "related_records": [],
                "info": {},
                "result": False,
                "error": f"Error getting related records: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_account_hierarchy")
class GetAccountHierarchy(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            account_id = inputs["account_id"]
            include_modules = inputs.get("include_modules", ["Contacts", "Deals", "Tasks", "Events", "Calls"])
            
            # Get the account details first
            account_url = get_zoho_api_url(context, f"/Accounts/{account_id}")
            account_response = await context.fetch(
                account_url,
                method="GET",
                headers=headers,
                params={"fields": "Account_Name,Industry,Phone,Website,Owner"}
            )
            
            account_data = account_response.get("data", [{}])[0] if account_response.get("data") else {}
            
            # Initialize hierarchy data
            hierarchy = {
                "account": account_data,
                "contacts": [],
                "deals": [],
                "tasks": [],
                "events": [],
                "calls": []
            }
            
            # Fetch related records for each requested module
            for module in include_modules:
                try:
                    related_url = get_zoho_api_url(context, f"/Accounts/{account_id}/{module}")
                    default_fields = get_default_fields_for_module(module)
                    
                    related_response = await context.fetch(
                        related_url,
                        method="GET",
                        headers=headers,
                        params={"fields": ','.join(default_fields), "per_page": "50"}
                    )
                    
                    related_data = related_response.get("data", [])
                    hierarchy[module.lower()] = related_data
                    
                except Exception:
                    # If a related module fails, continue with others
                    hierarchy[module.lower()] = []
            
            return ActionResult(data={

                **hierarchy,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "account": {},
                "contacts": [],
                "deals": [],
                "tasks": [],
                "events": [],
                "calls": [],
                "result": False,
                "error": f"Error getting account hierarchy: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_contact_activities")
class GetContactActivities(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            contact_id = inputs["contact_id"]
            include_modules = inputs.get("include_modules", ["Tasks", "Events", "Calls"])
            
            # Get the contact details first
            contact_url = get_zoho_api_url(context, f"/Contacts/{contact_id}")
            contact_response = await context.fetch(
                contact_url,
                method="GET",
                headers=headers,
                params={"fields": "First_Name,Last_Name,Email,Phone,Account_Name"}
            )
            
            contact_data = contact_response.get("data", [{}])[0] if contact_response.get("data") else {}
            
            # Initialize activities data
            activities = {
                "contact": contact_data,
                "tasks": [],
                "events": [],
                "calls": [],
                "activity_summary": {
                    "total_tasks": 0,
                    "total_events": 0,
                    "total_calls": 0
                }
            }
            
            # Fetch activities for each requested module
            for module in include_modules:
                try:
                    related_url = get_zoho_api_url(context, f"/Contacts/{contact_id}/{module}")
                    default_fields = get_default_fields_for_module(module)
                    
                    related_response = await context.fetch(
                        related_url,
                        method="GET",
                        headers=headers,
                        params={"fields": ','.join(default_fields), "per_page": "100"}
                    )
                    
                    related_data = related_response.get("data", [])
                    activities[module.lower()] = related_data
                    activities["activity_summary"][f"total_{module.lower()}"] = len(related_data)
                    
                except Exception:
                    # If a module fails, continue with others
                    activities[module.lower()] = []
                    activities["activity_summary"][f"total_{module.lower()}"] = 0
            
            return ActionResult(data={

                **activities,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "contact": {},
                "tasks": [],
                "events": [],
                "calls": [],
                "activity_summary": {"total_tasks": 0, "total_events": 0, "total_calls": 0},
                "result": False,
                "error": f"Error getting contact activities: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_deal_relationships")
class GetDealRelationships(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            deal_id = inputs["deal_id"]
            include_activities = inputs.get("include_activities", True)
            
            # Get the deal details first
            deal_url = get_zoho_api_url(context, f"/Deals/{deal_id}")
            deal_response = await context.fetch(
                deal_url,
                method="GET",
                headers=headers,
                params={"fields": "Deal_Name,Stage,Amount,Account_Name,Contact_Name,Owner"}
            )
            
            deal_data = deal_response.get("data", [{}])[0] if deal_response.get("data") else {}
            
            # Initialize relationship data
            relationships = {
                "deal": deal_data,
                "account": None,
                "contact": None,
                "tasks": [],
                "events": [],
                "calls": [],
                "relationship_summary": {
                    "has_account": False,
                    "has_contact": False,
                    "total_activities": 0
                }
            }
            
            # Get related account if available
            if deal_data.get("Account_Name") and isinstance(deal_data["Account_Name"], dict):
                account_id = deal_data["Account_Name"].get("id")
                if account_id:
                    try:
                        account_url = get_zoho_api_url(context, f"/Accounts/{account_id}")
                        account_response = await context.fetch(
                            account_url,
                            method="GET",
                            headers=headers,
                            params={"fields": "Account_Name,Industry,Phone,Website"}
                        )
                        relationships["account"] = account_response.get("data", [{}])[0]
                        relationships["relationship_summary"]["has_account"] = True
                    except Exception:
                        pass
            
            # Get related contact if available
            if deal_data.get("Contact_Name") and isinstance(deal_data["Contact_Name"], dict):
                contact_id = deal_data["Contact_Name"].get("id")
                if contact_id:
                    try:
                        contact_url = get_zoho_api_url(context, f"/Contacts/{contact_id}")
                        contact_response = await context.fetch(
                            contact_url,
                            method="GET",
                            headers=headers,
                            params={"fields": "First_Name,Last_Name,Email,Phone,Title"}
                        )
                        relationships["contact"] = contact_response.get("data", [{}])[0]
                        relationships["relationship_summary"]["has_contact"] = True
                    except Exception:
                        pass
            
            # Get activities if requested
            if include_activities:
                activity_modules = ["Tasks", "Events", "Calls"]
                total_activities = 0
                
                for module in activity_modules:
                    try:
                        activity_url = get_zoho_api_url(context, f"/Deals/{deal_id}/{module}")
                        default_fields = get_default_fields_for_module(module)
                        
                        activity_response = await context.fetch(
                            activity_url,
                            method="GET",
                            headers=headers,
                            params={"fields": ','.join(default_fields), "per_page": "50"}
                        )
                        
                        activity_data = activity_response.get("data", [])
                        relationships[module.lower()] = activity_data
                        total_activities += len(activity_data)
                        
                    except Exception:
                        relationships[module.lower()] = []
                
                relationships["relationship_summary"]["total_activities"] = total_activities
            
            return ActionResult(data={

                **relationships,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "deal": {},
                "account": None,
                "contact": None,
                "tasks": [],
                "events": [],
                "calls": [],
                "relationship_summary": {"has_account": False, "has_contact": False, "total_activities": 0},
                "result": False,
                "error": f"Error getting deal relationships: {str(e)}"
            }, cost_usd=0)

@zoho.action("execute_coql_query")
class ExecuteCOQLQuery(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            url = get_zoho_api_url(context, "/coql")
            
            # Build COQL request payload
            payload = {
                "select_query": inputs["select_query"]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )
            
            # Process response
            data = response.get("data", [])
            info = response.get("info", {})
            
            return ActionResult(data={

                "data": data,
                "info": info,
                "result": True
            }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "data": [],
                "info": {},
                "result": False,
                "error": f"Error executing COQL query: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_related_records")
class UpdateRelatedRecords(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            module = inputs["module"]
            record_id = inputs["record_id"]
            related_module = inputs["related_module"]
            related_record_id = inputs["related_record_id"]
            update_data = inputs["update_data"]
            
            url = get_zoho_api_url(context, f"/{module}/{record_id}/{related_module}/{related_record_id}")
            
            # Create request payload
            payload = {
                "data": [update_data]
            }
            
            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )
            
            # Process response
            if response.get("data") and len(response["data"]) > 0:
                update_result = response["data"][0]
                
                if update_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "updated_record": update_result.get("details", {}),
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "updated_record": {},
                        "result": False,
                        "error": update_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "updated_record": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)
                
        except Exception as e:
            return ActionResult(data={

                "updated_record": {},
                "result": False,
                "error": f"Error updating related record: {str(e)}"
            }, cost_usd=0)

@zoho.action("create_note")
class CreateNote(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            module = inputs["module"]
            record_id = inputs["record_id"]
            url = get_zoho_api_url(context, f"/{module}/{record_id}/Notes")

            # Build note data
            note_data = {
                "Note_Content": inputs["Note_Content"]
            }

            if 'Note_Title' in inputs and inputs['Note_Title']:
                note_data['Note_Title'] = inputs['Note_Title']

            # Create request payload
            payload = {
                "data": [note_data]
            }

            # Make API request
            response = await context.fetch(
                url,
                method="POST",
                headers=headers,
                json=payload
            )

            # Process response
            if response.get("data") and len(response["data"]) > 0:
                note_result = response["data"][0]

                if note_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "note": {
                            "id": note_result.get("details", {}).get("id", ""),
                            "details": note_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "note": {},
                        "result": False,
                        "error": note_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "note": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)

        except Exception as e:
            return ActionResult(data={

                "note": {},
                "result": False,
                "error": f"Error creating note: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_contact_notes")
class GetContactNotes(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            module = inputs["module"]
            record_id = inputs["record_id"]
            url = get_zoho_api_url(context, f"/{module}/{record_id}/Notes")

            # Build query parameters
            params = build_notes_query_params(inputs)

            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )

            # Process response
            notes_data = response.get("data", [])
            info = response.get("info", {})

            return ActionResult(data={

                "notes": notes_data,
                "info": info,
                "result": True
            }, cost_usd=0)

        except Exception as e:
            return ActionResult(data={

                "notes": [],
                "info": {},
                "result": False,
                "error": f"Error getting record notes: {str(e)}"
            }, cost_usd=0)

@zoho.action("get_note")
class GetNote(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            note_id = inputs["note_id"]
            url = get_zoho_api_url(context, f"/Notes/{note_id}")

            # Build query parameters
            params = {}
            if 'fields' in inputs and inputs['fields']:
                if isinstance(inputs['fields'], list):
                    params['fields'] = ','.join(inputs['fields'])
                else:
                    params['fields'] = inputs['fields']

            # Make API request
            response = await context.fetch(
                url,
                method="GET",
                headers=headers,
                params=params
            )

            # Process response
            if response.get("data") and len(response["data"]) > 0:
                note_data = response["data"][0]
                return ActionResult(data={

                    "note": note_data,
                    "result": True
                }, cost_usd=0)
            else:
                return ActionResult(data={

                    "note": {},
                    "result": False,
                    "error": "Note not found"
                }, cost_usd=0)

        except Exception as e:
            return ActionResult(data={

                "note": {},
                "result": False,
                "error": f"Error getting note: {str(e)}"
            }, cost_usd=0)

@zoho.action("update_note")
class UpdateNote(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            note_id = inputs["note_id"]
            url = get_zoho_api_url(context, f"/Notes/{note_id}")

            # Build update data - only Note_Title and Note_Content can be updated
            update_data = {}

            if 'Note_Title' in inputs and inputs['Note_Title']:
                update_data['Note_Title'] = inputs['Note_Title']

            if 'Note_Content' in inputs and inputs['Note_Content']:
                update_data['Note_Content'] = inputs['Note_Content']

            # Create request payload
            payload = {
                "data": [update_data]
            }

            # Make API request
            response = await context.fetch(
                url,
                method="PUT",
                headers=headers,
                json=payload
            )

            # Process response
            if response.get("data") and len(response["data"]) > 0:
                note_result = response["data"][0]

                if note_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "note": {
                            "id": note_result.get("details", {}).get("id", ""),
                            "details": note_result.get("details", {})
                        },
                        "result": True
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "note": {},
                        "result": False,
                        "error": note_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "note": {},
                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)

        except Exception as e:
            return ActionResult(data={

                "note": {},
                "result": False,
                "error": f"Error updating note: {str(e)}"
            }, cost_usd=0)

@zoho.action("delete_note")
class DeleteNote(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            headers = build_zoho_headers(context)
            note_id = inputs["note_id"]
            url = get_zoho_api_url(context, f"/Notes/{note_id}")

            # Make API request
            response = await context.fetch(
                url,
                method="DELETE",
                headers=headers
            )

            # Process response
            if response.get("data") and len(response["data"]) > 0:
                delete_result = response["data"][0]

                if delete_result.get("code") == "SUCCESS":
                    return ActionResult(data={

                        "result": True,
                        "message": "Note deleted successfully"
                    }, cost_usd=0)
                else:
                    return ActionResult(data={

                        "result": False,
                        "error": delete_result.get("message", "Unknown error occurred")
                    }, cost_usd=0)
            else:
                return ActionResult(data={

                    "result": False,
                    "error": "No response data received"
                }, cost_usd=0)

        except Exception as e:
            return ActionResult(data={

                "result": False,
                "error": f"Error deleting note: {str(e)}"
            }, cost_usd=0)
