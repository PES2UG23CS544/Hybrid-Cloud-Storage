import os
import pickle
import socket
import io
import mysql.connector
from datetime import datetime
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Authenticate Google Drive API
def authenticate():
    creds = None
    if os.path.exists("token.json"):
        with open("token.json", "rb") as token:
            creds = pickle.load(token)
    if not creds or not creds.valid:
        flow = InstalledAppFlow.from_client_secrets_file("client_secret.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "wb") as token:
            pickle.dump(creds, token)
    return creds

creds = authenticate()
drive_service = build("drive", "v3", credentials=creds)

# List files in Google Drive folder
def list_files_in_drive(folder_id):
    query = f"'{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id, name, mimeType, size, createdTime)").execute()
    return results.get("files", [])

# Download file from Google Drive
def download_file(file_id, file_name, save_path):
    request = drive_service.files().get_media(fileId=file_id)
    file_path = os.path.join(save_path, file_name)
    fh = io.FileIO(file_path, 'wb')
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    print(f"✅ Downloaded: {file_name} to {save_path}")

# Fetch metadata from MySQL database
def fetch_metadata():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="hybrid_cloud"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, mime_type, size, created_time, web_view_link FROM file_metadata")
    records = cursor.fetchall()
    cursor.close()
    conn.close()
    return records

# View downloadable files
def view_downloadable_files(folder_id):
    files = list_files_in_drive(folder_id)
    if not files:
        print("❌ No files found.")
        return []
    print("\n📂 Files in Shared Google Drive Folder:")
    for i, file in enumerate(files):
        print(f"{i+1}. {file['name']} | {file['mimeType']} | {file.get('size', 'unknown')} bytes | {file['createdTime']}")
    return files

# Receive metadata over LAN from the specified server IP
def receive_metadata_from_server():
    SERVER_IP = '10.1.17.118'  # Fixed IP Address
    PORT = 6000
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
            client.connect((SERVER_IP, PORT))
            print(f"📡 Connected to server at {SERVER_IP}:{PORT}\n")

            # Receive data in chunks and build complete message
            received_chunks = []
            while True:
                chunk = client.recv(4096)
                if not chunk:
                    break
                received_chunks.append(chunk.decode())

            full_data = ''.join(received_chunks)

            # Display in terminal
            print("\n📥 Received Metadata:\n")
            print("----------- METADATA -----------")
            print(full_data)
            print("--------------------------------")

            # Write to local file
            with open("synced_metadata.txt", "w", encoding="utf-8") as f:
                f.write(full_data)

            print("📄 Metadata saved locally in 'synced_metadata.txt'.")

    except Exception as e:
        print(f"❌ Could not connect to server: {e}")

# Main program loop
def main():
    folder_id = input("Enter the Google Drive Folder ID: ").strip()
    save_path = input("Enter the folder path where you want to save downloads: ").strip()
    while True:
        print("\n=== Hybrid Cloud Downloader ===")
        print("1. View files in Drive folder")
        print("2. Download a file")
        print("3. Receive metadata over LAN")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            view_downloadable_files(folder_id)
        elif choice == '2':
            files = view_downloadable_files(folder_id)
            if files:
                try:
                    index = int(input("Enter the file number to download: ")) - 1
                    if 0 <= index < len(files):
                        file = files[index]
                        download_file(file['id'], file['name'], save_path)
                    else:
                        print("❌ Invalid file number.")
                except ValueError:
                    print("❌ Please enter a valid number.")
        elif choice == '3':
            receive_metadata_from_server()
        elif choice == '4':
            print("👋 Exiting. Farewell, Cap’n!")
            break
        else:
            print("❌ Invalid choice. Try again.")

if __name__ == "__main__":
    main()