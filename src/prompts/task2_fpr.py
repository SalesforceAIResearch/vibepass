"""
Code debugging prompts for VIBEPASS.
"""

PROMPT_FPR_GIVEN_TEST = """
You are an expert software engineer specializing in debugging.

You are provided with:
- **Problem Description** – Defines the expected behavior of a function, including input variables and constraints.
- **Buggy Solution** – A Python function that may contain one or more bugs.
- **Test Case** – {test_case_description}

Your task:
1. Identify all bug(s) in the implementation.
2. {test_case_instruction}
3. Reason step by step before producing a fix.
4. Produce a corrected implementation that is functionally correct for all valid inputs — not just the test case.
5. Preserve the original code structure and style — only change what is necessary to fix the bug(s).
6. If you believe the implementation is already correct, state that in your reasoning and return it unchanged.

You must respond using exactly this format, with no text outside the XML tags:
<reasoning>
YOUR STEP-BY-STEP REASONING HERE
</reasoning>
<solution>
YOUR CORRECTED IMPLEMENTATION HERE
</solution>

Here are two examples:

<example_1>
<problem>
Given a list of integers, return the maximum difference between adjacent elements.
Return 0 if the list has fewer than 2 elements.
</problem>

<buggy_solution>
def max_diff(nums):
    max_d = 0
    for i in range(len(nums)):
        max_d = max(max_d, nums[i] - nums[i-1])
    return max_d
</buggy_solution>

<test_case>
    <input>nums = [1, 2, 3]</input>
    <expected_output>1</expected_output>
</test_case>

<reasoning>
The loop uses range(len(nums)), so at i=0 it computes nums[0] - nums[-1], wrapping around
to the last element. This is incorrect — only adjacent forward pairs should be compared.
Fixing this by starting the loop at index 1 eliminates the wrap-around.
Verification: [1, 2, 3] → diffs are (2-1)=1, (3-2)=1 → max is 1. Correct.
</reasoning>
<solution>
def max_diff(nums):
    max_d = 0
    for i in range(1, len(nums)):
        max_d = max(max_d, nums[i] - nums[i-1])
    return max_d
</solution>
</example_1>

<example_2>
<problem>
Given a list of integers, return True if any value appears at least twice, False otherwise.
</problem>

<buggy_solution>
def contains_duplicate(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return True
</buggy_solution>

<test_case>
    <input>nums = [1, 2, 3]</input>
    <expected_output>False</expected_output>
</test_case>

<reasoning>
The function correctly tracks seen elements and returns True early when a duplicate is found.
However, the final return unconditionally returns True instead of False,
meaning any list with no duplicates still returns True.
Fix: change the final return to False.
Verification: [1, 2, 3] → no duplicates found → reaches final return → returns False. Correct.
</reasoning>
<solution>
def contains_duplicate(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False
</solution>
</example_2>

Now debug the following. Remember to reason step by step and use exactly the format above:

<problem>
{problem}
</problem>

<buggy_solution>
{solution}
</buggy_solution>

<test_case>
    <input>{failing_test_input}</input>
    <expected_output>{failing_test_expected}</expected_output>
</test_case>
"""

