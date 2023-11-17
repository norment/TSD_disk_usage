#!/bin/python
import pandas as pd
import networkx as nx
from collections import ChainMap
import argparse
import os

def set_cummulative_weight_all(G,node,what):
    G.nodes[node][f'c_{what}'] = sum([G.nodes[node].get(f'{user}_{what}', 0) for user in set([i.split('_')[0] for i in G.nodes[node].keys() if i[:2] != 'c_'])])
    for child in G.neighbors(node):
        G.nodes[node][f'c_{what}']+=set_cummulative_weight_all(G,child,what)
    return G.nodes[node][f'c_{what}']

def set_cummulative_weight_by_user(G,node,what,user):
    G.nodes[node][f'c_{user}_{what}'] = G.nodes[node].get(f'{user}_{what}', 0)
    for child in G.neighbors(node):
        G.nodes[node][f'c_{user}_{what}']+=set_cummulative_weight_by_user(G,child,what,user)
    return G.nodes[node][f'c_{user}_{what}']

def to_write(G, node, minfiles, minsize, user): # more than 1GiB or 100 files
    def _to_write1(G, node, minfiles, minsize, user):
        if G.nodes[node][f'c_{user}_Size'] > (minsize) or G.nodes[node][f'c_{user}_Files'] > minfiles:
            return [{'Files': G.nodes[node][f'c_{user}_Files'], 'Size': G.nodes[node][f'c_{user}_Size'], 'Path': node}] + sum([_to_write1(G, child, minfiles, minsize, user) for child in G.neighbors(node)], [])
        else:
            return []
    def _to_write2(G, node, minfiles, minsize):
        if G.nodes[node]['c_Size'] > (minsize) or G.nodes[node]['c_Files'] > minfiles:
            return [{'Files': G.nodes[node]['c_Files'], 'Size': G.nodes[node]['c_Size'], 'Path': node}] + sum([_to_write2(G, child, minfiles, minsize) for child in G.neighbors(node)], [])
        else:
            return []
    return _to_write1(G, node, minfiles, minsize, user) if user else _to_write2(G, node, minfiles, minsize)
    
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A python script to interpret disk usage report for TSD.')
    parser.add_argument('--infile', default='disk_report_latest', type=str, help='Input file, default is raw_report_latest')
    parser.add_argument('--root', type=str, help='Root folder to aggregate disk usage into')
    parser.add_argument('--out', default=None, type=str, help='Output file, default is stdout')
    parser.add_argument('--minfiles', default=100, type=int, help='minimum file count in directories to include in output, default is 100')
    parser.add_argument('--minsize', default=(1<<30) ,type=int, help='minimum size directories to include in output, default is 1073741824')
    parser.add_argument('--user', default=None, type=str, help='user to filter on, default is no-user')
    args = parser.parse_args()
    
    raw = pd.read_csv(args.infile, sep='\t', names='Path User Size Files'.split())
    raw=raw.groupby('Path').agg(list)
    root = os.path.realpath(args.root)
    edges = raw.index.map(lambda x: (x.rsplit('/',1)[0] if x.rsplit('/',1)[0] else '/' ,x))[1:]   
    nodes = raw.apply(lambda x: (x.name, ChainMap(*[{x.User[i]+'_Size': x['Size'][i], x.User[i]+'_Files': x['Files'][i]} for i in range(len(x.User))])), axis=1).values
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)
    assert(nx.is_tree(G))
    
    if args.user == None:
        set_cummulative_weight_all(G, root, 'Size')
        set_cummulative_weight_all(G, root, 'Files')
    else:
        set_cummulative_weight_by_user(G, root, 'Size', args.user)
        set_cummulative_weight_by_user(G, root, 'Files', args.user)
        
    df = pd.DataFrame(to_write(G, root, args.minfiles, args.minsize, args.user))
    df.sort_values('Files', inplace=True, ascending=False)
    if args.out:
        df.to_csv(args.out, index=False)
    else:
        print(df.to_string(index=False))
