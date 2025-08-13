def extract_todays_vision_in_frame(ocr_text):
    """枠内の今日の視力（3-4行目）を正確に抽出"""
    
    lines = ocr_text.split('\n')
    
    result = {
        'right_naked': None,      # 右裸眼（今日・枠内）
        'right_corrected': None,  # 右矯正（今日・枠内）
        'left_naked': None,       # 左裸眼（今日・枠内）
        'left_corrected': None,   # 左矯正（今日・枠内）
        'previous_right': None,   # 前回の右（枠外）
        'previous_left': None,    # 前回の左（枠外）
        'debug_info': []
    }
    
    # 方法1: 枠線を検出して、枠内のV.d./V.s.を取得
    frame_start = -1
    frame_end = -1
    
    for i, line in enumerate(lines):
        # 枠の開始を検出（┌ または ─ が複数）
        if ('┌' in line or '─' * 3 in line or '━' * 3 in line) and frame_start == -1:
            frame_start = i
            result['debug_info'].append(f"枠開始検出: 行{i+1}")
        
        # 枠の終了を検出（└ または ─ が複数）
        elif ('└' in line or '─' * 3 in line or '━' * 3 in line) and frame_start != -1:
            frame_end = i
            result['debug_info'].append(f"枠終了検出: 行{i+1}")
            break
    
    # 枠内のV.d./V.s.を探す
    if frame_start != -1 and frame_end != -1:
        for i in range(frame_start + 1, frame_end):
            line = lines[i]
            
            # V.d.（右眼）
            if re.search(r'V\.?\s*[dD]\.?\s*[=＝]', line):
                vision_data = extract_vision_value_from_line(line)
                result['right_naked'] = vision_data['naked']
                result['right_corrected'] = vision_data['corrected']
                result['debug_info'].append(f"枠内V.d.: {line[:50]}")
            
            # V.s.（左眼）
            elif re.search(r'V\.?\s*[sS]\.?\s*[=＝]', line):
                vision_data = extract_vision_value_from_line(line)
                result['left_naked'] = vision_data['naked']
                result['left_corrected'] = vision_data['corrected']
                result['debug_info'].append(f"枠内V.s.: {line[:50]}")
    
    # 方法2: 枠が検出できない場合、2回目のV.d./V.s.を取得
    if not result['right_naked'] and not result['left_naked']:
        result['debug_info'].append("枠検出失敗、順序で判定")
        
        vd_count = 0
        vs_count = 0
        
        for i, line in enumerate(lines):
            # 既往症が来たら終了
            if '既往症' in line:
                break
            
            # V.d.の処理
            if re.search(r'V\.?\s*[dD]\.?\s*[=＝]', line):
                vd_count += 1
                vision_data = extract_vision_value_from_line(line)
                
                if vd_count == 1:
                    # 1回目は前回
                    result['previous_right'] = vision_data['naked']
                elif vd_count == 2:
                    # 2回目が今日（枠内）
                    result['right_naked'] = vision_data['naked']
                    result['right_corrected'] = vision_data['corrected']
                    result['debug_info'].append(f"2回目V.d.（今日）: {line[:50]}")
            
            # V.s.の処理
            elif re.search(r'V\.?\s*[sS]\.?\s*[=＝]', line):
                vs_count += 1
                vision_data = extract_vision_value_from_line(line)
                
                if vs_count == 1:
                    # 1回目は前回
                    result['previous_left'] = vision_data['naked']
                elif vs_count == 2:
                    # 2回目が今日（枠内）
                    result['left_naked'] = vision_data['naked']
                    result['left_corrected'] = vision_data['corrected']
                    result['debug_info'].append(f"2回目V.s.（今日）: {line[:50]}")
    
    # 方法3: 既往症から逆算（最終手段）
    if not result['right_naked'] and not result['left_naked']:
        result['debug_info'].append("既往症から逆算")
        
        medical_history_line = -1
        for i, line in enumerate(lines):
            if '既往症' in line:
                medical_history_line = i
                break
        
        if medical_history_line > 0:
            # 既往症の直前2行が今日の視力（枠内）
            if medical_history_line >= 2:
                # 直前の行がV.s.
                vs_line = lines[medical_history_line - 1]
                if 'V.s' in vs_line or 'V.S' in vs_line:
                    vs_data = extract_vision_value_from_line(vs_line)
                    result['left_naked'] = vs_data['naked']
                    result['left_corrected'] = vs_data['corrected']
                    result['debug_info'].append(f"既往症前V.s.: {vs_line[:50]}")
            
            if medical_history_line >= 3:
                # 2行前がV.d.
                vd_line = lines[medical_history_line - 2]
                if 'V.d' in vd_line or 'V.D' in vd_line:
                    vd_data = extract_vision_value_from_line(vd_line)
                    result['right_naked'] = vd_data['naked']
                    result['right_corrected'] = vd_data['corrected']
                    result['debug_info'].append(f"既往症前V.d.: {vd_line[:50]}")
    
    return result

def detect_frame_pattern(lines):
    """枠のパターンを検出"""
    
    patterns = {
        'box': False,      # ┌─┐└─┘ パターン
        'line': False,     # ──── パターン
        'asterisk': False, # **** パターン
        'equal': False     # ==== パターン
    }
    
    for line in lines:
        if '┌' in line or '└' in line or '│' in line:
            patterns['box'] = True
        if '─' * 3 in line or '━' * 3 in line:
            patterns['line'] = True
        if '*' * 3 in line:
            patterns['asterisk'] = True
        if '=' * 3 in line:
            patterns['equal'] = True
    
    return patterns

def extract_vision_value_from_line_enhanced(line):
    """視力値抽出の強化版（より多くのパターンに対応）"""
    
    result = {
        'naked': None,
        'corrected': None
    }
    
    # 前処理：全角を半角に統一
    line = line.replace('．', '.').replace('＝', '=')
    
    # 裸眼視力のパターン（優先順位順）
    naked_patterns = [
        # 標準パターン
        r'V\.?\s*[dDsS]\.?\s*=\s*(0\.\d+)',  # V.d.= 0.6
        r'V\.?\s*[dDsS]\.?\s*=\s*(1\.[025])',  # V.d.= 1.0, 1.2, 1.5
        r'V\.?\s*[dDsS]\.?\s*=\s*(2\.0)',      # V.d.= 2.0
        
        # 分離パターン
        r'V\.?\s*[dDsS]\.?\s*=\s*(\d)\s*[,，.\s]\s*(\d)',  # V.d.= 0, 6
        
        # 誤認識パターン
        r'V\.?\s*[dDsS]\.?\s*=\s*(\d{2})',     # V.d.= 06 → 0.6
    ]
    
    for pattern in naked_patterns:
        match = re.search(pattern, line)
        if match:
            if len(match.groups()) == 2:
                # 分離された数字
                result['naked'] = combine_separated_numbers(match.group(1), match.group(2))
            else:
                result['naked'] = fix_and_validate_vision(match.group(1))
            break
    
    # 矯正視力のパターン
    # 括弧内の最初の数値
    bracket_match = re.search(r'\(([^)]+)\)', line)
    if bracket_match:
        bracket_content = bracket_match.group(1)
        
        # n.c.チェック
        if re.search(r'n\.?c\.?', bracket_content, re.IGNORECASE):
            result['corrected'] = 'n.c.'
        else:
            # 数値を探す
            num_match = re.search(r'([\d.]+)', bracket_content)
            if num_match:
                result['corrected'] = fix_and_validate_vision(num_match.group(1))
    
    return result