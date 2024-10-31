from typing import Optional
import requests
import typer
from typing_extensions import Annotated

app = typer.Typer()
list_results = []

# Função para aceder ao URL
def pedido(limit, page):
    url = f"https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236&limit={limit}&page={page}"
    payload = {}
    headers = {'User-Agent': "ALPCD_5"}  # Necessário por 'User-Agent' nos headers
    res = requests.request("GET", url, headers=headers, data=payload)
    if res.status_code == 200:  # Verificar se o acesso foi bem sucedido (200 OK)
        results = res.json()
        return results
    else:
        print(f"Erro {res.status_code} - {res.text}")
        return {}

# Comando para obter os n trabalhos publicados mais recentes
@app.command()
def top(n: Annotated[Optional[int], typer.Argument()] = None):  # Chama o número de trabalhos a escolher n
    if not list_results:
        fetch_data()
    if n is None:  # Nenhum n selecionado, portanto assume o valor padrão None
        return
    else:
        sorted_results = sorted(list_results, key=lambda x: x["publishedAt"], reverse=True)  # Ordena a lista de resultados pela data de publicação
        print(sorted_results[:n])  # Devolve os n primeiros valores da lista

@app.command()      #só para aparecerem os comandos (preciasa de pelo menos dois) (não faz nada importante)
def mayb_is_this(name:str):
    if name:
        print(f"Helo {name}")       #diz ola ao nome dado


def fetch_data():
    global list_results  # Para ser acessado dentro de outras funções
    limit = 100
    page = 1
    response = pedido(limit, page)
    list_results = response["results"]
    print("A recolher respostas do URL...")

    while page * limit < response["total"]:  # Para limite=100 e total=1261, página vai até 13
        page += 1
        try:  # Caso seja devolvido um dicionário vazio, para não ocorrerem erros
            new_results = pedido(limit, page)["results"]
            list_results += new_results  # Lista com todos os resultados que vai incrementando
        except:
            print(f"Erro ao obter resultados da página {page}.")

    response["results"] = list_results  # Finalmente cria o 'response' com todos os resultados
    print("Finalizado.")

if __name__ == "__main__":
    app()  # Executa a app Typer
