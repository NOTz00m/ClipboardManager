import os
import io
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle

SCOPES = ['https://www.googleapis.com/auth/drive.file']
APP_FOLDER_NAME = 'ClipboardManagerSync'
SYNC_FILENAME = 'clipboard_history.json'


def authenticate_gdrive(token_path, credentials_path='credentials.json'):
    """
    Authenticate with Google Drive and return a service object.
    token_path: where to store the user's OAuth token (pickle file)
    credentials_path: path to the OAuth client credentials JSON
    """
    creds = None
    if os.path.exists(token_path):
        with open(token_path, 'rb') as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(credentials_path):
                raise FileNotFoundError(
                    f"Credentials file '{credentials_path}' not found. Please follow these steps:\n"
                    "1. Go to https://console.cloud.google.com/\n"
                    "2. Create a new project or select an existing one\n"
                    "3. Enable the Google Drive API\n"
                    "4. Go to 'APIs & Services' > 'Credentials'\n"
                    "5. Click 'Create Credentials' > 'OAuth client ID'\n"
                    "6. Choose 'Desktop app' as the application type\n"
                    "7. Download the credentials and save as 'credentials.json' in the app directory"
                )
            try:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                raise Exception(f"Failed to authenticate with Google Drive: {str(e)}")
        with open(token_path, 'wb') as token:
            pickle.dump(creds, token)
    service = build('drive', 'v3', credentials=creds)
    return service


def get_or_create_app_folder(service):
    results = service.files().list(q="mimeType='application/vnd.google-apps.folder' and name='%s' and trashed=false" % APP_FOLDER_NAME,
                                   spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if items:
        return items[0]['id']
    # create folder
    file_metadata = {
        'name': APP_FOLDER_NAME,
        'mimeType': 'application/vnd.google-apps.folder'
    }
    folder = service.files().create(body=file_metadata, fields='id').execute()
    return folder.get('id')


def upload_file(local_path, service, folder_id):
    # check if file exists
    query = f"name='{SYNC_FILENAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    media = MediaFileUpload(local_path, resumable=True)
    if items:
        # update existing file
        file_id = items[0]['id']
        service.files().update(fileId=file_id, media_body=media).execute()
    else:
        # create new file
        file_metadata = {'name': SYNC_FILENAME, 'parents': [folder_id]}
        service.files().create(body=file_metadata, media_body=media, fields='id').execute()


def download_file(local_path, service, folder_id):
    query = f"name='{SYNC_FILENAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    request = service.files().get_media(fileId=file_id)
    fh = io.FileIO(local_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    return True


def delete_file(service, folder_id):
    query = f"name='{SYNC_FILENAME}' and '{folder_id}' in parents and trashed=false"
    results = service.files().list(q=query, spaces='drive', fields='files(id, name)').execute()
    items = results.get('files', [])
    if not items:
        return False
    file_id = items[0]['id']
    service.files().delete(fileId=file_id).execute()
    return True


def unlink_gdrive_token(token_path):
    if os.path.exists(token_path):
        os.remove(token_path) 