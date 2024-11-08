from typing import Optional
import requests
import typer
from typing_extensions import Annotated
from datetime import datetime

app = typer.Typer()
list_results = []

# Função para aceder ao URL
def pedido(limit, page):
    url = f"https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236&limit={limit}&page={page}"
    payload = {}
    headers = {'User-Agent': "ALPCD_5"}  # Necessário por 'User-Agent' nos headers
    res = requests.request("GET", url, headers=headers, data=payload)
    if res.status_code == 200:  # Verificar se a resposta foi bem-sucedida (200 OK)
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

    # Verifica se a resposta contém a chave 'results'
    if not response or "results" not in response:
        print("Nenhum resultado encontrado na resposta da API.")
        return
    
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
def top(n: int):  # Chama o número de trabalhos a escolher n
    if not list_results:
        fetch_data()

    # Ordena os resultados pela data de publicação, do mais recente para o mais antigo
    sorted_results = sorted(list_results, key=lambda x: x["publishedAt"], reverse=True)

    # Se não houver trabalhos suficientes, o número de trabalhos será ajustado para o total disponível
    num_results = min(n, len(sorted_results))

    simplified_results = []
    for job in sorted_results[:num_results]:
        # Formatação da data de publicação para mostrar apenas "YYYY-MM-DD HH:MM"
        published_at = job.get("publishedAt", "Não há informação")
        if published_at != "Não há informação":
            try:
                # Converte a string da data para um objeto datetime
                published_at = datetime.strptime(published_at, "%Y-%m-%d %H:%M:%S")
                # Formata para "YYYY-MM-DD HH:MM"
                published_at = published_at.strftime("%Y-%m-%d %H:%M")
            except ValueError:
                published_at = "Não há informação"

        # Verifica todos os campos e substitui por "Não há informação" caso não existam ou sejam None
        job_type = ", ".join([type["name"] for type in job.get("types", [])]) if job.get("types") else "Não há informação"

        simplified_job = {
            "Título": job.get("title", "Não há informação"),
            "Empresa": job.get("company", {}).get("name", "Não há informação"),
            "Data de Publicação": published_at,
            "Salário": job.get("wage", "Não há informação") if job.get("wage") is not None else "Não há informação",
            "Localização": ", ".join([loc["name"] for loc in job.get("locations", [])]) or "Não há informação",
            "Tipo de Trabalho": job_type
        }

        # Formatação conforme pedido, com \n para quebra de linha
        formatted_result = f"Título: {simplified_job['Título']}\n" \
                           f"Empresa: {simplified_job['Empresa']}\n" \
                           f"Data de Publicação: {simplified_job['Data de Publicação']}\n" \
                           f"Salário: {simplified_job['Salário']}\n" \
                           f"Localização: {simplified_job['Localização']}\n" \
                           f"Tipo de Trabalho: {simplified_job['Tipo de Trabalho']}\n"

        simplified_results.append(formatted_result)

    # Exibe os resultados formatados
    print("\n".join(simplified_results))


# b)
@app.command()
def search(localidade: str, empresa: str, n_jobs: int):
    if not list_results:  # Se não há dados, faz a coleta
        fetch_data()

    # Filtra os resultados para incluir apenas trabalhos do tipo Full-time, pela empresa e localização
    filtered_jobs = [
        job for job in list_results
        if "Full-time" in [type["name"] for type in job.get("types", [])]
        and empresa.lower() in job.get("company", {}).get("name", "").lower()
        and localidade.lower() in [loc["name"].lower() for loc in job.get("locations", [])]
    ]

    # Verifica se há resultados filtrados
    if not filtered_jobs:
        print("Não há trabalhos disponíveis para essa pesquisa.")
        return

    # Limita os resultados ao número solicitado (n_jobs)
    filtered_jobs = filtered_jobs[:n_jobs]
    
    # Simplifica os resultados para exibir as informações desejadas
    simplified_results = []
    for job in filtered_jobs:
        simplified_job = {
            "Título": job.get("title", "Não há informação"),
            "Empresa": job.get("company", {}).get("name", "Não há informação"),
            "Data de Publicação": job.get("publishedAt", "Não há informação"),
            "Salário": job.get("wage", "Não há informação") if job.get("wage") is not None else "Não há informação",
            "Localização": ", ".join([loc["name"] for loc in job.get("locations", [])]) or "Não há informação",
            "Tipo de Trabalho": ", ".join([type["name"] for type in job.get("types", [])]) if job.get("types") else "Não há informação"
        }

        # Formatação conforme pedido, com \n para quebra de linha
        formatted_result = f"Título: {simplified_job['Título']}\n" \
                           f"Empresa: {simplified_job['Empresa']}\n" \
                           f"Data de Publicação: {simplified_job['Data de Publicação']}\n" \
                           f"Salário: {simplified_job['Salário']}\n" \
                           f"Localização: {simplified_job['Localização']}\n" \
                           f"Tipo de Trabalho: {simplified_job['Tipo de Trabalho']}\n"

        simplified_results.append(formatted_result)

    # Exibe os resultados formatados
    print("\n".join(simplified_results))


# d)  Comando para buscar trabalhos por habilidades, empresa e número de trabalhos (não implementado completamente)
@app.command()
def skills(skills: str, nome_empresa: str, num_trabalhos: int):
    if not list_results:
        fetch_data()

if __name__ == "__main__":
    app()  # Executa a app Typer



