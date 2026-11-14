# -*- coding: utf-8 -*-
"""Une listas M3U locais e organiza URLs alternativas por canal.
Não verifica autorização nem reprodução. Não envia URLs a terceiros.
"""
from pathlib import Path
from collections import OrderedDict
from urllib.parse import urlsplit, urlunsplit
import re, unicodedata

BASE = Path(__file__).resolve().parent
INPUTS = [BASE / 'Brazuka-Detectados.m3u', BASE / 'Novos-Detectados.m3u']
OUTPUT_GROUP = BASE / 'Nossa-IPTV-Agrupada.m3u'
OUTPUT_MANUAL = BASE / 'Nossa-IPTV-Fontes-Separadas.m3u'
REPORT = BASE / 'Nossa-IPTV-Relatorio.txt'

# Não agrupar afiliadas, regiões, canais numerados ou canais com nomes parecidos.
# Apenas retira marcadores de qualidade/fonte no FINAL do nome.
QUALITY = re.compile(r'(?i)(?:\s*(?:\[|\()(?:h\.?265|hevc|h\.?264|1080p|720p|480p|4k|uhd|fhd|hd|sd|alter|alt|fonte\s*\d+)(?:\]|\)))+$')
TAIL = re.compile(r'(?i)(?:\s+(?:4k|uhd|fhd|hd|sd|h\.?265|hevc|h\.?264|1080p|720p|480p|\[alter\]|\[alt\]|\[fonte\s*\d+\]|fonte\s*\d+|\u00b9|\u00b2|\u00b3))+$')
ATTR = re.compile(r'([\w-]+)="([^"]*)"')

def normalize(name):
    name = QUALITY.sub('', name.strip())
    while True:
        next_name = TAIL.sub('', name).strip()
        if next_name == name: break
        name = next_name
    name = re.sub(r'\s+', ' ', name)
    return name

def key_for(name):
    norm = unicodedata.normalize('NFKD', normalize(name)).casefold()
    return ''.join(c for c in norm if not unicodedata.combining(c)).strip()

def read_m3u(path):
    entries=[]; pending=None; options=[]
    for raw in path.read_text(encoding='utf-8-sig', errors='replace').splitlines():
        line=raw.strip()
        if line.startswith('#EXTINF:'):
            pending=line; options=[]
        elif line.startswith('#'):
            if pending and not line.startswith('#EXTM3U'): options.append(line)
        elif line and pending:
            if line.startswith(('http://','https://','rtmp://','rtsp://')):
                name=pending.rsplit(',',1)[-1].strip()
                attrs=dict(ATTR.findall(pending.split(',',1)[0]))
                entries.append({'name':name,'url':line,'attrs':attrs,'options':options[:]})
            pending=None; options=[]
    return entries

def extinf(name, attrs):
    # Os metadados originais permanecem, com o nome padronizado.
    parts=[]
    for k,v in attrs.items():
        if k in ('group-title','tvg-id','tvg-logo','tvg-name') and v:
            parts.append(f'{k}="{v.replace(chr(34), "")}"')
    return '#EXTINF:-1' + (' ' + ' '.join(parts) if parts else '') + ',' + name

def write_playlist(path, groups, separate=False):
    lines=['#EXTM3U']
    for channel in groups.values():
        for i, entry in enumerate(channel['sources'], 1):
            name=channel['name'] + (f' | Fonte {i}' if separate and len(channel['sources'])>1 else '')
            lines.append(extinf(name, channel['attrs']))
            lines.extend(entry['options'])
            lines.append(entry['url'])
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')

def main():
    missing=[str(p) for p in INPUTS if not p.is_file()]
    if missing:
        print('ARQUIVOS NAO ENCONTRADOS:')
        for p in missing: print(' -',p)
        print('Coloque os dois M3U na mesma pasta deste script e execute novamente.')
        return
    groups=OrderedDict(); seen_urls=set(); totals=[]; duplicates=0
    for path in INPUTS:
        entries=read_m3u(path); totals.append((path.name,len(entries)))
        for e in entries:
            # URLs exatas duplicadas são eliminadas, mesmo entre canais.
            if e['url'] in seen_urls:
                duplicates+=1; continue
            seen_urls.add(e['url'])
            k=key_for(e['name'])
            if not k: continue
            if k not in groups:
                groups[k]={'name':normalize(e['name']), 'attrs':e['attrs'].copy(), 'sources':[]}
            else:
                for a in ('tvg-id','tvg-logo','group-title'):
                    if not groups[k]['attrs'].get(a) and e['attrs'].get(a):
                        groups[k]['attrs'][a]=e['attrs'][a]
            groups[k]['sources'].append(e)
    write_playlist(OUTPUT_GROUP,groups)
    write_playlist(OUTPUT_MANUAL,groups,True)
    multi=[g for g in groups.values() if len(g['sources'])>1]
    report=['NOSSA IPTV - RELATORIO','', 'Entradas por arquivo:']
    report += [f'  {n}: {q}' for n,q in totals]
    report += ['',f'URLs identicas descartadas: {duplicates}',f'URLs unicas: {len(seen_urls)}',f'Canais agrupados por nome: {len(groups)}',f'Canais com 2+ fontes: {len(multi)}','','CANAIS COM FONTES ALTERNATIVAS:']
    report += [f"{g['name']}: {len(g['sources'])} fontes" for g in multi]
    report += ['', 'ATENCAO: fontes detectadas pelo ffprobe nao sao garantia de reproducao, nem de autorizacao de transmissao.', 'A playlist agrupada repete EXTINF com mesmo nome/ID. O player pode ou nao unir as fontes.', 'A playlist de fontes separadas permite selecionar cada entrada manualmente.']
    REPORT.write_text('\n'.join(report)+'\n',encoding='utf-8')
    print('\n'.join(report[:10]))
    print('\nCRIADOS:',OUTPUT_GROUP.name,OUTPUT_MANUAL.name,REPORT.name,sep='\n - ')

if __name__=='__main__': main()
