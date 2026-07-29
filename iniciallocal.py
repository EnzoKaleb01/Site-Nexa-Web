"""
iniciar_local.py — sobe tudo de uma vez só
-------------------------------------------------------------------
Roda o backend (Flask, porta 5000) e o site (nexaweb.html, porta 8000)
ao mesmo tempo, e já abre o navegador no endereço certo.

Isso existe pra evitar o erro mais comum: abrir o nexaweb.html de um
jeito que o navegador bloqueia (https, ou clicando duas vezes no
arquivo). Rodando por aqui, o site sempre abre em http://localhost,
igual ao backend — sem bloqueio.

Como usar:
    python iniciar_local.py

Deixe essa janela aberta enquanto estiver testando. Ctrl+C encerra os dois.
"""

import http.server
import os
import socketserver
import sys
import threading
import time
import webbrowser

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# nexaweb.html normalmente fica na pasta de cima (ao lado da pasta nexaweb-backend)
CANDIDATOS_SITE = [
    os.path.dirname(BASE_DIR),  # pasta pai (estrutura padrão de entrega)
    BASE_DIR,                    # caso tenha colocado o html na mesma pasta do backend
    os.getcwd(),                 # pasta de onde o comando foi rodado
]

PORTA_BACKEND = 5000
PORTA_SITE = 8000


def encontrar_pasta_do_site():
    for pasta in CANDIDATOS_SITE:
        if os.path.isfile(os.path.join(pasta, "nexaweb.html")):
            return pasta
    return None


def subir_backend():
    import app as modulo_flask  # importa o app.py desta mesma pasta
    modulo_flask.app.run(port=PORTA_BACKEND, debug=False, use_reloader=False)


def subir_site(pasta_site):
    os.chdir(pasta_site)
    handler = http.server.SimpleHTTPRequestHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(("", PORTA_SITE), handler) as httpd:
        httpd.serve_forever()


def main():
    pasta_site = encontrar_pasta_do_site()
    if not pasta_site:
        print("Não encontrei o arquivo nexaweb.html perto daqui.")
        print("Coloque este script na mesma pasta do nexaweb-backend, com o")
        print("nexaweb.html logo acima (ou ao lado), e rode de novo.")
        sys.exit(1)

    print(f"Site encontrado em: {pasta_site}")
    print(f"Subindo backend em http://localhost:{PORTA_BACKEND}")
    thread_backend = threading.Thread(target=subir_backend, daemon=True)
    thread_backend.start()

    print(f"Subindo site em http://localhost:{PORTA_SITE}")
    thread_site = threading.Thread(target=subir_site, args=(pasta_site,), daemon=True)
    thread_site.start()

    time.sleep(1.5)  # dá tempo dos dois servidores subirem antes de abrir o navegador

    url = f"http://localhost:{PORTA_SITE}/nexaweb.html"
    print(f"Abrindo {url} no navegador...")
    webbrowser.open(url)

    print("\nTudo rodando! Deixe esta janela aberta.")
    print("Pra parar, feche esta janela ou aperte Ctrl+C.\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nEncerrando...")


if __name__ == "__main__":
    main()