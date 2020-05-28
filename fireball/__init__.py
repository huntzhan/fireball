import functools
import inspect
import sys
import traceback
import pdb
import importlib
import importlib.util
import os

import fire


def pdb_excepthook(type_, value, traceback_):
    traceback.print_exception(type_, value, traceback_)
    pdb.pm()


def take_over_excepthook(option, excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        print(
            f'[fireball] {option}: Cannot take-over sys.excepthook '
            'since we are in iterative mode.',
            file=sys.stderr,
        )
        good = False

    if not sys.stderr.isatty():
        print(
            f'[fireball] {option}: Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.',
            file=sys.stderr,
        )
        good = False

    if good:
        print(f'[fireball] {option}: Setup successfully.')
        sys.excepthook = excepthook


def inject_param(parameters, var_positional_idx, var_keyword_idx, name, default):
    if var_positional_idx < 0:
        kind = inspect.Parameter.POSITIONAL_OR_KEYWORD
    else:
        kind = inspect.Parameter.KEYWORD_ONLY

    if var_keyword_idx < 0:
        insert_idx = len(parameters)
    else:
        insert_idx = var_keyword_idx

    parameters.insert(insert_idx, inspect.Parameter(
        name=name,
        default=default,
        kind=kind,
    ))


def bind_fire_debug(func):
    sig_func = inspect.signature(func)

    PARAM_PDB_ON_ERROR = 'pdb_on_error'
    func_contains_param_pdb_on_error = PARAM_PDB_ON_ERROR in sig_func.parameters

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = wrapper.__signature__.bind(*args, **kwargs)
        bound_args.apply_defaults()

        # Pop injected parameters.
        pdb_on_error = False
        if not func_contains_param_pdb_on_error:
            pdb_on_error = bound_args.arguments.pop(PARAM_PDB_ON_ERROR)

        # PDB.
        if pdb_on_error:
            take_over_excepthook(PARAM_PDB_ON_ERROR, pdb_excepthook)

        # python-fire will write this to stdout/stderr.
        return func(*bound_args.args, **bound_args.kwargs)

    # Patch signature.
    sig_wrapper = inspect.signature(wrapper)
    parameters = list(sig_wrapper.parameters.values())

    var_positional_idx = -1
    var_keyword_idx = -1
    for param_idx, param in enumerate(parameters):
        if param.kind == inspect.Parameter.VAR_POSITIONAL:
            assert var_positional_idx == -1
            var_positional_idx = param_idx
        elif param.kind == inspect.Parameter.VAR_KEYWORD:
            assert var_keyword_idx == -1
            var_keyword_idx = param_idx

    if not func_contains_param_pdb_on_error:
        inject_param(
            parameters,
            var_positional_idx,
            var_keyword_idx,
            PARAM_PDB_ON_ERROR,
            False,
        )

    new_sig_wrapper = sig_wrapper.replace(parameters=parameters)
    wrapper.__signature__ = new_sig_wrapper

    # Bind to python-fire.
    return lambda: fire.Fire(wrapper)


def bind_fire_release(func):
    return lambda: fire.Fire(func)


def cli(func, debug=False):
    if debug:
        return bind_fire_debug(func)
    else:
        return bind_fire_release(func)


def exec():
    if len(sys.argv) < 2:
        print('fireball <func_path>', file=sys.stderr)
        sys.exit(1)

    # Input.
    func_path = sys.argv[1]

    if ':' not in func_path:
        print('func_path: should have format like foo.bar:baz.', file=sys.stderr)
        sys.exit(1)

    module_path, func_name = func_path.strip().split(':')
    if not module_path:
        print('Missing module_path.', file=sys.stderr)
        sys.exit(1)
    if not func_name:
        print('Missing func_name.', file=sys.stderr)
        sys.exit(1)

    # Add the current working directory to sys.path for non-package import.
    cwd_path = os.getcwd()
    if cwd_path not in sys.path:
        sys.path.append(cwd_path)

    # Load module.
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        print(f'importlib.import_module cannot find module {module_path}.', file=sys.stderr)
        sys.exit(1)

    # Load function.
    func = getattr(module, func_name)
    if func is None:
        print(f'Cannot find function {func_name}.', file=sys.stderr)
        sys.exit(1)

    # Call function.
    func_cli = cli(func, debug=True)
    sys.argv = [func.__name__] + sys.argv[2:]
    func_cli()
