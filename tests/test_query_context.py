from backend.api.query import _stored_context_chat_history


def test_stored_context_chat_history_prefers_compact_snapshot_history():
    conversation = {
        "turns": [
            {
                "question": "What is a 555 timer?",
                "answer": "# Pretty display answer\n\nLots of Markdown.",
                "responseSnapshot": {
                    "chatHistory": [["What is a 555 timer?", "# Pretty display answer\n\nLots of Markdown."]],
                    "contextChatHistory": [["What is a 555 timer?", "Compact answer for model context."]],
                },
            }
        ]
    }

    assert _stored_context_chat_history(conversation) == [
        ["What is a 555 timer?", "Compact answer for model context."]
    ]


def test_stored_context_chat_history_rebuilds_from_turns_without_snapshot():
    conversation = {
        "turns": [
            {
                "question": "What is pin 3?",
                "answer": "Pin 3 is output.",
            }
        ]
    }

    assert _stored_context_chat_history(conversation) == [["What is pin 3?", "Pin 3 is output."]]

