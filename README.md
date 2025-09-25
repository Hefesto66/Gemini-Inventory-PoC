Padronizador de componentes de IA (PoC)
📖 Sobre o Projeto
Este projeto é uma Prova de Conceito (Prova de Conceito) desenvolvido para explorar e entender como capacidades da API do Google Gemini no contexto de aplicações especializadas. O objetivo principal foi criar um sistema inteligente para padronizar e enriquecer dados de insumos elétricos, servindo como protetor para uma futura implementação de uma lógica de LLM em produção no WebApp interno da AX Automação.

A aplicação funciona em um cliente simples de terminal e é capaz de:

Receber uma descrição de um componente elétrico.

Classificar o componente em uma categoria pré-definida.

Sugerir um nome padronizado para o componente.

Aprender com as interações, salvando novos exemplos em uma base de conhecimento.

📚 Funções Principais
Arquitetura Modular: O código é organizado de forma limpa, separando a lógica de interação com o usuário (main.py), o núcleo de IA (ai_core.py) e o gerenciamento de dados (data_manager.py).

Fluxo de IA de Múltiplos Passos: A IA primeiro classificado o insumo para entender o contexto e depois realizar a padronização, garantindo resultados mais precisos.

Base de Conhecimento Dinâmica: O sistema utiliza um arquivo standard-inventory.json como uma "memória", que é consultada e atualizada a cada nova interação, permitindo que a IA "aprenda" com o uso.

Interação via Terminal: A aplicação é operada diretamente pelo terminal, com um loop interativo que guia o usuário.

🛠️ Tecnologias Utilizadas
Linguagem: Python

Inteligência Artificial: Google Gemini API (google-generativeai)

Gerenciamento de Dados: JSON

🧑‍💻 Como Executar o Projeto
Siga os passos abaixo para configurar e executar o projeto em seu ambiente local.

1. Pré-requisitos
Python 3.8 ou superior

Uma chave de API do Google Gemini. Você pode obter uma no Google AI Studio.

2. Instalação
um. Clone o repositório:
clone git [URL_DO_SEU_REPOSITÓRIO]
cd [NOME_DO_SEU_REPOSITÓRIO]

b. Crie e ativo um ambiente virtual:
python -m venv venv
# Sem Windows
venv\Scripts\ativar
# Sem macOS/Linux
fonte venv/bin/activate

c. Crie um arquivo requirements.txt com o seguinte conteúdo:
google-generativeai
python-dotenv

d. Instale como dependências:
pip install -r requisitos.txt

3. Configuração
um. Crie um arquivo .env na raiz do projeto para armazenar sua chave de API de forma segura:
GEMINI_API_KEY="CHAVE_API"

b. Garanta que os arquivos de dados estejam apresenta:
categorias.json
inventário padrão.json

4. Execução
Para iniciar uma aplicação, execute o arquivo main.py:
python main.py

Siga como instruções no terminal para interagir com o assistente de IA.
_______________________________________________________________________________________

📈 Possíveis Melhores Futuras
Este projeto serve como uma excelente base. As próximas etapas para evoluir-lo seriam:

Interface Web: Desenvolvedor uma interface visual simples com Streamlit ou Gradio para tornar a ferragem mais acessível.

Tratamento de Erros: Implementar um tratamento de erros mais robusto para lidar com falhas de API ou problemas de formação de arquivos.

Testes Unitários: Adicionar testes para funções em ai_core.py e data_manager.py para garantir a confiabilidade do código.
