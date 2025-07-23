import requests

url = "https://api.deepseek.com/v1/chat/completions"
headers = {
    "Authorization": "Bearer sk-934228700fb4454f9203a495b02c5ccd",
    "Content-Type": "application/json"
}
data = {
    "model": "deepseek-chat",
    "messages": [
        {"role": "user", "content": "Explain quantum computing in simple terms."}
    ],
    "temperature": 0.7,
    "max_tokens": 200
}

response = requests.post(url, headers=headers, json=data)
print(response.json()["choices"][0]["message"]["content"])
# print(response.json())