from typing import Optional, List
from bs4 import BeautifulSoup
import requests
import typer
from typing_extensions import Annotated
import re
import json
#import spacy
#from spacy.matcher import PhraseMatcher
#from skillNer.general_params import SKILL_DB # type: ignore
#from skillNer.skill_extractor_class import SkillExtractor # type: ignore
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
import re
import csv

app = typer.Typer()
list_results = []

# Função para aceder ao URL
def request(url, headers, get_soup = False):
    payload = {}
    res = requests.request("GET", url, headers=headers, data=payload)
    if res.status_code == 200:  # Verificar se a resposta foi bem-sucedida (200 OK)
        if get_soup:
            soup = BeautifulSoup(res.text, "lxml")
            return soup
        else:
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

def export_to_csv2(data, filename):
    with open(filename, 'w', newline='\n',encoding='utf-8') as csvfile:
        writer = csv.writer(csvfile, delimiter=',')

        if type(data) == list:
            e = data
        else:
            e = [data]

        header = list(e[0].keys())

        writer.writerow(header)
        
        for element in e:
            values = []
            for value in element.values():
                values.append(value)
            writer.writerow(values)

def fetch_data():
    global list_results  # Para ser acessado dentro de outras funções
    limit = 100
    page = 1
    url = f"https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236&limit={limit}&page={page}"
    headers = {'User-Agent': "ALPCD_5", 'Cookie': 'itjobs_pt=3cea3cc1f4c6a847f8c459367edf7143:94de45f2a55a15b2672adf8788ac8072e7bfd5c5'}
    response = request(url, headers)

    # Verifica se a resposta contém a chave 'results' ou se não há resposta
    if not response or "results" not in response:
        print("Nenhum resultado encontrado na resposta da API.")
        return
    
    list_results = response["results"]
    print("A recolher respostas do URL...")

    while page * limit < response["total"]:  # Para limite=100 e total=1261, página vai até 13
        page += 1
        try:  # Caso seja devolvido um dicionário vazio, para não ocorrerem erros
            url = f"https://api.itjobs.pt/job/list.json?api_key=ee176fa9456283ab9c42f357b036e236&limit={limit}&page={page}"
            new_results = request(url, headers)["results"]
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
        print("Dados exportados para search.csv")

#c)
@app.command()
def salary(job_id: Annotated[str, typer.Argument(help="Id do trabalho")]):
    """
    Obtém o salário dum trabalho.
    """
    # Usar a função com retentativa para obter os detalhes do job
    url = f"https://api.itjobs.pt/job/get.json?api_key=ee176fa9456283ab9c42f357b036e236&id={job_id}"
    headers = {'User-Agent': "ALPCD_5", 'Cookie': 'itjobs_pt=3cea3cc1f4c6a847f8c459367edf7143:94de45f2a55a15b2672adf8788ac8072e7bfd5c5'}  # Necessário por 'User-Agent' nos headers
    job_data = request(url, headers)
    
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
        print("Dados exportados para skills.csv")

#TP2
#a)
from bs4 import BeautifulSoup

@app.command()
def get(job_id: Annotated[int, typer.Argument(help="ID do trabalho")], export: Optional[bool] = False):
    """
    Busca informações de uma vaga específica (jobID) e enriquece com dados da empresa do AmbitionBox.
    """
    # 1. Obter dados da vaga usando a API
    url = f"https://api.itjobs.pt/job/get.json?api_key=ee176fa9456283ab9c42f357b036e236&id={job_id}"
    headers = {'User-Agent': "ALPCD_5", 'Cookie': 'itjobs_pt=3cea3cc1f4c6a847f8c459367edf7143:94de45f2a55a15b2672adf8788ac8072e7bfd5c5'}  # Necessário por 'User-Agent' nos headers
    job_data = request(url, headers)
    if not job_data:
        print(f"Não foi possível encontrar o jobID {job_id}. Verifique se o ID é válido.")
        return

    # 2. Recolher o nome da empresa para procurar dados no AmbitionBox
    company_name = job_data.get("company", {}).get("name", "Desconhecida")
    if company_name == "Desconhecida":
        print("Não foi possível obter o nome da empresa.")
        return
    modified_company_name = re.sub(r'(.)( *Portugal)(.*)', r"\1", company_name)

    # 3. Fazer Web Scraping no AmbitionBox
    ambitionbox_url = f"https://www.ambitionbox.com/overview/{re.sub(' ', '-', modified_company_name).lower()}-overview"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    }
    soup = request(ambitionbox_url, headers, get_soup=True)

    # 4. Extrair dados relevantes (ajuste os seletores conforme o HTML do AmbitionBox)
    try:
        rating = soup.find("span", class_="css-1jxf684 text-primary-text font-pn-700 text-xl !text-base").text
        description = soup.find("div", class_="text-sm font-pn-400 [&_ul]:list-disc [&_ol]:list-[auto] [&_ul]:ml-5 [&_ol]:ml-5").find("p").text
        benefits_soup = soup.find_all("div", class_="css-146c3p1 font-pn-600 text-sm text-primary-text")
        if benefits_soup:
            benefits = [b.text for b in benefits_soup]
    except AttributeError:
        print("Não foi possível encontrar informações adicionais no AmbitionBox.")
        rating, description, benefits = "N/A", "N/A", []

    # 5. Combinar dados e exibir como JSON
    enriched_data = {
        "id": job_id,
        "title": job_data.get("title"),
        "company_name": company_name,
        "rating": rating,
        "ambition_box_description": description,
        "ambition_box_benefits": benefits,
    }
    print(enriched_data)
    if export:
        export_to_csv2(enriched_data, "get.csv")
        print("Dados exportados para get.csv")
