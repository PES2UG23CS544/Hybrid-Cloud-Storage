import os
import sys
import pickle
from datetime import datetime
import mysql.connector
import socket
import ssl
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google_auth_oauthlib.flow import InstalledAppFlow

sys.stdout.reconfigure(encoding='utf-8')

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Authentication with Google Drive API
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

# Log metadata into MySQL
def insert_metadata_mysql(file_name, mime_type, size, created_time, web_view_link):
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="hybrid_cloud"
    )
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO file_metadata (file_name, mime_type, size, created_time, web_view_link)
        VALUES (%s, %s, %s, %s, %s)
    """, (file_name, mime_type, size, created_time, web_view_link))
    conn.commit()
    cursor.close()
    conn.close()

# Creating or getting folder on Drive
def create_or_find_folder(folder_name):
    query = f"name = '{folder_name}' and mimeType = 'application/vnd.google-apps.folder'"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    folders = results.get("files", [])
    if folders:
        return folders[0]['id']
    folder_metadata = {"name": folder_name, "mimeType": "application/vnd.google-apps.folder"}
    folder = drive_service.files().create(body=folder_metadata, fields="id").execute()
    return folder["id"]

# Checking if file already exists in Drive
def file_exists_in_drive(file_name, folder_id):
    query = f"name='{file_name}' and '{folder_id}' in parents and trashed=false"
    results = drive_service.files().list(q=query, fields="files(id)").execute()
    return len(results.get("files", [])) > 0

# Uploading file and logging metadata
def upload_to_drive(file_path, folder_id):
    file_name = os.path.basename(file_path)
    if file_exists_in_drive(file_name, folder_id):
        print(f"[SKIPPED] {file_name} already exists in the folder.")
        return
    file_metadata = {"name": file_name, "parents": [folder_id]}
    media = MediaFileUpload(file_path, resumable=True)
    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink, size, createdTime, mimeType"
    ).execute()
    print(f"[UPLOADED] {file_name}")
    print(f"[LINK] {file['webViewLink']}")
    insert_metadata_mysql(
        file_name,
        file['mimeType'],
        int(file.get('size', 0)),
        datetime.strptime(file['createdTime'], "%Y-%m-%dT%H:%M:%S.%fZ"),
        file['webViewLink']
    )

# To view all uploaded metadata
def view_uploaded_metadata():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="root123",
        database="hybrid_cloud"
    )
    cursor = conn.cursor()
    cursor.execute("SELECT file_name, mime_type, size, created_time, web_view_link FROM file_metadata")
    records = cursor.fetchall()
    print("\n[METADATA LOGGED IN MYSQL]:")
    for row in records:
        print(f"- {row[0]} | {row[1]} | {row[2]} bytes | {row[3]} | {row[4]}")
    cursor.close()
    conn.close()

# Fetching the metadata rows for LAN sync
def fetch_all_metadata():
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

# Secure Socket server to sync metadata
def sync_metadata_over_lan():
    HOST = "0.0.0.0"   #DHCP
    PORT = 5000
    CERT_FILE = "cert.pem"
    KEY_FILE = "key.pem"

    try:
        context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.bind((HOST, PORT))
            server.listen(1)
            print(f"\n📡 Server listening securely on port {PORT}...")
            conn, addr = server.accept()
            with context.wrap_socket(conn, server_side=True) as secure_conn:
                print(f"✅ Secure connection established with {addr}")
                rows = fetch_all_metadata()
                if not rows:
                    secure_conn.sendall("⚠ No metadata found to sync.\n".encode())
                else:
                    secure_conn.sendall("📥 SYNCED METADATA:\n".encode())
                    metadata_text = "\n".join([
                        f"{row[0]} | {row[1]} | {row[2]} bytes | {row[3]} | {row[4]}"
                        for row in rows
                    ])
                    secure_conn.sendall(metadata_text.encode())
                print("📤 Metadata sent successfully.")
    except Exception as e:
        print(f"❌ Sync failed: {e}")

# Menu
def main():
    folder_name = "SharedHybridStorage"
    folder_id = create_or_find_folder(folder_name)
    while True:
        print("\n=== Hybrid Cloud Storage Menu ===")
        print("1. Upload a file")
        print("2. View uploaded metadata")
        print("3. Sync metadata over LAN")
        print("4. Exit")
        choice = input("Enter your choice: ")

        if choice == '1':
            path = input("Enter full file path to upload: ").strip().strip('"')
            if os.path.exists(path):
                upload_to_drive(path, folder_id)
            else:
                print("❌ File not found.")

        elif choice == '2':
            view_uploaded_metadata()

        elif choice == '3':
            sync_metadata_over_lan()

        elif choice == '4':
            print("👋 Exiting. Byee, Cap’n!")
            break

        else:
            print("❌ Invalid choice. Try again.")

if _name_ == "_main_":
    creds = authenticate()
    drive_service = build("drive", "v3", credentials=creds)
    main()