#!/bin/bash

# Array of Python code snippets for code runner
code_snippets=(
  'print("Hello World!")
print(2 + 2)'
  'import math
print(f"Pi is {math.pi:.4f}")
print(f"Square root of 16: {math.sqrt(16)}")'
  'numbers = [1, 2, 3, 4, 5]
print(f"Sum: {sum(numbers)}")
print(f"Average: {sum(numbers)/len(numbers)}")'
  'import datetime
now = datetime.datetime.now()
print(f"Current time: {now}")
print(f"Day of week: {now.strftime(\"%A\")}")'
  'data = {"apple": 5, "banana": 3, "orange": 8}
for fruit, count in data.items():
    print(f"{fruit}: {count}")'
  'import random
print(f"Random number: {random.randint(1, 100)}")
print(f"Random choice: {random.choice([\"red\", \"blue\", \"green\"])}")'
  'text = "Hello World"
print(f"Uppercase: {text.upper()}")
print(f"Length: {len(text)}")
print(f"Reversed: {text[::-1]}")'
  'for i in range(5):
    print(f"Number: {i}")
print("Simple loop test")'
  'import json
data = {"name": "test", "value": 42}
json_str = json.dumps(data)
print(f"JSON: {json_str}")
print(f"Parsed back: {json.loads(json_str)}")'
  'def factorial(n):
    return 1 if n <= 1 else n * factorial(n-1)
print(f"Factorial of 5: {factorial(5)}")
print(f"Factorial of 3: {factorial(3)}")'
)

# Select a random code snippet
random_index=$((RANDOM % ${#code_snippets[@]}))
selected_code="${code_snippets[$random_index]}"

# Escape the code for JSON (same approach as e2b script)
escaped_code=$(printf '%s' "$selected_code" | \
  sed 's/\\/\\\\/g' | \
  sed 's/"/\\"/g' | \
  sed 's/	/\\t/g' | \
  awk '{printf "%s\\n", $0}' | \
  sed 's/\\n$//')

curl -w " HTTP_STATUS:%{http_code}\n" -X POST http://localhost:1984/call-tool \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "mcp-server-code-runner_run-code",
    "tool_args": {
      "languageId": "python",
      "code": "'"$escaped_code"'"
    }
  }'
