import json
import argparse
from dataclasses import dataclass, field
import logging
import os
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from lcb_runner.benchmarks import CodeGenerationProblem
from lcb_runner.evaluation import extract_instance_results
from lcb_runner.runner.scenario_router import get_metrics
from lcb_runner.utils.scenarios import Scenario
import random
from utils import make_code_request, read_jsonl, get_lcb_data, read_json
from llm_generator import get_generator
from prompts import (
    PROMPT_CORNER_CASE_WO_CHECKER_PYTHON_DIRECT,
    PROMPT_CORNER_CASE_WITH_CHECKER_PYTHON_DIRECT,
    PROMPT_CORNER_CASE_WITH_CHECKER_PYTHON_COT,
    PROMPT_JUDGE_PYTHON,
    PROMPT_DEBUG_GENERATED_TEST_PYTHON,
    PROMPT_DEBUG_GIVEN_TEST_PYTHON,
    PROMPT_DEBUG_NO_TEST_PYTHON,
    PROMPT_DEBUG_NO_TEST_PYTHON_STATELESS,
    PROMPT_DEBUG_GIVEN_TEST_RATIONALE_PYTHON
)

random.seed(42)
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class VIBEPASSInstance:
    """Instance of a VIBEPASS problem."""
    question_id: str
    question_title: str
    question_content: str
    platform: str
    contest_id: str
    contest_date: str
    starter_code: str
    difficulty: str
    coca_id: str = None
    function_name: str = None
    correct_human_solution: str = None
    correct_model_solution: str = None
    buggy_model_solution: str = None
    bug_type: str = None
    test_checker: str = None
    buggy_model: str = None
    metadata: dict = None
    coca_id: str = None
    response: dict = field(default_factory=dict)


