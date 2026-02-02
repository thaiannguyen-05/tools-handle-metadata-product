#!/usr/bin/env python3
"""
adding.py
- Read ALL sheets from product.xlsx
- Iterate through each product (row)
- Call POST to create simple product
- Call PUT to update product details
"""

from __future__ import annotations
import sys
import time
import random
from pathlib import Path
import pandas as pd
import requests

# ---------------------------
# Constants
# ---------------------------
API_BASE_URL = "https://api.redai.vn/api/v1"
POST_ENDPOINT = f"{API_BASE_URL}/user/simple-customer-products"
PUT_ENDPOINT_TEMPLATE = f"{API_BASE_URL}/user/products/physical/{{id}}"

# Column Aliases
KEYS_NAME = ["Tên SP", "Tên sản phẩm", "Name", "Tên"]
KEYS_PRICE = ["Giá sản phẩm", "Giá bán", "Giá"]
KEYS_HN = ["Tồn HN", "Tồn kho Hà Nội", "Tồn Hà Nội", "Kho HN"]
KEYS_SG = ["Tồn SG", "Tồn kho Sài Gòn", "Tồn Sài Gòn", "Kho SG"]
KEYS_BRAND = ["Thương Hiệu", "Thương hiệu", "Brand"]
KEYS_CAT = ["Ngành hàng", "Ngành Hàng", "Category"]
KEYS_WARRANTY = ["BH (Tháng)", "BH(Tháng)", "Bảo hành", "BH", "Bảo hành (tháng)"]


def get_api_key() -> str:
    """Prompt user for API Key."""
    print("Please enter your x-api-key:")
    try:
        key = input().strip()
        if not key:
            print("❌ API Key cannot be empty.")
            sys.exit(1)
        return key
    except EOFError:
        print("❌ Could not read input.")
        sys.exit(1)


def val_from_aliases(row: pd.Series, aliases: list[str]) -> str | float | int | None:
    """Try to find a value from a list of column aliases."""
    for alias in aliases:
        if alias in row:
            return row[alias]
    return None


def create_simple_product(api_key: str, name: str, description: str) -> str | None:
    """
    Step 1: Create simple product.
    Returns product ID if successful, None otherwise.
    """
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }
    
    payload = {
        "name": name,
        "description": description,
        "productType": "PHYSICAL"
    }
    
    try:
        resp = requests.post(POST_ENDPOINT, json=payload, headers=headers, timeout=30)
        
        try:
            data = resp.json()
        except:
             print(f"   ❌ POST Response Not JSON: {resp.text[:100]}")
             return None

        # Check 'code' in response body as per example
        if data.get("code") == 201:
            product_id = data.get("result", {}).get("id")
            if not product_id:
                 print(f"   ⚠ Created but ID missing in 'result': {data}")
                 return None
                 
            print(f"   ✅ Created Simple Product: ID {product_id}")
            return str(product_id)
        else:
            print(f"   ❌ Failed to create. Code: {data.get('code')}, Msg: {data.get('message')}")
            return None
            
    except Exception as e:
        print(f"   ❌ POST Request Error: {e}")
        return None


