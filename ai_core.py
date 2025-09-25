try:
    # Nova forma preferida em versões mais recentes
    from google import genai
except Exception:
    try:
        # Fallback para nomes de módulo alternativos
        import google.generativeai as genai
    except Exception:
        raise ImportError("Não foi possível importar 'genai' do pacote google. Instale 'google-generativeai' ou verifique sua instalação.")
import json
import os
from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env, se existir
load_dotenv()

# Preferir GEMINI_API_KEY, com fallback para GOOGLE_API_KEY
api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
if not api_key:
    raise ValueError(
        "A chave de API Gemini não foi encontrada. Defina GEMINI_API_KEY no seu .env ou no ambiente."
    )

# Inicializa o cliente genai: tentar API moderna (Client) e fallback para API antiga (configure)
MODEL_NAME = "gemini-2.5-flash"

_USE_CLIENT_API = False
client = None
try:
    # Algumas versões do pacote expõem Client
    client = genai.Client(api_key=api_key)
    _USE_CLIENT_API = True
except Exception:
    # Fallback: configure the global module (older API)
    try:
        genai.configure(api_key=api_key)
        _USE_CLIENT_API = False
    except Exception as e:
        raise RuntimeError("Não foi possível inicializar o cliente genai: " + str(e))


def _extract_text_from_response(response):
    """Tenta extrair o texto da resposta do genai client com vários fallbacks."""
    text = getattr(response, "text", None)
    if text:
        return text

    # Estrutura alternativa que algumas versões podem retornar
    try:
        return response.output[0].content[0].text
    except Exception:
        return str(response)


# GUIA_DE_PADRONIZACAO: regras detalhadas para padronizar nomes e extrair atributos
GUIA_DE_PADRONIZACAO = """
Guia de Padronização de Nomes e Atributos

Regras Gerais:
- Todos os nomes devem estar em MAIÚSCULAS.
- Se o código/modelo do fabricante não for encontrado, use " - (SEM MODELO)".
- Unidades devem ser abreviadas conforme o padrão técnico (ex: A para Ampères, V para Volts, kW, kVA).
- Marcas devem aparecer apenas se forem parte do nome comercial; caso contrário, mover para atributos.
- Nunca inclua o código NCM no nome padronizado. Se for mencionado, extraia-o para os atributos.
- Nunca inclua o código de barras no nome padronizado. Se for mencionado, extraia-o para os atributos.
- Nunca inclua o código de compra do fabricante no nome padronizado. Se for mencionado, extraia-o para os atributos.
- Para Disjuntores, a corrente e o número de polos devem ser escritos em sequência, sem vírgula entre eles (ex: '6A BIPOLAR')

Formato de Saída (exigido):
Retorne APENAS um objeto JSON com as chaves:
{
    "standard_name": "...",
    "attributes": {
        "Marca": "...",
        "Modelo": "...",
        "Polos": "...",
        "Corrente Nominal": "...",
        "IP": "...",
        "Tensão": "...",
        "Observações": "..."
    }
}

Regras de Extração de Atributos:
- Sempre tente extrair Marca e Modelo (separados).
- Corrente nominal deve ficar em formato "<valor>A" (ex: "125A").
- Tensão deve ser expressa como "<valor>V" ou faixa (ex: "230V").
- Grau de proteção como "IP67" quando mencionado.
- Polos para disjuntores e outros: padronizar como "MONOPOLAR", "BIPOLAR", "TRIPOLAR", "TETRAPOLAR".
- Para Plugues e tomadas, "1P+T+N", "2P+T+N", "3P+T+N", etc.

Boas Práticas de Nome:
- Remova palavras desnecessárias como "novo", "modelo", "referência".
- Use hífen e vírgulas conforme o template de cada categoria.
- Mantenha abreviações técnicas (EX: "NCM" pode ser extraído para atributos, mas não é parte do nome padronizado).

Comportamento diante de incerteza:
- Se algum atributo não puder ser identificado com confiança, deixe-o ausente no campo attributes.
- Nunca retorne texto explicativo fora do objeto JSON.
- Sempre preste atenção máxima à distinção crucial entre Modelo e Código. A Descrição Padronizada deve obrigatoriamente terminar com o nome do modelo do produto (ex: SAK 4 EN, Polaris, A3T-2.5) e nunca com o código numérico de compra do fabricante (ex: C012836.0100, 811090603)
- Se um modelo alfanumérico específico não for evidente, o nome da linha do produto (ex: Polaris) deverá ser usado como modelo.
- Para Quadros e Armários, as dimensões na descrição devem ser sempre seguidas pela indicação de formato (LxAxP).
- os componentes (como porta ou placa de montagem) só devem ser mencionados na descrição se estiverem faltando (ex: 'SEM PLACA DE MONTAGEM'). Se o item for completo, não liste seus componentes
"""


