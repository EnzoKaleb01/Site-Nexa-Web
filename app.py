"""
Nexa Web — backend em Python (Flask)
-------------------------------------------------------------------
Dois bancos de dados SQLite SEPARADOS:

  users.db     -> cadastro dos clientes (nome, e-mail, senha com hash)
  feedback.db  -> avaliações dos clientes (nota, comentário, foto/vídeo)

Como rodar localmente:
  1) pip install -r requirements.txt
  2) python app.py
  3) A API sobe em http://localhost:5000

O front-end (nexaweb.html) chama essa API através da constante
API_BASE_URL, definida no <script> do próprio HTML. Se você mudar
a porta ou fizer deploy em outro endereço, atualize essa constante lá.
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

from flask import Flask, g, jsonify, request
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_DB_PATH = os.path.join(BASE_DIR, "users.db")
FEEDBACK_DB_PATH = os.path.join(BASE_DIR, "feedback.db")

# Limite de tamanho por avaliação (foto/vídeo em base64), ~4.5MB de texto
MAX_MEDIA_CHARS = 4_500_000

app = Flask(__name__)
# Em produção, troque "*" pelo domínio real do seu site (ex: https://enzokaleb01.github.io)
CORS(app, resources={r"/api/*": {"origins": "*"}})


# --------------------------------------------------------------------------
# Conexões — cada banco é aberto por request e fechado ao final (g context)
# --------------------------------------------------------------------------
def get_users_db():
    if "users_db" not in g:
        g.users_db = sqlite3.connect(USERS_DB_PATH)
        g.users_db.row_factory = sqlite3.Row
    return g.users_db


def get_feedback_db():
    if "feedback_db" not in g:
        g.feedback_db = sqlite3.connect(FEEDBACK_DB_PATH)
        g.feedback_db.row_factory = sqlite3.Row
    return g.feedback_db


@app.teardown_appcontext
def close_dbs(exception=None):
    users_db = g.pop("users_db", None)
    if users_db is not None:
        users_db.close()
    feedback_db = g.pop("feedback_db", None)
    if feedback_db is not None:
        feedback_db.close()


def init_dbs():
    users_conn = sqlite3.connect(USERS_DB_PATH)
    users_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    users_conn.commit()
    users_conn.close()

    feedback_conn = sqlite3.connect(FEEDBACK_DB_PATH)
    feedback_conn.execute(
        """
        CREATE TABLE IF NOT EXISTS feedback (
            id TEXT PRIMARY KEY,
            user_email TEXT NOT NULL,
            user_name TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT NOT NULL,
            media_type TEXT,
            media_data TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    feedback_conn.commit()
    feedback_conn.close()


# Roda sempre que o módulo é carregado — funciona tanto com "python app.py"
# quanto com um servidor de produção (gunicorn app:app, por exemplo).
init_dbs()


def now_iso():
    return datetime.now(timezone.utc).isoformat()


# --------------------------------------------------------------------------
# Banco 1: cadastro de clientes (users.db)
# --------------------------------------------------------------------------
@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or len(password) < 4:
        return jsonify({"error": "Preencha nome, e-mail e uma senha com pelo menos 4 caracteres."}), 400

    db = get_users_db()
    existing = db.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
    if existing:
        return jsonify({"error": "Esse e-mail já tem cadastro. Tente entrar."}), 409

    user_id = str(uuid.uuid4())
    db.execute(
        "INSERT INTO users (id, name, email, password_hash, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, name, email, generate_password_hash(password), now_iso()),
    )
    db.commit()

    return jsonify({"id": user_id, "name": name, "email": email}), 201


@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    db = get_users_db()
    row = db.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not row or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "E-mail ou senha incorretos."}), 401

    return jsonify({"id": row["id"], "name": row["name"], "email": row["email"]})


# --------------------------------------------------------------------------
# Banco 2: avaliações dos clientes (feedback.db)
# --------------------------------------------------------------------------
@app.route("/api/feedback", methods=["GET"])
def list_feedback():
    db = get_feedback_db()
    rows = db.execute(
        "SELECT id, user_name, rating, comment, media_type, media_data, created_at "
        "FROM feedback ORDER BY created_at DESC"
    ).fetchall()
    return jsonify([dict(row) for row in rows])


@app.route("/api/feedback", methods=["POST"])
def create_feedback():
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    rating = data.get("rating")
    comment = (data.get("comment") or "").strip()
    media_type = data.get("media_type")
    media_data = data.get("media_data")

    if not email or not comment or rating not in (1, 2, 3, 4, 5):
        return jsonify({"error": "Dados incompletos. Informe e-mail, comentário e uma nota de 1 a 5."}), 400

    if media_data and len(media_data) > MAX_MEDIA_CHARS:
        return jsonify({"error": "Esse arquivo é muito grande. Escolha uma foto ou vídeo menor."}), 413

    # Confere se o e-mail pertence a um cliente cadastrado (banco 1)
    users_db = get_users_db()
    user = users_db.execute("SELECT name FROM users WHERE email = ?", (email,)).fetchone()
    if not user:
        return jsonify({"error": "Faça login antes de avaliar."}), 401

    feedback_id = str(uuid.uuid4())
    feedback_db = get_feedback_db()
    feedback_db.execute(
        "INSERT INTO feedback (id, user_email, user_name, rating, comment, media_type, media_data, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (feedback_id, email, user["name"], int(rating), comment, media_type, media_data, now_iso()),
    )
    feedback_db.commit()

    return jsonify({"id": feedback_id}), 201


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)