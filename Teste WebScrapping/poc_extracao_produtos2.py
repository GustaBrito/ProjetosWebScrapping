import time
import re
import os
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import NoSuchElementException, TimeoutException

URL_BASE = 'https://www.supercentralonline.com.br/'
CIDADE_TESTE = 'CIDADE_SUPERCENTRAL'

SELECTOR_EXPANDIR_DEPARTAMENTOS = ".text-3xl.icon-expand_more"
SELECTOR_CARD_PRODUTO_GERAL = ".vertical.ng-star-inserted" 
SELECTOR_PRECO = ".font-bold"

SELECTOR_FECHAR_MODAL_OU_AVISO = "button.close, .close-button, [aria-label='Fechar'], .modal-fechar, .fechar-aviso-cookie"


###################################################################################
#  FUNÇÕES UTILITÁRIAS 
###################################################################################

def pausa(tempo_em_segundos: float):
    """Gera uma pausa em segundos para sincronização."""
    time.sleep(tempo_em_segundos)

def trata_campo_preco(valor: str) -> str:
    """Trata o valor do preço. Retorna '0.00' se for inválido, senão retorna o valor formatado."""
    valor_auxiliar = valor.upper().strip()
    valor_auxiliar = valor_auxiliar.replace('R$', '').replace('.', '').replace('UN', '').strip()
    valor_auxiliar = valor_auxiliar.replace(',', '.')
    try:
        return "{:.2f}".format(float(valor_auxiliar))
    except ValueError:
        return '0.00' 

def trata_campo_descricao(descricao: str) -> str:
    """Trata a descrição removendo espaços duplos e limpando."""
    descricao_tratada: str = descricao.replace('  ', ' ').strip()
    return descricao_tratada

###################################################################################
#  CLASSE DE EXTRAÇÃO 
###################################################################################

