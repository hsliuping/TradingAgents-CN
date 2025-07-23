import openai
openai.api_key = "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"
print(openai.ChatCompletion.create(model="gpt-4-0613", messages=[{"role": "user", "content": "Hello"}]))
