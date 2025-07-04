import socket

SERVER_IP = '10.1.4.177'  
PORT = 5000


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client:
    try:
        client.connect((SERVER_IP, PORT))
        print(f"📡 Connected to server at {SERVER_IP}:{PORT}\n")

        received = client.recv(8192).decode()
        print("📥 Received Metadata:")
        print("""\n------------------------------------\n""")
        print(received)
        print("""\n------------------------------------""")

    except Exception as e:
        print(f"❌ Could not connect to server: {e}")



