import os
import re
import argparse

# 配置路径
DEFAULT_MAPPING_FILE = 'bank.txt'
DEFAULT_WEM_FOLDER = 'Extracted_WEM'

def load_rename_metadata(mapping_file):
    name_lookup = {}
    wem_meta = {}

    parenthesized_name_pattern = re.compile(r'dwSoundBankID\s*=\s*(\d+)\s*\(([^)]+)\)')
    bank_id_pattern = re.compile(r'dwSoundBankID\s*=\s*(\d+)')
    media_header_pattern = re.compile(r'MediaHeader\[(\d+)\]')
    wem_id_pattern = re.compile(r'\bid\s*=\s*(\d+)')

    current_bnk_id = None
    current_bnk_name = None
    current_media_index = None
    awaiting_media_id = False

    print(f"正在解析 {mapping_file}...")
    with open(mapping_file, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
            bank_match = parenthesized_name_pattern.search(line)
            if bank_match:
                current_bnk_id = bank_match.group(1)
                current_bnk_name = bank_match.group(2)
                continue

            bank_id_match = bank_id_pattern.search(line)
            if bank_id_match:
                current_bnk_id = bank_id_match.group(1)
                current_bnk_name = current_bnk_id

            media_match = media_header_pattern.search(line)
            if media_match:
                current_media_index = int(media_match.group(1))
                awaiting_media_id = True
                continue

            if awaiting_media_id:
                wem_match = wem_id_pattern.search(line)
                if wem_match:
                    sound_id = wem_match.group(1)
                    wem_meta[sound_id] = {
                        'name': current_bnk_name or current_bnk_id or 'unknown',
                        'wem_index': str(current_media_index + 1) if current_media_index is not None else '',
                        'bnk_id': current_bnk_id or '',
                    }
                    awaiting_media_id = False

    print(f"成功载入 {len(wem_meta)} 条 WEM 元数据。")
    return name_lookup, wem_meta


def batch_rename(mapping_file=DEFAULT_MAPPING_FILE, wem_folder=DEFAULT_WEM_FOLDER):
    if not os.path.exists(mapping_file):
        print(f"[错误] 找不到映射文件: {mapping_file}")
        return
    if not os.path.exists(wem_folder):
        print(f"[错误] 找不到文件夹: {wem_folder}")
        return

    name_lookup, wem_meta = load_rename_metadata(mapping_file)

    print("开始重命名...\n")

    # 2. 遍历 Extracted_WEM 文件夹进行重命名
    success_count = 0
    conflict_resolved_count = 0
    fail_count = 0
    
    # 正则：匹配 "任意数字 (十六进制).wem"
    file_pattern = re.compile(r'^(\d+)\s*\(?([0-9a-fA-F]+)\)?\.wem$')

    for file in os.listdir(wem_folder):
        if not file.lower().endswith('.wem'):
            continue
            
        match = file_pattern.match(file)
        if match:
            dec_id = match.group(1) # 开头的十进制
            hex_id = match.group(2) # 括号里的十六进制
            
            try:
                converted_hex_id = str(int(hex_id, 16))
            except ValueError:
                converted_hex_id = None

            target_id = None
            if dec_id in wem_meta:
                target_id = dec_id
            elif converted_hex_id and converted_hex_id in wem_meta:
                target_id = converted_hex_id

            if target_id:
                meta = wem_meta[target_id]
                old_path = os.path.join(wem_folder, file)
                
                # 改名后格式如：事件名_WEM-ID_WEM序号_BNK-ID.wem
                new_name = f"{meta['name']}_{hex_id}_{meta['wem_index']}_{meta['bnk_id']}.wem"
                new_path = os.path.join(wem_folder, new_name)
                
                # 如果依然极度逆天地存在同名文件，追加 dec_id
                if os.path.exists(new_path):
                    new_name = f"{meta['name']}_{hex_id}_{meta['wem_index']}_{meta['bnk_id']}_{dec_id}.wem"
                    new_path = os.path.join(wem_folder, new_name)
                    conflict_resolved_count += 1
                
                try:
                    os.rename(old_path, new_path)
                    print(f"[成功] {file} -> {new_name}")
                    success_count += 1
                except Exception as e:
                    print(f"[失败] 无法重命名 {file}: {e}")
                    fail_count += 1
            else:
                fail_count += 1
        else:
            # 降级备用方案
            simple_match = re.match(r'^(\d+)', file)
            if simple_match:
                sound_id = simple_match.group(1)
                if sound_id in name_lookup:
                    old_path = os.path.join(wem_folder, file)
                    new_name = f"{name_lookup[sound_id]}_{sound_id}.wem"
                    new_path = os.path.join(wem_folder, new_name)
                    try:
                        os.rename(old_path, new_path)
                        success_count += 1
                    except:
                        fail_count += 1
                else:
                    fail_count += 1

    print(f"\n处理完成！")
    print(f"成功重命名: {success_count} 个文件 (其中包含 {conflict_resolved_count} 个重名冲突解决)")
    print(f"没有匹配到名字的文件: {fail_count} 个")

def parse_args():
    parser = argparse.ArgumentParser(description='Rename WEM files using a mapping file.')
    parser.add_argument('mapping_file_positional', nargs='?', help='映射文件路径')
    parser.add_argument('wem_folder_positional', nargs='?', help='WEM 文件夹路径')
    parser.add_argument('--mapping-file', dest='mapping_file_option', help='映射文件路径，默认: bank.txt')
    parser.add_argument('--wem-folder', dest='wem_folder_option', help='WEM 文件夹路径，默认: Extracted_WEM')

    args = parser.parse_args()
    args.mapping_file = args.mapping_file_option or args.mapping_file_positional or DEFAULT_MAPPING_FILE
    args.wem_folder = args.wem_folder_option or args.wem_folder_positional or DEFAULT_WEM_FOLDER
    return args


if __name__ == '__main__':
    args = parse_args()
    batch_rename(args.mapping_file, args.wem_folder)
