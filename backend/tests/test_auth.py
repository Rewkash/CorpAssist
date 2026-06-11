import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(client):
    email = 'client@example.com'
    password = 'password123'

    register_response = await client.post(
        '/auth/register',
        json={'email': email, 'password': password, 'role': 'client'},
    )
    assert register_response.status_code == 200
    register_payload = register_response.json()
    assert register_payload['token_type'] == 'bearer'
    assert register_payload['access_token']

    login_response = await client.post(
        '/auth/login',
        json={'email': email, 'password': password},
    )
    assert login_response.status_code == 200
    login_payload = login_response.json()
    assert login_payload['token_type'] == 'bearer'
    assert login_payload['access_token']

    me_response = await client.get(
        '/auth/me',
        headers={'Authorization': f"Bearer {login_payload['access_token']}"},
    )
    assert me_response.status_code == 200
    me_payload = me_response.json()
    assert me_payload['email'] == email
    assert me_payload['role'] == 'client'
    assert me_payload['id'] == 1
