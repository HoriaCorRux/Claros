# backend/app.py
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
from api.routes import api_bp
from models.models import db

# Create the Flask app
app = Flask(__name__)

# Configure the database
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://clarostestuser:testpwd1@localhost/clarosdb'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configure JWT
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change this to a secure key in production
jwt = JWTManager(app)

# Initialize the database
db.init_app(app)

# Register the Blueprint
app.register_blueprint(api_bp, url_prefix='/api')

# Create the database tables
with app.app_context():
    db.create_all()

# Run the app
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)