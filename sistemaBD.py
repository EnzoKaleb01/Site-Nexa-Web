"""
sistemaBD.py — módulo de banco de dados da Nexa Web
-------------------------------------------------------------------
Aqui fica TODA a lógica de banco de dados, separada do Flask (app.py
só chama essas funções e transforma o resultado em resposta HTTP).

Dois bancos SQLite completamente separados, em arquivos diferentes:

  usuarios.db   -> cadastro dos clientes (nome, e-mail, senha com hash)
  avaliacoes.db -> avaliações dos clientes (nota, comentário, foto/vídeo)
"""

import os
import sqlite3
import uuid
from datetime import datetime, timezone

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DB_USUARIOS = os.path.join(BASE_DIR, "usuarios.db")
CAMINHO_DB_AVALIACOES = os.path.join(BASE_DIR, "avaliacoes.db")

# Limite de tamanho por avaliação (foto/vídeo em base64), ~4.5MB de texto
LIMITE_MIDIA_CARACTERES = 4_500_000


class ErroSistemaBD(Exception):
    """Erro esperado (dados inválidos, e-mail duplicado, etc.) — app.py
    sabe transformar isso na resposta HTTP certa."""
    def __init__(self, codigo, mensagem):
        self.codigo = codigo  # usado pelo app.py pra escolher o status HTTP
        self.mensagem = mensagem
        super().__init__(mensagem)


def _conectar(caminho):
    conexao = sqlite3.connect(caminho)
    conexao.row_factory = sqlite3.Row
    return conexao


def _agora_iso():
    return datetime.now(timezone.utc).isoformat()


def inicializar_bancos():
    """Cria os dois bancos e suas tabelas, se ainda não existirem.
    Seguro de chamar toda vez que o app sobe — não apaga dados existentes."""
    with _conectar(CAMINHO_DB_USUARIOS) as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                senha_hash TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )

    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS avaliacoes (
                id TEXT PRIMARY KEY,
                usuario_email TEXT NOT NULL,
                usuario_nome TEXT NOT NULL,
                nota INTEGER NOT NULL,
                comentario TEXT NOT NULL,
                tipo_midia TEXT,
                dados_midia TEXT,
                criado_em TEXT NOT NULL
            )
            """
        )


# --------------------------------------------------------------------------
# Banco 1 — cadastro de clientes (usuarios.db)
# --------------------------------------------------------------------------
def criar_usuario(nome, email, senha):
    nome = (nome or "").strip()
    email = (email or "").strip().lower()
    senha = senha or ""

    if not nome or not email or len(senha) < 4:
        raise ErroSistemaBD("dados_invalidos", "Preencha nome, e-mail e uma senha com pelo menos 4 caracteres.")

    with _conectar(CAMINHO_DB_USUARIOS) as conexao:
        existente = conexao.execute("SELECT id FROM usuarios WHERE email = ?", (email,)).fetchone()
        if existente:
            raise ErroSistemaBD("email_duplicado", "Esse e-mail já tem cadastro. Tente entrar.")

        usuario_id = str(uuid.uuid4())
        conexao.execute(
            "INSERT INTO usuarios (id, nome, email, senha_hash, criado_em) VALUES (?, ?, ?, ?, ?)",
            (usuario_id, nome, email, generate_password_hash(senha), _agora_iso()),
        )

    return {"id": usuario_id, "name": nome, "email": email}


def autenticar_usuario(email, senha):
    email = (email or "").strip().lower()
    senha = senha or ""

    with _conectar(CAMINHO_DB_USUARIOS) as conexao:
        linha = conexao.execute("SELECT * FROM usuarios WHERE email = ?", (email,)).fetchone()

    if not linha or not check_password_hash(linha["senha_hash"], senha):
        raise ErroSistemaBD("credenciais_invalidas", "E-mail ou senha incorretos.")

    return {"id": linha["id"], "name": linha["nome"], "email": linha["email"]}


def buscar_usuario_por_email(email):
    email = (email or "").strip().lower()
    with _conectar(CAMINHO_DB_USUARIOS) as conexao:
        linha = conexao.execute("SELECT nome FROM usuarios WHERE email = ?", (email,)).fetchone()
    return {"nome": linha["nome"]} if linha else None


# --------------------------------------------------------------------------
# Banco 2 — avaliações dos clientes (avaliacoes.db)
# --------------------------------------------------------------------------
def criar_avaliacao(email, nota, comentario, tipo_midia, dados_midia):
    email = (email or "").strip().lower()
    comentario = (comentario or "").strip()

    if not email or not comentario or nota not in (1, 2, 3, 4, 5):
        raise ErroSistemaBD("dados_invalidos", "Informe e-mail, comentário e uma nota de 1 a 5.")

    if dados_midia and len(dados_midia) > LIMITE_MIDIA_CARACTERES:
        raise ErroSistemaBD("midia_grande", "Esse arquivo é muito grande. Escolha uma foto ou vídeo menor.")

    usuario = buscar_usuario_por_email(email)
    if not usuario:
        raise ErroSistemaBD("nao_autenticado", "Faça login antes de avaliar.")

    avaliacao_id = str(uuid.uuid4())
    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        conexao.execute(
            "INSERT INTO avaliacoes "
            "(id, usuario_email, usuario_nome, nota, comentario, tipo_midia, dados_midia, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (avaliacao_id, email, usuario["nome"], int(nota), comentario, tipo_midia, dados_midia, _agora_iso()),
        )

    return {"id": avaliacao_id}


def listar_avaliacoes():
    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        linhas = conexao.execute(
            "SELECT id, usuario_nome, nota, comentario, tipo_midia, dados_midia, criado_em "
            "FROM avaliacoes ORDER BY criado_em DESC"
        ).fetchall()

    return [
        {
            "id": linha["id"],
            "user_name": linha["usuario_nome"],
            "rating": linha["nota"],
            "comment": linha["comentario"],
            "media_type": linha["tipo_midia"],
            "media_data": linha["dados_midia"],
            "created_at": linha["criado_em"],
        }
        for linha in linhas
    ]