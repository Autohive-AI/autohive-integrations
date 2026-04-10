from autohive_integrations_sdk import Integration, ExecutionContext, ActionHandler
from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials

google_sheets = Integration.load()

SPREADSHEET_MIMETYPE = 'application/vnd.google-apps.spreadsheet'


def build_credentials(context: ExecutionContext) -> Credentials:
    access_token = context.auth['credentials']['access_token']
    return Credentials(token=access_token, token_uri='https://oauth2.googleapis.com/token')


def build_sheets_service(context: ExecutionContext):
    creds = build_credentials(context)
    return build('sheets', 'v4', credentials=creds)


def build_drive_service(context: ExecutionContext):
    creds = build_credentials(context)
    return build('drive', 'v3', credentials=creds)


@google_sheets.action("sheets_list_spreadsheets")
class ListSpreadsheets(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            drive = build_drive_service(context)
            q_parts: List[str] = [f"mimeType='{SPREADSHEET_MIMETYPE}'", "trashed=false"]
            name_contains = inputs.get('name_contains')
            owner = inputs.get('owner')
            if name_contains:
                # Escape single quotes in search string
                safe = name_contains.replace("'", "\\'")
                q_parts.append(f"name contains '{safe}'")
            if owner:
                # owner can be 'me' or email
                if owner == 'me':
                    q_parts.append("'me' in owners")
                else:
                    q_parts.append(f"'{owner}' in owners")
            params: Dict[str, Any] = {
                'q': ' and '.join(q_parts),
                'supportsAllDrives': True,
                'includeItemsFromAllDrives': True,
                'fields': 'files(id,name,owners,modifiedTime),nextPageToken'
            }
            if 'pageSize' in inputs:
                params['pageSize'] = inputs['pageSize']
            if 'pageToken' in inputs:
                params['pageToken'] = inputs['pageToken']

            result = drive.files().list(**params).execute()
            response = {
                'files': result.get('files', []),
                'result': True
            }
            next_page = result.get('nextPageToken')
            if isinstance(next_page, str) and next_page:
                response['nextPageToken'] = next_page
            return response
        except HttpError as e:
            return {'files': [], 'result': False, 'error': f'Google Drive API error: {str(e)}'}
        except Exception as e:
            return {'files': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_get_spreadsheet")
class GetSpreadsheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            include_grid = bool(inputs.get('include_grid_data', False))
            request = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                includeGridData=include_grid
            )
            spreadsheet = request.execute()
            return {'spreadsheet': spreadsheet, 'result': True}
        except HttpError as e:
            return {'spreadsheet': {}, 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'spreadsheet': {}, 'result': False, 'error': str(e)}


@google_sheets.action("sheets_list_sheets")
class ListSheets(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            result = service.spreadsheets().get(
                spreadsheetId=spreadsheet_id,
                includeGridData=False,
                fields='sheets(properties(sheetId,title,index,gridProperties(frozenRowCount,frozenColumnCount,rowCount,columnCount)))'
            ).execute()
            sheets_list = [s.get('properties', {}) for s in result.get('sheets', [])]
            return {'sheets': sheets_list, 'result': True}
        except HttpError as e:
            return {'sheets': [], 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'sheets': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_read_range")
class ReadRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            a1 = inputs['range']
            value_render = inputs.get('valueRenderOption')
            dt_render = inputs.get('dateTimeRenderOption')
            params: Dict[str, Any] = {
                'spreadsheetId': spreadsheet_id,
                'range': a1
            }
            if value_render:
                params['valueRenderOption'] = value_render
            if dt_render:
                params['dateTimeRenderOption'] = dt_render
            result = service.spreadsheets().values().get(**params).execute()
            return {
                'range': result.get('range', a1),
                'values': result.get('values', []),
                'result': True
            }
        except HttpError as e:
            return {'range': inputs.get('range'), 'values': [], 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'range': inputs.get('range'), 'values': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_write_range")
class WriteRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            spreadsheet_id = inputs['spreadsheet_id']
            a1 = inputs['range']
            values = inputs['values']
            input_option = inputs.get('inputOption', 'RAW')
            dry_run = bool(inputs.get('dry_run', False))

            if dry_run:
                # Validate by attempting a read of the target range to ensure spreadsheet exists
                service = build_sheets_service(context)
                _ = service.spreadsheets().get(spreadsheetId=spreadsheet_id, includeGridData=False).execute()
                # Estimate cells
                rows = len(values)
                cols = max((len(r) for r in values), default=0)
                return {
                    'updatedRange': a1,
                    'updatedRows': rows,
                    'updatedColumns': cols,
                    'updatedCells': rows * cols,
                    'dryRun': True,
                    'result': True
                }

            service = build_sheets_service(context)
            body = {'values': values}
            result = service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=a1,
                valueInputOption=input_option,
                body=body
            ).execute()
            return {
                'updatedRange': result.get('updatedRange', a1),
                'updatedRows': result.get('updatedRows', 0),
                'updatedColumns': result.get('updatedColumns', 0),
                'updatedCells': result.get('updatedCells', 0),
                'dryRun': False,
                'result': True
            }
        except HttpError as e:
            return {'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'result': False, 'error': str(e)}


@google_sheets.action("sheets_append_rows")
class AppendRows(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            a1 = inputs['range']
            rows = inputs['rows']
            input_option = inputs.get('inputOption', 'RAW')
            body = {'values': rows}
            result = service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=a1,
                valueInputOption=input_option,
                insertDataOption='INSERT_ROWS',
                body=body
            ).execute()
            return {'updates': result.get('updates', result), 'result': True}
        except HttpError as e:
            return {'updates': {}, 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'updates': {}, 'result': False, 'error': str(e)}


@google_sheets.action("sheets_format_range")
class FormatRange(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            sheet_id = inputs['sheetId']
            grid_range = inputs['gridRange']
            style = inputs['style']

            requests = [
                {
                    'repeatCell': {
                        'range': {
                            'sheetId': sheet_id,
                            **grid_range
                        },
                        'cell': {
                            'userEnteredFormat': style
                        },
                        'fields': 'userEnteredFormat'
                    }
                }
            ]
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            return {'replies': result.get('replies', []), 'result': True}
        except HttpError as e:
            return {'replies': [], 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'replies': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_freeze")
class FreezePanes(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            service = build_sheets_service(context)
            spreadsheet_id = inputs['spreadsheet_id']
            sheet_id = inputs['sheetId']
            rows = inputs.get('rows')
            cols = inputs.get('columns')

            update_props: Dict[str, Any] = {'sheetId': sheet_id, 'gridProperties': {}}
            fields: List[str] = []
            if rows is not None:
                update_props['gridProperties']['frozenRowCount'] = rows
                fields.append('gridProperties.frozenRowCount')
            if cols is not None:
                update_props['gridProperties']['frozenColumnCount'] = cols
                fields.append('gridProperties.frozenColumnCount')

            requests = [{
                'updateSheetProperties': {
                    'properties': update_props,
                    'fields': ','.join(fields) if fields else 'gridProperties'
                }
            }]

            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            return {'replies': result.get('replies', []), 'result': True}
        except HttpError as e:
            return {'replies': [], 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'replies': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_batch_update")
class SheetsBatchUpdate(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            spreadsheet_id = inputs['spreadsheet_id']
            requests = inputs['requests']
            dry_run = bool(inputs.get('dry_run', False))

            # Basic validation: ensure it's a list of dicts
            if not isinstance(requests, list) or not all(isinstance(r, dict) for r in requests):
                return {'result': False, 'error': 'requests must be an array of objects'}

            if dry_run:
                # Validate by fetching spreadsheet metadata
                service = build_sheets_service(context)
                _ = service.spreadsheets().get(spreadsheetId=spreadsheet_id, includeGridData=False).execute()
                return {'replies': [], 'dryRun': True, 'result': True}

            service = build_sheets_service(context)
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={'requests': requests}
            ).execute()
            return {'replies': result.get('replies', []), 'dryRun': False, 'result': True}
        except HttpError as e:
            return {'replies': [], 'result': False, 'error': f'Google Sheets API error: {str(e)}'}
        except Exception as e:
            return {'replies': [], 'result': False, 'error': str(e)}


@google_sheets.action("sheets_duplicate_spreadsheet")
class DuplicateSpreadsheet(ActionHandler):
    async def execute(self, inputs: Dict[str, Any], context: ExecutionContext):
        try:
            drive = build_drive_service(context)
            source_id = inputs['source_spreadsheet_id']
            new_title = inputs['new_title']
            body: Dict[str, Any] = {'name': new_title}
            parent_folder_id = inputs.get('parent_folder_id')
            if parent_folder_id:
                body['parents'] = [parent_folder_id]
            result = drive.files().copy(
                fileId=source_id,
                body=body,
                supportsAllDrives=True,
                fields='id,name,mimeType,parents,webViewLink'
            ).execute()
            return {'file_metadata': result, 'result': True}
        except HttpError as e:
            return {'file_metadata': {}, 'result': False, 'error': f'Google Drive API error: {str(e)}'}
        except Exception as e:
            return {'file_metadata': {}, 'result': False, 'error': str(e)}


