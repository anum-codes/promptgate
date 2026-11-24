from promptgate.assertions import Context, run_assertion


def check(output, **spec):
    return run_assertion(output, spec, Context(latency_ms=120))[0]


def test_text_assertions():
    assert check("Hello World", type="contains", value="World")
    assert not check("Hello World", type="contains", value="world")
    assert check("Hello World", type="icontains", value="world")
    assert check("fine", type="not_contains", value="As an AI")
    assert check("  yes \n", type="equals", value="yes")
    assert check("Answer: 42", type="regex", value=r"\d+")
    assert check("ANSWER", type="regex", value="answer", ignore_case=True)
    assert check("abc", type="starts_with", value="ab")


def test_length_and_latency():
    assert check("abc", type="max_chars", value=3)
    assert not check("abcd", type="max_chars", value=3)
    assert check("abc", type="min_chars", value=3)
    assert check("x", type="max_latency_ms", value=200)
    assert not check("x", type="max_latency_ms", value=100)


def test_json_assertions_handle_fences():
    fenced = '```json\n{"a": {"b": [1, 2]}, "ok": true}\n```'
    assert check(fenced, type="json_valid")
    assert not check("not json", type="json_valid")
    assert check(fenced, type="json_field", path="a.b.1", value=2)
    assert check(fenced, type="json_field", path="ok")
    assert not check(fenced, type="json_field", path="missing")
    assert not check(fenced, type="json_field", path="ok", value=False)


def test_unknown_and_malformed_assertions_fail_cleanly():
    assert not check("x", type="nope")
    assert not check("x", type="contains")  # missing value


def test_llm_judge():
    class Judge:
        def __init__(self, reply):
            self.reply = reply

        def complete(self, prompt):
            return self.reply

    ok = run_assertion("x", {"type": "llm_judge", "value": "c"}, Context(judge=Judge("PASS. good")))
    bad = run_assertion("x", {"type": "llm_judge", "value": "c"}, Context(judge=Judge("FAIL: no")))
    none = run_assertion("x", {"type": "llm_judge", "value": "c"}, Context())
    assert ok[0] and not bad[0] and not none[0]
