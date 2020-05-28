# fireball

Built on [python-fire](https://github.com/google/python-fire) to make binding & debugging easier.

## Install

```bash
pip install fireball
```

## Usage

###Invoke Python Function In Command Line

Basic usage:

```bash
$ fireball os:getcwd
/Users/huntzhan/Data/Project/personal/fireball

$ fireball os.path:join 'foo' 'bar'
foo/bar

$ fireball base64:b64encode 'b"foo"'
b'Zm9v
```

Help doc:

```bash
$ fireball base64:b64encode -- --help
NAME
    b64encode - Encode the bytes-like object s using Base64 and return a bytes object.

SYNOPSIS
    b64encode S <flags>

DESCRIPTION
    Optional altchars should be a byte string of length 2 which specifies an
    alternative alphabet for the '+' and '/' characters.  This allows an
    application to e.g. generate url or filesystem safe Base64 strings.

POSITIONAL ARGUMENTS
    S

FLAGS
    --altchars=ALTCHARS
    --pdb_on_error=PDB_ON_ERROR

NOTES
    You can also use flags syntax for POSITIONAL ARGUMENTS
```

PDB post-morden:

```bash
$ fireball base64:b64encode 'test' --pdb_on_error
ERROR:root:Traceback (most recent call last):
  File "/Users/huntzhan/.pyenv/versions/fireball/bin/fireball", line 6, in <module>
    sys.exit(import_module('fireball').exec())
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 169, in exec
    func_cli()
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 114, in <lambda>
    return lambda: fire.Fire(wrapper)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 138, in Fire
    component_trace = _Fire(component, args, parsed_flag_args, context, name)
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 463, in _Fire
    component, remaining_args = _CallAndUpdateTrace(
  File "/Users/huntzhan/.pyenv/versions/fireball/lib/python3.8/site-packages/fire/core.py", line 672, in _CallAndUpdateTrace
    component = fn(*varargs, **kwargs)
  File "/Users/huntzhan/Data/Project/personal/fireball/fireball/__init__.py", line 85, in wrapper
    return func(*bound_args.args, **bound_args.kwargs)
  File "/Users/huntzhan/.pyenv/versions/3.8.2/lib/python3.8/base64.py", line 58, in b64encode
    encoded = binascii.b2a_base64(s, newline=False)
TypeError: a bytes-like object is required, not 'str'

[7] > /Users/huntzhan/.pyenv/versions/3.8.2/lib/python3.8/base64.py(58)b64encode()
-> encoded = binascii.b2a_base64(s, newline=False)
(Pdb++) ll
  51     def b64encode(s, altchars=None):
  52         """Encode the bytes-like object s using Base64 and return a bytes object.
  53
  54         Optional altchars should be a byte string of length 2 which specifies an
  55         alternative alphabet for the '+' and '/' characters.  This allows an
  56         application to e.g. generate url or filesystem safe Base64 strings.
  57         """
  58  ->     encoded = binascii.b2a_base64(s, newline=False)
  59         if altchars is not None:
  60             assert len(altchars) == 2, repr(altchars)
  61             return encoded.translate(bytes.maketrans(b'+/', altchars))
  62         return encoded
(Pdb++)
```

### Define The Project Entry Point

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

