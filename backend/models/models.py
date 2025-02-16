from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.dialects.postgresql import JSONB

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class DataRecord(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255))  # Store original filename
    data = db.Column(JSONB)  # JSONB field for the data

    def __init__(self, filename, data):
        self.filename = filename
        self.data = data

class DataSetMetadata(db.Model):  # Define the DataSetMetadata model
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), unique=True, nullable=False) # Ensure filename is unique
    schema = db.Column(JSONB)

    def __init__(self, filename, schema):
        self.filename = filename
        self.schema = schema