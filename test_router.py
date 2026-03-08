"""
Test script for the prompt router.
Runs the 15+ required test messages and generates route_log.jsonl.
"""

import os
import sys

# Ensure we can import app
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import process_message

TEST_MESSAGES = [
    "how do i sort a list of objects in python?",
    "explain this sql query for me",
    "This paragraph sounds awkward, can you help me fix it?",
    "I'm preparing for a job interview, any tips?",
    "what's the average of these numbers: 12, 45, 23, 67, 34",
    "Help me make this better.",
    "I need to write a function that takes a user id and returns their profile, but also i need help with my resume.",
    "hey",
    "Can you write me a poem about clouds?",
    "Rewrite this sentence to be more professional.",
    "I'm not sure what to do with my career.",
    "what is a pivot table",
    "fxi thsi bug pls: for i in range(10) print(i)",
    "How do I structure a cover letter?",
    "My boss says my writing is too verbose.",
]


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY environment variable is required.")
        print("Create a .env file or export OPENAI_API_KEY before running.")
        sys.exit(1)

    print("Running prompt router tests...\n")
    for i, msg in enumerate(TEST_MESSAGES, 1):
        print(f"[{i}/{len(TEST_MESSAGES)}] Input: {msg[:60]}{'...' if len(msg) > 60 else ''}")
        try:
            response = process_message(msg)
            print(f"     Response: {response[:100]}{'...' if len(response) > 100 else ''}\n")
        except Exception as e:
            print(f"     ERROR: {e}\n")

    print("Tests complete. Check route_log.jsonl for logged entries.")


if __name__ == "__main__":
    main()
