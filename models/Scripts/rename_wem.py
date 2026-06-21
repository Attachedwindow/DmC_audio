import os
import re

# 配置路径
MAPPING_FILE = 'bank.txt'
WEM_FOLDER = 'Extracted_WEM'

def batch_rename():
    if not os.path.exists(MAPPING_FILE):
        print(f"[错误] 找不到映射文件: {MAPPING_FILE}")
        return
    if not os.path.exists(WEM_FOLDER):
        print(f"[错误] 找不到文件夹: {WEM_FOLDER}")
        return

    # 1. 读取 bank.txt 并解析映射关系
    mapping_dict = {}
    id_name_pattern = re.compile(r'(\d+)\s+([\w\-_]+)')
    parentheses_pattern = re.compile(r'(?:ID|id)\s*=\s*(\d+)\s*\(([\w\-_]+)\)')

    print("正在解析 bank.txt...")
    with open(MAPPING_FILE, 'r', encoding='utf-8', errors='ignore') as f:
        for line in f:
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

    # 2. 遍历 Extracted_WEM 文件夹进行重命名
    success_count = 0
    conflict_resolved_count = 0
    fail_count = 0
    
    # 正则：匹配 "任意数字 (十六进制).wem"
    file_pattern = re.compile(r'^(\d+)\s*\(?([0-9a-fA-F]+)\)?\.wem$')

    for file in os.listdir(WEM_FOLDER):
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
            if dec_id in mapping_dict:
                target_id = dec_id
            elif converted_hex_id and converted_hex_id in mapping_dict:
                target_id = converted_hex_id

            if target_id:
                old_path = os.path.join(WEM_FOLDER, file)
                
                # 新文件名拼接括号里的唯一 hex_id，杜绝重名冲突
                # 改名后格式如：VO_UNDERGROUNDWORLD_PA_c80f2dd0.wem
                new_name = f"{mapping_dict[target_id]}_{hex_id}.wem"
                new_path = os.path.join(WEM_FOLDER, new_name)
                
                # 如果依然极度逆天地存在同名文件，追加 dec_id
                if os.path.exists(new_path):
                    new_name = f"{mapping_dict[target_id]}_{hex_id}_{dec_id}.wem"
                    new_path = os.path.join(WEM_FOLDER, new_name)
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
                if sound_id in mapping_dict:
                    old_path = os.path.join(WEM_FOLDER, file)
                    new_name = f"{mapping_dict[sound_id]}_{sound_id}.wem"
                    new_path = os.path.join(WEM_FOLDER, new_name)
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

if __name__ == '__main__':
    batch_rename()
