#!/usr/bin/env python3
"""Precise decoder for the AstroBugz Construct 2 data.js using the runtime ref table."""
import json, re

BASE = '/root/5a06b8e65bdb/ASTROBYTE/src/app/webapp/arcade/astrobugz/'
proj = json.load(open(BASE + 'data.js', encoding='utf-8-sig'))['project']
types, families, layouts, sheets = proj[3], proj[4], proj[5], proj[6]

# --- ACE ref table from c2runtime.js ---
src = open(BASE + 'c2runtime.js', encoding='utf-8').read()
i = src.find('cr.getObjectRefTable = function () { return [')
j = src.find('];', i)
entries = re.findall(r'cr\.[A-Za-z0-9_.$]+', src[i:j])
# entries[0] is 'cr.getObjectRefTable' itself; table starts at entries[1]
ref = entries[1:]
def acename(idx):
    if 0 <= idx < len(ref):
        e = ref[idx]
        e = e.replace('cr.plugins_.', '').replace('cr.behaviors.', 'beh.').replace('cr.system_object.prototype.', 'System.')
        e = e.replace('.prototype.', '.')
        return e
    return f'?{idx}'

TNAME = {}
for idx, t in enumerate(types):
    TNAME[idx] = t[0]

def obj(idx):
    if idx == -1: return 'System'
    return TNAME.get(idx, f'obj{idx}')

def expr(p):
    if not isinstance(p, list):
        return repr(p)
    tag = p[0]
    if tag in (0, 1): return str(p[1])
    if tag == 2: return json.dumps(p[1])
    if tag == 3: return '(-' + expr(p[1]) + ')' if len(p) == 2 else f'?neg{json.dumps(p)}'
    if tag == 4: return '(' + ' + '.join(expr(x) for x in p[1:]) + ')'
    if tag == 5: return '(' + ' - '.join(expr(x) for x in p[1:]) + ')'
    if tag == 6: return '(' + ' * '.join(expr(x) for x in p[1:]) + ')'
    if tag == 7:
        if len(p) == 2: return expr(p[1])
        return '(' + ' / '.join(expr(x) for x in p[1:]) + ')'
    if tag == 8: return '(' + ' % '.join(expr(x) for x in p[1:]) + ')'
    if tag == 10: return '(' + ' & '.join(expr(x) for x in p[1:]) + ')'
    if tag == 11: return f'setvar:{p[1]}'
    if tag == 12: return '(' + ' == '.join(expr(x) for x in p[1:]) + ')'
    if tag == 13: return '(' + ' != '.join(expr(x) for x in p[1:]) + ')'
    if tag == 14: return '(' + ' < '.join(expr(x) for x in p[1:]) + ')'
    if tag == 15: return '(' + ' <= '.join(expr(x) for x in p[1:]) + ')'
    if tag == 16: return '(' + ' > '.join(expr(x) for x in p[1:]) + ')'
    if tag == 17: return '(' + ' >= '.join(expr(x) for x in p[1:]) + ')'
    if tag == 18: return f'({expr(p[1])} ? {expr(p[2])} : {expr(p[3])})'
    if tag == 19:
        args = p[2] if len(p) > 2 and isinstance(p[2], list) else []
        nm = acename(p[1]).replace('System.exps.', '')
        return f'{nm}({", ".join(expr(a) for a in args)})'
    if tag == 20:
        nm = acename(p[2])
        nm = nm.split('.exps.')[-1]
        args = p[5] if len(p) > 5 and isinstance(p[5], list) else []
        return f'{obj(p[1])}.{nm}({", ".join(expr(a) for a in args)})'
    if tag == 21:
        return f'{obj(p[1])}.var{p[4]}'
    if tag == 22:
        nm = acename(p[3]).split('.exps.')[-1]
        args = p[6] if len(p) > 6 and isinstance(p[6], list) else []
        return f'{obj(p[1])}.{p[2]}.{nm}({", ".join(expr(a) for a in args)})'
    if tag == 23:
        return f'${p[1]}'
    return f'?tag{tag}:{json.dumps(p)[:100]}'

OPS = ['=', '!=', '<', '<=', '>', '>=']
def aceparam(p):
    if not isinstance(p, list): return repr(p)
    tag = p[0]
    if tag in (0, 1, 7): return expr(p[1])
    if tag == 2: return json.dumps(p[1])
    if tag == 3: return f'opt#{p[1]}'
    if tag == 4: return f'OBJ:{obj(p[1])}'
    if tag == 5: return 'layer:' + (expr(p[1]) if isinstance(p[1], list) else str(p[1]))
    if tag == 6: return f'layout:{p[1]}'
    if tag == 8: return f'op{OPS[p[1]] if p[1] < 6 else p[1]}'
    if tag == 10: return f'ivar#{p[1]}'
    if tag == 11: return f'gvar:{p[1]}'
    if tag == 13:
        return 'args(' + ', '.join(aceparam(x) for x in p[1:]) + ')'
    return f'?p{tag}:{json.dumps(p)[:80]}'

def fmt_cond(c):
    # cond: [objidx, aceid, behavior, unknown, inverted?, static?, ?, sid, ?, params?]
    o, a, beh = c[0], c[1], c[2]
    inverted = bool(c[5]) if len(c) > 5 else False
    params = c[-1] if c and isinstance(c[-1], list) and all(isinstance(x, list) for x in c[-1]) else None
    nm = acename(a)
    nm = nm.split('.cnds.')[-1] if '.cnds.' in nm else nm
    b = f'.{beh}' if beh else ''
    ps = '(' + ', '.join(aceparam(x) for x in (params or [])) + ')'
    return ('NOT ' if inverted else '') + f'{obj(o)}{b}.{nm}{ps}'

def fmt_act(a):
    o, aid, beh = a[0], a[1], a[2]
    params = a[-1] if a and isinstance(a[-1], list) and all(isinstance(x, list) for x in a[-1]) else None
    nm = acename(aid)
    nm = nm.split('.acts.')[-1] if '.acts.' in nm else nm
    b = f'.{beh}' if beh else ''
    ps = '(' + ', '.join(aceparam(x) for x in (params or [])) + ')'
    return f'{obj(o)}{b}.{nm}{ps}'

def walk(events, ind):
    pad = '  ' * ind
    for ev in events:
        if not isinstance(ev, list): continue
        if ev[0] == 0:
            group, is_or = ev[1], ev[2]
            conds, acts = ev[5], ev[6]
            subs = ev[7] if len(ev) > 7 else []
            if isinstance(group, list):
                print(pad + f'# ==== GROUP: {group[1]} ====')
            joiner = '  OR  ' if is_or else '  AND  '
            cs = joiner.join(fmt_cond(c) for c in conds) or '(always)'
            print(pad + 'WHEN ' + cs + ':')
            for a in acts:
                print(pad + '    ' + fmt_act(a))
            if subs: walk(subs, ind + 1)
        elif ev[0] == 1:
            print(pad + f'VAR {ev[1]} = {ev[3]!r}')
        elif ev[0] == 2:
            print(pad + f'INCLUDE {ev[1]}')

for sheet in sheets:
    print(f'\n{"#"*90}\n# SHEET: {sheet[0]}\n{"#"*90}')
    walk(sheet[1], 0)
