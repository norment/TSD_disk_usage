#!/bin/python
import pandas as pd
import networkx as nx
import datetime
import pickle
import os
import sys

where = '/'
if len(sys.argv) == 2:
    where = sys.argv[1]
os.system(f"""find {where} -not -path "/sys*" -not -path "/proc*" -not -path "*/.snapshots*" -not -path "*/.afm*" -not -path "*/s3-api*" -not -path "/tsd/projects0*/p*/home*" \( -type f -o -type d \) -exec stat -c $'%f\t%U\t%s\t%n' {{}} \; > raw-report-{datetime.datetime.now().strftime("%Y-%m-%d")}"""
)
raw = pd.read_csv(f'raw-report-{datetime.datetime.now().strftime("%Y-%m-%d")}', sep='\t', names='Mode User Size Path'.split())
raw.drop_duplicates('Path', inplace=True) #omittable?
G = nx.DiGraph()
edges = raw.Path.map(lambda x: (x.rsplit('/',1)[0],x))
nodes = raw.apply(lambda x: [x['Path'], {'User': x['User'], 'Size': x['Size'], 'Files': int(x['Mode']=='81a4')}], axis=1).values
G.add_nodes_from(nodes)
G.add_edges_from(edges)

def set_cummulative_weight(G,node,what):
    G.nodes[node][f'c_{what}'] = G.nodes[node].get(what, 0)
    for child in G.neighbors(node):
        G.nodes[node][f'c_{what}']+=set_cummulative_weight(G,child,what)
    return G.nodes[node][f'c_{what}']

set_cummulative_weight(G, '', 'Size')
set_cummulative_weight(G, '', 'Files')

def to_write(G, node, minfiles=100, minsize=1<<30): # more than 1GiB or 100 files
    if G.nodes[node]['c_Size'] > (minsize) or G.nodes[node]['c_Files'] > minfiles:
        return [{'Files': G.nodes[node]['c_Files'], 'Size': G.nodes[node]['c_Size'], 'Path': node}] + sum([to_write(G, child) for child in G.neighbors(node)], [])
    else:
        return []

df = pd.DataFrame(to_write(G, ''))
df.sort_values('Files', inplace=True, ascending=False)
pickle.dump(G, open(f'raw-report-{datetime.datetime.now().strftime("%Y-%m-%d")}.pickle', 'wb'))

os.system(f"""ln -sf raw-report-{datetime.datetime.now().strftime("%Y-%m-%d")}.pickle latest.pickle""")
df.to_csv(f'p33-data-usage-{datetime.datetime.now().strftime("%Y-%m-%d")}.txt', sep='\t', index=False)
os.system(f"""ln -sf p33-data-usage-{datetime.datetime.now().strftime("%Y-%m-%d")}.txt p33-data-usage-latest.txt""")
