import functools
import importlib
import importlib.util
import inspect
import logging
import os
import pdb
import sys
import traceback

import fire

logging.basicConfig(level=os.getenv('LOGGING_LEVEL', 'INFO'))
logger = logging.getLogger()


def pdb_excepthook(type_, value, traceback_):
    logger.error(''.join(traceback.format_exception(type_, value, traceback_)))
    pdb.pm()


def fireball_take_over_excepthook(option, excepthook):
    good = True

    if hasattr(sys, 'ps1'):
        logger.warning(
            '--%s: Cannot take-over sys.excepthook '
            'since we are in iterative mode.',
            option,
        )
        good = False

    if not sys.stderr.isatty():
        logger.warning(
            '--%s: Cannot take-over sys.excepthook '
            'since we don\'t have a tty-like device.',
            option,
        )
        good = False

    if good:
        logger.debug('--%s: Setup successfully.', option)
        sys.excepthook = excepthook


def fireball_print_cmd(arguments_copy):
    break_limit = 79
    indent = 2

    components = ['fireball', sys.argv[0]]
    for key, val in arguments_copy.items():
        if isinstance(val, bool):
            if val:
                components.append(f"--{key}")
        else:
            components.append(f"--{key}='{val}'")

    header = 'COMMAND:'
    one_line = ' '.join(components)
    if len(one_line) <= break_limit:
        logger.info(header + '\n' + one_line + '\n')

    else:
        lines = [components[0] + ' ' + components[1] + ' \\']
        for idx, component in enumerate(components[2:], start=2):
            prefix = ' ' * indent
            suffix = ' \\' if idx < len(components) - 1 else ''
            lines.append(prefix + component + suffix)
        logger.info(header + '\n' + '\n'.join(lines) + '\n')


def fireball_inject_param(parameters, var_positional_idx, var_keyword_idx, name, default):
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


PARAM_PDB_ON_ERROR = 'pdb_on_error'
PARAM_PRINT_CMD = 'print_cmd'


def wrap_func(func):
    sig_func = inspect.signature(func)

    func_contains_param_pdb_on_error = PARAM_PDB_ON_ERROR in sig_func.parameters
    func_contains_param_print_cmd = PARAM_PRINT_CMD in sig_func.parameters

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        bound_args = wrapper.__signature__.bind(*args, **kwargs)
        bound_args.apply_defaults()

        arguments_copy = bound_args.arguments.copy()

        # PDB.
        if not func_contains_param_pdb_on_error:
            pdb_on_error = bound_args.arguments.pop(PARAM_PDB_ON_ERROR)
            if pdb_on_error:
                fireball_take_over_excepthook(PARAM_PDB_ON_ERROR, pdb_excepthook)

        # Print command.
        if not func_contains_param_print_cmd:
            print_cmd = bound_args.arguments.pop(PARAM_PRINT_CMD)
            if print_cmd:
                fireball_print_cmd(arguments_copy)

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

    # PDB.
    if not func_contains_param_pdb_on_error:
        fireball_inject_param(
            parameters,
            var_positional_idx,
            var_keyword_idx,
            PARAM_PDB_ON_ERROR,
            False,
        )

    # Print command.
    if not func_contains_param_print_cmd:
        fireball_inject_param(
            parameters,
            var_positional_idx,
            var_keyword_idx,
            PARAM_PRINT_CMD,
            False,
        )

    new_sig_wrapper = sig_wrapper.replace(parameters=parameters)
    wrapper.__signature__ = new_sig_wrapper

    return wrapper


def cli(func):
    func = wrap_func(func)
    return lambda: fire.Fire(func)


def exec():
    # Input.
    # fireball <module_path>:<func_name> ...
    #                                    ^ sys.argv[2:]
    #          ^ sys.argv[1]
    # ^ sys.argv[0]
    if len(sys.argv) < 2:
        logger.error('fireball <func_path>\nExample: fireball os:getcwd')
        sys.exit(1)

    func_path = sys.argv[1]

    if ':' not in func_path:
        logger.error('<func_path>: should have format like "foo.bar:baz".')
        sys.exit(1)

    module_path, func_name = func_path.strip().split(':')
    if not module_path:
        logger.error('Missing module_path.')
        sys.exit(1)
    if not func_name:
        logger.error('Missing func_name.')
        sys.exit(1)

    # Add the current working directory to sys.path for non-package import.
    cwd_path = os.getcwd()
    if cwd_path not in sys.path:
        sys.path.append(cwd_path)

    # Load module.
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError:
        logger.error('importlib.import_module cannot find module %s.', module_path)
        sys.exit(1)

    # Load function.
    func = getattr(module, func_name)
    if func is None:
        logger.error('Cannot find function %s.', func_name)
        sys.exit(1)

    # Patch to <module_path>:<func_name> ...
    sys.argv = sys.argv[1:]

    # Call function.
    func_cli = cli(func)
    func_cli()
