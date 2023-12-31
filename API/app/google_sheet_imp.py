#!/usr/bin/env python3
import google.auth
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from pathlib import Path
import os.path
import re
import numpy as np
import pandas as pd

# Get credentials from this file
credentials_file = "/home/ubuntu/certificates/google_cloud_credentials/credentials.json"
token_file = "/home/ubuntu/certificates/google_cloud_credentials/token.json"
SERVICE_ACCOUNT_FILE = '/home/ubuntu/certificates/google_cloud_credentials/'

class Document_CRUD():
    """
    
        *add description here explaining what exacly is this*
    
    """
    SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
    def __init__(self, Spreadsheet_ID=None):
        self.Spreadsheet_ID = Spreadsheet_ID
        self.service_ = self.auth()
        self.column_rangeName = "C8:K8"

    def generate_auth_url(self):
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, self.SCOPES)
        flow.redirect_uri = 'http://185.254.206.129/code'  # Your redirect URI

        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true')
        
        return authorization_url

    def exchange_code(self, code):
        flow = InstalledAppFlow.from_client_secrets_file(
            credentials_file, self.SCOPES)
        flow.redirect_uri = 'http://185.254.206.129/code'  # Your redirect URI

        flow.fetch_token(code=code)

        # Save the credentials for the next run
        with open(token_file, "w") as token_file_obj:
            token_file_obj.write(flow.credentials.to_json())

        return flow.credentials

    def auth(self):
        creds = None
        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, self.SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                raise Exception("No valid credentials provided. Run the authorization process.")
        return build("sheets", "v4", credentials=creds)

    def feature_decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HttpError as error:
                print(f"An error occurred: {error}")
                return error
        return wrapper
                       

    def get_sheet_id(self, sheet_name):
        service = self.auth()
        spreadsheet_info = service.spreadsheets().get(spreadsheetId=self.Spreadsheet_ID).execute()
        for sheet in spreadsheet_info['sheets']:
            if sheet['properties']['title'] == sheet_name:
                return sheet['properties']['sheetId']
        return None  # Or handle the case where the sheet name is not found

    @feature_decorator
    def append(self, range_name, value_input_option, values):
        service = self.auth()

        # Append data to the sheet
        body = {"values": values}
        append_result = service.spreadsheets().values().append(
            spreadsheetId=self.Spreadsheet_ID,
            range=range_name,
            valueInputOption=value_input_option,
            insertDataOption="INSERT_ROWS",
            body=body
        ).execute()

        # Calculate the new row indices for borders
        updated_range = append_result.get('updates', {}).get('updatedRange', '')
        start_row_index = self.extract_row_index(updated_range)
        num_rows = append_result.get('updates', {}).get('updatedRows', 0)
        end_row_index = start_row_index + num_rows

        # Assuming you have a valid method to get the sheet ID
        sheet_id = self.get_sheet_id("Your Sheet Name")  # Replace "Your Sheet Name" with the actual sheet name

        # Call function to print the borders
        self.update_border_request(sheet_id, start_row_index, end_row_index, 2, 11)

    

    def update_border_request(self, sheet_id, start_row_index, end_row_index, start_column_index, end_column_index, 
                                    border_style=None, new_title=None):
        if border_style is None:
            border_style = {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0, "alpha": 1}}

        service = self.auth()

        # Initialize requests list
        requests = []

        # Adding border update request
        border_request = {
            "updateBorders": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": start_row_index,
                    "endRowIndex": end_row_index,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": end_column_index
                },
                "top": border_style,
                "bottom": border_style,
                "left": border_style,
                "right": border_style,
                "innerHorizontal": border_style,
                "innerVertical": border_style
            }
        }
        requests.append(border_request)

        # Adding spreadsheet properties update request, if a new title is provided
        if new_title:
            properties_request = {
                "updateSpreadsheetProperties": {
                    "properties": {
                        "title": new_title
                    },
                    "fields": "title"
                }
            }
            requests.append(properties_request)

        # Sending the batch update request
        try:
            result = service.spreadsheets().batchUpdate(
                spreadsheetId=self.Spreadsheet_ID, 
                body={"requests": requests}
            ).execute()

            return result
        except HttpError as error:
            print(f"An error occurred: {error}")
            return error
        
    def extract_row_index(self, range_string):
        # Pattern to match the row number in the range string (e.g., '5' in 'Sheet1!A5:Z5')
        match = re.search(r'(\d+)', range_string.split('!')[1])
        if match:
            return int(match.group(1)) - 1  # Subtract 1 to convert to zero-based index
        else:
            return 0  # Default to 0 if no match is found
    
    @feature_decorator
    def read_excel(self, range_name, enum=False):
        """Read the range and return enumerated if requested, excluding the header."""        
        
        result = (
            self.service_.spreadsheets().values()
            .get(spreadsheetId=self.Spreadsheet_ID, range=range_name)
            .execute()
        )
        try:
            pre_result = result.get('values', [])
        except Exception as e:
            self.send_message(f"An error occurred: {e}")
            return np.array([])
        
        # Check if pre_result is empty and return an empty array if so
        if not pre_result:
            return np.array([])
        
        # Find the maximum number of columns in any row
        max_cols = max(len(row) for row in pre_result)

        # Create a result array with an additional column for enumeration if needed
        n_cols = max_cols + 1 if enum else max_cols
        result_ = np.full((len(pre_result), n_cols), '', dtype=object)

        # Populate the result array
        for i, row in enumerate(pre_result):
            if enum:
                result_[i, 0] = str(i)  # Enumeration column
                end_col = min(len(row) + 1, n_cols)
                result_[i, 1:end_col] = row[:end_col - 1]
            else:
                end_col = min(len(row), n_cols)
                result_[i, :end_col] = row[:end_col]

        return np.array(result_)



    @feature_decorator
    def send_message(self, message, type = "warning", error_message=["An error ocurred"], ):
        range_name = "B4:B5"
        values = [
            [error_message[0]],
            [message]
        ]

        data = [
            {"range": range_name, "values": values}
        ]

        if type == "warning":
            background_color = [252, 186, 3]
        elif type == "error":
            background_color = [252, 3, 3]
        elif type == "message":
            background_color = [61, 252, 3]
        else:
            background_color = [3, 11, 252]

        body = {"valueInputOption": "USER_ENTERED", "data": data}
        result = (
            self.service_.spreadsheets().values()
            .batchUpdate(spreadsheetId=self.Spreadsheet_ID, body=body)
            .execute()
        )
        print(f"{(result.get('totalUpdatedCells'))} cells updated.")

        border_style = {"style": "SOLID", "width": 1, "color": {"red": 0, "green": 0, "blue": 0, "alpha": 1}}
        
        requests = [
            {
                "updateBorders": {
                    "range": {
                        "sheetId": self.get_sheet_id("pau's spreadseet"), 
                        "startRowIndex": 3,  # Adjust as needed
                        "endRowIndex": 5,    # Adjust as needed
                        "startColumnIndex": 1,  # B column
                        "endColumnIndex": 2  # up to but not including C column
                    },
                    "top": border_style,
                    "bottom": border_style,
                    "left": border_style,
                    "right": border_style,
                    "innerHorizontal": border_style,
                    "innerVertical": border_style
                }
            },
            {
                "repeatCell": {
                    "range": {
                        "sheetId": self.get_sheet_id("pau's spreadsheet"),
                        "startRowIndex": 3,  
                        "endRowIndex": 4,
                        "startColumnIndex": 1,  
                        "endColumnIndex": 2
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "backgroundColor": {
                                "red": background_color[0] / 255.0,
                                "green": background_color[1] / 255.0,
                                "blue": background_color[2] / 255.0,
                                "alpha": 1
                            }
                        }
                    },
                    "fields": "userEnteredFormat.backgroundColor"
                }
            }
        ]
        
     
        self.service_.spreadsheets().batchUpdate(
            spreadsheetId=self.Spreadsheet_ID, 
            body={"requests": requests}
        ).execute()


        return result.get('totalUpdatedCells', None)


    def clear_cell_formatting(self):
        sheet_id = self.get_sheet_id("pau's spreadsheet")  # Ensure this returns the correct sheet ID
        # Define the range to clear
        requests = [{
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": 3, 
                    "endRowIndex": 5,   
                    "startColumnIndex": 1,
                    "endColumnIndex": 3    
                },
                "fields": "userEnteredValue,userEnteredFormat.backgroundColor,userEnteredFormat.borders"  # Fields to clear
            }
        }]

        body = {
            "requests": requests
        }

        try:
            # Make the API call to batchUpdate
            response = self.service_.spreadsheets().batchUpdate(
                spreadsheetId=self.Spreadsheet_ID,  # Ensure this is the correct spreadsheet ID
                body=body
            ).execute()
            print(f"Cleared cell formatting: {response}")
        except Exception as e:
            print(f"An error occurred: {e}")

    @feature_decorator
    def get_all_columns_name_and_status(self):
        """
        Get all the column name and if is in italic mode or no

        """

        range_name = "C8:Z8" # Change this as needed
        sheet = self.service_.spreadsheets()
        data_format_result = sheet.get(spreadsheetId=self.Spreadsheet_ID, ranges=range_name,
                   fields='sheets(data(rowData(values(effectiveFormat(textFormat(italic))))))').execute()
        
        result = sheet.values().get(spreadsheetId=self.Spreadsheet_ID, range=range_name).execute().get('values', [])[0]
        
        _result = []
        for i, value in enumerate(data_format_result.get('sheets', [])[0].get('data', [])[0].get('rowData', [])[0].get('values', [])):
            _result.append({
                'value': result[i],
                'is_italic': True if value.get('effectiveFormat', None).get('textFormat', None).get('italic', None) else False
                # We can add more states here as needed 
            })

        return _result
        


if __name__ == "__main__":

    SheetCRUD = Document_CRUD()
    SheetCRUD.Spreadsheet_ID = "1kpj7e08JrhsH4WKJhQeIYXWUh4k4Nc4vKSd-DuZqpVw"

    range_name = "C9:Z9999999"
    result = SheetCRUD.read_excel(range_name, enum=True)
    print(result)
    print(result.shape)

    # result = SheetCRUD.get_all_columns_name_and_status()
    # print(len(result))
    
    # SheetCRUD.Spreadsheet_ID = "1kpj7e08JrhsH4WKJhQeIYXWUh4k4Nc4vKSd-DuZqpVw"
    # # SheetCRUD.auth()
    valueInputOption = "USER_ENTERED"
    range_name = "C19:K10"
    # values = [["Pepero","García Olona","+34 640523319","08901","https://url.com","Mide más de 1.80","Solucionado","Vendido correctamente",""]]
    # SheetCRUD.append(range_name, valueInputOption, final.tolist())