def get_category_from_llm(user_description, categories):
    """Classifica a descrição do usuário em uma categoria da lista fornecida."""
    prompt = f"""
Analise a descrição do insumo fornecida pelo usuário e classifique-a em UMA das categorias a seguir.
Retorne APENAS o nome exato da categoria correspondente da lista. Não adicione nenhuma outra palavra.

Descrição do Usuário: "{user_description}"

Lista de Categorias Válidas:
{json.dumps(categories, indent=2, ensure_ascii=False)}

Categoria Escolhida:
"""

    if _USE_CLIENT_API:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = _extract_text_from_response(response)
    else:
        # fallback para API mais antiga: tentar GenerativeModel
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            text = _extract_text_from_response(response)
        except Exception:
            # última alternativa: alguma função genai.generate_text / generate_content direta
            try:
                response = genai.generate_text(prompt, model=MODEL_NAME)
                text = _extract_text_from_response(response)
            except Exception as e:
                raise RuntimeError("Falha ao chamar a API genai: " + str(e))
    return text.strip()


def create_standard_item_from_llm(user_description, category, examples=None, use_web_search=False):
    """Gera um item padronizado em JSON (standard_name + attributes) a partir da descrição.

    Aceita uma lista opcional de exemplos (cada exemplo é um dict com ao menos 'standard_name').
    Faz validação local para evitar que a IA invente modelos ou mude atributos essenciais.
    """
    import re

    # Constrói a seção de exemplos, se houver
    examples_prompt_section = ""
    if examples:
        examples_str = "\n".join([f"- {ex.get('standard_name','')}" for ex in examples])
        examples_prompt_section = f"""
### Exemplos de Itens Já Cadastrados Nesta Categoria
Use os seguintes itens como referência de estilo e formatação:
{examples_str}
"""

    # Extrações locais obrigatórias (serão exigidas no resultado)
    detected = {}
    # corrente nominal (ex: 20A, 125A)
    m = re.search(r"(\d{1,4}\s*[Aa])", user_description)
    if m:
        detected['Corrente Nominal'] = m.group(1).upper().replace(' ', '')

    # tensão (ex: 230V)
    m = re.search(r"(\d{2,4}\s*[Vv])", user_description)
    if m:
        detected['Tensão'] = m.group(1).upper().replace(' ', '')

    # capacidade de ruptura (ex: 10kA)
    m = re.search(r"(\d+(?:[,\.]\d+)?\s*[kK][aA])", user_description)
    if m:
        detected['Capacidade de Ruptura'] = m.group(1).upper().replace(' ', '').replace(',', '.')

    # grau de proteção (IP)
    m = re.search(r"(IP\s*\d{2})", user_description, re.IGNORECASE)
    if m:
        detected['IP'] = m.group(1).upper().replace(' ', '')

    # polos/terminais
    p = re.search(r"(MONOPOLAR|BIPOLAR|TRIPOLAR|TETRAPOLAR|\dP\+T\+N|\dP\+T|\dP|1P\+T\+N|3P\+T\+N)", user_description, re.IGNORECASE)
    if p:
        poles_raw = p.group(1).upper()
        if 'MONOPOLAR' in poles_raw:
            poles = '1P'
        elif 'BIPOLAR' in poles_raw:
            poles = '2P'
        elif 'TRIPOLAR' in poles_raw:
            poles = '3P'
        else:
            poles = poles_raw.replace(' ', '')
        detected['Polos'] = poles

    # NCM (observação)
    m = re.search(r"NCM\s*[:\-]?\s*(\d[\d\.]+)", user_description, re.IGNORECASE)
    if m:
        detected.setdefault('Observações', '')
        detected['Observações'] = f"NCM: {m.group(1)}"

    prompt = f"""
Você é um especialista em catalogação de materiais industriais. Sua tarefa é criar uma **nova e única** entrada padronizada a partir da descrição de um usuário, usando um guia de regras e exemplos existentes como referência de **formato**.

---
### FLUXO DE TRABALHO OBRIGATÓRIO

**PASSO 1: COLETA E VERIFICAÇÃO DE DADOS**
- Analise a "Descrição do Usuário".
- Pesquise na web para encontrar o datasheet do produto e verificar todos os atributos técnicos relevantes, como corrente, polos, curva, e o **código exato do Modelo do fabricante**. Crie um conjunto consolidado de informações verificadas.

**PASSO 2: GERAÇÃO DO `standard_name` (SÍNTESE)**
- Use as informações consolidadas do Passo 1 para construir o `standard_name`.
- **AÇÃO:**
    1. Encontre o template para a categoria "{category}" no GUIA DE PADRONIZAÇÃO.
    2. Usando os dados que você coletou, **preencha os campos** do template.

- #### **REGRAS DE PONTUAÇÃO E ESTRUTURA (MUITO IMPORTANTE):**
    - Os separadores (principalmente as **vírgulas e espaços**) definidos no template são **fixos e obrigatórios**.
    - Uma vírgula só deve ser adicionada se houver um bloco de informação válido a seguir.
    - Se uma informação para um campo do template (ex: `CURVA [LETRA]`) não for encontrada, **omita o campo E a vírgula que o precede**. Isso é essencial para evitar vírgulas duplas ou penduradas.
    
    - ### **EXCEÇÃO ESPECIAL PARA DISJUNTORES E MINIDISJUNTORES ###**
    - **REGRA:** Apenas para as categorias que contenham "DISJUNTOR" ou "MINIDISJUNTOR", a Corrente e os Polos devem ser agrupados **SEM VÍRGULA** entre eles. Este formato específico é crucial para a busca no sistema Odoo.
    - **Exemplo CERTO:** `MINIDISJUNTOR TERMOMAGNÉTICO, 20A BIPOLAR, ...`
    - **Exemplo ERRADO:** `MINIDISJUNTOR TERMOMAGNÉTICO, 20A, BIPOLAR, ...`
    - Para todas as outras categorias, a regra da vírgula como separador continua válida.


- #### **EXEMPLO DE RACIOCÍNIO (PENSE PASSO A PASSO):**
    - **Template:** `MINIDISJUNTOR [TIPO], [CORRENTE][POLOS], CURVA [LETRA], [CAPACIDADE]kA - MODELO`
    - **Dados Disponíveis:** Corrente=20A, Polos=BIPOLAR, Capacidade=10kA, Modelo=MDW-C20-2. (A informação da Curva não foi encontrada).
    - **Construção:**
        1. Começo com `MINIDISJUNTOR TERMOMAGNÉTICO`.
        2. Adiciono a próxima parte: `20A BIPOLAR`. Junto as duas com uma vírgula: `MINIDISJUNTOR TERMOMAGNÉTICO, 20A BIPOLAR`.
        3. A próxima parte é `CURVA [LETRA]`. Como não tenho essa informação, eu **pulo essa parte e a vírgula que viria antes dela**.
        4. Adiciono a próxima parte: `10kA`. Junto com o bloco anterior usando uma vírgula: `MINIDISJUNTOR TERMOMAGNÉTICO, 20A BIPOLAR, 10kA`.
        5. Finalizo com o modelo: `MINIDISJUNTOR TERMOMAGNÉTICO, 20A BIPOLAR, 10kA - MDW-C20-2`.
    - **SIGA ESTE RACIOCÍNIO PARA GARANTIR A PONTUAÇÃO CORRETA.**

- **FORMATAÇÃO FINAL OBRIGATÓRIA:** O nome deve ser **INTEIRAMENTE EM LETRAS MAIÚSCULAS** e DEVE terminar com " - [MODELO ENCONTRADO NO PASSO 1]".

**PASSO 3: MONTAGEM FINAL DO JSON**
- Crie o objeto `attributes` listando todos os dados técnicos relevantes coletados no Passo 1.
- Monte a saída final em um único objeto JSON, contendo o `standard_name` que você construiu no Passo 2 e o objeto `attributes`.
- Garanta consistência total entre as informações apresentadas no nome e no objeto de atributos.

### JSON DE SAÍDA:
"""

    if _USE_CLIENT_API:
        response = client.models.generate_content(model=MODEL_NAME, contents=prompt)
        text = _extract_text_from_response(response)
    else:
        try:
            model = genai.GenerativeModel(MODEL_NAME)
            response = model.generate_content(prompt)
            text = _extract_text_from_response(response)
        except Exception:
            try:
                response = genai.generate_text(prompt, model=MODEL_NAME)
                text = _extract_text_from_response(response)
            except Exception as e:
                raise RuntimeError("Falha ao chamar a API genai: " + str(e))

    # Limpa a saída caso venha em bloco de código
    cleaned = text.strip().replace("```json", "").replace("```", "")

    # tenta parsear
    parsed = None
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        print("Erro: A IA não retornou um JSON válido.")
        print("Resposta bruta da IA:\n", cleaned)

    # Validação e aplicação forçada: constrói o standard_name a partir dos atributos retornados (ou detectados) e padroniza saída
    def _normalize_polos(p):
        if not p:
            return None
        p = p.upper().strip()
        mapping = {'1P': 'MONOPOLAR', '2P': 'BIPOLAR', '3P': 'TRIPOLAR', '4P': 'TETRAPOLAR'}
        if p in mapping:
            return mapping[p]
        # já pode vir como MONOPOLAR etc.
        if 'MONOPOLAR' in p or 'BIPOLAR' in p or 'TRIPOLAR' in p or 'TETRAPOLAR' in p:
            return p
        return p

    def _build_standard_name_from_attrs(attrs):
        # attrs: dict with possible keys Marca, Modelo, Polos, Corrente Nominal, IP, Tensão, Observações, Capacidade de Ruptura
        # Decide um 'tipo' baseado na descrição do usuário e/ou categoria
        td = user_description.upper()
        cat = (category or '').upper()
        if 'MINIDISJUNT' in td or 'MINIDISJUNT' in cat:
            tipo = 'MINIDISJUNTOR TERMOMAGNÉTICO'
        elif 'DISJUNT' in td or 'DISJUNT' in cat:
            tipo = 'DISJUNTOR TERMOMAGNÉTICO'
        elif 'TOMADA' in td or 'PLUG' in td or 'TOMADA' in cat:
            tipo = 'TOMADA'
        else:
            # fallback: use first two words of the user description
            tipo = ' '.join(td.split()[:2]) if td else 'ITEM'

        parts = [tipo]

        # Corrente Nominal
        corrente = attrs.get('Corrente Nominal') or attrs.get('Corrente')
        if corrente:
            parts.append(corrente.upper().replace(' ', ''))

        # Polos (normalizar para palavras como MONOPOLAR)
        polos = _normalize_polos(attrs.get('Polos'))
        if polos:
            parts.append(polos)

        # Tensão
        tens = attrs.get('Tensão')
        if tens:
            parts.append(tens.upper().replace(' ', ''))

        # Capacidade de ruptura
        cap = attrs.get('Capacidade de Ruptura')
        if cap:
            parts.append(cap.upper().replace(' ', ''))

        modelo = attrs.get('Modelo') or ''
        modelo = modelo.strip() if modelo else ''
        if modelo:
            model_part = modelo
        else:
            model_part = '(SEM MODELO)'

        std_name = ' '.join(parts) + ' - ' + model_part
        # clean spacing and enforce uppercase
        std_name = ' '.join(std_name.split()).upper()
        return std_name

    def _validate_and_fix(parsed_obj):
        if not isinstance(parsed_obj, dict):
            return None

        # Start from parsed attributes, but ensure keys exist
        attrs = parsed_obj.get('attributes', {}) or {}

        # Ensure detected local attributes are present if missing in parsed attrs
        for k, v in detected.items():
            if k == 'Observações':
                attrs.setdefault('Observações', v)
            else:
                attrs.setdefault(k, v)

        # Normalize some keys and values
        # Guarantee all expected keys exist (empty string if unknown)
        expected_keys = ['Marca', 'Modelo', 'Polos', 'Corrente Nominal', 'IP', 'Tensão', 'Observações', 'Capacidade de Ruptura']
        for k in expected_keys:
            attrs.setdefault(k, '')

        # Build standard_name from attrs (this enforces that the name reflects the attributes)
        constructed_name = _build_standard_name_from_attrs(attrs)

        constructed = dict(parsed_obj)
        constructed['attributes'] = attrs
        constructed['standard_name'] = constructed_name
        return constructed

    final = _validate_and_fix(parsed) if parsed is not None else None
    return final