#b)
@app.command()
def statistics():
    """
    Gera estatísticas de vagas agrupadas por Zona e Tipo de Trabalho em um CSV.
    """
    url_jobs = f"https://www.ambitionbox.com/servicegateway-ambitionbox/jobs-services/v0/jobs?isFilterApplied=true&page=1"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
        "AppId": "931",
        "SystemId":"ambitionbox-jobs-services"
        }

    stats = {}
    jobs = request(url_jobs, headers)
    max_page = jobs['pagination']['totalPages']
    for page in range(1, 5):
        print(f"A analisar a página {page}.")
        jobs = request(f"https://www.ambitionbox.com/servicegateway-ambitionbox/jobs-services/v0/jobs?isFilterApplied=true&page={page}",headers)
        if jobs == {}:
            break
        jobs = jobs['jobs']
        if page == 1:
            jobs = jobs[1:]

        for job in jobs:
            job_id = job['jobId']
            job_info = request(f"https://www.ambitionbox.com/servicegateway-ambitionbox/jobs-services/v0/jobs/info/{job_id}", headers)
            if job_info == {}:
                continue

            job_info = job_info['data']
            job_type = job_info['jobProfile']
            locations = job_info['locations']
            vacancies = job_info['vacancies']
            for zone in locations:
                key = (zone, job_type)
                stats[key] = stats.get(key, 0) + vacancies

    sorted_stats = dict(sorted(stats.items(), key=lambda item: item[1], reverse=True))

    filename = "job_statistics.csv"
    with open(filename, "w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Zona", "Tipo de Trabalho", "Nº de Vagas"])
        for (zone, job_type), count in sorted_stats.items():
            writer.writerow([zone, job_type, count])

    print(f"Ficheiro '{filename}' criado com sucesso.")

#c)
@app.command()
def list_skills(search:Annotated[str, typer.Argument(help="Profissão a procurar")], export: Optional[bool] = False):
    """
    Obtém o top10 de competências mais requisitadas para a profissão dada.
    """
    search = search.lower().strip()
    final_search = re.sub(r'\s+', '-', search)
    url = f"https://www.ambitionbox.com/servicegateway-ambitionbox/jobs-services/v0/jobs/meta?jobProfile={final_search}&pageName=profileJobs"
    headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "AppId": "931",
    "SystemId":"ambitionbox-jobs-services"
    }

    jobProfile = request(url, headers)
    jobProfileIds = jobProfile["data"]["jobProfileIds"]
    if jobProfileIds != []:
        skills = []

        for id in jobProfileIds:
            url = f"https://www.ambitionbox.com/servicegateway-ambitionbox/jobs-services/v0/jobs/filters?profileIds={id}&isFilterApplied=true"
            skills += request(url, headers)["filters"]["skills"][:10]

        if len(jobProfileIds) > 1:
            sorted_skills = sorted(skills, key=lambda x: x['count'], reverse=True)
            skills = sorted_skills[:10]

        final_skills = []
        for element in skills:
            skill = element['name']
            count = element['count']
            final_skills.append({'skill':skill,'count':count})

        print(final_skills)
        if export:
            export_to_csv2(final_skills, "final_skills.csv")
            print("Dados exportados para final_skills.csv")
    else:
        print("Profissão inexistente em lista.")

#d)
@app.command()
def getd(job_id: Annotated[int, typer.Argument(help="ID do trabalho")], export: Optional[bool] = False):

    # Dados da vaga 
    url = f"https://api.itjobs.pt/job/get.json?api_key=ee176fa9456283ab9c42f357b036e236&id={job_id}"
    headers = {'User-Agent': "ALPCD_5", 'Cookie': 'itjobs_pt=3cea3cc1f4c6a847f8c459367edf7143:94de45f2a55a15b2672adf8788ac8072e7bfd5c5'}  # Necessário por 'User-Agent' nos headers
    job_data = request(url, headers)
    if not job_data:
        print(f"Não foi possível encontrar o jobID {job_id}. Verifique se o ID é válido.")
        return

    # 2. Nome da empresa 
    company_name = job_data.get("company", {}).get("name", "Desconhecida")
    if company_name == "Desconhecida":
        print("Não foi possível obter o nome da empresa.")
        return
    modified_company_name = re.sub(r'(.)( *Portugal)(.*)', r"\1", company_name)

    url = f"https://www.simplyhired.pt/_next/data/XJuAWs-VlRLF8qpN2iQ1H/pt-PT/search.json?q={re.sub(' ', '+', modified_company_name).lower()}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:98.0) Gecko/20100101 Firefox/98.0"}
    response = request(url, headers)

    # 4. Extrair dados relevantes (ajuste os seletores conforme o HTML do SimplyHired)
    try:
        employer_info = response['pageProps']['viewJobData']
        rating = employer_info['employerOverallRating']
        description = employer_info['jobDescriptionHtml']
        benefits = employer_info['benefits']

        description = BeautifulSoup(description, "html.parser").get_text(strip=True)

    except:
        print("Não foi possível encontrar informações adicionais no SimplyHired.")
        rating, description, benefits = "N/A", "N/A", []


    enriched_data = {
        "id": job_id,
        "title": job_data.get("title"),
        "company_name": company_name,
        "rating": rating,
        "simplyhired_description": description,
        "simplyhired_benefits": benefits,
    }
    print(json.dumps(enriched_data, indent=4))

    if export:
        export_to_csv2(enriched_data, "get.csv")
        print("Dados exportados para get.csv")

if __name__ == "__main__":
    app()