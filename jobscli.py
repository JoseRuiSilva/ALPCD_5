import requests
import typer

url = "https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236"

payload = {}
headers = {
  'User-Agent': "ALPCD_5"
}

response = requests.request("GET", url, headers=headers, data=payload)

print(response.json())