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

###################################################################################
#  FUNÇÕES UTILITÁRIAS
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
    descricao_tratada: str = descricao.replace('  ', ' ').strip()
    return descricao_tratada

###################################################################################
#  CLASSE DE EXTRAÇÃO OTIMIZADA
###################################################################################

class PocPesquisaOtimizada:


    def __init__(self, navegador, logger_func):
        self.navegador = navegador
        self.logger = logger_func 

        self.registros_vistos = 0 
        self.registros_positivos = 0

    def expandir_menu_departamentos(self):
        """Clica no ícone de seta para expandir todos os departamentos."""
        self.logger("🔄 Tentando expandir o menu de departamentos...")
        try:

            botao = WebDriverWait(self.navegador, 5).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SELECTOR_EXPANDIR_DEPARTAMENTOS))
            )
            botao.click()
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

            WebDriverWait(self.navegador, 5).until(
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
            self.logger(f"   [SYNC-ERRO] Falha ao aguardar produtos: {err}")
            return False

    def _extrair_dados_pagina_atual(self) -> tuple[list, int, int]:
        """Extrai apenas produtos com preço da página atualmente carregada. Retorna a lista de produtos, 
        o total de vistos e o total de positivos."""
        produtos_encontrados = []

        vistos_na_pagina = 0
        positivos_na_pagina = 0

        # Configura o implicitly_wait para 1s para acelerar a falha em produtos sem preço
        self.navegador.implicitly_wait(1) 
        
        etiquetas = self.navegador.find_elements(By.CSS_SELECTOR, SELECTOR_CARD_PRODUTO_GERAL)
        
        self.logger(f"   [EXTRACAO] Encontrados {len(etiquetas)} elementos de produto na página.")

        for etiqueta in etiquetas:
            descricao_tratada = None
            
            try:
                descricao_el = etiqueta.find_element(By.CSS_SELECTOR, ".vip-card-produto-descricao")
                descricao_tratada = trata_campo_descricao(descricao_el.text)

                vistos_na_pagina += 1 

                preco_el = etiqueta.find_element(By.CSS_SELECTOR, SELECTOR_PRECO)
                preco_valor = preco_el.text
                
                preco_formatado = trata_campo_preco(preco_valor)

                if preco_formatado != '0.00':
                    produtos_encontrados.append({'descricao': descricao_tratada, 'preco': preco_formatado})
                    positivos_na_pagina += 1 
                    
                    log_message = f" ✅ {descricao_tratada[:80].ljust(80)} | R$ {preco_formatado}"
                    self.logger(log_message)
                else:
                    self.logger(f"   ❌ FILTRADO: Preço 0.00. Descrição: {descricao_tratada[:80].ljust(80)}")

            except NoSuchElementException:
                # produto sem preço
                if descricao_tratada:
                    vistos_na_pagina += 1 
                    self.logger(f"   ❌ FILTRADO: Preço NULL. Descrição: {descricao_tratada[:80].ljust(80)}")
                else:
                    pass 
            except Exception as err:
                self.logger(f"   [EXTRACAO-ERRO] Falha ao extrair um produto: {err}")

        # Retorna o implicitly_wait para o padrão (5s)
        self.navegador.implicitly_wait(5) 

        return produtos_encontrados, vistos_na_pagina, positivos_na_pagina

    def controla_paginacao_url(self, url_departamento: str) -> tuple[list, int, int]:
        """Coleta produtos de todas as páginas de um departamento, navegando por URL (?page=X).
        Retorna a lista de produtos, o total de vistos e o total de positivos do departamento."""
        pagina_atual = 1
        produtos_coletados = []
        total_vistos = 0
        total_positivos = 0

        while True:
            url_navegacao = f"{URL_BASE}{url_departamento}"
            if pagina_atual > 1:
                url_navegacao = f"{url_navegacao}?page={pagina_atual}"

            self.logger(f"\n   [NAVEGACAO] Acessando Página: {pagina_atual} | URL: {url_navegacao}")

            MAX_TENTATIVAS = 2
            carregamento_sucesso = False

            for tentativa in range(1, MAX_TENTATIVAS + 1):
                try:
                    self.navegador.get(url_navegacao)
                    pausa(3) # Aumentei a pausa para dar tempo ao servidor e evitar 500
                    
                    if self.aguarda_pagina_produtos_carregar():
                        carregamento_sucesso = True
                        break # Sai do loop de tentativas
                    elif tentativa == MAX_TENTATIVAS:
                        self.logger("   [RETRY-FAIL] Nenhuma tentativa obteve produtos. Falha ao carregar página.")
                
                except Exception as e:
                    self.logger(f"   [RETRY-ERRO] Erro na tentativa {tentativa}: {e}. Tentando novamente após pausa.")
                    pausa(5) # Pausa maior em caso de erro de rede ou timeout
            
            # Se o carregamento não foi bem-sucedido após as tentativas
            if not carregamento_sucesso:
                if pagina_atual == 1:
                    self.logger("   [PAG-FIM] Nenhum produto carregado na primeira página após tentativas. Pulando departamento.")
                else:
                    self.logger("   [PAG-FIM] Falha ao carregar produtos na página seguinte. Assumindo fim da paginação.")
                break
            
            # Se o carregamento foi bem-sucedido, extrai os dados
            produtos_pagina_atual, vistos_na_pagina, positivos_na_pagina = self._extrair_dados_pagina_atual()
            
            # Contadores
            total_vistos += vistos_na_pagina
            total_positivos += positivos_na_pagina
            
            if not produtos_pagina_atual and pagina_atual > 1:
                self.logger("   [PAG-FIM] Página acessada, mas vazia. Fim da paginação.")
                break

            produtos_coletados.extend(produtos_pagina_atual)
            
            pagina_atual += 1
            
        return produtos_coletados, total_vistos, total_positivos

###################################################################################
#  ROTINA PRINCIPAL DE TESTE
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
    
    # Contadores globais
    total_registros_vistos = 0 
    total_registros_positivos = 0

    def log_to_file(message, is_flow_message=False):
        if is_flow_message:
            print(message) 
        
        with open(log_file_path, 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    
    # Função auxiliar para fechar o popup de seleção de loja (Obrigatório para prosseguir)
    def trata_popup_inicial(driver, logger):
        # Seletor mais provável para o botão de fechar o modal ou confirmar a cidade
        # Se .icon-close não funcionar, inspecione o botão de fechar (X)
        SELETOR_FECHAR_MODAL = ".icon-close" 
        
        try:
            logger("🔄 Tentando tratar o modal de seleção de loja/cidade...")
            
            # Usamos um tempo maior (10s) para garantir que o modal carregue
            botao_fechar = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, SELETOR_FECHAR_MODAL))
            )
            botao_fechar.click()
            pausa(1) # Pequena pausa para o modal desaparecer
            logger("✅ Modal de seleção de loja fechado/ignorado. Prosseguindo.")
        except TimeoutException:
            logger("⚠️ Modal de seleção de loja não encontrado ou não apareceu. Prosseguindo.")
        except Exception as e:
            logger(f"❌ Erro ao tentar fechar/ignorar o modal: {e}")
        
    log_to_file(f"=======================================================", is_flow_message=True)
    log_to_file(f"INÍCIO DO POC DE EXTRAÇÃO: {URL_BASE}", is_flow_message=True)
    log_to_file(f"ATENÇÃO: Extraindo APENAS produtos com PREÇO.", is_flow_message=True)
    log_to_file(f"ARQUIVO DE LOG DE DETALHES: {log_file_path}", is_flow_message=True)
    log_to_file(f"=======================================================")

    navegador = None
    todos_os_produtos = []
    
    try:
        opcoes = webdriver.ChromeOptions()
        opcoes.add_argument("--start-maximized")
        opcoes.add_argument("--disable-infobars")
        
        navegador = webdriver.Chrome(options=opcoes) 
        
        # Tempo de espera implícita padrão
        navegador.implicitly_wait(5) 
        
        log_to_file("Iniciando navegação...", is_flow_message=True)
        navegador.get(URL_BASE)
        
        # --- NOVO TRECHO PARA TRATAR O POPUP/MODAL INICIAL ---
        trata_popup_inicial(navegador, log_to_file)
        # ---------------------------------------------------

        poc = PocPesquisaOtimizada(navegador, log_to_file)

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
            
            # Recebe os contadores do departamento
            produtos_departamento, vistos_depto, positivos_depto = poc.controla_paginacao_url(link_departamento)
            
            todos_os_produtos.extend(produtos_departamento)
            
            # Acumula nos contadores globais
            total_registros_vistos += vistos_depto
            total_registros_positivos += positivos_depto
            
            log_to_file(f"\n<<< FIM DEPTO: {nome_departamento}. Vistos: {vistos_depto} | Positivos: {positivos_depto} >>>")
            pausa(1)

    except Exception as e:
        log_to_file(f"\n[ERRO CATASTRÓFICO] Ocorreu um erro fatal no teste: {e}", is_flow_message=True)
        
    finally:
        if navegador:
            navegador.quit()
        
        # O timestamp de fim estava faltando no log_to_file final, adicionei
        tempofim = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_to_file("\n\n#######################################################", is_flow_message=True)
        log_to_file(f"PROCESSO FINALIZADO.", is_flow_message=True)
        log_to_file(f"TOTAL DE REGISTROS VISTOS: {total_registros_vistos}", is_flow_message=True)
        log_to_file(f"TOTAL DE REGISTROS POSITIVOS (COM PREÇO): {total_registros_positivos}", is_flow_message=True)
        log_to_file(f"TEMPO DE INICIO:{timestamp} - TEMPO DE FIM: {tempofim}")
        log_to_file("#######################################################", is_flow_message=True)

if __name__ == '__main__':
    inicializar_teste()