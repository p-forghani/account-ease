from app.models import User


def test_register(client):
    response_get = client.get("/auth/register")
    assert response_get.status_code == 200
    assert b"Register" in response_get.data
    response_post = client.post(
        "/auth/register",
        data={
            'first_name': 'test name',
            'last_name': 'test lastname',
            'email': 't@g.com',
            'password': 'Testpassword1',
            'confirm_password': 'Testpassword1',
        }
    )
    assert response_post.status_code == 302
    user = User.query.filter_by(email='t@g.com').first()
    assert user is not None
    assert user.first_name == 'test name'
    assert user.last_name == 'test lastname'
