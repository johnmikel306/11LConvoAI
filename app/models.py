from flask_pymongo import PyMongo

# Initialize PyMongo
mongo = PyMongo()

class User:
    def __init__(self, username, email):
        self.username = username
        self.email = email

    def save_to_db(self):
        mongo.db.users.insert_one({
            'username': self.username,
            'email': self.email
        })

    @classmethod
    def find_by_username(cls, username):
        user_data = mongo.db.users.find_one({'username': username})
        if user_data:
            return cls(user_data['username'], user_data['email'])
        return None 
