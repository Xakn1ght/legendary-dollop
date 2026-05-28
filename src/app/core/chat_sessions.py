# Dictionary to store active chat sessions
admin_to_user = {}  # {admin_chat_id: user_chat_id}
user_to_admin = {}  # {user_chat_id: admin_chat_id}

# Dictionary to map relayed message IDs for replies
# {new_message_id: original_message_id}
_message_map = {} 