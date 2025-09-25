import data_manager
import ai_core
import json

def find_similar_item(user_description, category, inventory):
    """
    (Passo 3b) Procura por itens similares no inventário existente.
    Esta é uma busca simples por enquanto. Pode ser melhorada com embeddings no futuro.
    """
    # Lógica de similaridade pode ser aprimorada.
    # Por enquanto, vou considerar um item parecido se alguma palavra chave bater.
    # Para uma melhoria, talvez usar a propria LLM para fazer essa comparação.
    
    import re
    from difflib import SequenceMatcher

    def normalize(s):
        if not s:
            return ""
        s = s.lower()
        s = re.sub(r"[^a-z0-9à-ÿ\s+]+", " ", s)
        s = re.sub(r"\s+", " ", s).strip()
        return s

    # extrai atributos críticos da descrição do usuário para comparação estrita
    detected = {}
    m = re.search(r"(\d{1,4}\s*[Aa])", user_description)
    if m:
        detected['Corrente Nominal'] = m.group(1).upper().replace(' ', '')
    m = re.search(r"(\d{2,4}\s*[Vv])", user_description)
    if m:
        detected['Tensão'] = m.group(1).upper().replace(' ', '')
    m = re.search(r"(\d+(?:[,\.]\d+)?\s*[kK][aA])", user_description)
    if m:
        detected['Capacidade de Ruptura'] = m.group(1).upper().replace(' ', '').replace(',', '.')
    p = re.search(r"(MONOPOLAR|BIPOLAR|TRIPOLAR|TETRAPOLAR|\dP\+T\+N|\dP\+T|\dP|1P\+T\+N|3P\+T\+N)", user_description, re.IGNORECASE)
    if p:
        pr = p.group(1).upper()
        if 'MONOPOLAR' in pr:
            detected['Polos'] = '1P'
        elif 'BIPOLAR' in pr:
            detected['Polos'] = '2P'
        elif 'TRIPOLAR' in pr:
            detected['Polos'] = '3P'
        else:
            detected['Polos'] = pr.replace(' ', '')

    # tenta identificar um possível codigo/modelo (tokens alfanuméricos com digitos)
    model_tokens = [t for t in re.findall(r"\b[A-Za-z0-9\-]{3,}\b", user_description) if re.search(r"\d", t)]
    detected['ModelTokens'] = model_tokens

    user_norm = normalize(user_description)
    user_tokens = set(user_norm.split())

    best_score = 0.0
    best_item = None

    for item in inventory:
        if item.get('category') != category:
            continue

        # quick rejection based on detected numeric/critical attributes
        item_attrs = item.get('attributes', {}) or {}
        # if user specifies corrente and item has different corrente, skip
        if 'Corrente Nominal' in detected and item_attrs.get('Corrente Nominal'):
            if detected['Corrente Nominal'] != item_attrs.get('Corrente Nominal'):
                continue
        # if user specifies Polos and item has different polos, skip
        if 'Polos' in detected and item_attrs.get('Polos'):
            if detected['Polos'] != item_attrs.get('Polos'):
                continue
        # if user has a model token and item standard_name doesn't contain it, it's less likely
        std_name = (item.get('standard_name') or '').upper()
        if detected.get('ModelTokens'):
            if not any(tok.upper() in std_name for tok in detected['ModelTokens']):
                # penalize but don't fully reject; reduce chance
                model_token_penalty = 0.2
            else:
                model_token_penalty = 0.0
        else:
            model_token_penalty = 0.0

        # compose searchable text from standard_name and raw descriptions
        texts = []
        if item.get('standard_name'):
            texts.append(item['standard_name'])
        if item.get('raw_descriptions_found'):
            texts.extend(item.get('raw_descriptions_found'))

        combined = " ".join(texts)
        combined_norm = normalize(combined)
        combined_tokens = set(combined_norm.split())

        # token overlap (Jaccard-like)
        if user_tokens or combined_tokens:
            intersection = user_tokens.intersection(combined_tokens)
            union = user_tokens.union(combined_tokens)
            token_score = len(intersection) / max(1, len(union))
        else:
            token_score = 0.0

        # sequence similarity against standard_name (if exists)
        seq_score = 0.0
        if std_name:
            seq_score = SequenceMatcher(None, user_norm, normalize(std_name)).ratio()

        # combine scores (weighted) and apply model token penalty
        score = max(token_score, seq_score * 0.9) - model_token_penalty

        if score > best_score:
            best_score = score
            best_item = item

    # threshold to decide if similar enough
    if best_score >= 0.45:
        return best_item
    return None


