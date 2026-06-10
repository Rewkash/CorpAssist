import pytest


async def _register_client(client, email: str = 'client@example.com') -> str:
    response = await client.post(
        '/auth/register',
        json={'email': email, 'password': 'password123', 'role': 'client'},
    )
    assert response.status_code == 200
    return response.json()['access_token']


@pytest.mark.asyncio
async def test_client_chat_smoke_flow(client):
    token = await _register_client(client)
    headers = {'Authorization': f'Bearer {token}'}

    start_response = await client.post('/chat/conversations/start', headers=headers)
    assert start_response.status_code == 200
    conversation = start_response.json()
    assert conversation['id'] == 1
    assert conversation['status'] == 'open'
    assert conversation['client_id'] == 1

    message_text = 'Здравствуйте, нужна помощь с заказом.'
    send_response = await client.post(
        '/chat/messages',
        headers=headers,
        json={'conversation_id': conversation['id'], 'text': message_text},
    )
    assert send_response.status_code == 200
    message = send_response.json()
    assert message['conversation_id'] == conversation['id']
    assert message['sender_id'] == 1
    assert message['text'] == message_text
    assert message['status'] == 'sent'

    messages_response = await client.get(f"/chat/messages/{conversation['id']}", headers=headers)
    assert messages_response.status_code == 200
    messages = messages_response.json()
    assert len(messages) == 1
    assert messages[0]['id'] == message['id']
    assert messages[0]['text'] == message_text

    read_response = await client.post(
        '/chat/messages/read',
        headers=headers,
        json={'conversation_id': conversation['id']},
    )
    assert read_response.status_code == 200
    assert read_response.json() == {'status': 'ok'}
