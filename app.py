from flask import Flask, request, jsonify
from flask_cors import CORS
from datetime import datetime
import mysql.connector

app = Flask(__name__)
CORS(app)

# Database Connection
db_config = {
    "host": "localhost",
    "user": "root",
    "password": "******",
    "database": "Bitespeed"
}

def get_db_connection():
    return mysql.connector.connect(**db_config)

@app.route('/identify', methods=['POST'])
def identify_contact():
    if request.content_type != 'application/json':
        return jsonify({"error": "Content-Type must be application/json"}), 415

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "Invalid JSON data"}), 400

    email = data.get("email")
    phoneNumber = data.get("phoneNumber")

    if not email and not phoneNumber:
        return jsonify({"error": "Either email or phoneNumber must be provided"}), 400

    db = get_db_connection()
    cursor = db.cursor(dictionary=True)

    # Step 1: Fetch existing contacts
    query = "SELECT * FROM contacts WHERE email = %s OR phoneNumber = %s"
    cursor.execute(query, (email, phoneNumber))
    matching_contacts = cursor.fetchall()

    if matching_contacts:
        # Step 2: Identify primary contact
        primary_contact = next((c for c in matching_contacts if c["linkPrecedence"] == "primary"), matching_contacts[0])
        primary_contact_id = primary_contact["id"]

        # Step 3: Check if the new entry is already in the DB
        for contact in matching_contacts:
            if contact["email"] == email and contact["phoneNumber"] == phoneNumber:
                # If exact match exists, return existing response
                response_data = {
                    "contact": {
                        "primaryContactId": primary_contact_id,
                        "emails": list(set([c["email"] for c in matching_contacts if c["email"]])),
                        "phoneNumbers": list(set([c["phoneNumber"] for c in matching_contacts if c["phoneNumber"]])),
                        "secondaryContactIds": [c["id"] for c in matching_contacts if c["id"] != primary_contact_id]
                    }
                }
                cursor.close()
                db.close()
                return jsonify(response_data), 200

        # Step 4: If new details entered, insert as secondary contact
        createdAt = datetime.utcnow()
        insert_query = """
        INSERT INTO contacts (phoneNumber, email, linkedId, linkPrecedence, createdAt, updatedAt, deletedAt)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        values = (phoneNumber, email, primary_contact_id, "secondary", createdAt, createdAt, None)
        cursor.execute(insert_query, values)
        db.commit()

        # Step 5: Re-fetch updated contacts
        cursor.execute(query, (email, phoneNumber))
        updated_contacts = cursor.fetchall()

        # Step 6: Build updated response
        response_data = {
            "contact": {
                "primaryContactId": primary_contact_id,
                "emails": list(set([c["email"] for c in updated_contacts if c["email"]])),
                "phoneNumbers": list(set([c["phoneNumber"] for c in updated_contacts if c["phoneNumber"]])),
                "secondaryContactIds": [c["id"] for c in updated_contacts if c["id"] != primary_contact_id]
            }
        }

        cursor.close()
        db.close()
        return jsonify(response_data), 201

    # Step 7: If no contact exists, create a new primary contact
    createdAt = datetime.utcnow()
    insert_query = """
    INSERT INTO contacts (phoneNumber, email, linkedId, linkPrecedence, createdAt, updatedAt, deletedAt)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    values = (phoneNumber, email, None, "primary", createdAt, createdAt, None)
    cursor.execute(insert_query, values)
    db.commit()
    new_contact_id = cursor.lastrowid

    response_data = {
        "contact": {
            "primaryContactId": new_contact_id,
            "emails": [email] if email else [],
            "phoneNumbers": [phoneNumber] if phoneNumber else [],
            "secondaryContactIds": []
        }
    }

    cursor.close()
    db.close()
    return jsonify(response_data), 201

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)
