import requests

url = 'http://127.0.0.1:8000/api/transcript/upload'
files = {'file': ('test.jpg', b'dummy content', 'image/jpeg')}

try:
    response = requests.post(url, files=files)
    print("Status Code:", response.status_code)
    print("Response:", response.text)
except Exception as e:
    print("Error:", e)
