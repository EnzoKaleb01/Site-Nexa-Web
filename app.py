"""
Nexa Web — backend em Python (Flask)
-------------------------------------------------------------------
Sem cadastro/login: qualquer visitante pode enviar uma avaliação
direto, com o nome dele. A lógica de banco de dados está toda em
sistemaBD.py — este arquivo só cuida das rotas HTTP.

Como rodar localmente (jeito rápido, um comando só):
  1) pip install -r requirements.txt
  2) python iniciar_local.py
     -> sobe o backend E o site juntos, e já abre o navegador certo.

Como rodar manualmente (dois terminais):
  Terminal 1: python app.py                        (API em http://localhost:5000)
  Terminal 2: python -m http.server 8000            (site em http://localhost:8000)
  Depois abra http://localhost:8000/nexaweb.html

O front-end (nexaweb.html) chama essa API através da constante
API_BASE_URL, definida no <script> do próprio HTML.
"""

from flask import Flask, jsonify, request
from flask_cors import CORS

import sistemaBD

app = Flask(__name__)
# Em produção, troque "*" pelo domínio real do seu site (ex: https://enzokaleb01.github.io)
CORS(app, resources={r"/api/*": {"origins": "*"}})

# Cria o banco (avaliacoes.db) assim que o app é carregado — funciona
# com "python app.py", com "flask run" e com servidores de produção.
sistemaBD.inicializar_bancos()

# Mapeia os códigos de erro do sistemaBD.py pro status HTTP certo
_STATUS_POR_ERRO = {
    "dados_invalidos": 400,
    "midia_grande": 413,
    "nao_encontrada": 404,
    "token_invalido": 403,
}


@app.route("/api/feedback", methods=["GET"])
def listar_feedback():
    return jsonify(sistemaBD.listar_avaliacoes())


@app.route("/api/feedback", methods=["POST"])
def criar_feedback():
    data = request.get_json(silent=True) or {}
    try:
        resultado = sistemaBD.criar_avaliacao(
            data.get("name"),
            data.get("rating"),
            data.get("comment"),
            data.get("media_type"),
            data.get("media_data"),
        )
        return jsonify(resultado), 201
    except sistemaBD.ErroSistemaBD as erro:
        return jsonify({"error": erro.mensagem}), _STATUS_POR_ERRO.get(erro.codigo, 400)


@app.route("/api/feedback/<avaliacao_id>", methods=["DELETE"])
def remover_feedback(avaliacao_id):
    data = request.get_json(silent=True) or {}
    try:
        sistemaBD.excluir_avaliacao(avaliacao_id, data.get("delete_token"))
        return jsonify({"ok": True})
    except sistemaBD.ErroSistemaBD as erro:
        return jsonify({"error": erro.mensagem}), _STATUS_POR_ERRO.get(erro.codigo, 400)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)