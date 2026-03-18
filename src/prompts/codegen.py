"""
Code generation prompts for different competitive programming platforms.
"""

PROMPT_CODEGEN_LEETCODE = """You are an expert {lang} programmer. You will be given a problem specification, and your task is to generate a correct {lang} program that satisfies the specification and passes all tests.

## Instructions

* You are provided with a problem description that defines the expected behavior, including all input variables and constraints.
* Ensure the solution handles all edge cases correctly.
* Prefer efficient algorithms that respect the implied time and memory constraints.
* Output only the solution code within the specified delimiters.

## Problem Description

{problem_description}

## Starter Code

```python
{starter_code}
```

Make sure your solution could be called with the above function name and define it under `Class Solution`.

<solution>
```{lang}
WRITE THE CORRECT IMPLEMENTATION HERE
```
</solution>

Do not generate any reasoning or explanation. Only provide the final implementation in the format above."""

PROMPT_CODEGEN_ATCODER = """You are an expert {lang} programmer. You will be given a problem specification, and your task is to generate a correct {lang} program that satisfies the specification and passes all tests.

## Instructions

* You are provided with a problem description that defines the expected behavior, including all input variables and constraints.
* Ensure the solution handles all edge cases correctly.
* Prefer efficient algorithms that respect the implied time and memory constraints.
* Read input from stdin and write output to stdout.
* Output only the solution code within the specified delimiters.

## Problem Description

{problem_description}

## Answer Format

This solution should read from standard input and write to standard output, include `input()` in your code and properly process the inputs for running the solution.

<solution>
```{lang}
WRITE THE CORRECT IMPLEMENTATION HERE
```
</solution>

Do not generate any reasoning or explanation. Only provide the final implementation in the format above."""

PROMPT_CODEGEN_CODEFORCES = PROMPT_CODEGEN_ATCODER  # Same format as AtCoder
