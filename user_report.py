#!/bin/python3
import pandas as pd
import networkx as nx
import datetime
import pickle
import argparse

parser = argparse.ArgumentParser(description='Filter disk usage report by username')
parser.add_argument('uname', help='username')
parser.add_argument('-i','--in', help='.pickle input, default: latest.pickle', default='latest.pickle')
parser.add_argument('-o','--out', help='output, default: username-YYYY-MM-DD.txt', default='')
parser.add_argument('-s','--min-size', help='min size [bytes] to include in report, default: 1073741824', default=1<<30)
parser.add_argument('-f','--min-files', help='min file count to include in report, default: 100',default=100)

args = vars(parser.parse_args())
if args['out'] == '':
    args['out'] = f'{args["uname"]}-{datetime.datetime.now().strftime("%Y-%m-%d")}.txt'
    
G=pickle.load(open(args['in'], 'rb'))

def set_cummulative_weight_by_user(G,node,what,user):
    G.nodes[node][f'c_{user}_{what}'] = G.nodes[node].get(what, 1)*(G.nodes[node].get('User',None)==user)
    for child in G.neighbors(node):
        G.nodes[node][f'c_{user}_{what}']+=set_cummulative_weight_by_user(G,child,what,user)
    return G.nodes[node][f'c_{user}_{what}']

set_cummulative_weight_by_user(G, '', 'Size', args['uname'])
set_cummulative_weight_by_user(G, '', 'Files', args['uname'])

def to_write(G, node):#more than 1GiB or 100 files
    if G.nodes[node][f"c_{args['uname']}_Size"] > (int(args['min_size'])) or G.nodes[node][f"c_{args['uname']}_Files"] > int(args['min_files']):
        return [{'Files': G.nodes[node][f"c_{args['uname']}_Files"], 'Size': G.nodes[node][f"c_{args['uname']}_Size"], 'Path': node}] + sum([to_write(G, child) for child in G.neighbors(node)], [])
    else:
        return []

df = pd.DataFrame(to_write(G, ''))
df.sort_values('Files', inplace=True, ascending=False)
df.to_csv(f'{args["out"]}.txt', sep='\t', index=False)
