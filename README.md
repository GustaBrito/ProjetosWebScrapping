# 🕸️ Web Scraper para Supermercado Online: SuperCentral

<div align="center">
  <img src="https://img.shields.io/badge/Python-3.8+-blue.svg" alt="Python 3.8+">
  <img src="https://img.shields.io/badge/Selenium-WebDriver-green.svg" alt="Selenium WebDriver">
  <img src="https://img.shields.io/badge/Web-Scraping-orange.svg" alt="Web Scraping">
</div>

> Sistema automatizado e resiliente de extração de dados de produtos e preços do SuperCentral Online.

---

## 📋 Sobre o Projeto

Sistema robusto de **web scraping** desenvolvido em Python para coleta estruturada de dados de produtos, preços e disponibilidade do supermercado online **SuperCentral**.

É a solução ideal para:
* **Análise de Mercado** e monitoramento de preços.
* **Monitoramento Competitivo** em tempo real.
* **Processos ETL** (Extração, Transformação e Carga) para alimentação de sistemas internos.

---

## 🚀 Funcionalidades Chave

O scraper foi construído com foco em **inteligência**, **extração precisa** e **resiliência**.

### 🔍 Navegação Inteligente (Selenium)
* ✅ **Expansão automática** do menu de departamentos.
* ✅ Navegação eficiente por **URL parameters** (substituindo cliques em botões de paginação).
* ✅ Tratamento de **modais, popups e barras de cookies**.
* ✅ Sincronização inteligente com **waits explícitos** (`WebDriverWait`) para carregamento de elementos.

### 📊 Extração de Dados
* ✅ Coleta precisa de **descrição, preço** e outras informações dos produtos.
* ✅ **Filtro automático** de produtos sem preço ou com valor zero/inválido.
* ✅ Tratamento e **formatação padronizada** dos campos extraídos.
* ✅ Métricas em tempo real (**vistos** vs. **positivos**).

### 🔧 Resiliência e Logs
* ✅ Sistema de **retry** para falhas de carregamento e *Timeouts*.
* ✅ Tratamento robusto de **exceções** (e.g., `TimeoutException`, `NoSuchElementException`).
* ✅ **Timeout configurável** para operações críticas.
* ✅ **Log detalhado** de execução com *timestamps*, níveis de detalhe (INFO, ERRO) e métricas de performance.

---

## 🛠️ Tecnologias

### Stack Tecnológica
* **Python 3.8+**
* **Selenium WebDriver**
* **Chrome Driver** (ou outro browser driver)
* **WebDriverWait** e Tratamento de Exceções

🔧 Configuração (Parâmetros Ajustáveis)

Os principais parâmetros podem ser ajustados diretamente no código:

PAUSA_CARREGAMENTO = 3       # Pausa em segundos após carregamentos longos

TIMEOUT_PADRAO = 5           # Timeout máximo para elementos

MAX_TENTATIVAS = 2           # Máximo de retries em caso de falha

# Seletores CSS (exemplo)

SELECTOR_EXPANDIR_DEPARTAMENTOS = ".text-3xl.icon-expand_more"

SELECTOR_CARD_PRODUTO = ".vertical.ng-star-inserted"

SELECTOR_PRECO = ".font-bold"

# 🏗️ Arquitetura (Estrutura de Classes)

O projeto é orientado a objetos para facilitar a manutenção e a escalabilidade:

    """
    Classe principal que orquestra todo o processo de scraping
    (expansão, paginação, extração, logging e tratamento de erros).
    """
    def expandir_menu_departamentos(self)
    def obter_links_departamentos(self)
    def controla_paginacao_url(self)
    def _extrair_dados_pagina_atual(self)
