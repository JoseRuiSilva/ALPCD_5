from typing import Optional, List
import requests
import typer
from typing_extensions import Annotated
import re
import spacy
from spacy.matcher import PhraseMatcher
from skillNer.general_params import SKILL_DB # type: ignore
from skillNer.skill_extractor_class import SkillExtractor # type: ignore
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re
import csv

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
    if res.status_code == 200:  # Verificar se a resposta foi bem-sucedida (200 OK)
        results = res.json()
        return results
    else:
        print(f"Erro {res.status_code} - {res.text}")
        return {}

# Função para exportar dados para CSV
def export_to_csv(data, filename):
    with open(filename, 'w+', newline='\n',encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')
        # Cabeçalho do CSV
        writer.writerow(["titulo", "empresa", "descricao", "data_publicacao", "salario", "localizacao"])
        
        # Escreve as linhas de dados
        for item in data:
            titulo = item["title"]
            empresa = item["company"]["name"]
            descricao = re.sub(r'<[^>]*>', '', item["body"])
            data_publicacao = item["publishedAt"]
            salario = item["wage"]
            try:
                localizacao = ", ".join(loc["name"] for loc in item["locations"])
            except:
                localizacao = "Não há informação"
            writer.writerow([titulo, empresa, descricao, data_publicacao, salario, localizacao])

def fetch_data():
    global list_results  # Para ser acessado dentro de outras funções
    limit = 100
    page = 1
    response = pedido(limit, page)

    # Verifica se a resposta contém a chave 'results' ou se não há resposta
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

def filter_by_dates_results(list_results, start_date, end_date):    # Função para o d), devolve resultados num intervalo
    sorted_results = sorted(list_results, key=lambda x: x["updatedAt"], reverse=True)   # Organiza os resultados de maior para menor data de atualizacao
    filtered_results = []

    for res in sorted_results:
        update_date_str = res['updatedAt']
        update_date = datetime.strptime(update_date_str, '%Y-%m-%d %H:%M:%S')
        if update_date <= end_date:   #  Enquanto a data de atualizacao for menor do que a data final, acrescenta ao resultado final
            filtered_results.append(res)
        if update_date < start_date:  # Quando for menor que a data inicial, devido ao sort, podemos parar porque não há mais resultados que queiramos
            break
    print(f"A analisar {len(filtered_results)} resultados no intervalo dado.")
    return filtered_results

def process_job(res, given_skills, skill_extractor):
    body = res['body']
    try:
        annotations = skill_extractor.annotate(body)
    except (IndexError, ValueError) as e:
        print(f"Erro a processar o 'body': {e}")
        return None

    annoted_skills = [skill['doc_node_value'].lower() for skill in annotations['results']['full_matches']]
    annoted_skills += [skill['doc_node_value'].lower() for skill in annotations['results']['ngram_scored']]

    if all(item in annoted_skills for item in given_skills):    #set(given_skills) & set(annoted_skills):
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
def top(n_jobs: Annotated[int, typer.Argument(help="Número de trabalhos")], export: Optional[bool] = False):  # Chama o número de trabalhos a escolher n
    """
    Obtém os últimos trabalhos publicados.
    """
    if not list_results:
        fetch_data()

    sorted_results = sorted(list_results, key=lambda x: x["publishedAt"], reverse=True)  # Ordena a lista de resultados pela data de publicação
    print(sorted_results[:n_jobs])  # Devolve os n primeiros valores da lista
    
    if export:
        export_to_csv(sorted_results[:n_jobs], "top_jobs.csv")
        print("Dados exportados para top_jobs.csv")
#b)
@app.command()
def search(localidade: Annotated[str, typer.Argument(help="Localidade a procurar")], empresa: Annotated[str, typer.Argument(help="Empresa do trabalho")], n_jobs: Annotated[int, typer.Argument(help="Número de trabalhos")], export: Optional[bool] = False):
    """
    Obtém os trabalhos 'full-time' numa empresa, numa localidade.
    """
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
    print(filtered_jobs)
    print("\n".join(simplified_results))
    
    if export:
        export_to_csv(filtered_jobs, "search.csv")
        print("Dados exportados para top_jobs.csv")

#c)
@app.command()
def salary(job_id: Annotated[str, typer.Argument(help="Id do trabalho")]):
    """
    Obtém o salário dum trabalho.
    """
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
        description = job_data.get("body", "")
        matches = re.findall(r"\b\d{1,3}(?:\.\d{3})*(?:,\d{2})?\b", description)
        
        if matches:
            # Exibe o primeiro valor encontrado que pode representar um salário
            salary_estimate = matches[0]
            print(f"Salário estimado encontrado na descrição: {salary_estimate}")
        else:
            print("Salário não especificado na oferta de emprego.")

#d)
@app.command()
def skills(given_skills:Annotated[List[str], typer.Argument(help="Competências a procurar '[skill1,skill2,...]'")], start_date:Annotated[str, typer.Argument(help="Início (yyyy-mm-dd HH:MM:SS)")], end_date:Annotated[str, typer.Argument(help="Fim (yyyy-mm-dd HH:MM:SS)")], export: Optional[bool] = False):
    """
    Obtém os trabalhos que seguem pede certas competências atualizadas no intervalo dado.
    """
    # Transforma as skills dadas numa lista de skills com valores em minusculas
    joined_skills = ' '.join(given_skills).lower()
    given_skills = re.findall(r'[^\[\],\s]+', joined_skills)

    if not list_results:
        fetch_data()
    
    # Iniciar o skill extractor
    nlp = spacy.load("en_core_web_lg")
    skill_extractor = SkillExtractor(nlp, SKILL_DB, PhraseMatcher)

    start_date, end_date = start_date.replace(' ',''), end_date.replace(' ','')

    if end_date < start_date:
        print(f"Data final menor que inicial, a iniciar com valores trocados...")
        start_date, end_date = end_date, start_date

    if len(start_date) == 10:
        start_date += " 00:00:01"
    if len(end_date) == 10:
        end_date += " 23:59:59"

    try:
        start_date = datetime.strptime(start_date, '%Y-%m-%d %H:%M:%S')
        end_date = datetime.strptime(end_date, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print("Erro ao ler as datas, verifique se estas existem.")
        return {}
    
    filtered_results = filter_by_dates_results(list_results, start_date, end_date)

    results = process_jobs_concurrently(filtered_results, given_skills, skill_extractor, max_workers=8)
    print(results)

    if export:
        export_to_csv(results, "skills.csv")
        print("Dados exportados para top_jobs.csv")
    

if __name__ == "__main__":
    app()  # Executa a app Typer