def update_product_details(api_key: str, product_id: str, row_data: pd.Series, sheet_name: str) -> None:
    """
    Step 2: Update product details (PUT).
    """
    url = PUT_ENDPOINT_TEMPLATE.format(id=product_id)
    headers = {
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }

    # Helper to clean/parse numbers
    def get_float(val):
        try:
            return float(val) if pd.notnull(val) else 0.0
        except:
            return 0.0

    def get_int(val):
        try:
            return int(val) if pd.notnull(val) else 0
        except:
            return 0
    
    def get_str(val):
        return str(val).strip() if pd.notnull(val) else ""

    # Extract
    name_val = val_from_aliases(row_data, KEYS_NAME)
    name = str(name_val).strip() if name_val else "Unnamed Product"

    price_val = val_from_aliases(row_data, KEYS_PRICE)
    price = get_float(price_val)

    qty_hn = get_int(val_from_aliases(row_data, KEYS_HN))
    qty_sg = get_int(val_from_aliases(row_data, KEYS_SG))
    total_qty = qty_hn + qty_sg
    
    brand_raw = val_from_aliases(row_data, KEYS_BRAND)
    brand = get_str(brand_raw)
    
    category = get_str(val_from_aliases(row_data, KEYS_CAT))
    warranty = get_str(val_from_aliases(row_data, KEYS_WARRANTY))

    print(f"   📝 Debug Extraction -> Name: {name} | Price: {price} | Qty: {total_qty} | Brand: '{brand}' (Raw: {brand_raw}) | Cat: '{category}' | Warranty: '{warranty}'")

    # Ensure uniqueness of SKU/Barcode to avoid backend errors
    sku = f"SKU-{product_id}" 
    barcode = f"893{str(int(time.time()))[-9:]}" 

    payload = {
        "basicInfo": {
            "name": name,
            "description": sheet_name,
            "tags": [sheet_name]
        },
        "pricing": {
            "price": {
                "listPrice": price,
                "salePrice": price,
                "currency": "VND"
            },
            "typePrice": "HAS_PRICE"
        },
        "physicalInfo": {
            "sku": sku, 
            "barcode": barcode,
            "shipmentConfig": {
                "widthCm": 25,
                "heightCm": 5,
                "lengthCm": 30,
                "weightGram": 200
            }
        },
        "customFields": [
            {
                "id": 220,
                "value": warranty  # Swapped based on debug: User said 220=Brand but it showed Warranty value? 
                                   # Wait. User said Brand showed Warranty Value (36).
                                   # My code sent Warranty Value (36) to ID 136.
                                   # So ID 136 MUST BE Brand.
                                   # My code sent Brand Value (AMD) to ID 220.
                                   # So ID 220 MUST BE Warranty.
                                   # So I swap them here: 220 <- Warranty, 136 <- Brand.
            },
            {
                "id": 216,
                "value": category
            },
            {
                "id": 215,
                "value": str(qty_hn) 
            },
            {
                "id": 212,
                "value": str(qty_sg)
            },
            {
                "id": 136,
                "value": brand
            }
        ],
        "inventoryManagement": {
            "quantity": total_qty
        }
    }

    try:
        resp = requests.put(url, json=payload, headers=headers, timeout=30)
        
        if resp.status_code in [200, 201]:
             print(f"   ✅ Updated details for Product ID {product_id}")
        else:
             print(f"   ⚠ Update failed. Status: {resp.status_code}, Body: {resp.text}")

    except Exception as e:
        print(f"   ❌ PUT Request Error: {e}")


def main() -> None:
    excel_file = Path("product.xlsx")
    if not excel_file.exists():
        print(f"❌ File not found: {excel_file.resolve()}")
        return

    api_key = get_api_key()

    print("Loading Excel file... Please wait.")
    try:
        # Read all sheets
        dfs = pd.read_excel(excel_file, sheet_name=None, engine="openpyxl")
    except Exception as e:
        print(f"❌ Error reading Excel: {e}")
        return

    print(f"Found {len(dfs)} sheets.")

    for sheet_name, df in dfs.items():
        # Clean column names (strip whitespace)
        df.columns = df.columns.str.strip()
        
        print(f"\nProcessing Sheet: {sheet_name} | {len(df)} rows")
        
        for index, row in df.iterrows():
            # Use aliases to find name
            name_val = val_from_aliases(row, KEYS_NAME)
            product_name = str(name_val).strip() if name_val else ""
            
            # Skip empty rows if name is missing
            if not product_name or product_name.lower() == "nan":
                # Check if row is completely empty or just name?
                # Sometimes user wants to import even if name matches other columns? 
                # Promtp implied Name is key.
                continue

            print(f" -> Processing Row {index + 1}: {product_name}")
            
            # Step 1: POST
            created_id = create_simple_product(api_key, product_name, sheet_name)
            
            if created_id:
                # Step 2: PUT
                update_product_details(api_key, created_id, row, sheet_name)
                
                # Small delay to be nice
                time.sleep(0.5)

if __name__ == "__main__":
    main()
