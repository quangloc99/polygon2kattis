import tomllib

data = tomllib.load(open("defs.toml", "rb"))

with open("defs.latex", "w") as f:
    print(r'% This part is generated from `defs.toml` on codeforces.polygon. ', file=f)
    print(file=f)
    for field in data['english']['command'] + data['common']['command']:
        args = ''.join(map(lambda s: f'O{{{s}}}', field['args']))
        print(fr'\NewDocumentCommand{{\{field['name']}}}{{{args}}}{{{field['body']}}}', file=f)
        print(file=f)

