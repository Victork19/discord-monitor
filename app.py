from flask import Flask, request, render_template, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os
import requests
from config import get_settings

app = Flask(__name__)
settings = get_settings()

app.config['SQLALCHEMY_DATABASE_URI'] = settings.SQLALCHEMY_DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = settings.SQLALCHEMY_TRACK_MODIFICATIONS
app.config['SECRET_KEY'] = settings.SECRET_KEY

db = SQLAlchemy(app)

# Models
class Server(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    server_name = db.Column(db.String(100))
    server_id = db.Column(db.String(50), unique=True)
    invite_link = db.Column(db.String(200))
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

class MemberJoin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String(50))
    username = db.Column(db.String(100))
    join_timestamp = db.Column(db.DateTime)
    server_id = db.Column(db.String(50))
    server_name = db.Column(db.String(100))
    account_created_at = db.Column(db.DateTime)

# API: Log Member Join
@app.route('/api/log_member', methods=['POST'])
def log_member():
    api_key = request.headers.get('X-API-KEY')
    if settings.API_SHARED_SECRET and api_key != settings.API_SHARED_SECRET:
        return jsonify({"status": "unauthorized"}), 401

    try:
        data = request.get_json()
        if not data:
            return jsonify({"status": "error", "message": "No JSON data"}), 400

        server = Server.query.filter_by(server_id=data['server_id']).first()
        if not server:
            print(f"Ignoring unmonitored server: {data['server_id']}")
            return jsonify({"status": "ignored"}), 200

        # Parse timestamps
        join_ts_str = data['join_timestamp'].replace('Z', '+00:00')
        join_timestamp = datetime.fromisoformat(join_ts_str)
        account_created_at = None
        if data.get('account_created_at'):
            acct_ts_str = data['account_created_at'].replace('Z', '+00:00')
            account_created_at = datetime.fromisoformat(acct_ts_str)

        member = MemberJoin(
            user_id=data['user_id'],
            username=data['username'],
            join_timestamp=join_timestamp,
            server_id=data['server_id'],
            server_name=data['server_name'],
            account_created_at=account_created_at
        )
        db.session.add(member)
        db.session.commit()
        print(f"Logged join: {data['username']} to {data['server_name']}")
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        print(f"Error logging join: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500

# Dashboard Routes
@app.route('/')
def dashboard():
    servers = Server.query.all()
    logs = MemberJoin.query.order_by(MemberJoin.join_timestamp.desc()).limit(50).all()
    return render_template('dashboard.html', servers=servers, logs=logs)

@app.route('/add_server', methods=['POST'])
def add_server():
    invite_link = request.form.get('invite_link', '').strip()
    if not invite_link:
        return "Invite link required.", 400
    if not settings.BOT_TOKEN:
        return "BOT_TOKEN required for auto-fetch.", 400

    try:
        code = invite_link.split('/')[-1]
        headers = {'Authorization': f'Bot {settings.BOT_TOKEN}'}
        response = requests.get(f'https://discord.com/api/v9/invites/{code}', headers=headers)
        response.raise_for_status()
        invite_data = response.json()
        if 'guild' not in invite_data:
            return "Invalid invite: No guild.", 400

        server_id = str(invite_data['guild']['id'])
        server_name = invite_data['guild']['name']
    except Exception as e:
        return f"Fetch error: {str(e)}", 400

    existing = Server.query.filter_by(server_id=server_id).first()
    if existing:
        return "Server already monitored.", 400

    new_server = Server(server_name=server_name, server_id=server_id, invite_link=invite_link)
    db.session.add(new_server)
    db.session.commit()
    return redirect(url_for('dashboard'))

@app.route('/remove_server/<int:server_id>')
def remove_server(server_id):
    server = Server.query.get_or_404(server_id)
    db.session.delete(server)
    db.session.commit()
    return redirect(url_for('dashboard'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, host='0.0.0.0', port=5000)