class PocPesquisaOtimizada:

    def __init__(self, navegador, logger_func):
        self.navegador = navegador
        self.logger = logger_func 

    def fechar_modal_inicial(self):
        """Tenta fechar modais/popups que podem bloquear o acesso ao menu."""
        self.logger("🔄 Verificando e tentando fechar modais iniciais (Cidade/Aviso)...")

        seletores_tentativa = [
            By.CSS_SELECTOR, "button.close",
            By.CSS_SELECTOR, ".close-button",
            By.CSS_SELECTOR, ".close-modal",
            By.XPATH, "//button[contains(text(), 'Fechar')]",
            By.XPATH, "//span[contains(text(), 'Entrar')]" 
        ]

        for i in range(0, len(seletores_tentativa), 2):
            by_type = seletores_tentativa[i]
            selector = seletores_tentativa[i+1]
            try:
                botao = WebDriverWait(self.navegador, 3).until(
                    EC.element_to_be_clickable((by_type, selector))
                )
                self.logger(f"   [MODAL] Clicando no seletor: {selector}")
                botao.click()
                pausa(1.5) # Pausa para o modal sumir
                self.logger("   [MODAL] Modal fechado com sucesso.")
                return True
            except (TimeoutException, NoSuchElementException):
                continue
            except Exception as e:
                self.logger(f"   [MODAL-ERRO] Erro ao tentar fechar modal com {selector}: {e}")
        
        self.logger("   [MODAL] Nenhum modal de bloqueio encontrado ou fechado.")
        return False


    def expandir_menu_departamentos(self):
        """Clica no ícone de seta para expandir todos os departamentos."""
        self.logger("🔄 Tentando expandir o menu de departamentos...")
        try:
            botao = WebDriverWait(self.navegador, 10).until(
                # EC.visibility_of_element_located é mais seguro em headless
                EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_EXPANDIR_DEPARTAMENTOS))
            )
            # Tenta clicar com JavaScript se o clique normal falhar 
            self.navegador.execute_script("arguments[0].click();", botao)
            pausa(2)
            self.logger("✅ Menu de departamentos expandido.")
            return True
        except Exception as err:
            self.logger(f"❌ Não foi possível expandir o menu: {err}")
            return False

    def obter_links_departamentos(self):
        """Coleta todos os caminhos relativos de departamento ('departamentos/...')."""
        selector_links = "a[href^='/departamentos/']"
        
        try:
            WebDriverWait(self.navegador, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector_links))
            )
            links_el = self.navegador.find_elements(By.CSS_SELECTOR, selector_links)
            
            links_unicos = []
            hrefs_vistos = set()
            
            for link in links_el:
                href = link.get_attribute('href')
                match = re.search(r'(departamentos/[^/]+)', href)
                if match:
                    path = match.group(0) 
                    if path not in hrefs_vistos:
                        hrefs_vistos.add(path)
                        links_unicos.append(path)

            self.logger(f"✅ Encontrados {len(links_unicos)} caminhos de departamento únicos.")
            return links_unicos
            
        except Exception as err:
            self.logger(f"❌ Erro ao obter links de departamentos: {err}")
            return []

    def aguarda_pagina_produtos_carregar(self):
        """Aguarda a visibilidade de um elemento de produto para garantir o carregamento."""
        try:
            WebDriverWait(self.navegador, 5).until( 
                EC.presence_of_element_located((By.CSS_SELECTOR, ".vip-card-produto-descricao"))
            )
            return True
        except TimeoutException:
            return False
        except Exception as err:
            self.logger(f"   [SYNC-ERRO] Falha ao aguardar produtos: {err}")
            return False
        
    def _extrair_dados_pagina_atual(self) -> list:
        # A lógica de extração (ignorar NULLs e setar implicitly_wait para 1s)
        produtos_encontrados = []
        self.navegador.implicitly_wait(1) 
        etiquetas = self.navegador.find_elements(By.CSS_SELECTOR, SELECTOR_CARD_PRODUTO_GERAL)
        self.logger(f"   [EXTRACAO] Encontrados {len(etiquetas)} elementos de produto na página.")

        for etiqueta in etiquetas:
            descricao_tratada = None
            try:
                descricao_el = etiqueta.find_element(By.CSS_SELECTOR, ".vip-card-produto-descricao")
                descricao_tratada = trata_campo_descricao(descricao_el.text)
                
                preco_el = etiqueta.find_element(By.CSS_SELECTOR, SELECTOR_PRECO)
                preco_formatado = trata_campo_preco(preco_el.text)
                
                if preco_formatado != '0.00':
                    produtos_encontrados.append({'descricao': descricao_tratada, 'preco': preco_formatado})
                    log_message = f"   ✅ PRODUTO: {descricao_tratada[:80].ljust(80)} | Preço: R$ {preco_formatado}"
                    self.logger(log_message)
                else:
                    self.logger(f"   ❌ FILTRADO: Preço 0.00. Descrição: {descricao_tratada[:80].ljust(80)}")
            except NoSuchElementException:
                if descricao_tratada:
                    self.logger(f"   ❌ FILTRADO: Preço NULL. Descrição: {descricao_tratada[:80].ljust(80)}")
                else:
                    pass 
            except Exception as err:
                self.logger(f"   [EXTRACAO-ERRO] Falha ao extrair um produto: {err}")

        self.navegador.implicitly_wait(10) 
        return produtos_encontrados


    def controla_paginacao_url(self, url_departamento: str) -> list:
        """Coleta produtos de todas as páginas de um departamento, navegando por URL (?page=X)."""
        pagina_atual = 1
        produtos_coletados = []

        while True:
            url_navegacao = f"{URL_BASE}{url_departamento}"
            if pagina_atual > 1:
                url_navegacao = f"{url_navegacao}?page={pagina_atual}"

            self.logger(f"\n   [NAVEGACAO] Acessando Página: {pagina_atual} | URL: {url_navegacao}")

            self.navegador.get(url_navegacao)
            pausa(0.5) 

            if not self.aguarda_pagina_produtos_carregar():
                if pagina_atual == 1:
                    self.logger("   [PAG-FIM] Nenhum produto carregado na primeira página. Pulando departamento.")
                    break
                else:
                    self.logger("   [PAG-FIM] Falha ao carregar produtos na página seguinte. Assumindo fim da paginação.")
                    break
            
            produtos_pagina_atual = self._extrair_dados_pagina_atual()
            
            if not produtos_pagina_atual and pagina_atual > 1:
                self.logger("   [PAG-FIM] Página acessada, mas vazia. Fim da paginação.")
                break

            produtos_coletados.extend(produtos_pagina_atual)
            
            pagina_atual += 1
            
        return produtos_coletados

