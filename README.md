# fireball

Built on [python-fire](https://github.com/google/python-fire) to make binding & debugging easier.

## Install

```bash
pip install fireball
```

## Usage

Example:

```python
# app.py
import fireball

def foo(a, b=2):
    print('foo', a, b)
    assert 0

# `debug=True` injects an extra option `--pdb_on_error` to `foo`.
foo_cli = fireball.cli(foo, debug=True)
```

Bind as entry point:

```
# pyproject.toml.
[tool.poetry.scripts]
foo = "path.to.app:foo_cli"

# setup.py
setup(
    ...
    entry_points={
        'console_scripts': [
            'foo_cli = path.to.app:foo_cli',
        ],
    },
    ...
)
```

Activate the entry point in your shell then invoke:

```shell
$ foo_cli --help
NAME
    foo

SYNOPSIS
    foo A <flags>

POSITIONAL ARGUMENTS
    A

FLAGS
    --b=B
    --pdb_on_error=PDB_ON_ERROR

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
    
$ foo_cli this_is_a this_is_b
foo this_is_a this_is_b
Traceback (most recent call last):
  File "/Users/huntzhan/.pyenv/versions/fireball/bin/fireball", line 6, in <module>
    sys.exit(import_module('fireball').exec())
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 135, in exec
    return func_cli()
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 80, in <lambda>
    return lambda: fire.Fire(wrapper)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 138, in Fire
    component_trace = _Fire(component, args, parsed_flag_args, context, name)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 463, in _Fire
    component, remaining_args = _CallAndUpdateTrace(
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 672, in _CallAndUpdateTrace
    component = fn(*varargs, **kwargs)
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 61, in wrapper
    return func(**bound_args.arguments)
  File "/Users/huntzhan/Data/Project/personal/fireball/tools/debug_import.py", line 3, in foo
    assert 0
AssertionError

$ foo_cli this_is_a this_is_b --pdb_on_error
[fireball] pdb_on_error: Setup successfully.
foo this_is_a this_is_b
Traceback (most recent call last):
  File "/Users/huntzhan/.pyenv/versions/fireball/bin/fireball", line 6, in <module>
    sys.exit(import_module('fireball').exec())
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 135, in exec
    return func_cli()
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 80, in <lambda>
    return lambda: fire.Fire(wrapper)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 138, in Fire
    component_trace = _Fire(component, args, parsed_flag_args, context, name)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 463, in _Fire
    component, remaining_args = _CallAndUpdateTrace(
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 672, in _CallAndUpdateTrace
    component = fn(*varargs, **kwargs)
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 61, in wrapper
    return func(**bound_args.arguments)
  File "/Users/huntzhan/Data/Project/personal/fireball/tools/debug_import.py", line 3, in foo
    assert 0
AssertionError
[7] > /Users/huntzhan/Data/Project/personal/fireball/tools/debug_import.py(3)foo()
-> assert 0
(Pdb++) ll
   1     def foo(a, b=2):
   2         print('foo', a, b)
   3  ->     assert 0
(Pdb++)
```

You can even invoke a function directly in shell, without binding as entry point:

```bash
$ fireball path.to.app:foo --help
$ fireball path.to.app:foo this_is_a this_is_b
$ fireball path.to.app:foo this_is_a this_is_b --pdb_on_error
```