PROMPT_FPR_SELF_TEST = """
You are an expert software engineer specializing in debugging. You find inputs where the specification and implementation disagree, then fix the implementation. Your failure mode is anchoring to the implementation — you actively resist this by always reading the spec first.

You are provided with:
- **Problem Description** – Defines the expected behavior of a function, including input variables and constraints.
- **Buggy Solution** – A Python function that may contain one or more bugs.

Guaranteed: the buggy solution always produces wrong answers (no crashes).
Guaranteed: every input has exactly one correct output.

Your task has two phases:

================================================================
PHASE 1 — GENERATE ONE FAILING TEST CASE
================================================================
Produce ONE minimal failing test case that exposes the bug.

CORE INVARIANTS:
1. Expected output must come from the spec — NEVER from the buggy code.
2. If spec and buggy code agree on your input, that input is useless — pick another.
3. Use the smallest input that discriminates — complexity beyond that is noise.
4. Prefer boundary values, minimum-size inputs, and edge cases first. If boundary inputs do not expose the bug, increase input size by the smallest possible increment and recheck.

BUG PATTERN PRIMER (use for analogical recall):
- Wrong condition (>= vs >)      → boundary value where element equals threshold
- Wrong initialisation            → minimum boundary input
- Missing base case               → minimum boundary input
- Off-by-one in index/range       → first or last element
- Accumulator not flushed         → longest run ending at last element
- Missing edge case               → empty, single-element, or zero input
- Incorrect greedy assumption     → carefully constructed counterexample

Use the scratchpad to reason before emitting the test case:

<scratchpad>
Analogical recall: [one sentence — similar bug pattern and how it was exposed]
Spec quote: [exact sentence from problem description governing your input]
Spec examples: [at least one typical and one boundary example derived from spec quote only]
Hypotheses:
  H1 / H2 / H3: [three plausible structural flaws]
  Selected: [chosen + one-sentence justification]
Escalation: [start simplest, check disagreement, stop at first discriminating input]
Falsification: [one non-discriminating input — confirms hypothesis]
Interface: [Function Call — arg types / STDIN — format description]
Chosen: [literal input value]
Correct output: [value + one-line derivation from spec quote]
Trace: [step-by-step: var=val → condition → outcome. ≤5 steps.]
Disagreement:
  Spec→[X] | Buggy→[Y] | X != Y ✓ (If X == Y — discard this input, restart scratchpad.)
Confidence: [High / Medium / Low]
</scratchpad>

If no discriminating input is found after exhausting 3 hypotheses, write "No discriminating input found" and stop — do not hallucinate a disagreement.

================================================================
PHASE 2 — DEBUG USING THE FAILING TEST CASE
================================================================
1. Use the failing test case as ground truth to guide your diagnosis.
2. Identify all bug(s) — the test case exposes at least one, but there may be more.
3. Reason step by step before producing a fix.
4. Produce a corrected implementation that is functionally correct for all valid inputs — not just the failing test case.
5. Preserve the original code structure and style — only change what is necessary to fix the bug(s).

================================================================
OUTPUT FORMAT
================================================================
You must respond using exactly this format, with no text outside the tags except the scratchpad:

<scratchpad>
YOUR TEST GENERATION REASONING HERE
</scratchpad>

<input>
FAILING TEST CASE INPUT HERE
</input>
<output>
FAILING TEST CASE EXPECTED OUTPUT HERE
</output>
<actual_output>
ACTUAL OUTPUT OF BUGGY SOLUTION ON FAILING TEST CASE
</actual_output>
<reasoning>
YOUR STEP-BY-STEP DEBUG REASONING HERE
</reasoning>
<solution>
YOUR CORRECTED IMPLEMENTATION HERE
</solution>

INPUT FORMAT RULES:
- Function-based: one argument per line, valid Python literals only. Strings in double quotes.
- STDIN-based: raw stdin exactly as read.
- Fewer than 20 elements unless size-dependence is justified in scratchpad.

Format checks (retry up to 2 times; emit <warning> tag if still failing):
  ✓ Types, format, and tag contracts satisfied.
  ✓ Nothing appears after </solution>.

================================================================
CORRECT REASONING EXAMPLE — FOLLOW THIS
================================================================

<problem>
Given a list of integers, return the index of the first element greater than the given threshold.
Return -1 if none exists.
Constraints: list length 1–100, integers 0–1000, threshold 0–1000.
</problem>

<buggy_solution>
def first_above(nums, threshold):
    for i, x in enumerate(nums):
        if x >= threshold:
            return i
    return -1
</buggy_solution>

<scratchpad>
Analogical recall: "wrong condition >= instead of >" — boundary value where element equals threshold always discriminates.

Spec quote: "return the index of the first element GREATER THAN the given threshold" — strictly greater, equal does not qualify.

Spec examples: first_above([5], 5)→-1 (boundary)   first_above([3,5,7], 5)→2 (typical, first strictly greater is index 2)

Hypotheses:
  H1: >= instead of > (equal values incorrectly match) ← smallest discriminating input
  H2: returns last match instead of first
  H3: off-by-one in index
  Selected: H1 — boundary input [5], threshold=5 immediately discriminates.

Escalation: [5], threshold=5 → Spec→-1. Buggy: 5>=5→returns 0. DISAGREE ✓ Stop.

Falsification: [6], threshold=5 → both return 0. Non-discriminating. Confirms H1.

Interface: Function Call — args: list[int], int.

Chosen: [5], threshold=5
Correct output: -1  (5 is not strictly greater than 5)
Trace: i=0, x=5, threshold=5 → 5>=5 is True → return 0 ← wrong
Disagreement:
  Spec→-1 | Buggy→0 | -1 != 0 ✓
Confidence: High
</scratchpad>

<input>
[5]
5
</input>
<output>
-1
</output>
<actual_output>
0
</actual_output>
<reasoning>
The failing test confirms the function returns 0 for input [5] with threshold=5, but the correct answer is -1.
The condition uses >= instead of >, so elements equal to the threshold are incorrectly matched.
The spec requires strictly greater than — the fix is to replace >= with >.
This is a general bug affecting all inputs where an element equals the threshold, not just this test case.
Verification: first_above([5], 5) → 5 > 5 is False → loop ends → return -1. Correct.
</reasoning>
<solution>
def first_above(nums, threshold):
    for i, x in enumerate(nums):
        if x > threshold:
            return i
    return -1
</solution>

================================================================
INCORRECT REASONING EXAMPLE — DO NOT FOLLOW
================================================================

<problem>
(same as correct example above)
</problem>

<buggy_solution>
(same as correct example above)
</buggy_solution>

<scratchpad — WRONG — DO NOT FOLLOW>
Looking at the code, it uses >= so for [3, 5, 7], threshold=5
it returns index 1. Expected output: 1.
</scratchpad — WRONG>

WHY WRONG:
- No spec quote — reasoning is unanchored from the specification.
- Expected output derived FROM the buggy code, not the spec. The spec says STRICTLY GREATER THAN — value 5 equals the threshold, so the correct answer is index 2 (value 7), not index 1.
- Skipped hypotheses, escalation, falsification, and disagreement check.
- This test case PASSES the buggy solution — it is completely useless.

================================================================
Now solve the following. Remember: read the spec first, generate the minimal discriminating test case, then debug step by step.
================================================================

<problem>
{problem}
</problem>

<buggy_solution>
{solution}
</buggy_solution>
"""

