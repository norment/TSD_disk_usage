#!/bin/python
import pandas as pd
import networkx as nx
from collections import ChainMap
import argparse
import os
import subprocess
import numpy as np
from datetime import datetime

def set_cummulative_weight_all(G,node,what):
    G.nodes[node][f'c_{what}'] = sum([G.nodes[node].get(f'{user}_{what}', 0) for user in set([i.split('_')[0] for i in G.nodes[node].keys() if i[:2] != 'c_'])])
    for child in G.neighbors(node):
        G.nodes[node][f'c_{what}']+=set_cummulative_weight_all(G,child,what)
    return G.nodes[node].get(f'c_{what}', 0)

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
        if G.nodes[node].get('c_Size',0) > (minsize) or G.nodes[node].get('c_Files',0) > minfiles:
            return [{'Files': G.nodes[node].get('c_Files', 0), 'Size': G.nodes[node].get('c_Size',0), 'Path': node}] + sum([_to_write2(G, child, minfiles, minsize) for child in G.neighbors(node)], [])
        else:
            return []
    return _to_write1(G, node, minfiles, minsize, user) if user else _to_write2(G, node, minfiles, minsize)

def get_root(G, node):
    if len(list(G.predecessors(node))) == 0:
        return node
    else:
        return get_root(G, G.predecessors(node)[0])

def connect_graph(G, node):
    if len(list(G.predecessors(node))) != 0:
        connect_graph(G, list(G.predecessors(node))[0])
    else: # Either root or source of the problem
        if G.nodes[node]: # root
            pass
        else:
            current_node = node
            while '/' in current_node:
                # Split the current node to move up one level in the hierarchy
                current_node = current_node.rsplit('/', 1)[0]
                # Check if this parent node exists
                if G.has_node(current_node):
                    # Reassign all children of the original node to this parent
                    for child in list(G.successors(node)):
                        # Remove current parents of the child
                        for current_parent in list(G.predecessors(child)):
                            G.remove_edge(current_parent, child)
                        # Set the new parent for the child
                        G.add_edge(current_node, child)
                    G.remove_node(node)
                    return

def bytes_to_readable(bytes):
    for unit in ['bytes', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB']:
        if bytes < 1024:
            return f"{bytes:.1f}{unit}"
        bytes /= 1024
    return f"{bytes:.1f}YB"

def files_to_readable(files):
    for unit in ['', 'K', 'M']:
        if files < 1000:
            return f"{files:.1f}{unit}"
        files /= 1000
    return f"{files:.1f}G"

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='A python script to interpret disk usage report for TSD.')
    parser.add_argument('--infile', default='disk_report_latest', type=str, help='Input file, default is raw_report_latest')
    parser.add_argument('--out', default='', type=str, help='Suffix of the output directory and Infix of the output files, all user report will created in cwd')
    parser.add_argument('--minfiles', default=100, type=int, help='minimum file count in directories to include in output, default is 100')
    parser.add_argument('--minsize', default=(1<<30) ,type=int, help='minimum size directories to include in output, default is 1073741824')
    parser.add_argument('--user', default=None, type=str, help='UID to filter on, default is no-user')
    args = parser.parse_args()

    raw = pd.read_csv(args.infile, sep='\t', names='Path User Size Files'.split())

    dropped = raw[raw.isna().any(axis=1)]
    if dropped.shape[0] > 0:
        print('dropped:')
        print(dropped)
        raw.dropna(inplace=True)

    raw['Size'] = raw['Size'].astype(int)
    raw['Files'] = raw['Files'].astype(int)

    users=raw.User.unique()
    users=users[users!='dir']
    raw=raw.groupby('Path').agg(list)
    print(f'{len(users)} users found.')
    print(users)
    edges = raw.index.map(lambda x: (x.rsplit('/',1)[0] if x.rsplit('/',1)[0] else '/' ,x))[1:]
    nodes = raw.apply(lambda x: (x.name, ChainMap(*[{str(x.User[i])+'_Size': x['Size'][i], str(x.User[i])+'_Files': x['Files'][i]} for i in range(len(x.User))])), axis=1).values
    G = nx.DiGraph()
    G.add_nodes_from(nodes)
    G.add_edges_from(edges)

    if not nx.is_tree(G):
        U=G.to_undirected()
        ccs = list(nx.connected_components(U))
        for c in (ccs):
            connect_graph(G,list(c)[0])

    assert(nx.is_tree(G))
    root= get_root(G,next(iter(G.nodes().keys())))
    date = datetime.now().strftime('%y%m%d')
    directory = date+'_'+args.out
    if not os.path.exists(directory):
        os.makedirs(directory)

    if args.user == None:
        GG=G.copy()
        set_cummulative_weight_all(GG, root, 'Size')
        set_cummulative_weight_all(GG, root, 'Files')
        df = pd.DataFrame(to_write(GG, root, args.minfiles, args.minsize, args.user))
        df['Files_h'] = df['Files'].apply(files_to_readable)
        df['Size_h'] = df['Size'].apply(bytes_to_readable)
        df = df["Files Size Files_h Size_h Path".split(' ')]
        df.sort_values('Files', inplace=True, ascending=False)
        df.to_csv(directory +'_all_users_by_files.csv', index=False, sep='\t')
        df.sort_values('Size', inplace=True, ascending=False)
        df.to_csv(directory +'_all_users_by_size.csv', index=False, sep='\t')

    if args.user != None:
        users = [args.user]
    for user in users:
        try:
            username = subprocess.check_output(f"id -un {user}", shell=True).decode()[:-1]
        except Exception:
            username = user
        print(f'Calculating the disk usage of {username}')
        GG = G.copy()
        set_cummulative_weight_by_user(GG, root, 'Size', user)
        set_cummulative_weight_by_user(GG, root, 'Files', user)
        df = pd.DataFrame(to_write(GG, root, args.minfiles, args.minsize, user))
        if df.shape[0] > 0:
            df['Files_h'] = df['Files'].apply(files_to_readable)
            df['Size_h'] = df['Size'].apply(bytes_to_readable)
            df = df["Files Size Files_h Size_h Path".split(' ')]
            df.sort_values('Files', inplace=True, ascending=False)
            df.to_csv(directory+'/'+directory+'_'+username+'_by_files.csv', index=False, sep='\t')
            df.sort_values('Size', inplace=True, ascending=False)
            df.to_csv(directory+'/'+directory+'_'+username+'_by_size.csv', index=False, sep='\t')
        else:
            print(f'user {username} doesn\'t have a significant amount or size of files.')
    print('done')

