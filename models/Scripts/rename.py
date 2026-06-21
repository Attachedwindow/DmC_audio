import argparse
import os
import re


MAPPING_FILE = 'bank.txt'
WEM_FOLDER = 'Extracted_WEM'


def parse_args():
    parser = argparse.ArgumentParser(description='Rename extracted WEM files from a bank mapping file.')
    parser.add_argument('mapping_file', nargs='?', default=MAPPING_FILE, help='Path to the bank mapping file.')
    parser.add_argument('wem_folder', nargs='?', default=WEM_FOLDER, help='Folder containing extracted WEM files.')
    return parser.parse_args()


def batch_rename(mapping_file, wem_folder):
    if not os.path.exists(mapping_file):
        print(f"[错误] 找不到映射文件: {mapping_file}")
        return
    if not os.path.exists(wem_folder):
        print(f"[错误] 找不到文件夹: {wem_folder}")
        return

    mapping_dict = {}
    id_name_pattern = re.compile(r'(\d+)\s+([\w\-_]+)')
    parentheses_pattern = re.compile(r'(?:ID|id)\s*=\s*(\d+)\s*\(([\w\-_]+)\)')

    print('正在解析 bank.txt...')
    with open(mapping_file, 'r', encoding='utf-8', errors='ignore') as file_handle:
        for line in file_handle:
            paren_match = parentheses_pattern.search(line)
            if paren_match:
                sound_id = paren_match.group(1)
                file_name = paren_match.group(2)
                mapping_dict[sound_id] = file_name
                continue

            match = id_name_pattern.search(line)
            if match:
                sound_id = match.group(1)
                file_name = match.group(2)
                if not file_name.isdigit():
                    mapping_dict[sound_id] = file_name

    print(f"成功载入 {len(mapping_dict)} 组映射关系。开始重命名...\n")

    success_count = 0
    conflict_resolved_count = 0
    fail_count = 0

    file_pattern = re.compile(r'^(\d+)\s*\(?([0-9a-fA-F]+)\)?\.wem$')

    for file_name in os.listdir(wem_folder):
        if not file_name.lower().endswith('.wem'):
            continue

        match = file_pattern.match(file_name)
        if match:
            dec_id = match.group(1)
            hex_id = match.group(2)

            try:
                converted_hex_id = str(int(hex_id, 16))
            except ValueError:
                converted_hex_id = None

            target_id = None
            if dec_id in mapping_dict:
                target_id = dec_id
            elif converted_hex_id and converted_hex_id in mapping_dict:
                target_id = converted_hex_id

            if target_id:
                old_path = os.path.join(wem_folder, file_name)
                new_name = f"{mapping_dict[target_id]}_{hex_id}.wem"
                new_path = os.path.join(wem_folder, new_name)

                if os.path.exists(new_path):
                    new_name = f"{mapping_dict[target_id]}_{hex_id}_{dec_id}.wem"
                    new_path = os.path.join(wem_folder, new_name)
                    conflict_resolved_count += 1

                try:
                    os.rename(old_path, new_path)
                    print(f"[成功] {file_name} -> {new_name}")
                    success_count += 1
                except Exception as error:
                    print(f"[失败] 无法重命名 {file_name}: {error}")
                    fail_count += 1
            else:
                fail_count += 1
        else:
            simple_match = re.match(r'^(\d+)', file_name)
            if simple_match:
                sound_id = simple_match.group(1)
                if sound_id in mapping_dict:
                    old_path = os.path.join(wem_folder, file_name)
                    new_name = f"{mapping_dict[sound_id]}_{sound_id}.wem"
                    new_path = os.path.join(wem_folder, new_name)
                    try:
                        os.rename(old_path, new_path)
                        success_count += 1
                    except Exception:
                        fail_count += 1
                else:
                    fail_count += 1

    print('\n处理完成！')
    print(f"成功重命名: {success_count} 个文件 (其中包含 {conflict_resolved_count} 个重名冲突解决)")
    print(f"没有匹配到名字的文件: {fail_count} 个")


def main():
    args = parse_args()
    batch_rename(args.mapping_file, args.wem_folder)


if __name__ == '__main__':
    main()