PROMPT_FPR_NO_TEST = """
You are an expert software engineer specializing in debugging.

You are provided with:
- **Problem Description** – Defines the expected behavior of a function, including input variables and constraints.
- **Buggy Solution** – A Python function that may contain one or more bugs.

Your task:
1. Identify all bug(s) in the implementation.
2. Reason step by step before producing a fix.
3. Produce a corrected implementation that is functionally correct for all valid inputs.
4. Preserve the original code structure and style — only change what is necessary to fix the bug(s).
5. If you believe the implementation is already correct, state that in your reasoning and return it unchanged.

You must respond using exactly this format, with no text outside the XML tags:
<reasoning>
YOUR STEP-BY-STEP REASONING HERE
</reasoning>
<solution>
YOUR CORRECTED IMPLEMENTATION HERE
</solution>

Here are two examples:

<example_1>
<problem>
Given a list of integers, return the maximum difference between adjacent elements.
Return 0 if the list has fewer than 2 elements.
</problem>

<buggy_solution>
def max_diff(nums):
    max_d = 0
    for i in range(len(nums)):
        max_d = max(max_d, nums[i] - nums[i-1])
    return max_d
</buggy_solution>

<reasoning>
The loop iterates range(len(nums)), so at i=0 it computes nums[0] - nums[-1], wrapping around
to the last element. This is incorrect — only adjacent forward pairs should be compared.
Fixing this by starting the loop at index 1 eliminates the wrap-around.
Verification: [1, 2, 3] → diffs are (2-1)=1, (3-2)=1 → max is 1. Correct.
</reasoning>
<solution>
def max_diff(nums):
    max_d = 0
    for i in range(1, len(nums)):
        max_d = max(max_d, nums[i] - nums[i-1])
    return max_d
</solution>
</example_1>

<example_2>
<problem>
Given a list of integers, return True if any value appears at least twice, False otherwise.
</problem>

<buggy_solution>
def contains_duplicate(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return True
</buggy_solution>

<reasoning>
The function correctly tracks seen elements and returns True early when a duplicate is found.
However, the final return statement unconditionally returns True instead of False,
meaning any list with no duplicates still returns True.
Fix: change the final return to False.
Verification: [1, 2, 3] → no duplicates found → reaches final return → returns False. Correct.
</reasoning>
<solution>
def contains_duplicate(nums):
    seen = set()
    for num in nums:
        if num in seen:
            return True
        seen.add(num)
    return False
</solution>
</example_2>

Now debug the following. Remember to reason step by step and use exactly the format above:

<problem>
{problem}
</problem>

<buggy_solution>
{solution}
</buggy_solution>
"""