"""中文数字转换工具

提供阿拉伯数字与中文数字之间的双向转换，以及法条条目号的归一化处理。
"""

_CN_DIGITS = '零一二三四五六七八九'
_CN_UNITS = ['', '十', '百', '千']
_CN_BIG_UNITS = ['', '万', '亿']


def num_to_chinese(n: int) -> str:
    """将阿拉伯数字（0~99999999）转为中文数字表示，如 577 → 五百七十七"""
    if n == 0:
        return '零'
    if n < 0:
        return '负' + num_to_chinese(-n)

    # 按万分组处理
    groups = []
    temp = n
    while temp > 0:
        groups.append(temp % 10000)
        temp //= 10000

    result = ''
    for i in range(len(groups) - 1, -1, -1):
        group = groups[i]
        group_str = four_digits_to_chinese(group)
        if group_str:
            # 如果当前组不是最高位，且该组不足四位（即高位组末尾有零），需要插零
            if i < len(groups) - 1 and group < 1000:
                result += '零'
            result += group_str + _CN_BIG_UNITS[i]
        elif result and i > 0:
            # 当前组为0但后面还有组，标记需要零
            if not result.endswith('零'):
                pass  # 会在下一组处理时通过 group < 1000 判断

    # 清理末尾的零
    result = result.rstrip('零')
    # "一十" 开头简化为 "十"（如 120 → 一百二十，但 10 → 十）
    if result.startswith('一十'):
        result = result[1:]
    return result


def four_digits_to_chinese(n: int) -> str:
    """将 0~9999 的四位以内数字转中文"""
    if n == 0:
        return ''
    digits = []
    for i in range(4):
        digits.append(n % 10)
        n //= 10
    # digits[0]=个位, digits[1]=十位, digits[2]=百位, digits[3]=千位
    result = ''
    zero_pending = False
    for i in range(3, -1, -1):
        d = digits[i]
        if d == 0:
            # 只有当后面（更低位的）已有非零数字时，才标记需要插零
            zero_pending = bool(result)
        else:
            if zero_pending and result:
                result += '零'
                zero_pending = False
            result += _CN_DIGITS[d] + _CN_UNITS[i]
    return result


def chinese_to_num(s: str) -> int:
    """将中文数字转为阿拉伯数字，如 '五百七十七' → 577"""
    if not s:
        return 0
    # 如果已经是纯数字
    if s.isdigit():
        return int(s)
    cn_map = {c: i for i, c in enumerate(_CN_DIGITS)}
    result = 0
    current = 0
    for ch in s:
        if ch in cn_map:
            current = cn_map[ch]
        elif ch == '十':
            if current == 0:
                current = 1
            result += current * 10
            current = 0
        elif ch == '百':
            if current == 0:
                current = 1
            result += current * 100
            current = 0
        elif ch == '千':
            if current == 0:
                current = 1
            result += current * 1000
            current = 0
        elif ch == '万':
            result = (result + current) * 10000
            current = 0
        elif ch == '亿':
            result = (result + current) * 100000000
            current = 0
    result += current
    return result


def normalize_item_no(item_no_str: str) -> str:
    """将条目号统一为中文格式，如 '20' → '二十'，'五百七十七' 保持不变"""
    item_no_str = item_no_str.strip()
    if item_no_str.isdigit():
        return num_to_chinese(int(item_no_str))
    return item_no_str
