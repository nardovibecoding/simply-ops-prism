# Examples

These examples show the public extension shape without exposing anyone's real
infrastructure.

## Add A Detector

Copy an example detector into one daemon's `detectors/` directory:

```bash
mkdir -p daemons/lint/detectors
cp examples/detectors/todo_counter.py daemons/lint/detectors/todo_counter.py
PRISM_INBOX="$(mktemp -d)" PRISM_TMPDIR="$(mktemp -d)" bash run_parallel.sh
```

A detector is any Python file with a `run()` function that returns a list of
finding dictionaries. Keep detectors read-only by default.

## Finding Shape

```python
def run():
    return [{
        "id": "lint:example:todo-counter",
        "title": "Example detector found TODO markers",
        "affected_surface": "source-tree",
        "priority": "P3",
        "confidence": "medium",
        "suggested_next_skill": "lint",
        "evidence": ["example-only"],
        "carry_forward": True,
    }]
```

Use fake paths, fake hosts, and fake tokens in public examples.
