import json
import uuid

INVENTORY_FILE = 'standard-inventory.json'
CATEGORIES_FILE = 'categories.json'

def load_inventory():
    """Carrega o inventário do arquivo JSON."""
    try:
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get("records", [])
    except (FileNotFoundError, json.JSONDecodeError):
        return []

def load_categories():
    """Carrega as categorias do arquivo JSON."""
    try:
        with open(CATEGORIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("Arquivo de categorias não encontrado!")
        return []

def save_inventory(inventory_data):
    """Salva os dados do inventário de volta no arquivo JSON."""
    # Carrega o arquivo existente para manter metadados, se houver
    try:
        with open(INVENTORY_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {"version": "1.1", "generated_at": "", "records": []}

    data["records"] = inventory_data

    with open(INVENTORY_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def find_item_by_id(item_id, inventory_data):
    """Encontra um item pelo seu ID."""
    for item in inventory_data:
        if item.get('id') == item_id:
            return item
    return None

def generate_id():
    """Gera um ID único."""
    return str(uuid.uuid4())