"""
sistemaBD.py — módulo de banco de dados da Nexa Web
-------------------------------------------------------------------
Aqui fica TODA a lógica de banco de dados, separada do Flask (app.py
só chama essas funções e transforma o resultado em resposta HTTP).

Sem cadastro/login: qualquer visitante pode enviar uma avaliação,
direto com o nome dele. Por isso agora só existe UM banco:

  avaliacoes.db -> avaliações dos clientes (nome, nota, comentário,
                   foto/vídeo, e um token secreto de exclusão)

O token de exclusão é gerado na hora que a avaliação é criada e
devolvido só naquela resposta — ele não aparece na listagem pública.
É o que garante que só quem enviou a avaliação consegue apagá-la.
"""

import os
import secrets
import sqlite3
import uuid
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CAMINHO_DB_AVALIACOES = os.path.join(BASE_DIR, "avaliacoes.db")

# Limite de tamanho por avaliação (foto/vídeo em base64), ~4.5MB de texto
LIMITE_MIDIA_CARACTERES = 4_500_000


class ErroSistemaBD(Exception):
    """Erro esperado (dados inválidos, avaliação não encontrada, etc.) —
    app.py sabe transformar isso na resposta HTTP certa."""
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
    """Cria o banco e a tabela, se ainda não existirem.
    Seguro de chamar toda vez que o app sobe — não apaga dados existentes."""
    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        conexao.execute(
            """
            CREATE TABLE IF NOT EXISTS avaliacoes (
                id TEXT PRIMARY KEY,
                nome TEXT NOT NULL,
                nota INTEGER NOT NULL,
                comentario TEXT NOT NULL,
                tipo_midia TEXT,
                dados_midia TEXT,
                token_exclusao TEXT NOT NULL,
                criado_em TEXT NOT NULL
            )
            """
        )


def criar_avaliacao(nome, nota, comentario, tipo_midia, dados_midia):
    nome = (nome or "").strip()
    comentario = (comentario or "").strip()

    if not nome or not comentario or nota not in (1, 2, 3, 4, 5):
        raise ErroSistemaBD("dados_invalidos", "Informe seu nome, um comentário e uma nota de 1 a 5.")

    if dados_midia and len(dados_midia) > LIMITE_MIDIA_CARACTERES:
        raise ErroSistemaBD("midia_grande", "Esse arquivo é muito grande. Escolha uma foto ou vídeo menor.")

    avaliacao_id = str(uuid.uuid4())
    token_exclusao = secrets.token_hex(16)

    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        conexao.execute(
            "INSERT INTO avaliacoes "
            "(id, nome, nota, comentario, tipo_midia, dados_midia, token_exclusao, criado_em) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (avaliacao_id, nome, int(nota), comentario, tipo_midia, dados_midia, token_exclusao, _agora_iso()),
        )

    # O token só é devolvido aqui, nesta resposta — a listagem pública nunca o inclui.
    return {"id": avaliacao_id, "delete_token": token_exclusao}


def listar_avaliacoes():
    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        linhas = conexao.execute(
            "SELECT id, nome, nota, comentario, tipo_midia, dados_midia, criado_em "
            "FROM avaliacoes ORDER BY criado_em DESC"
        ).fetchall()

    return [
        {
            "id": linha["id"],
            "user_name": linha["nome"],
            "rating": linha["nota"],
            "comment": linha["comentario"],
            "media_type": linha["tipo_midia"],
            "media_data": linha["dados_midia"],
            "created_at": linha["criado_em"],
        }
        for linha in linhas
    ]


def excluir_avaliacao(avaliacao_id, token_exclusao):
    with _conectar(CAMINHO_DB_AVALIACOES) as conexao:
        linha = conexao.execute(
            "SELECT token_exclusao FROM avaliacoes WHERE id = ?", (avaliacao_id,)
        ).fetchone()

        if not linha:
            raise ErroSistemaBD("nao_encontrada", "Essa avaliação não existe (talvez já tenha sido removida).")

        if not token_exclusao or not secrets.compare_digest(linha["token_exclusao"], token_exclusao):
            raise ErroSistemaBD("token_invalido", "Você só pode remover avaliações que você mesmo enviou.")

        conexao.execute("DELETE FROM avaliacoes WHERE id = ?", (avaliacao_id,))