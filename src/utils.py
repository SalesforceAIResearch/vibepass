import json
from glob import glob
from typing import Dict, List, Optional, Set, Tuple, Union
import requests
from glob import glob
from tqdm import tqdm
from dataclasses import dataclass, field

def execute_code(code, port=None, language='python', stdin=None, files=None, timeout=60):
    """Execute code in sandbox environment."""
    import os
    if port is None:
        port = int(os.environ.get('SANDBOX_PORT', '8080'))
    host = os.environ.get('SANDBOX_HOST', 'localhost')

    url = f'http://{host}:{port}/run_code'
    headers = {'Content-Type': 'application/json'}
    data = {
        'run_timeout': timeout,
        'code': code,
        'language': language
    }
    if stdin is not None:
        data['stdin'] = stdin
    if files is not None:
        data['files'] = files

    response = requests.post(url, headers=headers, json=data)
    if response.status_code != 200:
        raise Exception(f'Failed to execute code: {response.json().get("error", "Unknown error")}')
    return response.json()

def make_code_request(code, timeout=10, port=None):
    """Execute code in sandbox environment."""
    import os
    if port is None:
        port = int(os.environ.get('SANDBOX_PORT', '8080'))
    host = os.environ.get('SANDBOX_HOST', 'localhost')

    url = f'http://{host}:{port}/run_code'
    headers = {'Content-Type': 'application/json'}
    data = {
        'run_timeout': timeout,
        'code': code,
        'language': 'python'
    }

    response = requests.post(url, headers=headers, json=data)
    return response.json()   

def read_json(file):
    return json.load(open(file))

def read_jsonl_stream(path):
    with open(path, "r", encoding="utf-8") as f:
        for line in tqdm(f, desc='Reading JSONL file'):
            if line.strip():  # skip empty lines
                yield json.loads(line)

def read_jsonl(file):
    return [json.loads(line) for line in open(file)]

def read_text(file):
    return open(file).read()

def write_jsonl(file, data):
    with open(file, 'w') as f:
        for item in data:
            f.write(json.dumps(item) + '\n')

def write_json(file, data):
    json.dump(data, open(file, 'w'), indent=4, ensure_ascii=False)

def write_text(file, data):
    open(file, 'w').write(data)

def get_lcb_data(input_file):
    files = glob(input_file)
    all_data = []
    for fn in files:
        with open(fn, "r", encoding="utf-8") as f:
            for line in f:
                rec = json.loads(line)
                all_data.append(rec)

    all_data = {x.get('question_id'):x for x in all_data}
    return all_data

@dataclass
class VIBEPASSInstance:
    """Instance of a VIBEPASS problem."""
    question_id: str
    question_title: str
    question_content: str
    platform: str
    starter_code: str
    difficulty: str
    benchmark_id: str = None
    function_name: str = None
    correct_solution: dict = None
    buggy_solution: dict = None
    bug_type: str = None
    test_case: list[dict] = None
    response: dict = field(default_factory=dict)