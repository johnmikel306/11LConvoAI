from app import app
from app.services import create_user, get_user_by_username, update_user, delete_user

# Test the CRUD operations
def test_crud_operations():
    with app.app_context():
        # Create a user
        user = create_user('testuser', 'test@example.com')
        print(f'User created: {user.username}, {user.email}')

        # Retrieve the user
        retrieved_user = get_user_by_username('testuser')
        print(f'User retrieved: {retrieved_user.username}, {retrieved_user.email}')

        # Update the user
        updated_user = update_user('testuser', 'newemail@example.com')
        print(f'User updated: {updated_user.username}, {updated_user.email}')

        # Delete the user
        delete_success = delete_user('testuser')
        print(f'User deleted: {delete_success}')

if __name__ == '__main__':
    test_crud_operations()