def encontrar_exemplos_por_categoria(category, inventory, limit=3):
    """Encontra até 'limit' exemplos de itens na mesma categoria."""
    exemplos = [item for item in inventory if item.get('category') == category]
    return exemplos[:limit]


def main():
    """
    Fluxo principal da aplicação de terminal.
    """
    # Carrega os dados
    inventory = data_manager.load_inventory()
    categories = data_manager.load_categories()

    if not categories:
        print("Não foi possível iniciar. Verifique seu arquivo de categorias.")
        return

    print("--- Assistente de Cadastro de Insumos ---")
    
    # Ato 1: Análise e Sugestão
    # Passo 1: Ação do Usuário
    user_input = input("Digite a descrição do insumo (ex: 'disjuntor siemens 2p 40a'): ")

    print("\nAnalisando...")

    # Passo 3a: Classificação
    suggested_category = ai_core.get_category_from_llm(user_input, categories)
    print(f"Categoria sugerida: {suggested_category}")

    # Passo 3b/3c: Sempre buscar referências e gerar um novo padrão usando exemplos
    print("\nBuscando referências e preparando para padronização...")

    exemplos_para_ia = encontrar_exemplos_por_categoria(suggested_category, inventory)

    # A IA é chamada para criar um item NOVO e padronizado, usando os exemplos como referência de formato.
    new_item_details = ai_core.create_standard_item_from_llm(
        user_input,
        suggested_category,
        exemplos_para_ia
    )

    final_item_data = {}
    if new_item_details:
        final_item_data = {
            "id": data_manager.generate_id(),
            "category": suggested_category,
            "standard_name": new_item_details.get("standard_name"),
            "attributes": new_item_details.get("attributes"),
            "raw_descriptions_found": [user_input]
        }
        print(f"Nome Padrão sugerido: {final_item_data['standard_name']}")
    else:
        print("A IA não retornou detalhes válidos. Abortando criação.")
        return

    # Ato 2: Confirmação e Aprendizado
    # Passo 5: Validação Humana
    print("\n--- Validação ---")
    print(f"ID: {final_item_data.get('id')}")
    print(f"Categoria: {final_item_data.get('category')}")
    print(f"Atributos: {json.dumps(final_item_data.get('attributes'), indent=2, ensure_ascii=False)}")
    
    user_corrected_name = input(f"Edite o nome padrão se necessário ou pressione Enter para confirmar:\n[{final_item_data.get('standard_name')}] -> ")
    
    if user_corrected_name:
        final_item_data['standard_name'] = user_corrected_name.strip()

    # Passo 6 e 7: Salvar no "banco de dados"
    confirm = input("\nConfirmar e Salvar? (s/n): ").lower()
    if confirm == 's':
        # Verifica se o item já existe (caso de enriquecimento) ou é novo
        existing_item = data_manager.find_item_by_id(final_item_data.get('id'), inventory)
        if existing_item:
            # Atualiza o item existente
            existing_item.update(final_item_data)
        else:
            # Adiciona o novo item
            inventory.append(final_item_data)
        
        data_manager.save_inventory(inventory)
        print("✅ Item salvo com sucesso no inventário!")
    else:
        print("❌ Operação cancelada.")


if __name__ == "__main__":
    main()