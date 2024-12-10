from flask import Flask, request, jsonify
import requests
import pandas as pd
from twocaptcha import TwoCaptcha
from bs4 import BeautifulSoup
from threading import Thread

# Configuração da API do 2Captcha
API_KEY = "2f2625bb05b0cef3b93209071505d6a9"
solver = TwoCaptcha(API_KEY)

# Ajustar tempo limite e intervalo de polling
solver.default_timeout = 600 
solver.polling_interval = 10  # Intervalo de 10 segundos entre verificações

# Aplicação principal
app = Flask(__name__)

@app.route('/infos', methods=['POST'])
def infos():
    try:
        # Obtém os parâmetros da requisição
        params = request.json
        usuario = params.get("usuario")
        senha = params.get("senha")
        unidade_consumidora = params.get("unidade_consumidora")

        if not usuario or not senha or not unidade_consumidora:
            return jsonify({"error": "Parâmetros 'usuario', 'senha' e 'unidade_consumidora' são obrigatórios."}), 400

        # URL para login
        url_login = "https://agenciavirtual.neoenergiabrasilia.com.br/Account/EfetuarLogin"
        site_key = "6LdmOIAbAAAAANXdHAociZWz1gqR9Qvy3AN0rJy4"
        page_url = "https://agenciavirtual.neoenergiabrasilia.com.br/Account/EfetuarLogin"

        # Resolver o reCAPTCHA
        print("Resolvendo reCAPTCHA...")
        result = solver.recaptcha(sitekey=site_key, url=page_url)
        token = result["code"]  # Captura o token do reCAPTCHA
        print("Token do reCAPTCHA obtido:", token)

        # Dados do formulário de login
        data_login = {"CpfCnpj": usuario, "Senha": senha, "g-recaptcha-response": token}
        headers = {
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": "https://agenciavirtual.neoenergiabrasilia.com.br/Account/Login",
        }

        # Fazer login
        session = requests.Session()
        response_login = session.post(url_login, headers=headers, data=data_login)

        if response_login.status_code != 200:
            return jsonify({"error": "Erro no login", "status_code": response_login.status_code}), 401

        # Download da planilha
        url_planilha = "https://agenciavirtual.neoenergiabrasilia.com.br/HistoricoConsumo/ExportarExcelHistoricoConsumoFaturasBaixaTensao"
        data_planilha = {"Pagina": "1", "UnidadeConsumidora.CodigoCliente": unidade_consumidora}
        response_planilha = session.post(url_planilha, data=data_planilha)

        if response_planilha.status_code != 200:
            return jsonify({"error": "Erro ao baixar a planilha", "status_code": response_planilha.status_code}), 500

        # Salvar e ler planilha
        with open("Historico_Consumo.xlsx", "wb") as file:
            file.write(response_planilha.content)

        data = pd.read_excel("Historico_Consumo.xlsx")

        # Buscar data da próxima leitura
        url_proxima_leitura = f"https://agenciavirtual.neoenergiabrasilia.com.br/ProximaLeitura?codigo={unidade_consumidora}"
        response_tabela = session.get(url_proxima_leitura)

        if response_tabela.status_code == 200:
            soup = BeautifulSoup(response_tabela.content, 'html.parser')
            elemento_data = soup.select_one('#detalhes > div > div > div:nth-of-type(2) > span')
            data_proxima_leitura = elemento_data.text.strip() if elemento_data else None
        else:
            data_proxima_leitura = None

        return jsonify({
            "historico": data.to_dict(orient="records"),
            "proxima_leitura": data_proxima_leitura
        }), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Servidor de Keep-Alive
keep_alive_app = Flask('keep_alive')

@keep_alive_app.route('/')
def home():
    return "Estou vivo!"

def run_keep_alive():
    keep_alive_app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run_keep_alive)
    t.start()

# Executar a aplicação
if __name__ == '__main__':
    keep_alive()
    app.run(host='0.0.0.0', port=5000, debug=True)
