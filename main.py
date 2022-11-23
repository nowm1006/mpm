import os
from pathlib import Path
from functools import lru_cache
from operator import itemgetter
import json
from pprint import pprint
import requests
import typer

LOCK_FILE_NAME = 'package-lock.json'
app = typer.Typer()

@lru_cache()
def read_json(lock_name:str)->dict:
    lock_file = Path(lock_name)
    with lock_file.open() as fp:
        lock_dict = json.load(fp)
    return lock_dict 

def get_package_name(lock_name:str):
    package_name = next(iter(read_json(lock_name)['packages']['']['dependencies']))
    return package_name
    
def get_dep_package_list(lock_name:str)->list:
    lock_dict = read_json(lock_name)
    package_list = list(lock_dict['dependencies'].keys())
    return package_list

def get_dep_url_list(lock_name:str)->list:
    lock_dict = read_json(lock_name)
    url_list = [v['resolved'] for k,v in lock_dict['dependencies'].items()]
    return url_list
    
def append_dep_recurse(dep_dict:dict, package:str, level_list:list = [], level:int = 1)->list:
    info = dep_dict[package]
    if 'requires' in info:
        for requires_package in info['requires']:
            append_dep_recurse(dep_dict, requires_package, level_list, level+1)
    level_list.append(dict(
        level=level,
        package=package,
        url=info['resolved']
    ))
    return level_list 
    
def dedup(level_list:list)->list:
    n = len(level_list)
    item_to_pop = []
    for i in range(n):
        for j in range(i+1,n):
            if level_list[i]['url'] == level_list[j]['url']:
                item_to_pop.append(j)
    for i in sorted(item_to_pop, reverse=True):
        level_list.pop(i)
    return level_list

def get_dep_level_list(lock_name:str)->list:
    package_name = get_package_name(lock_name)
    lock_dict = read_json(lock_name)
    dependencies = lock_dict['dependencies']
    level_list = append_dep_recurse(dependencies,package_name)
    level_list = sorted(level_list, key=itemgetter('level'), reverse=True)
    dedup(level_list)
    return level_list

def generate_dependencies_dict(lock_name:str)->dict:
    package_name = get_package_name(lock_name)
    dep_level_list = get_dep_level_list(lock_name)
    dep_dict = {}
    for dep in dep_level_list:
        package = dep['package']
        filename = os.path.basename(dep['url'])
        dep_dict[package] = 'file:' + package_name + '/' + filename
    return {'dependencies':dep_dict}

@app.command()
def download(lock_name:str = LOCK_FILE_NAME):
    package_name = get_package_name(lock_name)
    for url in get_dep_url_list(lock_name):
        filepath:Path = Path(package_name)/os.path.basename(url)
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_bytes(requests.get(url).content)

@app.command()
def update_package_json(lock_name:str = LOCK_FILE_NAME):
    pathname:Path = Path('package.json') 
    with pathname.open('r') as fp:
        package_json = json.load(fp)
    dep_dict = generate_dependencies_dict(lock_name)
    package_json = {**package_json, **dep_dict}
    with pathname.open('w') as fp:
        json.dump(package_json, fp, sort_keys=False, indent=2)


if __name__ == '__main__':
    app()