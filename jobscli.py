from typing import Optional
import requests
import typer
from typing_extensions import Annotated
import re

app = typer.Typer()
list_results = []

# Função para aceder ao URL
def pedido(limit, page, job_id = None):
    if job_id:
        url = f"https://api.itjobs.pt/job/get.json?api_key=ee176fa9456283ab9c42f357b036e236&id={job_id}"
    else:
        url = f"https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236&limit={limit}&page={page}"
    payload = {}
    headers = {'User-Agent': "ALPCD_5", 'Cookie': 'itjobs_pt=3cea3cc1f4c6a847f8c459367edf7143:94de45f2a55a15b2672adf8788ac8072e7bfd5c5'}  # Necessário por 'User-Agent' nos headers
    res = requests.request("GET", url, headers=headers, data=payload)
    if res.status_code == 200:  # Verificar se o acesso foi bem sucedido (200 OK)
        results = res.json()
        return results
    else:
        print(f"Erro {res.status_code} - {res.text}")
        return {}
    
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

# Comando para obter os n trabalhos publicados mais recentes
@app.command()
#a)
def top(n: int):  # Chama o número de trabalhos a escolher n
    if not list_results:
        fetch_data()

    sorted_results = sorted(list_results, key=lambda x: x["publishedAt"], reverse=True)  # Ordena a lista de resultados pela data de publicação
    print(sorted_results[:n])  # Devolve os n primeiros valores da lista

#b)
@app.command()
def search(company_location:str, company_name:str, n_jobs:int):
    if not list_results:
        fetch_data()

#c)
@app.command()
def salary(job_id: str):
    # Usar a função com retentativa para obter os detalhes do job
    job_data = pedido(100,1,job_id)
    
    if job_data is None:
        print("Não foi possível obter os dados do job. Verifique o job_id e tente novamente.")
        return
    
    # Verificar se o campo wage está presente e tem valor
    wage = job_data.get("wage")
    if wage:
        print(f"Salário encontrado: {wage}")
    else:
        # Caso wage esteja vazio ou seja None, procurar por valores salariais em outros campos
        description = job_data.get("description", "")
        matches = re.findall(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\b", description)
        
        if matches:
            # Exibe o primeiro valor encontrado que pode representar um salário
            salary_estimate = matches[0]
            print(f"Salário estimado encontrado na descrição: {salary_estimate}")
        else:
            print("Salário não especificado na oferta de emprego.")

#d)
@app.command()
def skills(skills:str, nome_empresa:str, num_trabalhos:int):
    if not list_results:
        fetch_data()

if __name__ == "__main__":
    app()  # Executa a app Typer
