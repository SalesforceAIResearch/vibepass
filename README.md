# VIBEPASS: Can Vibe Coders Really Pass the Vibe Check?

Benchmark for evaluating LLMs on corner case generation, code judgment, and debugging. This dataset was generated using GPT, Gemini, and Claude and should not be used to develop competing models.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your API keys

# Run evaluation
python src/eval.py \
  --input data/benchmark.jsonl \
  --output outputs/results.jsonl \
  --model sonnet4.5 \
  --task corner_case \
  --mode wo_checker_direct
```

## Models

- **OpenAI**: `gpt-5-*` (add `_low`, `_medium`, `_high`, `_minimal` for effort)
- **Anthropic**: `opus4.6`, `sonnet4.6`, `opus4.5`, `sonnet4.5`, `haiku4.5` (add `_thinking`)
- **Gemini**: `gemini-2.0-flash-exp`, `gemini-1.5-pro`
- **Together AI**: Various open-source models

## Tasks

**Corner Case**: `wo_checker_direct`, `with_checker_direct`, `with_checker_cot`  
**Judge**: `judge_buggy`, `judge_correct_model`, `judge_correct_human`  
**Debug**: `debug_given_test_oracle`, `debug_given_test_generated`, `debug_no_test`, `debug_no_test_react`

## Arguments

```bash
--input FILE           # Input JSONL
--output FILE          # Output JSONL
--model MODEL          # Model name
--task TASK            # corner_case, judge, debug
--mode MODE            # Task mode
--lcb_data PATH        # LCB data (default: curation/data/lcb/test*.jsonl)
--timeout SECONDS      # Default: 60
--num_process_generate # Default: 16
--num_process_evaluate # Default: 4
```

## Environment Variables

```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=...              # Optional
X_API_KEY=...                    # Optional gateway key
TOGETHER_API_KEY=...
GOOGLE_CLOUD_PROJECT=...
GOOGLE_CLOUD_LOCATION=global
SANDBOX_HOST=localhost
SANDBOX_PORT=8080
```

## Input Format

```json
{
  "coca_id": "id",
  "question_id": "platform_id",
  "question_content": "Problem...",
  "platform": "leetcode",
  "buggy_model_solution": "def solution(): ...",
  "test_checker": "def is_valid_test(): ...",
  "starter_code": "class Solution: ..."
}
```

## Sandbox

Expects POST to `http://localhost:8080/run_code`:

```json
{"code": "print('hello')", "language": "python", "run_timeout": 10}
```

Returns:
```json
{"status": "Success", "run_result": {"status": "Finished", "stdout": "hello\n"}}
```

## Structure

```
.
├── .env.example         # Configuration template
├── .gitignore          # Git ignore patterns
├── LICENSE             # MIT License
├── README.md           # This file
├── requirements.txt    # Dependencies
└── src/
    ├── eval.py         # Main evaluation script
    ├── llm_generator.py # LLM providers
    ├── utils.py        # Utilities
    └── prompts/        # Prompt templates
        ├── corner_case.py
        ├── judge.py
        ├── debug.py
        └── codegen.py
```

## Citation

```bibtex
@article{vibepass2025,
  title={VIBEPASS: Can Vibe Coders Really Pass the Vibe Check?},
  year={2025}
}
```
