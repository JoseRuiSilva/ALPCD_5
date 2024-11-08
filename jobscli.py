from typing import Optional
from typing import List
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

def filter_by_dates_results(list_results, start_date, end_date):
    sorted_results = sorted(list_results, key=lambda x: x["updatedAt"], reverse=True)
    filtered_results = []

    for res in sorted_results:
        update_date_str = res['updatedAt'][:10]
        update_date = datetime.strptime(update_date_str, '%Y-%m-%d')
        if start_date <= update_date <= end_date:
            filtered_results.append(res)
        elif update_date < start_date:
            break

    return filtered_results

def process_job(res, given_skills, skill_extractor):
    body = res['body']
    try:
        annotations = skill_extractor.annotate(body)
    except (IndexError, ValueError) as e:
        print(f"Erro a processar o 'body': {e}")
        return None

    anoted_skills = set(skill['doc_node_value'] for skill in annotations['results']['full_matches'])
    anoted_skills.update(skill['doc_node_value'] for skill in annotations['results']['ngram_scored'])

    if set(given_skills) & anoted_skills:   #PERGUNTAR AO PROFESSOR, se for todos as skills dadas all(item in annoted_skills for item in given_skills)
        return res
    return None

def process_jobs_concurrently(list_of_results, given_skills, skill_extractor, max_workers=4):
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_res = {executor.submit(process_job, res, given_skills, skill_extractor): res for res in list_of_results}

        for future in as_completed(future_to_res):
            res = future.result()
            if res:
                results.append(res)

    return results

# Comando para obter os n trabalhos publicados mais recentes
@app.command()
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

#d)
@app.command()
def skills(skills:str, nome_empresa:str, num_trabalhos:int):
    if not list_results:
        fetch_data()

    
    # Iniciar o skill extractor
    nlp = spacy.load("en_core_web_lg")
    skill_extractor = SkillExtractor(nlp, SKILL_DB, PhraseMatcher)

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    except ValueError:
        print("Erro ao ler as datas, verifique se estas existem.")
        return {}
    
    if end_date < start_date:
        print("Data final menor que inicial, a iniciar com valores trocados...")
        filtered_results = filter_by_dates_results(list_results, end_date, start_date)
    else:
        filtered_results = filter_by_dates_results(list_results, start_date, end_date)

    results = process_jobs_concurrently(filtered_results, given_skills, skill_extractor, max_workers=8)
    print(results)

    

if __name__ == "__main__":
    app()  # Executa a app Typer