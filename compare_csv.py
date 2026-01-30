#!/usr/bin/env python3
"""
Tool so sánh 2 file CSV có cấu trúc giống nhau.
Đầu ra là các dòng khác nhau giữa file 2 so với file 1.
Tự động cập nhật sản phẩm qua API.
"""

import csv
import sys
import json
import time
from pathlib import Path

try:
    import requests
except ImportError:
    print("❌ Thiếu thư viện 'requests'. Đang cài đặt...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "requests"])
    import requests


def read_csv_to_dict(filepath):
    """Đọc CSV và trả về dictionary với key là Mã sản phẩm."""
    products = {}
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        for row in reader:
            product_code = row.get('Mã', '').strip()
            if product_code:
                products[product_code] = row
    return products


def search_product_api(product_name, api_key):
    """Tìm kiếm sản phẩm qua API và trả về ID."""
    try:
        url = "https://api.redai.vn/api/v1/user/customer-products"
        params = {
            'page': 1,
            'limit': 10,
            'search': product_name
        }
        
        headers = {
            'x-api-key': api_key
        }
        
        response = requests.get(url, params=params, headers=headers)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('code') == 200 and data.get('result', {}).get('items'):
                items = data['result']['items']
                # Tìm sản phẩm khớp chính xác
                for item in items:
                    if item.get('name', '').strip() == product_name.strip():
                        return item.get('id')
                # Nếu không có khớp chính xác, trả về item đầu tiên
                return items[0].get('id') if items else None
            return None
        else:
            print(f"  ❌ API trả về lỗi {response.status_code}: {response.text}")
            return None
    except Exception as e:
        print(f"❌ Lỗi khi tìm kiếm sản phẩm '{product_name}': {e}")
        return None


def update_product_api(product_id, product_data, changed_row, api_key):
    """Cập nhật sản phẩm qua API PUT."""
    try:
        url = f"https://api.redai.vn/api/v1/user/products/physical/{product_id}"
        
        # Chuyển đổi giá từ string sang float
        try:
            list_price = float(str(changed_row.get('Giá mới', '0')).replace(',', ''))
        except ValueError:
            list_price = 0
            
        try:
            quantity = int(float(str(changed_row.get('Tồn HN mới', '0')).replace(',', '')))
        except ValueError:
            quantity = 0
        
        payload = {
            "basicInfo": {
                "name": changed_row.get('Tên SP', ''),
                "description": changed_row.get('Tên SP', ''),
                "tags": []
            },
            "urls": [],
            "pricing": {
                "price": {
                    "listPrice": list_price,
                    "salePrice": list_price,
                    "currency": "VND"
                },
                "typePrice": "HAS_PRICE"
            },
            "customFields": [
                {
                    "id": 136,
                    "value": ""
                },
                {
                    "id": 212,
                    "value": ""
                },
                {
                    "id": 215,
                    "value": ""
                },
                {
                    "id": 216,
                    "value": ""
                }
            ],
            "inputRequirements": [],
            "inventoryManagement": {
                "quantity": quantity
            }
        }
        
        headers = {
            'x-api-key': api_key,
            'Content-Type': 'application/json'
        }
        
        response = requests.put(url, json=payload, headers=headers)
        
        if response.status_code == 200:
            result = response.json()
            return result.get('code') == 200
        else:
            print(f"  ❌ API trả về lỗi {response.status_code}: {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Lỗi khi cập nhật sản phẩm ID {product_id}: {e}")
        return False


def process_api_updates(differences, api_key):
    """Xử lý cập nhật sản phẩm qua API."""
    if not api_key:
        print("❌ Không có API key. Bỏ qua cập nhật API.")
        return
    
    # Chỉ xử lý sản phẩm thay đổi
    changed_products = [d for d in differences if d['Trạng thái'].startswith('THAY ĐỔI')]
    
    if not changed_products:
        print("Không có sản phẩm nào cần cập nhật qua API.")
        return
    
    print(f"\n{'='*100}")
    print(f"🔄 BẮT ĐẦU CẬP NHẬT QUA API - Tổng số: {len(changed_products)} sản phẩm")
    print(f"{'='*100}\n")
    
    success_count = 0
    failed_count = 0
    
    for idx, product in enumerate(changed_products, 1):
        # Sử dụng tên cũ để search nếu tên bị thay đổi, nếu không thì dùng tên hiện tại
        search_name = product.get('Tên SP cũ', '') or product.get('Tên SP', '')
        product_name = product.get('Tên SP', '')
        
        print(f"[{idx}/{len(changed_products)}] Xử lý: {product_name}")
        if product.get('Tên SP cũ') and product.get('Tên SP cũ') != product_name:
            print(f"  (Tên cũ: {search_name})")
        
        # Bước 1: Tìm kiếm sản phẩm bằng tên cũ
        print(f"  🔍 Đang tìm kiếm sản phẩm...")
        product_id = search_product_api(search_name, api_key)
        
        if not product_id:
            print(f"  ❌ Không tìm thấy sản phẩm trên hệ thống")
            failed_count += 1
            time.sleep(0.5)  # Delay để tránh spam API
            continue
        
        print(f"  ✓ Tìm thấy sản phẩm ID: {product_id}")
        
        # Bước 2: Cập nhật sản phẩm
        print(f"  📝 Đang cập nhật...")
        if update_product_api(product_id, product, product, api_key):
            print(f"  ✅ Cập nhật thành công!")
            print(f"     - Giá: {product.get('Giá cũ')} → {product.get('Giá mới')}")
            print(f"     - Tồn HN: {product.get('Tồn HN cũ')} → {product.get('Tồn HN mới')}")
            success_count += 1
        else:
            print(f"  ❌ Cập nhật thất bại")
            failed_count += 1
        
        print()
        time.sleep(0.5)  # Delay để tránh spam API
    
    print(f"{'='*100}")
    print(f"📊 KẾT QUẢ CẬP NHẬT:")
    print(f"  ✅ Thành công: {success_count}/{len(changed_products)}")
    print(f"  ❌ Thất bại: {failed_count}/{len(changed_products)}")
    print(f"{'='*100}\n")


def compare_products(file1_path, file2_path):
    """
    So sánh 2 file CSV.
    Trả về các sản phẩm ở file 2 có thông tin khác với file 1.
    """
    products1 = read_csv_to_dict(file1_path)
    products2 = read_csv_to_dict(file2_path)

    differences = []

    for code, product2 in products2.items():
        if code not in products1:
            # Sản phẩm mới trong file 2
            differences.append({
                'Mã': code,
                'Tên SP': product2.get('Tên SP', ''),
                'Tên SP cũ': '',
                'Trạng thái': 'MỚI',
                'Giá cũ': '',
                'Giá mới': product2.get('Giá bán', ''),
                'Tồn HN cũ': '',
                'Tồn HN mới': product2.get('Tồn HN', ''),
                'Tồn SG cũ': '',
                'Tồn SG mới': product2.get('Tồn SG', ''),
            })
        else:
            product1 = products1[code]
            # Kiểm tra các trường khác nhau
            changed_fields = []
            
            if product1.get('Giá bán') != product2.get('Giá bán'):
                changed_fields.append('Giá')
            if product1.get('Tồn HN') != product2.get('Tồn HN'):
                changed_fields.append('Tồn HN')
            if product1.get('Tồn SG') != product2.get('Tồn SG'):
                changed_fields.append('Tồn SG')
            if product1.get('Tên SP') != product2.get('Tên SP'):
                changed_fields.append('Tên SP')
            
            if changed_fields:
                differences.append({
                    'Mã': code,
                    'Tên SP': product2.get('Tên SP', ''),
                    'Tên SP cũ': product1.get('Tên SP', ''),  # Lưu tên cũ để search API
                    'Trạng thái': f"THAY ĐỔI: {', '.join(changed_fields)}",
                    'Giá cũ': product1.get('Giá bán', ''),
                    'Giá mới': product2.get('Giá bán', ''),
                    'Tồn HN cũ': product1.get('Tồn HN', ''),
                    'Tồn HN mới': product2.get('Tồn HN', ''),
                    'Tồn SG cũ': product1.get('Tồn SG', ''),
                    'Tồn SG mới': product2.get('Tồn SG', ''),
                })

    # Kiểm tra sản phẩm bị xóa (có trong file 1 nhưng không có trong file 2)
    for code, product1 in products1.items():
        if code not in products2:
            differences.append({
                'Mã': code,
                'Tên SP': product1.get('Tên SP', ''),
                'Tên SP cũ': '',
                'Trạng thái': 'ĐÃ XÓA',
                'Giá cũ': product1.get('Giá bán', ''),
                'Giá mới': '',
                'Tồn HN cũ': product1.get('Tồn HN', ''),
                'Tồn HN mới': '',
                'Tồn SG cũ': product1.get('Tồn SG', ''),
                'Tồn SG mới': '',
            })

    return differences


def print_results(differences):
    """In kết quả ra màn hình."""
    if not differences:
        print("Không có sự khác biệt nào giữa 2 file.")
        return

    print(f"\n{'='*100}")
    print(f"TỔNG SỐ THAY ĐỔI: {len(differences)}")
    print(f"{'='*100}\n")

    # Nhóm theo trạng thái
    new_products = [d for d in differences if d['Trạng thái'] == 'MỚI']
    deleted_products = [d for d in differences if d['Trạng thái'] == 'ĐÃ XÓA']
    changed_products = [d for d in differences if d['Trạng thái'].startswith('THAY ĐỔI')]

    if new_products:
        print(f"\n🆕 SẢN PHẨM MỚI ({len(new_products)}):")
        print("-" * 100)
        for p in new_products:
            print(f"  Mã: {p['Mã']}")
            print(f"  Tên: {p['Tên SP']}")
            print(f"  Giá: {p['Giá mới']}")
            print(f"  Tồn HN: {p['Tồn HN mới']} | Tồn SG: {p['Tồn SG mới']}")
            print()

    if deleted_products:
        print(f"\n🗑️ SẢN PHẨM ĐÃ XÓA ({len(deleted_products)}):")
        print("-" * 100)
        for p in deleted_products:
            print(f"  Mã: {p['Mã']}")
            print(f"  Tên: {p['Tên SP']}")
            print(f"  Giá cũ: {p['Giá cũ']}")
            print()

    if changed_products:
        print(f"\n📝 SẢN PHẨM THAY ĐỔI ({len(changed_products)}):")
        print("-" * 100)
        for p in changed_products:
            print(f"  Mã: {p['Mã']}")
            print(f"  Tên: {p['Tên SP']}")
            print(f"  Thay đổi: {p['Trạng thái']}")
            if p['Giá cũ'] != p['Giá mới']:
                print(f"  Giá: {p['Giá cũ']} → {p['Giá mới']}")
            if p['Tồn HN cũ'] != p['Tồn HN mới']:
                print(f"  Tồn HN: {p['Tồn HN cũ']} → {p['Tồn HN mới']}")
            if p['Tồn SG cũ'] != p['Tồn SG mới']:
                print(f"  Tồn SG: {p['Tồn SG cũ']} → {p['Tồn SG mới']}")
            print()


def export_to_csv(differences, output_path):
    """Xuất kết quả ra file CSV."""
    if not differences:
        print(f"Không có dữ liệu để xuất ra {output_path}")
        return

    fieldnames = ['Mã', 'Tên SP', 'Tên SP cũ', 'Trạng thái', 'Giá cũ', 'Giá mới',
                  'Tồn HN cũ', 'Tồn HN mới', 'Tồn SG cũ', 'Tồn SG mới']

    with open(output_path, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(differences)

    print(f"\n✅ Đã xuất kết quả ra file: {output_path}")


def main():
    # Kiểm tra tham số dòng lệnh
    if len(sys.argv) < 3:
        print("Usage: python compare_csv.py <file1.csv> <file2.csv> [output.csv] [--update-api]")
        print("  file1.csv: File gốc (ban đầu)")
        print("  file2.csv: File so sánh (sau)")
        print("  output.csv: (Tùy chọn) File xuất kết quả")
        print("  --update-api: (Tùy chọn) Tự động cập nhật qua API")
        sys.exit(1)

    file1_path = sys.argv[1]
    file2_path = sys.argv[2]
    
    # Xử lý tham số tùy chọn
    output_path = None
    update_via_api = False
    
    for i in range(3, len(sys.argv)):
        arg = sys.argv[i]
        if arg == '--update-api':
            update_via_api = True
        elif not output_path and not arg.startswith('--'):
            output_path = arg

    # Kiểm tra file tồn tại
    if not Path(file1_path).exists():
        print(f"❌ Lỗi: Không tìm thấy file '{file1_path}'")
        sys.exit(1)

    if not Path(file2_path).exists():
        print(f"❌ Lỗi: Không tìm thấy file '{file2_path}'")
        sys.exit(1)

    print(f"\n📊 So sánh:")
    print(f"   File 1 (gốc): {file1_path}")
    print(f"   File 2 (sau): {file2_path}")

    # So sánh và lấy danh sách thay đổi
    differences = compare_products(file1_path, file2_path)
    print_results(differences)

    # Xuất file nếu có
    if output_path:
        export_to_csv(differences, output_path)

    # Cập nhật qua API nếu được yêu cầu
    if update_via_api and differences:
        print("\n" + "="*100)
        api_key = input("🔑 Nhập x-api-key để cập nhật sản phẩm qua API: ").strip()
        
        if api_key:
            confirm = input(f"\n⚠️  Bạn có chắc chắn muốn cập nhật {len([d for d in differences if d['Trạng thái'].startswith('THAY ĐỔI')])} sản phẩm? (yes/no): ").strip().lower()
            
            if confirm in ['yes', 'y']:
                process_api_updates(differences, api_key)
            else:
                print("❌ Đã hủy cập nhật API.")
        else:
            print("❌ Không có API key. Bỏ qua cập nhật API.")
    elif update_via_api and not differences:
        print("\n✅ Không có thay đổi nào, không cần cập nhật API.")


if __name__ == '__main__':
    main()

