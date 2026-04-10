from autohive_integrations_sdk import (
    Integration, ExecutionContext, ActionHandler
)
from typing import Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Create the integration using the config.json
reviews = Integration.load()

# ---- Helper Functions ----

def build_credentials(context: ExecutionContext) -> Credentials:
    """Build Google credentials from ExecutionContext."""
    # Follow Gmail integration pattern: context.auth['credentials']['access_token']
    try:
        access_token = context.auth['credentials']['access_token']
    except (KeyError, TypeError) as e:
        # Debug: print what's actually in context.auth for troubleshooting
        print(f"Debug - context.auth type: {type(context.auth)}")
        print(f"Debug - context.auth content: {context.auth}")
        raise ValueError(f"No access token found in authentication context: {e}")
    
    creds = Credentials(
        token=access_token,
        token_uri='https://oauth2.googleapis.com/token'
    )
    return creds

def build_account_management_service(context: ExecutionContext):
    """Build Account Management service for listing accounts."""
    credentials = build_credentials(context)
    return build('mybusinessaccountmanagement', 'v1', credentials=credentials)

def build_business_info_service(context: ExecutionContext):
    """Build Business Information service (locations)."""
    credentials = build_credentials(context)
    return build('mybusinessbusinessinformation', 'v1', credentials=credentials)

def build_mybusiness_service(context: ExecutionContext):
    """Build My Business API for reviews & replies."""
    credentials = build_credentials(context)
    # Use specific discovery document URL for mybusiness v4 API
    discovery_url = 'https://developers.google.com/static/my-business/samples/mybusiness_google_rest_v4p9.json'
    return build('mybusiness', 'v4', credentials=credentials, discoveryServiceUrl=discovery_url)

def format_address(storefront_address: Dict[str, Any]) -> str:
    """Format address object into readable string."""
    if not storefront_address:
        return ""

    parts = []
    if 'addressLines' in storefront_address:
        parts.extend(storefront_address['addressLines'])
    if 'locality' in storefront_address:
        parts.append(storefront_address['locality'])
    if 'administrativeArea' in storefront_address:
        parts.append(storefront_address['administrativeArea'])
    if 'postalCode' in storefront_address:
        parts.append(storefront_address['postalCode'])

    return ', '.join(parts)


# ---- Action Handlers ----

@reviews.action("list_accounts")
class ListAccounts(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            # Use Account Management API for listing accounts
            service = build_account_management_service(context)
            
            # Call accounts().list() method
            request = service.accounts().list()
            response = request.execute()

            accounts = []
            for account in response.get('accounts', []):
                accounts.append({
                    "name": account.get('name', ''),
                    "accountName": account.get('accountName', ''),
                    "type": account.get('type', '')
                })

            return {
                "accounts": accounts,
                "result": True
            }

        except HttpError as e:
            return {
                "accounts": [],
                "result": False,
                "error": f"Google API error: {str(e)}"
            }
        except Exception as e:
            return {
                "accounts": [],
                "result": False,
                "error": str(e)
            }

@reviews.action("list_locations")
class ListLocations(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_business_info_service(context)
            account_name = inputs['account_name']

            # List locations for the account with required readMask
            # Adding phoneNumbers to complete location data
            read_mask = "name,title,storefrontAddress,phoneNumbers"
            request = service.accounts().locations().list(
                parent=account_name,
                readMask=read_mask
            )
            response = request.execute()

            locations = []
            for location in response.get('locations', []):
                address = format_address(location.get('storefrontAddress', {}))
                
                # Extract address from storefrontAddress if available
                address = format_address(location.get('storefrontAddress', {}))
                
                # Extract primary phone from phoneNumbers
                primary_phone = ''
                phone_numbers = location.get('phoneNumbers', {})
                if phone_numbers:
                    # Try different possible phone field structures
                    if 'primaryPhone' in phone_numbers:
                        primary_phone = phone_numbers['primaryPhone']
                    elif isinstance(phone_numbers, list) and phone_numbers:
                        primary_phone = phone_numbers[0].get('value', '') if isinstance(phone_numbers[0], dict) else str(phone_numbers[0])
                    elif isinstance(phone_numbers, str):
                        primary_phone = phone_numbers
                
                locations.append({
                    "name": location.get('name', ''),
                    "title": location.get('title', ''),
                    "address": address,
                    "primaryPhone": primary_phone
                })

            return {
                "locations": locations,
                "result": True
            }

        except HttpError as e:
            return {
                "locations": [],
                "result": False,
                "error": f"Google API error: {str(e)}"
            }
        except Exception as e:
            return {
                "locations": [],
                "result": False,
                "error": str(e)
            }

@reviews.action("list_reviews")
class ListReviews(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_mybusiness_service(context)
            location_name = inputs['location_name']

            # Validate location_name format
            if not location_name.startswith('accounts/'):
                return {
                    "reviews": [],
                    "result": False,
                    "error": f"Invalid location_name format: '{location_name}'. Expected format: 'accounts/{{account_id}}/locations/{{location_id}}'"
                }

            # List reviews for the location
            request = service.accounts().locations().reviews().list(parent=location_name)
            response = request.execute()

            reviews = []
            for review in response.get('reviews', []):
                reviewer = review.get('reviewer', {})
                reviewer_info = {
                    "displayName": reviewer.get('displayName', 'Anonymous')
                }

                review_reply = None
                if 'reviewReply' in review:
                    review_reply = {
                        "comment": review['reviewReply'].get('comment', ''),
                        "updateTime": review['reviewReply'].get('updateTime', '')
                    }

                review_data = {
                    "name": review.get('name', ''),
                    "reviewId": review.get('reviewId', ''),
                    "reviewer": reviewer_info,
                    "starRating": review.get('starRating', ''),
                    "comment": review.get('comment', ''),
                    "createTime": review.get('createTime', '')
                }

                if review_reply:
                    review_data["reviewReply"] = review_reply

                reviews.append(review_data)

            return {
                "reviews": reviews,
                "result": True
            }

        except HttpError as e:
            return {
                "reviews": [],
                "result": False,
                "error": f"Google API error: {str(e)}"
            }
        except Exception as e:
            return {
                "reviews": [],
                "result": False,
                "error": str(e)
            }

@reviews.action("reply_to_review")
class ReplyToReview(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_mybusiness_service(context)
            review_name = inputs['review_name']
            reply_comment = inputs['reply_comment']

            reply_body = {"comment": reply_comment}

            request = service.accounts().locations().reviews().updateReply(
                name=review_name,
                body=reply_body
            )
            response = request.execute()

            return {
                "reviewReply": {
                    "comment": response.get('comment', ''),
                    "updateTime": response.get('updateTime', '')
                },
                "result": True
            }

        except HttpError as e:
            return {
                "result": False,
                "error": f"Google API error: {str(e)}"
            }
        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }

@reviews.action("delete_review_reply")
class DeleteReviewReply(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_mybusiness_service(context)
            review_name = inputs['review_name']

            request = service.accounts().locations().reviews().deleteReply(name=review_name)
            request.execute()

            return {"result": True}

        except HttpError as e:
            return {
                "result": False,
                "error": f"Google API error: {str(e)}"
            }
        except Exception as e:
            return {
                "result": False,
                "error": str(e)
            }
