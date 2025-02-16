# backend/api/routes.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
import json

from models.models import db, User, DataRecord, DataSetMetadata
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

import pandas as pd
import os
from sqlalchemy import text

api_bp = Blueprint('api', __name__)
ALLOWED_EXTENSIONS = {'csv', 'xlsx'}


@api_bp.route('/auth/signup', methods=['POST'])
def signup():
    data = request.get_json()
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    if not username or not email or not password:
        return jsonify({"message": "Missing username, email, or password"}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({"message": "Username already exists"}), 400

    if User.query.filter_by(email=email).first():
        return jsonify({"message": "Email already exists"}), 400

    new_user = User(username=username, email=email)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()

    return jsonify({"message": "User created successfully"}), 201

@api_bp.route('/auth/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Missing username or password"}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not user.check_password(password):
        return jsonify({"message": "Invalid username or password"}), 401

    access_token = create_access_token(identity=user.id)
    return jsonify({"access_token": access_token}), 200


@api_bp.route('/protected', methods=['GET'])
@jwt_required()
def protected():
    current_user_id = get_jwt_identity()
    return jsonify({"message": f"Hello, user {current_user_id}"}), 200


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@api_bp.route('/data/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({"message": "No file part"}), 400

    file = request.files['file']

    if file.filename == '':
        return jsonify({"message": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"message": "File type not allowed"}), 400

    try:
        if file.filename.endswith('.csv'):
            df = pd.read_csv(file)
        elif file.filename.endswith('.xlsx'):
            df = pd.read_excel(file)

        # 1. Infer Schema
        schema = {col: str(df[col].dtype) for col in df.columns}  # Simplified type mapping

        # 2. Store Metadata (in a metadata table)
        metadata = DataSetMetadata(filename=file.filename, schema=json.dumps(schema))
        db.session.add(metadata)
        db.session.commit()

        # 3. Store Data (in JSONB field)
        data_list = df.to_dict(orient='records')
        dataset = DataRecord(filename=file.filename, data=data_list)
        db.session.add(dataset)
        db.session.commit()

        return jsonify({"message": "File uploaded and data stored successfully"}), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"message": str(e)}), 500


    
@api_bp.route('/data/aggregate', methods=['GET'])
def aggregate_data():
    try:
        filename = request.args.get('filename')
        column_name = request.args.get('column')
        operation_type = request.args.get('operation')

        operations = {
            'avg': 'AVG',
            'min': 'MIN',
            'max': 'MAX',
            'sum': 'SUM',
            'count': 'COUNT'
        }

        if operation_type not in operations:
            return jsonify({"error": f"Invalid operation '{operation}'"}), 400

        if not filename or not column_name:
            return jsonify({"error": "Missing 'filename' or 'column' parameter"}), 400

        metadata = DataSetMetadata.query.filter_by(filename=filename).first()
        if not metadata:
            return jsonify({"error": "File not found"}), 404

        schema = json.loads(metadata.schema)
        if column_name not in schema:
            return jsonify({"error": f"Column '{column_name}' not found in schema"}), 400

        query = text(f"""
            SELECT {operations[operation_type]}((e->>'{column_name}')::numeric)
            FROM data_record
            CROSS JOIN LATERAL jsonb_array_elements(data) e
            WHERE filename = :filename;
        """)


        result = db.session.execute(query, {'filename': filename}).scalar()
        return jsonify({operation_type: result}), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@api_bp.route('/data/filter', methods=['GET'])
def filter_data():
    try:
        # Get parameters from the request
        filename = request.args.get('filename')  # Filter by filename
        column = request.args.get('column')      # Column to filter on
        value = request.args.get('value')        # Value to compare against
        operator = request.args.get('operator')  # Comparison operator (default: '=')

        if not filename or not column or not value:
            return jsonify({"error": "Missing 'filename', 'column', or 'value' parameter"}), 400

        # Construct the query
        query = text(f"""
            SELECT e
            FROM data_record
            CROSS JOIN LATERAL jsonb_array_elements(data) e
            WHERE filename = :filename
              AND (e->>'{column}')::numeric {operator} :value
        """)

        # Execute the query
        results = db.session.execute(query, {'filename': filename, 'value': float(value)}).fetchall()

        # Handle empty result
        if not results:
            return jsonify({"error": f"No data found for column '{column}' {operator} {value} in filename '{filename}'"}), 404

        # Return the filtered data
        filtered_data = [dict(row[0]) for row in results]
        return jsonify(filtered_data), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500