class CoCaEvaluator:
    
    def __init__(self, args):
        self.args = args
        self.args.validate = self.args.output.replace('.jsonl', '.validate.jsonl')
        self.args.eval = self.args.output.replace('.jsonl', '.eval.jsonl')
        self.generator = get_generator(args.model)
        self.lcb_data = None

    def load_records(self, load_file, cache_file):        
        benchmark = read_jsonl(load_file)
        benchmark = [VIBEPASSInstance(**item) for item in benchmark]
        if cache_file and os.path.exists(cache_file):
            cached = read_jsonl(cache_file)
            done_ids = {item['coca_id'] for item in cached}
            benchmark = [item for item in benchmark if item.coca_id not in done_ids]
            print(f"Skipping {len(done_ids)} records")
        print(f"Loading {len(benchmark)} records")
        return benchmark

    def generate_response(self, item):
        try:
            if self.args.task == 'corner_case':
                if self.args.mode == 'wo_checker_direct':
                    prompt = PROMPT_CORNER_CASE_WO_CHECKER_PYTHON_DIRECT.format(
                    problem=item.question_content,
                    solution=item.buggy_model_solution)
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'with_checker_direct':
                    prompt = PROMPT_CORNER_CASE_WITH_CHECKER_PYTHON_DIRECT.format(
                    problem=item.question_content,
                    solution=item.buggy_model_solution,
                    test_validator=item.test_checker)
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'with_checker_cot':
                    prompt = PROMPT_CORNER_CASE_WITH_CHECKER_PYTHON_COT.format(
                    problem=item.question_content,
                    solution=item.buggy_model_solution,
                    test_validator=item.test_checker)
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                else:
                    raise ValueError(f"Invalid mode: {self.args.mode}")
            elif self.args.task == 'judge':
                if self.args.mode == 'judge_buggy':
                    prompt = PROMPT_JUDGE_PYTHON.format(
                        problem=item.question_content,
                        solution=item.buggy_model_solution)
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output   
                elif self.args.mode == 'judge_correct_model':
                    assert item.correct_model_solution is not None
                    prompt = PROMPT_JUDGE_PYTHON.format(
                        problem=item.question_content,
                        solution=item.correct_model_solution
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'judge_correct_human':
                    assert item.correct_human_solution is not None
                    prompt = PROMPT_JUDGE_PYTHON.format(
                        problem=item.question_content,
                        solution=item.correct_human_solution
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                else:
                    raise ValueError(f"Invalid mode: {self.args.mode}")
            elif self.args.task == 'debug':
                if self.args.mode == 'debug_given_test_oracle':
                    # Load oracle test cases from data directory if available
                    oracle_file = self.args.oracle_data if hasattr(self.args, 'oracle_data') else 'data/oracle_tests.json'
                    if os.path.exists(oracle_file):
                        temp_item = [v for k, v in read_json(oracle_file).items() if item.coca_id == k]
                        if len(temp_item) > 0:
                            temp_item = temp_item[0]
                        else:
                            temp_item = {'input': 'N/A', 'output': 'N/A'}
                    else:
                        temp_item = {'input': 'N/A', 'output': 'N/A'}
                    prompt = PROMPT_DEBUG_GIVEN_TEST_PYTHON.format(
                        test_case_description="A validated test case that is confirmed to expose a bug in the solution.",
                        test_case_instruction="Use the failing test case as ground truth to guide your diagnosis.",
                        problem=item.question_content,
                        solution=item.buggy_model_solution,                                
                        failing_test_input=temp_item['input'],
                        failing_test_expected=temp_item['output']
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_given_test_trivial':
                    # Load trivial test cases from data directory if available
                    trivial_file = self.args.trivial_data if hasattr(self.args, 'trivial_data') else 'data/trivial_tests.json'
                    if os.path.exists(trivial_file):
                        temp_item = [v for k, v in read_json(trivial_file).items() if item.coca_id == k]
                        if len(temp_item) > 0:
                            temp_item = temp_item[0]
                        else:
                            temp_item = {'input': 'N/A', 'output': 'N/A'}
                    else:
                        temp_item = {'input': 'N/A', 'output': 'N/A'}
                    prompt = PROMPT_DEBUG_GIVEN_TEST_PYTHON.format(
                        test_case_description="A validated test case that is confirmed to expose a bug in the solution.",
                        test_case_instruction="Use the failing test case as ground truth to guide your diagnosis.",
                        problem=item.question_content,
                        solution=item.buggy_model_solution,                                
                        failing_test_input=temp_item['input'],
                        failing_test_expected=temp_item['output']
                    )   
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_given_test_previous': 
                    temp_item = [temp_item for temp_item in read_jsonl(f'outputs/task1_lcb_{self.args.model}.jsonl') if temp_item['coca_id'] == item.coca_id][0]['response']['json_response']
                    prompt = PROMPT_DEBUG_GIVEN_TEST_PYTHON.format(
                        test_case_description="A test case generated by an AI model as a best-effort attempt to expose a bug. It may be imprecise or incorrect — treat it as a weak signal to guide reasoning, not as ground truth.",
                        test_case_instruction="Use the test case as a weak reference signal — do not overfit to it. The bug may be broader or different than what it implies.",
                        problem=item.question_content,
                        solution=item.buggy_model_solution,                                
                        failing_test_input=temp_item['input'],
                        failing_test_expected=temp_item['output']
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_given_test_rationale':
                    temp_item = [temp_item for temp_item in read_jsonl(f'outputs/task1_lcb_{self.args.model}.jsonl') if temp_item['coca_id'] == item.coca_id][0]['response']['json_response']
                    prompt = PROMPT_DEBUG_GIVEN_TEST_RATIONALE_PYTHON.format(
                        test_case_description="A fault-triggering test case input along with rationale behind it by an AI model as a best-effort attempt to expose a bug. It may be imprecise or incorrect — treat it as a weak signal to guide reasoning, not as ground truth.",
                        test_case_instruction="Use the test case input and rationale as a weak reference signal — do not overfit to it. The bug may be broader or different than what it implies.",
                        problem=item.question_content,
                        solution=item.buggy_model_solution,                                
                        test_case_input=temp_item['temp_item'],
                        test_case_rationale=temp_item['reasoning']
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_given_test_generated':
                    prompt = PROMPT_DEBUG_GENERATED_TEST_PYTHON.format(
                        problem=item.question_content,
                        solution=item.buggy_model_solution
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_no_test':
                    prompt = PROMPT_DEBUG_NO_TEST_PYTHON.format(
                        problem=item.question_content,
                        solution=item.buggy_model_solution
                    )
                    output = self.generator.generate(prompt)
                    item.response['raw_response'] = output
                elif self.args.mode == 'debug_no_test_react':
                    if self.lcb_data is None:
                        self.lcb_data = get_lcb_data(input_file=self.args.lcb_data)

                    buggy_solution = item.buggy_model_solution                    
                    lcb_sample = self.lcb_data.get(item.question_id)    
                    lcb_sample['private_test_cases'] = '[]' 
                    public_test_cases = json.loads(lcb_sample['public_test_cases'])  
                    history = [] # List of previous responses

                    for trial_idx in range(5):
                        grades = []
                        feedbacks = []
                        for test_case in public_test_cases:
                            lcb_sample['public_test_cases'] = json.dumps([test_case])
                            lcb_instances, combined_results = [], []
                            lcb_instances.append(CodeGenerationProblem(**lcb_sample)) # Gold Solution
                            combined_results.append(([buggy_solution], [buggy_solution]))
                            metrics = get_metrics(Scenario.codegeneration, None, lcb_instances, combined_results)
                            graded = extract_instance_results(metrics[1])
                            grades.append(graded[0][0])
                            feedbacks.append(metrics[2])
                        if all(grades) and trial_idx > 0:
                            break
                        else:
                            exec_feedback = ''                                            
                            for test_case, feedback in zip(public_test_cases, feedbacks):
                                feedback = json.loads(feedback[0][0])
                                if 'error_code' not in feedback:
                                    exec_feedback += f"Test Case (Input): {test_case['input'].strip()}\n"
                                    exec_feedback += f"Test Case (Expected Output): {test_case['output'].strip()}\n"
                                    exec_feedback += f"Feedback: Passed\n\n\n\n"
                                else:
                                    exec_feedback += f"Test Case (Input): {test_case['input'].strip()}\n"
                                    exec_feedback += f"Test Case (Expected Output): {test_case['output'].strip()}\n"
                                    exec_feedback += f"Feedback (Error Code): {feedback['error_code']}\n"
                                    exec_feedback += f"Feedback (Error Message): {feedback['error_message'].strip()}\n"
                                    if "output" in feedback:
                                        exec_feedback += f"Test Case (Actual Output): {feedback['output'].strip()}\n"
                                
                            prompt = PROMPT_DEBUG_NO_TEST_PYTHON_STATELESS.format(
                                problem=item.question_content,
                                solution=buggy_solution,
                                execution_feedback=exec_feedback
                            )
                            output = self.generator.generate(prompt)
                            history.append((prompt, output))                            
                            assert '```python' in output and '```' in output
                            solution = output.split('```python')[1].split('```')[0].strip()
                    item.response['raw_response'] = history[-1][1]
                    item.response['history'] = history
                else:
                    raise ValueError(f"Invalid mode: {self.args.mode}")                        
        except Exception as e:
            item.response['raw_response'] = None
            item.response['raw_response_error'] = {"error_message" : str(e)}

        output = item.response['raw_response']
        item.response['json_response'] = {}
        
        if output:
            try:
                if '<verdict>' in output:
                    item.response['json_response']["verdict"] = output.split('<verdict>')[1].split('</verdict>')[0].strip()
                if '<input>' in output:
                    item.response['json_response']["input"] = output.split('<input>')[1].split('</input>')[0].strip()
                    item.response['json_response']["output"] = output.split('<output>')[1].split('</output>')[0].strip()
                if '<reasoning>' in output:
                    item.response['json_response']["reasoning"] = output.split('<reasoning>')[1].split('</reasoning>')[0].strip()
                if '<solution>' in output:
                    item.response['json_response']["solution"] = output.split('<solution>')[1].split('</solution>')[0].strip()
            except Exception as e:
                item.response['json_response_error'] = {"error_type" : "ParsingError", "error_message" : str(e)}
        else:
            item.response['json_response_error'] = {"error_type" : "ParsingError", "error_message" : "Raw response is None"}
        return item

    def get_import_prefix(self):
        imports_all = ["typing", "collections", "functools", "itertools", "hashlib", "bisect", "datetime", "math"]
        imports_pkg = ["heapq", "math", "sys", "re", "os", "random", "string", "time", "json"]
        imports_str = "\n".join([f"from {import_} import *" for import_ in imports_all])
        imports_str += "\n" + "\n".join([f"import {import_}" for import_ in imports_pkg])
        imports_str += "\n" + "sys.setrecursionlimit(550000)\n\n"
        return imports_str

    def validate_test(self, item):
        if (item.response['json_response'].get('input') is None) or (item.response['json_response'].get('output') is None):
            item.response['is_valid_test'] = False
            item.response['is_valid_test_error'] = {"error_type" : "InputError", "error_message" : "Input is None"}
            return item

        import_prefix = self.get_import_prefix()
        test_valid_code = import_prefix + item.test_checker
        if item.platform == 'leetcode':
            test_valid_code +=f'\nprint (is_valid_test({item.response["json_response"]["input"].replace("\n", ",")}))'
        elif item.platform == 'atcoder':
            test_valid_code += f'\nprint(is_valid_test("""{item.response["json_response"]["input"]}"""))'
        else:
            raise ValueError(f"Invalid platform: {item.platform}")

        try:
            valid_result = make_code_request(test_valid_code, timeout=10)
            if valid_result['status'] == 'Success' and valid_result['run_result']['status']=='Finished':
                item.response['is_valid_test'] = valid_result['run_result']['stdout'].strip() == 'True'
            else:
                raise ValueError(f"Invalid inputs: {valid_result['run_result']['stderr']}") 
        except Exception as e:
            item.response['is_valid_test'] = False
            item.response['is_valid_test_error'] = {'error_type' : "RuntimeError", "error_message" : str(e)}
        return item

    def multiprocess_call(self, func, items, dump_file, num_process):
        with open(dump_file, 'a') as f:
            # for item in tqdm(items):
            #     item = func(item)
            #     f.write(json.dumps(item.__dict__) + '\n')
            
            with ThreadPoolExecutor(max_workers=num_process) as executor:
                future_to_item = {executor.submit(func, item): item for item in items}
                for future in tqdm(as_completed(future_to_item), total=len(items)):
                    result_item = future.result()
                    f.write(json.dumps(result_item.__dict__) + '\n')

    def _evaluate(self, items):
        assert not os.path.exists(self.args.eval)
        print(f"Evaluating {len(items)} records")
        LCB_DATA = get_lcb_data(input_file=self.args.lcb_data)
        lcb_instances, combined_results = [], []
        for item in items:
            if self.args.task == 'judge':
                assert self.args.mode in ['judge_buggy', 'judge_correct_model', 'judge_correct_human']                
                if item.response['json_response'].get('verdict') is None:
                    item.response['is_correct_verdict'] = False
                elif item.response['json_response'].get('verdict') == "program is correct":
                    item.response['is_correct_verdict'] = False if self.args.mode == 'judge_buggy' else True
                elif item.response['json_response'].get('verdict') == "program is buggy":
                    item.response['is_correct_verdict'] = True if self.args.mode == 'judge_buggy' else False
                else:
                    item.response['is_correct_verdict'] = False
                    item.response['is_correct_verdict_error'] = {"error_type" : "ParsingError", "error_message" : f"Invalid verdict {item.response['raw_response']}"}
                            
            lcb_sample = LCB_DATA.get(item.question_id)
            private_test_cases_str = lcb_sample.get('private_test_cases')
            
            if self.args.task in ['corner_case', 'judge'] or (self.args.task == 'debug' and self.args.mode in ['debug_given_test_generated']):
                lcb_sample['private_test_cases'] = '[]'
                if item.response.get('json_response') and item.response['json_response'].get('input') and item.response['json_response'].get('output'):                
                    lcb_sample['public_test_cases'] = json.dumps([{'input': item.response['json_response'].get('input'),
                    'output': item.response['json_response'].get('output'),
                    'testtype': 'functional' if item.platform == 'leetcode' else 'stdin'}])
                else:
                    lcb_sample['public_test_cases'] = '[]'
                lcb_instances.append(CodeGenerationProblem(**lcb_sample)) # Gold Solution
                lcb_instances.append(CodeGenerationProblem(**lcb_sample)) # Buggy Solution
                if item.correct_human_solution:
                    combined_results.append(([item.correct_human_solution], [item.correct_human_solution]))
                else:
                    combined_results.append(([item.correct_model_solution], [item.correct_model_solution]))
                try:
                    combined_results.append(([item.buggy_model_solution], [item.buggy_model_solution]))
                except Exception as e:
                    import pdb; pdb.set_trace()
                    
            if self.args.task == 'debug':
                lcb_sample['private_test_cases'] = private_test_cases_str
                lcb_instances.append(CodeGenerationProblem(**lcb_sample)) # Debug Solution
                try:
                    raw_response = item.response['json_response'].get('solution')
                except Exception as e:
                    raw_response = ''
                    assert 'json_response_error' in item.response, item.response
                if raw_response:
                    try:                    
                        if '```python' in raw_response and '```' in raw_response:
                            solution = raw_response.split('```python')[1].split('```')[0].strip()
                        else:
                            solution = raw_response
                    except Exception as e:
                        solution = ''
                        item.response['solution_parse_error'] = {"error_type" : "ParsingError", "error_message" : str(e)}                
                else:
                    solution = ''
                    item.response['solution_parse_error'] = {"error_type" : "ParsingError", "error_message" : "Solution is None"}                

                combined_results.append(([raw_response], [solution]))

        metrics = get_metrics(Scenario.codegeneration, self.args, lcb_instances, combined_results)
        graded = extract_instance_results(metrics[1])

        for i in range(len(items)):
            if self.args.task in ['corner_case', 'judge']:
                items[i].response['output_gold'] = json.loads(metrics[2][i*2][0])
                items[i].response['pass_gold'] = graded[i*2][0]

                items[i].response['output_buggy'] = json.loads(metrics[2][i*2+1][0])
                items[i].response['pass_buggy'] = graded[i*2+1][0]

                if items[i].response['pass_gold']:
                    items[i].response['pass_gold'] = items[i].response['pass_gold'] and items[i].response['output_gold']['execution time']>0
                if items[i].response['pass_buggy']:
                    items[i].response['pass_buggy'] = items[i].response['pass_buggy'] and items[i].response['output_buggy']['execution time']>0
                            
                items[i].response['is_cc_wild'] = (items[i].response['pass_buggy']==False) and items[i].response.get('is_valid_test', False)
                items[i].response['is_cc_io'] = (items[i].response['pass_gold']==True) and  (items[i].response['pass_buggy']==False) and items[i].response.get('is_valid_test', False)

                if not items[i].response['pass_buggy']: # Buggy Fails
                    actual_output = items[i].response['output_buggy'].get('output')
                    expected_output = items[i].response['output_buggy'].get('expected') if items[i].response['pass_gold'] else items[i].response['output_gold'].get('output')
                else: # Buggy Passes
                    actual_output = items[i].response['output_gold'].get('expected') if not items[i].response['pass_gold'] else None
                    expected_output = items[i].response['output_gold'].get('output') if not items[i].response['pass_gold'] else None
                items[i].response['is_cc_i'] = (actual_output != expected_output) and items[i].response.get('is_valid_test', False)
            elif self.args.task == 'debug':
                if self.args.mode == 'debug_given_test_generated':                    
                    items[i].response['output_gold'] = json.loads(metrics[2][i*3][0])
                    items[i].response['pass_gold'] = graded[i*3][0]

                    items[i].response['output_buggy'] = json.loads(metrics[2][i*3+1][0])
                    items[i].response['pass_buggy'] = graded[i*3+1][0]

                    items[i].response['output_debug'] = json.loads(metrics[2][i*3+2][0])
                    items[i].response['pass_debug'] = graded[i*3+2][0] and items[i].response['output_debug']['execution time']>0

                    if items[i].response['pass_gold']:
                        items[i].response['pass_gold'] = items[i].response['pass_gold'] and items[i].response['output_gold']['execution time']>0
                    if items[i].response['pass_buggy']:
                        items[i].response['pass_buggy'] = items[i].response['pass_buggy'] and items[i].response['output_buggy']['execution time']>0
                                
                    items[i].response['is_cc_wild'] = (items[i].response['pass_buggy']==False) and items[i].response.get('is_valid_test', False)
                    items[i].response['is_cc_io'] = (items[i].response['pass_gold']==True) and  (items[i].response['pass_buggy']==False) and items[i].response.get('is_valid_test', False)

                    if not items[i].response['pass_buggy']: # Buggy Fails
                        actual_output = items[i].response['output_buggy'].get('output')
                        expected_output = items[i].response['output_buggy'].get('expected') if items[i].response['pass_gold'] else items[i].response['output_gold'].get('output')
                    else: # Buggy Passes
                        actual_output = items[i].response['output_gold'].get('expected') if not items[i].response['pass_gold'] else None
                        expected_output = items[i].response['output_gold'].get('output') if not items[i].response['pass_gold'] else None
                    items[i].response['is_cc_i'] = (actual_output != expected_output) and items[i].response.get('is_valid_test', False)
                else:
                    items[i].response['output_debug'] = json.loads(metrics[2][i][0])
                    items[i].response['pass_debug'] = graded[i][0] and items[i].response['output_debug']['execution time']>0

        with open(self.args.eval, 'w') as f:
            for item in items:
                f.write(json.dumps(item.__dict__) + '\n')
        
    def evaluate(self):
        self.multiprocess_call(
            func=self.generate_response, 
            items=self.load_records(self.args.input, self.args.output), 
            dump_file=self.args.output,
            num_process=self.args.num_process_generate)
        if self.args.task in ['corner_case', 'judge'] or (self.args.task == 'debug' and self.args.mode == 'debug_given_test_generated'):
            self.multiprocess_call(
                func=self.validate_test, 
                items=self.load_records(self.args.output, self.args.validate), 
                dump_file=self.args.validate,
                num_process=self.args.num_process_evaluate)

        if not os.path.exists(self.args.eval):
            if self.args.task == 'debug' and self.args.mode != 'debug_given_test_generated':
                items=self.load_records(self.args.output, self.args.eval)
            else:
                items=self.load_records(self.args.validate, self.args.eval)
            self._evaluate(items)

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', type=str, required=True)
    parser.add_argument('--model', type=str, required=True)
    parser.add_argument('--output', type=str, required=True)
    parser.add_argument('--task', type=str, required=True, choices=['corner_case', 'judge', 'debug'])
    parser.add_argument('--mode', type=str, default='wo_checker_direct', choices=[
        # Corner Case
        'wo_checker_direct', 'with_checker_direct', 'with_checker_cot',
        # Judge
        'judge_buggy', 'judge_correct_model', 'judge_correct_human',
        # Debug
        'debug_given_test_oracle', 'debug_given_test_generated', 'debug_no_test','debug_no_test_react',  'debug_given_test_trivial', 'debug_given_test_previous', 'debug_given_test_rationale'])
    parser.add_argument('--lcb_data', type=str, default='curation/data/lcb/test*.jsonl')
    parser.add_argument('--timeout', type=int, default=60)
    parser.add_argument('--num_process_evaluate', type=int, default=4)
    parser.add_argument('--num_process_generate', type=int, default=16)
    return parser.parse_args()
    
def main():
    args = parse_args()
    assert args.input.endswith('.jsonl')
    assert args.output.endswith('.jsonl')

    print("Testing sandbox is working")
    test_run = make_code_request("print('Hello World')")
    assert test_run['status'] == 'Success'

    evaluator = CoCaEvaluator(args)  
    evaluator.evaluate()
    
if __name__ == '__main__':
    main()