###################################################################################
#  ROTINA PRINCIPAL DE TESTE 
###################################################################################

def inicializar_teste():
    """Rotina principal para iniciar o Selenium, orquestrar a extração e configurar o log de arquivo."""
    
    extracao_dir = "Extracao"
    try:
        os.makedirs(extracao_dir, exist_ok=True)
    except OSError as e:
        print(f"\n[ERRO CRÍTICO] Não foi possível criar o diretório '{extracao_dir}'. Verifique permissões. {e}")
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file_path = os.path.join(extracao_dir, f"Extracao_{timestamp}.txt")
    
    contador_produtos_final = 0

    def log_to_file(message, is_flow_message=False):
        if is_flow_message:
            print(message) 
        
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(message + '\n')

    log_to_file(f"=======================================================", is_flow_message=True)
    log_to_file(f"INÍCIO DO POC DE EXTRAÇÃO: {URL_BASE}", is_flow_message=True)
    log_to_file(f"MODO DE OPERAÇÃO: HEADLESS (MÁXIMA VELOCIDADE)", is_flow_message=True)
    log_to_file(f"ATENÇÃO: Tentando fechar modal que pode bloquear clique.", is_flow_message=True)
    log_to_file(f"ARQUIVO DE LOG DE DETALHES: {log_file_path}", is_flow_message=True)
    log_to_file(f"=======================================================")

    navegador = None
    todos_os_produtos = []
    
    try:

        opcoes = webdriver.ChromeOptions()

        opcoes.add_argument("window-size=1920,1080")
        opcoes.add_argument("--disable-infobars")
        opcoes.add_argument("--headless")
        opcoes.add_argument("--no-sandbox") 
        opcoes.add_argument("--disable-dev-shm-usage") 
        
        navegador = webdriver.Chrome(options=opcoes) 
        
        navegador.implicitly_wait(10) 
        
        log_to_file("Iniciando navegação...", is_flow_message=True)
        navegador.get(URL_BASE)

        poc = PocPesquisaOtimizada(navegador, log_to_file)
        
        poc.fechar_modal_inicial()
        
        if not poc.expandir_menu_departamentos():
             log_to_file("\n[FLUXO-ERRO] Falha crítica ao expandir departamentos. Encerrando.", is_flow_message=True)
             return

        links_departamentos = poc.obter_links_departamentos()
        
        if not links_departamentos:
            log_to_file("\n[FLUXO-ERRO] Nenhum link de departamento encontrado. Encerrando.", is_flow_message=True)
            return

        for link_departamento in links_departamentos:
            
            nome_departamento = link_departamento.split('/')[-1].replace('-', ' ').upper()
            
            log_to_file(f"\n\n=======================================================")
            log_to_file(f">>> INICIANDO DEPTO: {nome_departamento} | Link: {link_departamento} <<<")
            log_to_file(f"=======================================================")
            
            produtos_departamento = poc.controla_paginacao_url(link_departamento)
            
            todos_os_produtos.extend(produtos_departamento)
            contador_produtos_final = len(todos_os_produtos)
            
            log_to_file(f"\n<<< FIM DEPTO: {nome_departamento}. Produtos coletados: {len(produtos_departamento)} >>>")
            pausa(1)

    except Exception as e:
        log_to_file(f"\n[ERRO CATASTRÓFICO] Ocorreu um erro fatal no teste: {e}", is_flow_message=True)
        
    finally:
        if navegador:
            navegador.quit()
        
        log_to_file("\n\n#######################################################", is_flow_message=True)
        log_to_file(f"PROCESSO FINALIZADO. TOTAL GERAL DE PRODUTOS: {contador_produtos_final}", is_flow_message=True)
        log_to_file("#######################################################", is_flow_message=True)

if __name__ == '__main__':
    inicializar_teste()